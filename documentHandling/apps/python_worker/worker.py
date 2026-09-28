import json
import os
import sys
from hashlib import sha256
from typing import Any, Dict, List

try:
    from unstructured.partition.auto import partition
except Exception:
    partition = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

from sentence_transformers import SentenceTransformer

MODEL_CACHE: Dict[str, SentenceTransformer] = {}
BINARY_OFFICE_EXTENSIONS = {".pdf", ".docx", ".pptx"}


def read_stdin_json() -> Dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def write_json(payload: Dict[str, Any], exit_code: int = 0) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True))
    sys.exit(exit_code)


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """chunk_overlap: absolute Zeichen."""
    normalized = " ".join(text.replace("\r", "\n").split())
    if not normalized:
        return []
    chunks: List[str] = []
    cursor = 0
    overlap = max(0, min(max(0, chunk_size - 1), int(chunk_overlap)))
    step_size = max(1, chunk_size - overlap)
    while cursor < len(normalized):
        chunk = normalized[cursor : cursor + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        cursor += step_size
    return chunks


def overlap_chars_from_percent(chunk_size: int, overlap_percent: int) -> int:
    size = max(1, int(chunk_size or 1))
    pct = max(0, min(90, int(overlap_percent)))
    return max(0, min(size - 1, int(size * pct / 100)))


def parse_document(input_path: str, chunk_size: int, chunk_overlap: int) -> Dict[str, Any]:
    """chunk_overlap wird als Prozent der Chunk-Größe interpretiert (0–90)."""
    if not os.path.exists(input_path):
        return {"ok": False, "error": f"Datei nicht gefunden: {input_path}"}

    text = ""
    extension = os.path.splitext(input_path)[1].lower()
    if partition is not None and extension in {".pdf", ".docx", ".pptx", ".html", ".md", ".txt"}:
        try:
            elements = partition(filename=input_path)
            text = "\n".join(str(element) for element in elements if str(element).strip())
        except Exception:
            text = ""

    if not text and extension == ".pdf" and PdfReader is not None:
        try:
            reader = PdfReader(input_path)
            page_texts: List[str] = []
            for page in reader.pages:
                extracted = page.extract_text() or ""
                extracted = extracted.strip()
                if extracted:
                    page_texts.append(extracted)
            text = "\n".join(page_texts)
        except Exception:
            text = ""

    if not text:
        if extension in BINARY_OFFICE_EXTENSIONS:
            return {
                "ok": False,
                "error": (
                    "Parsing fehlgeschlagen: Kein lesbarer Text aus Datei extrahiert "
                    f"({extension}). Bitte Parser-Abhaengigkeiten installieren oder Datei als TXT/MD bereitstellen."
                ),
            }
        try:
            with open(input_path, "r", encoding="utf-8", errors="ignore") as handle:
                text = handle.read()
        except Exception as error:
            return {"ok": False, "error": f"Parsing fehlgeschlagen: {error}"}

    # Schutz gegen versehentliches Embedding von PDF-Binaerdaten.
    if text.lstrip().startswith("%PDF-"):
        return {
            "ok": False,
            "error": "Parsing fehlgeschlagen: PDF-Binaerdaten erkannt statt extrahiertem Text.",
        }

    chunks = chunk_text(text, chunk_size, overlap_chars_from_percent(chunk_size, chunk_overlap))
    chunk_objects: List[Dict[str, Any]] = []
    for chunk_index, chunk_text_value in enumerate(chunks):
        chunk_objects.append(
            {
                "chunkIndex": chunk_index,
                "text": chunk_text_value,
                "metadata": {
                    "sourcePath": input_path,
                    "extension": extension,
                    "sha256": sha256(chunk_text_value.encode("utf-8")).hexdigest(),
                },
            }
        )
    return {"ok": True, "chunks": chunk_objects}


def get_model(model_name: str) -> SentenceTransformer:
    if model_name not in MODEL_CACHE:
        MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return MODEL_CACHE[model_name]


def normalize_texts(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []

    normalized: List[str] = []
    for item in value:
        if item is None:
            continue
        if isinstance(item, str):
            text_value = item.strip()
        else:
            text_value = str(item).strip()
        if text_value:
            normalized.append(text_value)
    return normalized


def embed_texts(model_name: str, texts: Any) -> Dict[str, Any]:
    normalized_texts = normalize_texts(texts)
    if len(normalized_texts) == 0:
        return {"ok": True, "vectors": []}
    try:
        model = get_model(model_name)
        vectors: List[List[float]] = []
        for index, text in enumerate(normalized_texts):
            try:
                vector = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
            except Exception as item_error:
                preview = text[:120].replace("\n", " ")
                return {
                    "ok": False,
                    "error": f"Embedding fehlgeschlagen bei chunk {index}: {item_error} (text_preview={preview})",
                }

            if hasattr(vector, "tolist"):
                as_list = vector.tolist()
            else:
                as_list = list(vector)

            if isinstance(as_list, list) and len(as_list) > 0 and isinstance(as_list[0], list):
                if len(as_list) != 1:
                    return {"ok": False, "error": f"Embedding Rueckgabe unerwartet bei chunk {index}: batch-groesse {len(as_list)}"}
                vectors.append([float(value) for value in as_list[0]])
            else:
                vectors.append([float(value) for value in as_list])

        return {"ok": True, "vectors": vectors}
    except Exception as error:
        sample_type = type(normalized_texts[0]).__name__ if len(normalized_texts) > 0 else "none"
        return {
            "ok": False,
            "error": f"Embedding fehlgeschlagen: {error} (texts_count={len(normalized_texts)}, first_type={sample_type})",
        }


def run_health_check() -> Dict[str, Any]:
    return {"ok": True, "message": "Worker ist bereit."}


def main() -> None:
    if len(sys.argv) < 2:
        write_json({"ok": False, "error": "Kein Befehl uebergeben."}, 1)

    command = sys.argv[1]
    payload = read_stdin_json()

    if command == "health":
        write_json(run_health_check())
    elif command == "parse":
        write_json(
            parse_document(
                input_path=str(payload.get("inputPath", "")),
                chunk_size=int(payload.get("chunkSize", 900)),
                chunk_overlap=int(payload.get("chunkOverlap", 15)),
            )
        )
    elif command == "embed":
        texts = payload.get("texts", [])
        write_json(embed_texts(model_name=str(payload.get("model", "all-MiniLM-L6-v2")), texts=texts))
    else:
        write_json({"ok": False, "error": f"Unbekannter Befehl: {command}"}, 1)


if __name__ == "__main__":
    main()
