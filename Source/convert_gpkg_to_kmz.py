"""
GeoPackage (.gpkg) nach KMZ oder KML für Google Earth umwandeln.

Das Skript funktioniert mit beliebigen GeoPackages und fragt alles der Reihe
nach ab. Fragen, die für die gewählten Daten keine Rolle spielen, entfallen.

  1. GeoPackage-Datei
  2. welche Layer umgewandelt werden (alle oder einzelne)
  3. welches Attribut die Stecknadeln beschriftet (nur bei Punkt-Layern,
     dazu wird ein Beispieldatensatz angezeigt)
  4. eigenes Symbol statt der Stecknadel, als URL oder Datei (nur bei
     Punkt-Layern). Es wird ins KMZ eingebettet und funktioniert daher auch
     offline. SVG zeigt Google Earth nicht an, es wird deshalb in ein PNG mit
     transparentem Hintergrund umgewandelt (braucht: pip install resvg-py)
  5. Farbe, nie Schwarz:
        0 Weiss (Standard)   1 Rot      2 Orange   3 Gelb
        4 Grün               5 Blau     6 Indigo   7 Violett
  6. Höhenwerte behalten (nur wenn die Daten tatsächlich welche enthalten):
     Ja = 3D auf der gespeicherten Höhe über Meer, Nein = auf das Gelände gelegt
  7. Linien ohne Höhenwerte als Luftlinie, also gerade von Stützpunkt zu
     Stützpunkt statt dem Gelände folgend (z. B. für Seilbahnen)
  8. Sachdaten mitnehmen (in Google Earth per Klick sichtbar)
  9. Zieldatei (.kmz oder .kml)

Alle Geometrietypen (Punkte, Linien, Flächen und deren Multi-Varianten) werden
unterstützt, jedes Koordinatensystem wird nach WGS84 umgerechnet, das Google
Earth erwartet. Jeder Layer wird ein eigener Ordner in Google Earth.

Installation:  pip install geopandas          (resvg-py nur für SVG-Icons)
Aufruf:        python convert_gpkg_to_kmz.py
"""
import io
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import geopandas as gpd
import pandas as pd    # wird mit geopandas mitinstalliert
import shapely         # wird mit geopandas mitinstalliert

# Wählbare Farben als (Name, RGB-Hex). Index 0 ist der Standard.
FARBEN = [
    ("Weiss", "FFFFFF"),
    ("Rot", "FF0000"),
    ("Orange", "FFA500"),
    ("Gelb", "FFFF00"),
    ("Grün", "00C000"),
    ("Blau", "0000FF"),
    ("Indigo", "4B0082"),
    ("Violett", "EE82EE"),
]

LINIENBREITE = 3
FLAECHEN_DECKKRAFT = "66"   # Füllung halbtransparent (00 = unsichtbar, ff = deckend)
WGS84 = 4326                # EPSG-Code des Koordinatensystems von Google Earth
ICON_LISTE = "https://kml4earth.appspot.com/icons.html"
ICON_BREITE = 64            # Pixel, auf die ein SVG-Icon gerendert wird
STICHPROBE = 1000           # so viele Objekte pro Layer werden auf Höhenwerte geprüft


@dataclass
class Einstellungen:
    """Alles, was der Benutzer für die Umwandlung festgelegt hat."""
    layer: list          # umzuwandelnde Layer
    beschriftung: dict   # Layer -> Spalte für die Beschriftung (None = keine)
    icon: str            # URL oder Datei, leer = Stecknadel von Google Earth
    rgb: str             # Farbe als RGB-Hex
    hoehe_layer: set     # Layer, die 3D mit ihren Höhenwerten gezeichnet werden
    luftlinie: bool      # Linien ohne Höhe gerade durch die Luft statt am Gelände
    mit_attributen: bool


# --- Eingabe-Hilfen -------------------------------------------------------------
def frage_ja_nein(text, standard):
    """Ja/Nein-Frage. Enter liefert den Standard. Akzeptiert j/ja/y/yes und n/nein/no."""
    hinweis = "[J/n]" if standard else "[j/N]"
    while True:
        antwort = input(f"{text} {hinweis}: ").strip().lower()
        if antwort == "":
            return standard
        if antwort in ("j", "ja", "y", "yes"):
            return True
        if antwort in ("n", "nein", "no"):
            return False
        print("Bitte j oder n eingeben.")


