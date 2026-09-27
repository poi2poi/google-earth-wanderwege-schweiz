"""
GeoPackage (.gpkg) nach KMZ oder KML für Google Earth umwandeln.

Das Skript funktioniert mit beliebigen GeoPackages. Es fragt der Reihe nach:

  1. welche Layer umgewandelt werden (alle oder einzelne),
  2. welches Attribut die Stecknadeln von Punkt-Layern beschriftet
     (dazu wird ein Beispieldatensatz angezeigt),
  3. ob ein eigenes Symbol (URL oder Datei) statt der Stecknadel verwendet
     wird. Es wird ins KMZ eingebettet, die Datei funktioniert also auch
     offline. SVG kann Google Earth nicht anzeigen, es wird daher in ein PNG
     mit transparentem Hintergrund umgewandelt (braucht: pip install resvg-py),
  4. in welcher Farbe gezeichnet wird (nie Schwarz):

        0 Weiss (Standard)   1 Rot      2 Orange   3 Gelb
        4 Grün               5 Blau     6 Indigo   7 Violett

Alle Geometrietypen (Punkte, Linien, Flächen und deren Multi-Varianten) werden
unterstützt, jedes Koordinatensystem wird nach WGS84 umgerechnet, das Google
Earth erwartet. Jeder Layer wird ein eigener Ordner in Google Earth.
Jede Frage lässt sich mit einer Option überspringen (siehe --help).

Installation:  pip install geopandas          (resvg-py nur für SVG-Icons)
Beispiele:
    python convert_gpkg_to_kmz.py daten.gpkg               (fragt alles nach)
    python convert_gpkg_to_kmz.py daten.gpkg -o karte.kml  (unkomprimiertes KML)
    python convert_gpkg_to_kmz.py daten.gpkg --layer Station --beschriftung name
        --icon http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png --farbe 5
"""
import argparse
import io
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

import geopandas as gpd
import pandas as pd   # wird mit geopandas mitinstalliert

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
JA = ("", "j", "ja", "y", "yes")   # Enter zählt als Ja


@dataclass
class Einstellungen:
    """Alles, was der Benutzer für die Umwandlung festgelegt hat."""
    layer: list
    rgb: str
    icon: str = ""                                    # URL/Datei, leer = Stecknadel
    beschriftung: dict = field(default_factory=dict)  # Layer -> Spalte (None = keine)
    mit_attributen: bool = True


# --- Abfragen -------------------------------------------------------------------
def frage_zahl(text, minimum, maximum, standard=None):
    """Eine Zahl im Bereich minimum..maximum abfragen. Enter liefert den Standard."""
    while True:
        eingabe = input(text).strip()
        if eingabe == "" and standard is not None:
            return standard
        if eingabe.isdigit() and minimum <= int(eingabe) <= maximum:
            return int(eingabe)
        print("Ungültige Eingabe, bitte nochmals.")


def frage_layer(gpkg):
    """Enthaltene Layer anzeigen und abfragen, welche umgewandelt werden.

    Layer ohne Geometrie (reine Tabellen) werden nur zur Info angezeigt,
    denn sie lassen sich nicht auf einer Karte darstellen.
    """
    alle = gpd.list_layers(gpkg)
    karten_layer = alle[alle["geometry_type"].notna()]
    tabellen = alle[alle["geometry_type"].isna()]

    print(f"\nLayer in {gpkg.name}:")
    for nummer, (name, typ) in enumerate(karten_layer.itertuples(index=False), start=1):
        print(f"  {nummer}  {name} ({typ})")
    for name in tabellen["name"]:
        print(f"     {name} (keine Geometrie, wird übersprungen)")

    namen = list(karten_layer["name"])
    if input("Alle Layer umwandeln? [J/n]: ").strip().lower() in JA:
        return namen

    while True:
        eingabe = input("Nummern der gewünschten Layer, mit Komma getrennt (z. B. 1,3): ")
        teile = [t.strip() for t in eingabe.split(",") if t.strip()]
        if teile and all(t.isdigit() and 1 <= int(t) <= len(namen) for t in teile):
            return [namen[int(t) - 1] for t in teile]
        print("Ungültige Eingabe, bitte nochmals.")


def punkt_layer(gpkg, layer):
    """Von den gewählten Layern diejenigen, die Punkte enthalten (-> Stecknadeln)."""
    typen = gpd.list_layers(gpkg).set_index("name")["geometry_type"]
    return [name for name in layer if "Point" in str(typen.get(name, ""))]


def frage_beschriftung(gpkg, layer):
    """Pro Punkt-Layer abfragen, welches Attribut die Stecknadeln beschriftet.

    Zur Orientierung wird ein Beispieldatensatz mit allen Attributen angezeigt:
    von den ersten 100 der vollständigste, damit möglichst wenige Werte leer
    sind. Enter übernimmt eine Spalte "name", falls vorhanden.
    """
    beschriftung = {}
    for name in punkt_layer(gpkg, layer):
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


def ist_url(text):
    return text.startswith(("http://", "https://"))


def frage_icon():
    """Optional ein Icon (URL oder Datei, PNG/JPG/SVG) abfragen. Enter behält die Stecknadel."""
    print(f"\nEigenes Symbol für Punkte? Eine Auswahl gibt es unter {ICON_LISTE}")
    while True:
        quelle = input("Icon-URL oder Datei [Enter = Stecknadel von Google Earth]: ")
        quelle = quelle.strip().strip('"')   # Pfade aus dem Explorer haben Anführungszeichen
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
def koordinaten(coords):
    """Koordinatenfolge als KML-Text "lon,lat lon,lat ...". Höhe (Z) entfällt."""
    return " ".join(f"{x:.6f},{y:.6f}" for x, y, *_ in coords)


