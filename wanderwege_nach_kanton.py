"""
Wanderwege der Schweiz (swissTLM3D) nach Kantonen bzw. Regionen aufteilen und
zusammen mit den Kantonsgrenzen (swissBOUNDARIES3D) als KMZ für Google Earth
exportieren.

Installation:  pip install geopandas pyogrio shapely pyproj
Aufruf:        python wanderwege_nach_kanton.py
"""
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.ops import linemerge

# --- Einstellungen ----------------------------------------------------------
WEGE = "SWISSTLM3D_WANDERWEGE.gpkg"
GRENZEN = "swissBOUNDARIES3D_1_5_LV95_LN02.gpkg"
KMZ = Path("wanderwege_kmz") / "Wanderwege_Schweiz_nach_Kanton.kmz"

# KML-Farben sind aabbggrr (nicht rrggbb!)
WEG_FARBEN = {
    "Wanderweg": "ff00d7ff",       # gelb
    "Bergwanderweg": "ff0000e6",   # rot
    "Alpinwanderweg": "ffff6000",  # blau
}
GRENZ_FARBE = "ff000000"           # schwarz

# Kantone, die zu einer Region zusammengefasst werden; alle anderen bleiben einzeln
REGIONEN = {
    "Nordwestschweiz": ["Basel-Stadt", "Basel-Landschaft", "Jura"],
    "Westschweiz": ["Genève", "Vaud", "Neuchâtel", "Fribourg"],
    "Zentralschweiz": ["Luzern", "Zug", "Obwalden", "Nidwalden", "Schwyz", "Uri"],
    "Mittelland": ["Aargau", "Zürich", "Schaffhausen"],
    "Ostschweiz": ["St. Gallen", "Thurgau", "Appenzell Ausserrhoden",
                   "Appenzell Innerrhoden", "Liechtenstein", "Glarus"],
}


# --- Hilfsfunktionen --------------------------------------------------------
def lade(pfad, **kwargs):
    """GeoPackage-Layer laden, Höhe (Z) weglassen."""
    gdf = gpd.read_file(pfad, engine="pyogrio", **kwargs)
    gdf["geometry"] = shapely.force_2d(gdf.geometry.values)
    return gdf


def einzelteile(geom):
    """Multi-Geometrie in ihre Teile zerlegen, einfache Geometrie unverändert."""
    return geom.geoms if hasattr(geom, "geoms") else [geom]


def placemark(linie, stil, name=""):
    """Eine Linie als KML-Placemark."""
    koord = " ".join(f"{x:.6f},{y:.6f}" for x, y in np.asarray(linie.coords))
    name = f"<name>{name}</name>" if name else ""
    return (f"<Placemark>{name}<styleUrl>#{stil}</styleUrl><LineString>"
            f"<tessellate>1</tessellate><coordinates>{koord}</coordinates>"
            f"</LineString></Placemark>")


def wege_ordner(df, ordner):
    """KML-Ordner einer Region mit einem Unterordner pro Wegkategorie.

    Aneinanderstossende Segmente werden zu langen Linien verbunden, damit die
    Datei weniger Placemarks enthält.
    """
    out = [f"<Folder><name>{ordner}</name>"]
    for kategorie in WEG_FARBEN:
        geoms = df.geometry[df.wanderwege == kategorie]
        if geoms.empty:
            continue
        linien = [t for g in geoms if g is not None and not g.is_empty
                  for t in einzelteile(g)]
        verbunden = linemerge(shapely.MultiLineString(linien))
        out.append(f"<Folder><name>{kategorie}</name>")
        out += [placemark(l, kategorie) for l in einzelteile(verbunden)]
        out.append("</Folder>")
    out.append("</Folder>")
    return out


def grenzen_ordner(grenzen):
    """KML-Ordner mit den Kantonsgrenzen als Linien."""
    out = ["<Folder><name>Kantonsgrenzen</name>"]
    for name, geom in zip(grenzen["name"], grenzen.geometry):
        out += [placemark(l, "Grenze", name) for l in einzelteile(geom)]
    out.append("</Folder>")
    return out


def schreibe_kmz(pfad, titel, inhalt):
    """KML-Dokument mit Stilen zusammensetzen und als KMZ (ZIP) speichern."""
    stile = [f'<Style id="{k}"><LineStyle><color>{c}</color><width>3</width>'
             f"</LineStyle></Style>" for k, c in WEG_FARBEN.items()]
    stile.append(f'<Style id="Grenze"><LineStyle><color>{GRENZ_FARBE}</color>'
                 f"<width>2</width></LineStyle></Style>")
    kml = "\n".join(['<?xml version="1.0" encoding="UTF-8"?>',
                     '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
                     f"<name>{titel}</name>", *stile, *inhalt,
                     "</Document></kml>"])
    pfad.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(pfad, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml)


# --- 1) Daten laden (beide in LV95 / EPSG:2056) -----------------------------
print(f"Lade {WEGE}")
wege = lade(WEGE, columns=["wanderwege"])

print(f"Lade {GRENZEN}")
kantone = lade(GRENZEN, layer="tlm_kantonsgebiet")
kantone = kantone.dissolve(by="name", as_index=False)[["name", "geometry"]]

# Liechtenstein ist kein Kanton, gehört für die Wege aber zur Ostschweiz
land = lade(GRENZEN, layer="tlm_landesgebiet")
gebiete = pd.concat([kantone, land.loc[land.icc == "LI", ["name", "geometry"]]],
                    ignore_index=True)

# --- 2) Jedes Wegsegment einem Kanton zuordnen ------------------------------
print("Ordne Wege den Kantonen zu")

# Massgebend ist der Mittelpunkt des Segments
mitte = wege.copy()
mitte["geometry"] = wege.geometry.interpolate(0.5, normalized=True)

zuord = gpd.sjoin(mitte, gebiete, how="left", predicate="within")
zuord = zuord[~zuord.index.duplicated()]

# Wege, die über die Grenze ins Ausland laufen: nächstgelegenem Kanton zuordnen
ausland = zuord["name"].isna()
naechst = gpd.sjoin_nearest(mitte[ausland], gebiete, how="left")
naechst = naechst[~naechst.index.duplicated()]
zuord.loc[ausland, "name"] = naechst["name"]

# Kanton -> Region (falls zusammengefasst), sonst Kantonsname behalten
kanton_zu_region = {k: r for r, liste in REGIONEN.items() for k in liste}
wege["ordner"] = zuord["name"].replace(kanton_zu_region)

# --- 3) Nach WGS84 (EPSG:4326) für Google Earth -----------------------------
wege = wege.to_crs(4326)
grenzen = kantone.copy()
grenzen["geometry"] = grenzen.geometry.boundary   # Fläche -> Umrisslinie
grenzen = grenzen.to_crs(4326)

# --- 4) KMZ schreiben: Kantonsgrenzen zuoberst, dann ein Ordner pro Region --
inhalt = grenzen_ordner(grenzen)
for ordner, df in sorted(wege.groupby("ordner")):
    print(f"{ordner:25s} {len(df):7d} Segmente")
    inhalt += wege_ordner(df, ordner)

print(f"Schreibe {KMZ}")
schreibe_kmz(KMZ, "Wanderwege Schweiz nach Kanton", inhalt)