def frage_zahl(text, minimum, maximum, standard):
    """Eine Zahl im Bereich minimum..maximum abfragen. Enter liefert den Standard."""
    while True:
        eingabe = input(text).strip()
        if eingabe == "":
            return standard
        if eingabe.isdigit() and minimum <= int(eingabe) <= maximum:
            return int(eingabe)
        print("Ungültige Eingabe, bitte nochmals.")


def ohne_anfuehrungszeichen(text):
    """Pfade aus dem Explorer ("Als Pfad kopieren") haben Anführungszeichen."""
    return text.strip().strip('"')


def ist_url(text):
    return text.startswith(("http://", "https://"))


# --- Fragen ---------------------------------------------------------------------
def frage_gpkg():
    """Eingabedatei abfragen, bis eine vorhandene .gpkg-Datei angegeben ist."""
    while True:
        pfad = Path(ohne_anfuehrungszeichen(input("GeoPackage-Datei (.gpkg): ")))
        if pfad.is_file():
            return pfad
        print(f"Datei nicht gefunden: {pfad}")


def frage_layer(alle):
    """Enthaltene Layer anzeigen und abfragen, welche umgewandelt werden.

    Layer ohne Geometrie (reine Tabellen) werden nur zur Info angezeigt,
    denn sie lassen sich nicht auf einer Karte darstellen.
    """
    karten_layer = alle[alle["geometry_type"].notna()]
    print("\nEnthaltene Layer:")
    for nummer, (name, typ) in enumerate(karten_layer.itertuples(index=False), start=1):
        print(f"  {nummer}  {name} ({typ})")
    for name in alle.loc[alle["geometry_type"].isna(), "name"]:
        print(f"     {name} (keine Geometrie, wird übersprungen)")

    namen = list(karten_layer["name"])
    if frage_ja_nein("Alle Layer umwandeln?", standard=True):
        return namen
    while True:
        eingabe = input("Nummern der gewünschten Layer, mit Komma getrennt (z. B. 1,3): ")
        teile = [t.strip() for t in eingabe.split(",") if t.strip()]
        if teile and all(t.isdigit() and 1 <= int(t) <= len(namen) for t in teile):
            return [namen[int(t) - 1] for t in teile]
        print("Ungültige Eingabe, bitte nochmals.")


def frage_beschriftung(gpkg, punkt_layer):
    """Pro Punkt-Layer abfragen, welches Attribut die Stecknadeln beschriftet.

    Als Beispiel wird von den ersten 100 Datensätzen der vollständigste
    angezeigt, damit möglichst wenige Werte leer sind. Enter übernimmt eine
    Spalte "name", falls vorhanden.
    """
    beschriftung = {}
    for name in punkt_layer:
        stichprobe = gpd.read_file(gpkg, layer=name, rows=100)
        spalten = [s for s in stichprobe.columns if s != stichprobe.geometry.name]
        beispiel = stichprobe[spalten].notna().sum(axis=1).idxmax()
        standard = namensspalte(spalten)

        print(f"\nBeschriftung der Stecknadeln im Layer {name}. Beispieldatensatz:")
        print("  0  (keine Beschriftung)")
        for nummer, spalte in enumerate(spalten, start=1):
            wert = stichprobe.at[beispiel, spalte]
            print(f"  {nummer}  {spalte} = {'(leer)' if pd.isna(wert) else str(wert)[:50]}")

        vorgabe = f"Enter = {standard}" if standard else "Enter = keine"
        wahl = frage_zahl(f"Nummer des Attributs [{vorgabe}]: ", 0, len(spalten),
                          standard=spalten.index(standard) + 1 if standard else 0)
        beschriftung[name] = spalten[wahl - 1] if wahl else None
    return beschriftung


def frage_icon():
    """Optional ein Icon (URL oder Datei, PNG/JPG/SVG) abfragen. Enter behält die Stecknadel."""
    print(f"\nEigenes Symbol für Punkte? Eine Auswahl gibt es unter {ICON_LISTE}")
    while True:
        quelle = ohne_anfuehrungszeichen(
            input("Icon-URL oder Datei [Enter = Stecknadel von Google Earth]: "))
        if quelle == "" or ist_url(quelle) or Path(quelle).is_file():
            return quelle
        print("Weder URL (http:// bzw. https://) noch vorhandene Datei, bitte nochmals.")


def frage_farbe():
    """Farbe abfragen. Enter bedeutet Weiss (0)."""
    print("\nFarbe für die Geometrien:")
    for nummer, (name, _) in enumerate(FARBEN):
        print(f"  {nummer}  {name}")
    return frage_zahl(f"Zahl 0-{len(FARBEN) - 1} [Enter = Weiss]: ",
                      0, len(FARBEN) - 1, standard=0)