def ring_kml(ring):
    """Einen Flächenrand (LinearRing) als KML."""
    return f"<LinearRing><coordinates>{koordinaten(ring.coords)}</coordinates></LinearRing>"


def geometrie_kml(geom):
    """Shapely-Geometrie in das passende KML-Element umwandeln."""
    typ = geom.geom_type
    if typ == "Point":
        return f"<Point><coordinates>{koordinaten(geom.coords)}</coordinates></Point>"
    if typ in ("LineString", "LinearRing"):
        # tessellate: Linie folgt dem Gelände statt gerade durch die Luft
        return (f"<LineString><tessellate>1</tessellate>"
                f"<coordinates>{koordinaten(geom.coords)}</coordinates></LineString>")
    if typ == "Polygon":
        aussen = f"<outerBoundaryIs>{ring_kml(geom.exterior)}</outerBoundaryIs>"
        loecher = "".join(f"<innerBoundaryIs>{ring_kml(r)}</innerBoundaryIs>"
                          for r in geom.interiors)
        return f"<Polygon><tessellate>1</tessellate>{aussen}{loecher}</Polygon>"
    # MultiPoint, MultiLineString, MultiPolygon, GeometryCollection
    teile = "".join(geometrie_kml(teil) for teil in geom.geoms)
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


def placemarks(gdf, name_spalte, mit_attributen):
    """Alle Objekte eines Layers nacheinander als KML-Placemarks liefern."""
    spalten = [s for s in gdf.columns if s != gdf.geometry.name] if mit_attributen else []
    for _, zeile in gdf.iterrows():
        geom = zeile[gdf.geometry.name]
        if geom is None or geom.is_empty:
            continue
        name = ""
        if name_spalte and not pd.isna(zeile[name_spalte]):
            name = f"<name>{escape(str(zeile[name_spalte]))}</name>"
        yield (f"<Placemark>{name}<styleUrl>#stil</styleUrl>"
               f"{attribute_kml(zeile, spalten)}{geometrie_kml(geom)}</Placemark>\n")


# --- Ein- und Ausgabe -----------------------------------------------------------
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
        if not isinstance(gdf, gpd.GeoDataFrame):
            # Reine Tabelle ohne Geometrie (z. B. Stammdaten): nicht darstellbar
            print(f"  {name}: übersprungen (keine Geometrie)")
            continue
        if gdf.crs is not None:
            gdf = gdf.to_crs(WGS84)
        else:
            print(f"  Warnung: Layer {name} hat kein Koordinatensystem, "
                  "Koordinaten werden unverändert übernommen.")

        # Gewählte Beschriftung, sonst automatisch eine Spalte "name"
        if name in e.beschriftung:
            name_spalte = e.beschriftung[name]
        else:
            name_spalte = namensspalte(gdf.columns)
        if name_spalte not in gdf.columns:
            name_spalte = None

        print(f"  {name}: {len(gdf)} Objekte")
        datei.write(f"<Folder><name>{escape(name)}</name>\n")
        datei.writelines(placemarks(gdf, name_spalte, e.mit_attributen))
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


def argumente():
    """Kommandozeilen-Argumente definieren und einlesen."""
    parser = argparse.ArgumentParser(
        description="GeoPackage nach KMZ/KML für Google Earth umwandeln. "
                    "Was nicht als Option angegeben ist, wird nachgefragt.")
    parser.add_argument("gpkg", type=Path, help="Eingabedatei (.gpkg)")
    parser.add_argument("-o", "--ausgabe", type=Path,
                        help="Zieldatei (.kmz oder .kml). Standard: wie Eingabe, mit .kmz")
    parser.add_argument("-l", "--layer", nargs="+", help="Nur diese Layer umwandeln")
    parser.add_argument("-b", "--beschriftung",
                        help="Attribut für die Beschriftung, in allen Layern die es haben")
    parser.add_argument("-i", "--icon",
                        help=f'Icon für Punkte als URL oder Datei, SVG wird zu PNG '
                             f'("" = Stecknadel). Auswahl: {ICON_LISTE}')
    parser.add_argument("-f", "--farbe", type=int, choices=range(len(FARBEN)),
                        help="Farbe 0-7 (0 = Weiss)")
    parser.add_argument("--ohne-attribute", action="store_true",
                        help="Sachdaten weglassen (kleinere Datei)")
    return parser.parse_args()


def main():
    args = argumente()
    ziel = args.ausgabe or args.gpkg.with_suffix(".kmz")

    layer = args.layer or frage_layer(args.gpkg)
    if args.beschriftung is not None:
        beschriftung = {name: args.beschriftung for name in layer}
    else:
        beschriftung = frage_beschriftung(args.gpkg, layer)
    icon = args.icon if args.icon is not None else frage_icon()
    farbe = args.farbe if args.farbe is not None else frage_farbe()
    farbname, rgb = FARBEN[farbe]

    einstellungen = Einstellungen(layer, rgb, icon, beschriftung,
                                  not args.ohne_attribute)
    print(f"\n{args.gpkg} -> {ziel} ({farbname})")
    konvertiere(args.gpkg, ziel, einstellungen)
    print("Fertig.")


if __name__ == "__main__":
    main()
