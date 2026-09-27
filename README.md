**[Jump to English](#english)**

# Wanderwege Schweiz für Google Earth

Alle signalisierten Wanderwege der Schweiz in einer KMZ-Datei für Google Earth,
aufgeteilt nach Kanton bzw. Region. Das komplette Schweizer Wanderwegnetz,
also Wanderwege, Bergwanderwege und Alpinwanderwege, liegt darin als KML/KMZ vor,
erzeugt aus amtlichen Daten von swisstopo.

Wer Schweizer Wanderwege in Google Earth in 3D anschauen, Touren planen oder
das Wegnetz eines Kantons überblicken möchte, lädt die Datei herunter und öffnet
sie in Google Earth (Desktop oder Web).

## Download

- **[KMZ-Datei der Schweizer Wanderwege für Google Earth herunterladen (ca. 48 MB)](https://github.com/poi2poi/google-earth-wanderwege-schweiz/raw/main/Google-Earth/Wanderwege_Schweiz_nach_Kanton.kmz)**
- [Aktuelle Version als Release-Download](https://github.com/poi2poi/google-earth-wanderwege-schweiz/releases/latest/download/Wanderwege_Schweiz_nach_Kanton.kmz)
- [Python-Skript herunterladen](https://github.com/poi2poi/google-earth-wanderwege-schweiz/raw/main/Source/wanderwege_nach_kanton.py)

## Ordnerstruktur

| Ordner | Inhalt |
|---|---|
| [Google-Earth/](Google-Earth/) | KMZ-Datei für Google Earth |
| [Source/](Source/) | Python-Skripte: Erzeugung der KMZ-Datei und allgemeiner GeoPackage-Konverter |

## Inhalt

Die Wege sind nach Kategorie eingefärbt:

| Farbe | Kategorie |
|---|---|
| Gelb | Wanderweg |
| Rot | Bergwanderweg |
| Blau | Alpinwanderweg |

Zuoberst liegt der Ordner **Kantonsgrenzen** mit den Grenzen aller 26 Kantone
als schwarze Linien. Darunter folgen die Wege, gruppiert in diese Ordner:

| Ordner | Kantone |
|---|---|
| Nordwestschweiz | Basel-Stadt, Basel-Landschaft, Jura |
| Westschweiz | Genève, Vaud, Neuchâtel, Fribourg |
| Zentralschweiz | Luzern, Zug, Obwalden, Nidwalden, Schwyz, Uri |
| Mittelland | Aargau, Zürich, Schaffhausen |
| Ostschweiz | St. Gallen, Thurgau, Appenzell Ausserrhoden, Appenzell Innerrhoden, Glarus, Liechtenstein |
| Bern, Graubünden, Solothurn, Ticino, Valais | je ein eigener Ordner |

Jeder Ordner enthält pro Kategorie einen Unterordner, so lassen sich einzelne
Regionen oder Kategorien ein- und ausblenden.

Ein Wegsegment gehört zu dem Kanton, in dem sein Mittelpunkt liegt. Wege, die
über die Landesgrenze hinaus weiterführen, sind dem nächstgelegenen Kanton
zugeordnet und enden deshalb nicht an der Grenze.

## Selbst erzeugen

Die KMZ-Datei wird mit [Source/wanderwege_nach_kanton.py](Source/wanderwege_nach_kanton.py)
erzeugt. Die Regionen lassen sich dort im Dictionary `REGIONEN` anpassen.

1. Die beiden Datensätze (siehe unten) als GeoPackage herunterladen und in den
   Hauptordner des Repos legen (sie sind per `.gitignore` ausgeschlossen).
2. Abhängigkeiten installieren und Skript im Hauptordner starten:

   ```
   pip install geopandas pyogrio shapely pyproj
   python Source/wanderwege_nach_kanton.py
   ```

Die Datei landet in `Google-Earth/`.

## Beliebiges GeoPackage nach KMZ umwandeln

[Source/convert_gpkg_to_kmz.py](Source/convert_gpkg_to_kmz.py) wandelt ein
beliebiges GeoPackage (.gpkg) in eine KMZ- oder KML-Datei für Google Earth um:
alle Geometrietypen, jedes Koordinatensystem. Es zeigt die enthaltenen Layer an
und fragt, ob alle oder nur einzelne umgewandelt werden sollen. Die Farbe ist
wählbar: 0 Weiss (Standard), 1 Rot, 2 Orange, 3 Gelb, 4 Grün, 5 Blau, 6 Indigo,
7 Violett.

```
pip install geopandas
python Source/convert_gpkg_to_kmz.py daten.gpkg              # fragt nach Layern und Farbe
python Source/convert_gpkg_to_kmz.py daten.gpkg --layer strassen --farbe 5
python Source/convert_gpkg_to_kmz.py daten.gpkg -o karte.kml --ohne-attribute
```

Alle Optionen zeigt `python Source/convert_gpkg_to_kmz.py --help`.

## Datenquellen

- Wanderwege: [swissTLM3D Wanderwege](https://opendata.swiss/de/dataset/swisstlm3d-wanderwege)
- Kantonsgrenzen: [swissBOUNDARIES3D](https://www.swisstopo.admin.ch/de/landschaftsmodell-swissboundaries3d)

Quelle: Bundesamt für Landestopografie swisstopo

## Lizenz

Die Skripte stehen unter der [MIT-Lizenz](LICENSE). Für die Geodaten in der
KMZ-Datei gelten die Nutzungsbedingungen von swisstopo (Open Government Data,
Quellenangabe erforderlich).

Dies ist ein kostenloses Hobbyprojekt, ohne Verbindung zu einer Firma und ohne
kommerzielle Absicht.

---

<a id="english"></a>

# Swiss Hiking Trails for Google Earth

All signposted hiking trails in Switzerland in a single KMZ file for Google
Earth, grouped by canton or region. It covers the complete Swiss trail network,
including hiking trails, mountain hiking trails and alpine hiking trails, as
KML/KMZ, built from official swisstopo data.

If you want to see Swiss hiking trails in 3D in Google Earth, plan a hike or get
an overview of the trails in a canton, download the file and open it in Google
Earth (desktop or web).

## Download

- **[Download the KMZ file of Swiss hiking trails for Google Earth (approx. 48 MB)](https://github.com/poi2poi/google-earth-wanderwege-schweiz/raw/main/Google-Earth/Wanderwege_Schweiz_nach_Kanton.kmz)**
- [Latest version as a release download](https://github.com/poi2poi/google-earth-wanderwege-schweiz/releases/latest/download/Wanderwege_Schweiz_nach_Kanton.kmz)
- [Download the Python script](https://github.com/poi2poi/google-earth-wanderwege-schweiz/raw/main/Source/wanderwege_nach_kanton.py)

## Repository structure

| Folder | Contents |
|---|---|
| [Google-Earth/](Google-Earth/) | KMZ file for Google Earth |
| [Source/](Source/) | Python scripts: builds the KMZ file, plus a general GeoPackage converter |

## Contents

Trails are coloured by category, matching the Swiss trail markers:

| Colour | Category (name in the file) |
|---|---|
| Yellow | Hiking trail (Wanderweg) |
| Red | Mountain hiking trail (Bergwanderweg) |
| Blue | Alpine hiking trail (Alpinwanderweg) |

The top folder, **Kantonsgrenzen**, contains the borders of all 26 cantons as
black lines. Below it are the trails, grouped into these folders (folder names
in the file are in German):

| Folder | Cantons |
|---|---|
| Nordwestschweiz (Northwestern Switzerland) | Basel-Stadt, Basel-Landschaft, Jura |
| Westschweiz (Western Switzerland) | Genève, Vaud, Neuchâtel, Fribourg |
| Zentralschweiz (Central Switzerland) | Luzern, Zug, Obwalden, Nidwalden, Schwyz, Uri |
| Mittelland (Swiss Plateau) | Aargau, Zürich, Schaffhausen |
| Ostschweiz (Eastern Switzerland) | St. Gallen, Thurgau, Appenzell Ausserrhoden, Appenzell Innerrhoden, Glarus, Liechtenstein |
| Bern, Graubünden, Solothurn, Ticino, Valais | one folder each |

Each folder has one subfolder per trail category, so you can show or hide
individual regions or categories.

Each trail segment belongs to the canton that contains its midpoint. Trails
that continue across the national border are assigned to the nearest canton, so
they don't stop at the border.

## Build it yourself

The KMZ file is created by [Source/wanderwege_nach_kanton.py](Source/wanderwege_nach_kanton.py).
You can change the regions in the `REGIONEN` dictionary.

1. Download both datasets (see below) as GeoPackage and put them in the root
   folder of the repository (they are excluded via `.gitignore`).
2. Install the dependencies and run the script from the root folder:

   ```
   pip install geopandas pyogrio shapely pyproj
   python Source/wanderwege_nach_kanton.py
   ```

The file is written to `Google-Earth/`.

## Convert any GeoPackage to KMZ

[Source/convert_gpkg_to_kmz.py](Source/convert_gpkg_to_kmz.py) converts any
GeoPackage (.gpkg) into a KMZ or KML file for Google Earth: all geometry
types, any coordinate system. It lists the layers in the file and asks whether
to convert all of them or only some. You can pick the colour: 0 white
(default), 1 red, 2 orange, 3 yellow, 4 green, 5 blue, 6 indigo, 7 violet.

```
pip install geopandas
python Source/convert_gpkg_to_kmz.py data.gpkg              # asks for layers and colour
python Source/convert_gpkg_to_kmz.py data.gpkg --layer roads --farbe 5
python Source/convert_gpkg_to_kmz.py data.gpkg -o map.kml --ohne-attribute
```

`python Source/convert_gpkg_to_kmz.py --help` lists all options. The script's
options and messages are in German.

## Data sources

- Hiking trails: [swissTLM3D Wanderwege](https://opendata.swiss/de/dataset/swisstlm3d-wanderwege)
- Canton borders: [swissBOUNDARIES3D](https://www.swisstopo.admin.ch/de/landschaftsmodell-swissboundaries3d)

Source: Federal Office of Topography swisstopo

## License

The scripts are released under the [MIT License](LICENSE). The geodata in the
KMZ file is subject to swisstopo's terms of use (Open Government Data, source
attribution required).

This is a free hobby project, not affiliated with any company and with no
commercial intent.
