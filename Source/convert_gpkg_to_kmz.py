"""
GeoPackage (.gpkg) nach KMZ oder KML für Google Earth umwandeln.

Das Skript funktioniert mit beliebigen GeoPackages: Es zeigt die enthaltenen
Layer an und fragt, ob alle oder nur einzelne umgewandelt werden sollen. Es
unterstützt alle Geometrietypen (Punkte, Linien, Flächen und deren
Multi-Varianten) und rechnet jedes Koordinatensystem nach WGS84 um, das
Google Earth erwartet. Jeder Layer wird ein eigener Ordner in Google Earth.

Alle Geometrien werden in einer Farbe gezeichnet, nie in Schwarz:

    0 Weiss (Standard)   1 Rot      2 Orange   3 Gelb
    4 Grün               5 Blau     6 Indigo   7 Violett

Installation:  pip install geopandas
Beispiele:
    python convert_gpkg_to_kmz.py daten.gpkg               (fragt nach Layern und Farbe)
    python convert_gpkg_to_kmz.py daten.gpkg --farbe 5     (blau)
    python convert_gpkg_to_kmz.py daten.gpkg -o karte.kml  (unkomprimiertes KML)
    python convert_gpkg_to_kmz.py daten.gpkg --layer strassen --ohne-attribute
"""
import argparse
import io
import zipfile
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


# --- Farben -------------------------------------------------------------------
def kml_farbe(rgb, deckkraft="ff"):
    """RGB-Hex (z. B. "FFA500") in KML-Notation umwandeln.

    KML erwartet die Reihenfolge aabbggrr (Deckkraft, Blau, Grün, Rot),
    also genau umgekehrt zum üblichen rrggbb.
    """
    rot, gruen, blau = rgb[0:2], rgb[2:4], rgb[4:6]
    return f"{deckkraft}{blau}{gruen}{rot}".lower()


def frage_farbe():
    """Farbe interaktiv abfragen. Leere Eingabe bedeutet Weiss (0)."""
    print("Farbe für die Geometrien wählen:")
    for nummer, (name, _) in enumerate(FARBEN):
        print(f"  {nummer}  {name}")
    while True:
        eingabe = input(f"Zahl 0-{len(FARBEN) - 1} [0 = Weiss]: ").strip()
        if eingabe == "":
            return 0
        if eingabe.isdigit() and int(eingabe) < len(FARBEN):
            return int(eingabe)
        print("Ungültige Eingabe, bitte nochmals.")


def frage_layer(gpkg):
    """Enthaltene Layer anzeigen und abfragen, welche umgewandelt werden.

    Layer ohne Geometrie (reine Tabellen) werden nur zur Info angezeigt,
    denn sie lassen sich nicht auf einer Karte darstellen.
    """
    alle = gpd.list_layers(gpkg)
    karten_layer = list(alle.loc[alle["geometry_type"].notna(), "name"])
    tabellen = list(alle.loc[alle["geometry_type"].isna(), "name"])

    print(f"Layer in {gpkg.name}:")
    for nummer, name in enumerate(karten_layer, start=1):
        typ = alle.loc[alle["name"] == name, "geometry_type"].iloc[0]
        print(f"  {nummer}  {name} ({typ})")
    for name in tabellen:
        print(f"     {name} (keine Geometrie, wird übersprungen)")

    antwort = input("Alle Layer umwandeln? [J/n]: ").strip().lower()
    if antwort in ("", "j", "ja", "y", "yes"):
        return karten_layer

    while True:
        eingabe = input("Nummern der gewünschten Layer, mit Komma getrennt (z. B. 1,3): ")
        teile = [t.strip() for t in eingabe.split(",") if t.strip()]
        if teile and all(t.isdigit() and 1 <= int(t) <= len(karten_layer) for t in teile):
            return [karten_layer[int(t) - 1] for t in teile]
        print("Ungültige Eingabe, bitte nochmals.")


