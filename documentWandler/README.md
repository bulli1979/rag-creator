# PDF nach JSON und Markdown mit Docling

Dieses Projekt enthaelt einfache Python-Skripte, die alle PDF-Dateien aus einem **frei waehlbaren Input-Ordner** einlesen und die Ergebnisse unter einen **Output-Basisordner** schreiben:

- JSON-Dateien nach `output/json` (bzw. `{prefix}_json` bei gesetztem Praefix)
- Markdown nach `output/markdown` (bzw. `{prefix}_markdown`)
- RAG-Chunks nach `output/chunks` (bzw. `{prefix}_chunks`)

## Voraussetzungen

- Python 3.10 oder neuer

## Lokal starten

1. Abhaengigkeiten installieren:

```bash
pip install -r requirements.txt
```

1. PDFs in einen Ordner legen (beliebiger Pfad).

1. Skript starten — **Input** mit `-i` / `--input`, **Output-Basis** mit `-o` / `--output`:

```bash
python convert_pdfs.py -i "D:/meine_pdfs" -o "D:/docling_out"
```

Ohne Argumente gilt wie bisher: `./input` und `./output`.

Optionaler **Praefix** fuer die drei Unterordner (`json`, `markdown`, `chunks`): `--output-folder-prefix`. Beispiel Praefix `run1` erzeugt `run1_json`, `run1_markdown`, `run1_chunks` unter dem Output-Basisordner:

```bash
python convert_pdfs.py -i ./meine_pdfs -o ./out --output-folder-prefix run1
```

## RAG-Chunks separat erzeugen (optional)

Wenn du vorhandene JSON-Dateien nachtraeglich in RAG-Chunks umwandeln willst:

```bash
python build_rag_chunks.py --input-dir out/run1_json --output-dir out/run1_chunks
```

Oder fuer eine einzelne Datei:

```bash
python build_rag_chunks.py --input-json out/run1_json/deine_datei.json --output-dir out/run1_chunks
```

## Ergebnis

Nach dem Lauf findest du pro PDF (ohne Praefix, Pfade analog mit `{prefix}_…`):

- `<output>/json/<dateiname>.json`
- `<output>/markdown/<dateiname>.md`
- `<output>/chunks/<dateiname>.chunks.json`