def frage_hoehe(z_layer):
    """Fragen, ob die vorhandenen Höhenwerte genutzt werden."""
    print(f"\nDiese Layer enthalten Höhenwerte: {', '.join(z_layer)}")
    print("  Ja:   3D, auf der gespeicherten Höhe über Meer")
    print("  Nein: auf das Gelände von Google Earth gelegt")
    return frage_ja_nein("Höhe beibehalten?", standard=True)


def frage_luftlinie(linien_layer):
    """Fragen, ob Linien ohne Höhenwerte als Luftlinie gezeichnet werden."""
    print(f"\nLinien ohne Höhenwerte: {', '.join(linien_layer)}")
    print("  Nein: dem Gelände folgend (z. B. Wege, Strassen)")
    print("  Ja:   Luftlinie, gerade von Stützpunkt zu Stützpunkt (z. B. Seilbahnen)")
    return frage_ja_nein("Als Luftlinie zeichnen?", standard=False)


def frage_ziel(gpkg):
    """Zieldatei abfragen. Enter: gleicher Name wie die Eingabe, mit .kmz."""
    standard = gpkg.with_suffix(".kmz")
    eingabe = ohne_anfuehrungszeichen(input(f"\nZieldatei (.kmz oder .kml) [Enter = {standard}]: "))
    return Path(eingabe) if eingabe else standard


# --- Daten prüfen ---------------------------------------------------------------
def hat_hoehenwerte(gpkg, name):
    """Prüfen, ob ein Layer tatsächlich Höhenwerte enthält.

    Der Geometrietyp allein reicht nicht: Viele Daten sind als 3D deklariert,
    haben aber überall Höhe 0 oder keinen Wert. Geprüft wird eine Stichprobe.
    """
    stichprobe = gpd.read_file(gpkg, layer=name, rows=STICHPROBE)
    z = shapely.get_coordinates(stichprobe.geometry.values, include_z=True)[:, 2]
    return bool(((z == z) & (z != 0)).any())   # z == z ist False für NaN


# --- Icon -----------------------------------------------------------------------
def lade_icon(quelle):
    """Icon von URL oder Datei laden und als (Bilddaten, Dateiendung) liefern.

    SVG wird in PNG mit transparentem Hintergrund umgewandelt, weil Google
    Earth kein SVG anzeigt. Andere Formate (PNG, JPG, GIF) bleiben unverändert.
    """
    try:
        if ist_url(quelle):
            # Manche Server lehnen Anfragen ohne User-Agent ab
            anfrage = urllib.request.Request(quelle, headers={"User-Agent": "convert_gpkg_to_kmz"})
            with urllib.request.urlopen(anfrage, timeout=30) as antwort:
                daten = antwort.read()
        else:
            daten = Path(quelle).read_bytes()
    except OSError as fehler:
        raise SystemExit(f"Icon konnte nicht geladen werden: {quelle}\n  {fehler}")

    endung = Path(quelle.split("?")[0]).suffix.lower() or ".png"
    if endung == ".svg" or b"<svg" in daten[:1000]:   # auch SVG-URLs ohne Endung
        try:
            import resvg_py   # nur hier gebraucht, daher erst bei Bedarf laden
        except ImportError:
            raise SystemExit("Für SVG-Icons wird resvg-py gebraucht: pip install resvg-py")
        daten = resvg_py.svg_to_bytes(svg_string=daten.decode("utf-8"), width=ICON_BREITE)
        endung = ".png"
    return daten, endung


# --- Stil -----------------------------------------------------------------------
def kml_farbe(rgb, deckkraft="ff"):
    """RGB-Hex (z. B. "FFA500") in KML-Notation umwandeln.

    KML erwartet die Reihenfolge aabbggrr (Deckkraft, Blau, Grün, Rot),
    also genau umgekehrt zum üblichen rrggbb.
    """
    rot, gruen, blau = rgb[0:2], rgb[2:4], rgb[4:6]
    return f"{deckkraft}{blau}{gruen}{rot}".lower()