def stil_kml(rgb):
    """Gemeinsamer KML-Stil für Punkte, Linien und Flächen."""
    farbe = kml_farbe(rgb)
    fuellung = kml_farbe(rgb, FLAECHEN_DECKKRAFT)
    return (
        '<Style id="stil">'
        f"<IconStyle><color>{farbe}</color></IconStyle>"
        f"<LineStyle><color>{farbe}</color><width>{LINIENBREITE}</width></LineStyle>"
        f"<PolyStyle><color>{fuellung}</color></PolyStyle>"
        "</Style>"
    )


# --- Geometrie -> KML ---------------------------------------------------------
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


def namensspalte(gdf):
    """Spalte finden, deren Wert als Beschriftung dient (z. B. "name" oder "NAME")."""
    for spalte in gdf.columns:
        if spalte.lower() == "name":
            return spalte
    return None


def placemarks(gdf, mit_attributen):
    """Alle Objekte eines Layers nacheinander als KML-Placemarks liefern."""
    name_spalte = namensspalte(gdf)
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
def schreibe_kml(datei, gpkg, layer, rgb, mit_attributen):
    """Das ganze KML-Dokument Layer für Layer in eine offene Textdatei schreiben.

    Es wird fortlaufend geschrieben statt alles im Speicher zu sammeln, damit
    auch grosse GeoPackages funktionieren.
    """
    datei.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>\n'
                f"<name>{escape(gpkg.stem)}</name>{stil_kml(rgb)}\n")
    for name in layer:
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
        print(f"  {name}: {len(gdf)} Objekte")
        datei.write(f"<Folder><name>{escape(name)}</name>\n")
        datei.writelines(placemarks(gdf, mit_attributen))
        datei.write("</Folder>\n")
    datei.write("</Document></kml>\n")


def konvertiere(gpkg, ziel, layer, rgb, mit_attributen):
    """GeoPackage als KMZ (ZIP mit doc.kml) oder als reine KML-Datei speichern."""
    if ziel.suffix.lower() == ".kml":
        with open(ziel, "w", encoding="utf-8") as datei:
            schreibe_kml(datei, gpkg, layer, rgb, mit_attributen)
    else:
        with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as kmz:
            with kmz.open("doc.kml", "w") as roh, \
                    io.TextIOWrapper(roh, encoding="utf-8") as datei:
                schreibe_kml(datei, gpkg, layer, rgb, mit_attributen)


def argumente():
    """Kommandozeilen-Argumente definieren und einlesen."""
    parser = argparse.ArgumentParser(
        description="GeoPackage nach KMZ/KML für Google Earth umwandeln.")
    parser.add_argument("gpkg", type=Path, help="Eingabedatei (.gpkg)")
    parser.add_argument("-o", "--ausgabe", type=Path,
                        help="Zieldatei (.kmz oder .kml). Standard: wie Eingabe, mit .kmz")
    parser.add_argument("-l", "--layer", nargs="+",
                        help="Nur diese Layer umwandeln. Ohne Angabe wird nachgefragt")
    parser.add_argument("-f", "--farbe", type=int, choices=range(len(FARBEN)),
                        help="Farbe 0-7 (0 = Weiss). Ohne Angabe wird nachgefragt")
    parser.add_argument("--ohne-attribute", action="store_true",
                        help="Sachdaten weglassen (kleinere Datei)")
    return parser.parse_args()


def main():
    args = argumente()
    ziel = args.ausgabe or args.gpkg.with_suffix(".kmz")
    layer = args.layer or frage_layer(args.gpkg)
    farbe = args.farbe if args.farbe is not None else frage_farbe()
    farbname, rgb = FARBEN[farbe]

    print(f"{args.gpkg} -> {ziel} ({farbname})")
    konvertiere(args.gpkg, ziel, layer, rgb, not args.ohne_attribute)
    print("Fertig.")


if __name__ == "__main__":
    main()
