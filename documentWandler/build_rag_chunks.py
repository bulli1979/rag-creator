from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ALLOWED_LABELS = {"section_header", "text", "list_item", "caption", "title"}


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _extract_page_no(entry: dict[str, Any]) -> int | None:
    prov = entry.get("prov")
    if not isinstance(prov, list) or not prov:
        return None
    page_no = prov[0].get("page_no")
    return page_no if isinstance(page_no, int) else None


def _extract_units(doc: dict[str, Any], min_chars: int = 20) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    current_section = ""

    for entry in doc.get("texts", []):
        if not isinstance(entry, dict):
            continue

        label = entry.get("label")
        if label not in ALLOWED_LABELS:
            continue

        raw_text = entry.get("text") or entry.get("orig") or ""
        if not isinstance(raw_text, str):
            continue

        text = _normalize_text(raw_text)
        if len(text) < min_chars and label not in {"section_header", "title"}:
            continue

        if label in {"section_header", "title"}:
            current_section = text

        units.append(
            {
                "text": text,
                "label": label,
                "page_no": _extract_page_no(entry),
                "section_title": current_section,
            }
        )

    return units


def _word_count(text: str) -> int:
    return len(text.split())


def _build_chunks(
    units: list[dict[str, Any]],
    document_id: str,
    source_file: str,
    max_words: int = 350,
    min_words: int = 120,
    overlap_words: int = 50,
) -> list[dict[str, Any]]:
    if not units:
        return []

    chunks: list[dict[str, Any]] = []
    unit_words = [_word_count(unit["text"]) for unit in units]
    start = 0
    chunk_index = 0

    while start < len(units):
        end = start
        words = 0

        while end < len(units) and (words + unit_words[end] <= max_words or end == start):
            words += unit_words[end]
            end += 1

        while end < len(units) and words < min_words:
            words += unit_words[end]
            end += 1

        selected = units[start:end]
        if not selected:
            break

        text = "\n".join(unit["text"] for unit in selected)
        pages = [unit["page_no"] for unit in selected if isinstance(unit["page_no"], int)]
        labels = sorted({unit["label"] for unit in selected})

        section_title = ""
        for unit in selected:
            if unit["section_title"]:
                section_title = unit["section_title"]
                break

        chunk = {
            "id": f"{document_id}-c{chunk_index:04d}",
            "document_id": document_id,
            "source_file": source_file,
            "chunk_index": chunk_index,
            "text": text,
            "token_count_estimate": words,
            "char_count": len(text),
            "section_title": section_title,
            "labels": labels,
            "page_start": min(pages) if pages else None,
            "page_end": max(pages) if pages else None,
        }
        chunks.append(chunk)
        chunk_index += 1

        if end >= len(units):
            break

        back_words = 0
        next_start = end
        while next_start > start and back_words < overlap_words:
            next_start -= 1
            back_words += unit_words[next_start]

        if next_start <= start:
            next_start = start + 1
        start = next_start

    return chunks


def build_chunks_for_json(json_path: Path, chunks_output_dir: Path) -> Path:
    chunks_output_dir.mkdir(parents=True, exist_ok=True)

    with json_path.open("r", encoding="utf-8") as f:
        doc = json.load(f)

    document_id = str(doc.get("name", json_path.stem))
    source_file = str(doc.get("origin", {}).get("filename", f"{json_path.stem}.pdf"))

    units = _extract_units(doc)
    chunks = _build_chunks(units, document_id=document_id, source_file=source_file)

    output_path = chunks_output_dir / f"{json_path.stem}.chunks.json"
    output_path.write_text(
        json.dumps(
            {
                "document_id": document_id,
                "source_file": source_file,
                "chunk_count": len(chunks),
                "chunks": chunks,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return output_path


def process_json_directory(input_dir: Path, output_dir: Path) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        print(f"Keine JSON-Dateien in '{input_dir}' gefunden.")
        return

    for json_path in json_files:
        try:
            chunk_path = build_chunks_for_json(json_path, output_dir)
            print(f"Chunks erstellt: {chunk_path}")
        except Exception as exc:  # noqa: BLE001
            print(f"Fehler bei '{json_path.name}': {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Erzeugt RAG-optimierte Chunks aus Docling-JSON-Dateien."
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        help="Pfad zu einer einzelnen Docling-JSON-Datei",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("output/json"),
        help="Ordner mit Docling-JSON-Dateien (Standard: output/json)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/chunks"),
        help="Zielordner fuer Chunk-Dateien (Standard: output/chunks)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.input_json:
        try:
            output = build_chunks_for_json(args.input_json, args.output_dir)
            print(f"Chunks erstellt: {output}")
        except Exception as exc:  # noqa: BLE001
            print(f"Fehler bei '{args.input_json}': {exc}")
    else:
        process_json_directory(args.input_dir, args.output_dir)