def stil_kml(rgb, icon_href):
    """Gemeinsamer KML-Stil für Punkte, Linien und Flächen.

    icon_href ist der Pfad des eingebetteten Icons (leer = Stecknadel).
    Google Earth färbt das Icon in der gewählten Farbe ein. Bei Weiss bleibt
    ein eigenes Icon daher unverändert.
    """
    farbe = kml_farbe(rgb)
    fuellung = kml_farbe(rgb, FLAECHEN_DECKKRAFT)
    symbol = f"<Icon><href>{escape(icon_href)}</href></Icon>" if icon_href else ""
    return (
        '<Style id="stil">'
        f"<IconStyle><color>{farbe}</color>{symbol}</IconStyle>"
        f"<LineStyle><color>{farbe}</color><width>{LINIENBREITE}</width></LineStyle>"
        f"<PolyStyle><color>{fuellung}</color></PolyStyle>"
        "</Style>"
    )


# --- Geometrie -> KML -----------------------------------------------------------
def koordinaten(coords, hoehe):
    """Koordinatenfolge als KML-Text "lon,lat[,höhe] ...".

    Mit hoehe=True wird die Z-Koordinate (Meter über Meer) mitgeschrieben.
    """
    if hoehe:
        return " ".join(f"{x:.6f},{y:.6f},{z:.1f}" for x, y, z in coords)
    return " ".join(f"{x:.6f},{y:.6f}" for x, y, *_ in coords)


def lage_kml(hoehe, luftlinie=False):
    """Wie Google Earth die Geometrie in der Höhe platziert.

    absolute:         auf der gespeicherten Höhe über Meer (3D-Daten).
    relativeToGround: Stützpunkte am Boden, dazwischen gerade durch die Luft.
    tessellate:       auf das Gelände gelegt, Linien folgen dem Relief.
    """
    if hoehe:
        return "<altitudeMode>absolute</altitudeMode>"
    if luftlinie:
        return "<altitudeMode>relativeToGround</altitudeMode>"
    return "<tessellate>1</tessellate>"


def ring_kml(ring, hoehe):
    """Einen Flächenrand (LinearRing) als KML."""
    return (f"<LinearRing><coordinates>{koordinaten(ring.coords, hoehe)}"
            f"</coordinates></LinearRing>")


def geometrie_kml(geom, mit_hoehe, luftlinie):
    """Shapely-Geometrie in das passende KML-Element umwandeln.

    Hat die Geometrie Höhenwerte und ist mit_hoehe gesetzt, bleibt sie 3D.
    Sonst wird sie auf das Gelände gelegt, ausser Linien mit luftlinie=True:
    diese verlaufen gerade von Stützpunkt zu Stützpunkt durch die Luft.
    """
    typ = geom.geom_type
    hoehe = mit_hoehe and geom.has_z
    if typ == "Point":
        lage = lage_kml(hoehe) if hoehe else ""   # tessellate gibt es bei Punkten nicht
        return f"<Point>{lage}<coordinates>{koordinaten(geom.coords, hoehe)}</coordinates></Point>"
    if typ in ("LineString", "LinearRing"):
        return (f"<LineString>{lage_kml(hoehe, luftlinie)}"
                f"<coordinates>{koordinaten(geom.coords, hoehe)}</coordinates></LineString>")
    if typ == "Polygon":
        aussen = f"<outerBoundaryIs>{ring_kml(geom.exterior, hoehe)}</outerBoundaryIs>"
        loecher = "".join(f"<innerBoundaryIs>{ring_kml(r, hoehe)}</innerBoundaryIs>"
                          for r in geom.interiors)
        return f"<Polygon>{lage_kml(hoehe)}{aussen}{loecher}</Polygon>"
    # MultiPoint, MultiLineString, MultiPolygon, GeometryCollection
    teile = "".join(geometrie_kml(teil, mit_hoehe, luftlinie) for teil in geom.geoms)
    return f"<MultiGeometry>{teile}</MultiGeometry>"


def attribute_kml(zeile, spalten):
    """Sachdaten eines Objekts als KML-ExtendedData (in Google Earth per Klick sichtbar)."""
    daten = "".join(
        f'<Data name="{escape(spalte)}"><value>{escape(str(zeile[spalte]))}</value></Data>'
        for spalte in spalten
        if not pd.isna(zeile[spalte])   # leere Felder weglassen
    )
    return f"<ExtendedData>{daten}</ExtendedData>" if daten else ""


def namensspalte(spalten):
    """Spalte "name" (gross/klein egal) als naheliegende Beschriftung finden."""
    return next((s for s in spalten if s.lower() == "name"), None)


