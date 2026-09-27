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
| [Source/](Source/) | Python-Skript, das die KMZ-Datei erzeugt |

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

## Datenquellen

- Wanderwege: [swissTLM3D Wanderwege](https://opendata.swiss/de/dataset/swisstlm3d-wanderwege)
- Kantonsgrenzen: [swissBOUNDARIES3D](https://www.swisstopo.admin.ch/de/landschaftsmodell-swissboundaries3d)

Quelle: Bundesamt für Landestopografie swisstopo
