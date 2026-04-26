from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_rag_chunks import build_chunks_for_json
from docling.document_converter import DocumentConverter


def _subdir(output_dir: Path, folder_prefix: str, logical_name: str) -> Path:
    """Unterordner: logical_name oder '{prefix}_{logical_name}' wenn prefix gesetzt."""
    p = folder_prefix.strip().strip("/\\")
    if not p:
        return output_dir / logical_name
    return output_dir / f"{p}_{logical_name}"


def convert_pdfs(input_dir: Path, output_dir: Path, folder_prefix: str = "") -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_dir = _subdir(output_dir, folder_prefix, "json")
    markdown_dir = _subdir(output_dir, folder_prefix, "markdown")
    chunks_dir = _subdir(output_dir, folder_prefix, "chunks")
    json_dir.mkdir(parents=True, exist_ok=True)
    markdown_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"Keine PDF-Dateien in '{input_dir}' gefunden.")
        print("Lege PDF-Dateien in diesen Ordner und starte das Skript erneut.")
        return

    converter = DocumentConverter()

    for pdf_path in pdf_files:
        print(f"Verarbeite: {pdf_path.name}")
        try:
            result = converter.convert(str(pdf_path))

            markdown_text = result.document.export_to_markdown()
            json_data = result.document.export_to_dict()

            md_output_path = markdown_dir / f"{pdf_path.stem}.md"
            json_output_path = json_dir / f"{pdf_path.stem}.json"

            md_output_path.write_text(markdown_text, encoding="utf-8")
            json_output_path.write_text(
                json.dumps(json_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            print(f"  -> Markdown: {md_output_path}")
            print(f"  -> JSON: {json_output_path}")

            chunk_output_path = build_chunks_for_json(json_output_path, chunks_dir)
            print(f"  -> Chunks: {chunk_output_path}")
        except Exception as exc:  # noqa: BLE001
            print(f"  Fehler bei '{pdf_path.name}': {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Liest PDFs aus einem Ordner und konvertiert sie mit Docling in JSON und Markdown."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path("input"),
        help="Ordner mit PDF-Dateien (Standard: ./input)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output"),
        help="Ziel-Basisordner fuer die Ausgabe (Standard: ./output)",
    )
    parser.add_argument(
        "--output-folder-prefix",
        type=str,
        default="",
        metavar="PREFIX",
        help=(
            "Optionaler Praefix fuer die drei Ausgabe-Unterordner. "
            "Beispiel PREFIX 'run1' -> run1_json, run1_markdown, run1_chunks unter --output."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    input_dir = args.input.expanduser().resolve()
    output_dir = args.output.expanduser().resolve()
    prefix = str(args.output_folder_prefix or "")
    if any(sep in prefix for sep in ("/", "\\")):
        raise SystemExit("--output-folder-prefix darf keine Pfadtrenner enthalten.")
    if not input_dir.is_dir():
        raise SystemExit(f"Input-Ordner fehlt oder ist kein Verzeichnis: {input_dir}")
    convert_pdfs(input_dir, output_dir, folder_prefix=prefix)