def placemarks(gdf, name_spalte, mit_hoehe, e):
    """Alle Objekte eines Layers nacheinander als KML-Placemarks liefern."""
    spalten = [s for s in gdf.columns if s != gdf.geometry.name] if e.mit_attributen else []
    for _, zeile in gdf.iterrows():
        geom = zeile[gdf.geometry.name]
        if geom is None or geom.is_empty:
            continue
        name = ""
        if name_spalte and not pd.isna(zeile[name_spalte]):
            name = f"<name>{escape(str(zeile[name_spalte]))}</name>"
        yield (f"<Placemark>{name}<styleUrl>#stil</styleUrl>"
               f"{attribute_kml(zeile, spalten)}"
               f"{geometrie_kml(geom, mit_hoehe, e.luftlinie)}</Placemark>\n")


# --- Ausgabe --------------------------------------------------------------------
def schreibe_kml(datei, gpkg, e, icon_href):
    """Das ganze KML-Dokument Layer für Layer in eine offene Textdatei schreiben.

    Es wird fortlaufend geschrieben statt alles im Speicher zu sammeln, damit
    auch grosse GeoPackages funktionieren.
    """
    datei.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>\n'
                f"<name>{escape(gpkg.stem)}</name>{stil_kml(e.rgb, icon_href)}\n")
    for name in e.layer:
        gdf = gpd.read_file(gpkg, layer=name)
        if gdf.crs is not None:
            gdf = gdf.to_crs(WGS84)
        else:
            print(f"  Warnung: Layer {name} hat kein Koordinatensystem, "
                  "Koordinaten werden unverändert übernommen.")

        # Gewählte Beschriftung, sonst automatisch eine Spalte "name"
        name_spalte = e.beschriftung.get(name, namensspalte(gdf.columns))

        print(f"  {name}: {len(gdf)} Objekte")
        datei.write(f"<Folder><name>{escape(name)}</name>\n")
        datei.writelines(placemarks(gdf, name_spalte, name in e.hoehe_layer, e))
        datei.write("</Folder>\n")
    datei.write("</Document></kml>\n")


def konvertiere(gpkg, ziel, e):
    """GeoPackage als KMZ (ZIP mit doc.kml) oder als reine KML-Datei speichern.

    Ein eigenes Icon liegt im KMZ unter files/, beim KML als Datei daneben.
    """
    icon, endung = lade_icon(e.icon) if e.icon else (None, "")

    if ziel.suffix.lower() == ".kml":
        icon_href = f"{ziel.stem}_icon{endung}" if icon else ""
        if icon:
            (ziel.parent / icon_href).write_bytes(icon)
        with open(ziel, "w", encoding="utf-8") as datei:
            schreibe_kml(datei, gpkg, e, icon_href)
    else:
        icon_href = f"files/icon{endung}" if icon else ""
        with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as kmz:
            with kmz.open("doc.kml", "w") as roh, \
                    io.TextIOWrapper(roh, encoding="utf-8") as datei:
                schreibe_kml(datei, gpkg, e, icon_href)
            if icon:
                kmz.writestr(icon_href, icon)


# --- Ablauf ---------------------------------------------------------------------
def main():
    gpkg = frage_gpkg()
    alle = gpd.list_layers(gpkg)
    typen = dict(zip(alle["name"], alle["geometry_type"].astype(str)))

    layer = frage_layer(alle)
    punkt_layer = [n for n in layer if "Point" in typen[n]]
    beschriftung = frage_beschriftung(gpkg, punkt_layer)
    icon = frage_icon() if punkt_layer else ""
    farbname, rgb = FARBEN[frage_farbe()]

    # Höhenfrage nur, wenn Layer tatsächlich Höhenwerte enthalten
    z_layer = [n for n in layer if hat_hoehenwerte(gpkg, n)]
    hoehe_layer = set(z_layer) if z_layer and frage_hoehe(z_layer) else set()

    # Luftlinie nur für Linien, die nicht schon mit Höhe gezeichnet werden
    linien_layer = [n for n in layer if "LineString" in typen[n] and n not in hoehe_layer]
    luftlinie = frage_luftlinie(linien_layer) if linien_layer else False

    mit_attributen = frage_ja_nein(
        "\nSachdaten mitnehmen (in Google Earth per Klick sichtbar)?", standard=True)
    ziel = frage_ziel(gpkg)

    e = Einstellungen(layer, beschriftung, icon, rgb, hoehe_layer, luftlinie, mit_attributen)
    print(f"\n{gpkg} -> {ziel} ({farbname})")
    konvertiere(gpkg, ziel, e)
    print("Fertig.")


if __name__ == "__main__":
    main()
