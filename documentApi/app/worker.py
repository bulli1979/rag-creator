from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

import numpy as np

from .services.quiet_ml_env import apply_quiet_ml_env

apply_quiet_ml_env()

try:
    from unstructured.partition.auto import partition
except Exception:
    partition = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

from sentence_transformers import SentenceTransformer

_logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[str, SentenceTransformer] = {}
_BINARY_OFFICE_EXTENSIONS = {".pdf", ".docx", ".pptx"}


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    normalized = " ".join(text.replace("\r", "\n").split())
    if not normalized:
        return []
    chunks: list[str] = []
    cursor = 0
    step_size = max(1, chunk_size - chunk_overlap)
    while cursor < len(normalized):
        chunk = normalized[cursor: cursor + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        cursor += step_size
    return chunks


def parse_document(
    input_path: str, chunk_size: int, chunk_overlap: int
) -> dict[str, Any]:
    if not os.path.exists(input_path):
        return {"ok": False, "error": f"Datei nicht gefunden: {input_path}"}

    text = ""
    extension = os.path.splitext(input_path)[1].lower()

    if partition is not None and extension in {".pdf", ".docx", ".pptx", ".html", ".md", ".txt"}:
        try:
            elements = partition(filename=input_path)
            text = "\n".join(str(el) for el in elements if str(el).strip())
        except Exception:
            text = ""

    if not text and extension == ".pdf" and PdfReader is not None:
        try:
            reader = PdfReader(input_path)
            page_texts: list[str] = []
            for page in reader.pages:
                extracted = (page.extract_text() or "").strip()
                if extracted:
                    page_texts.append(extracted)
            text = "\n".join(page_texts)
        except Exception:
            text = ""

    if not text:
        if extension in _BINARY_OFFICE_EXTENSIONS:
            return {
                "ok": False,
                "error": (
                    "Parsing fehlgeschlagen: Kein lesbarer Text aus Datei extrahiert "
                    f"({extension}). Bitte Parser-Abhaengigkeiten installieren oder "
                    "Datei als TXT/MD bereitstellen."
                ),
            }
        try:
            with open(input_path, "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except Exception as exc:
            return {"ok": False, "error": f"Parsing fehlgeschlagen: {exc}"}

    if text.lstrip().startswith("%PDF-"):
        return {
            "ok": False,
            "error": "Parsing fehlgeschlagen: PDF-Binaerdaten erkannt statt extrahiertem Text.",
        }

    chunks = chunk_text(text, chunk_size, chunk_overlap)
    chunk_objects: list[dict[str, Any]] = []
    for idx, chunk_value in enumerate(chunks):
        chunk_objects.append(
            {
                "chunkIndex": idx,
                "text": chunk_value,
                "metadata": {
                    "sourcePath": input_path,
                    "extension": extension,
                    "sha256": hashlib.sha256(chunk_value.encode("utf-8")).hexdigest(),
                },
            }
        )
    return {"ok": True, "chunks": chunk_objects}


def _get_model(model_name: str) -> SentenceTransformer:
    if model_name not in _MODEL_CACHE:
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _MODEL_CACHE[model_name]


def _vectors_from_encode_output(encoded: Any) -> list[list[float]]:
    """sentence_transformers: ndarray (n, dim) oder bei einem Satz (dim,)."""
    arr = np.asarray(encoded)
    if arr.ndim == 1:
        return [[float(v) for v in arr]]
    return [[float(v) for v in row] for row in arr]


# Pro Teilbatch: Speicher und tqdm-Noise begrenzen (grosse Dokumente).
_EMBED_SUBBATCH = 128


def _encode_one_batch(
    model: SentenceTransformer, batch: list[str], internal_batch_size: int
) -> list[list[float]]:
    encoded = model.encode(
        batch,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=min(internal_batch_size, max(8, len(batch))),
    )
    return _vectors_from_encode_output(encoded)


def embed_texts(model_name: str, texts: list[str]) -> dict[str, Any]:
    normalized = [t.strip() for t in texts if isinstance(t, str) and t.strip()]
    if not normalized:
        return {"ok": True, "vectors": []}
    n = len(normalized)
    _logger.info("embed_texts start: model=%s chunks=%s", model_name, n)
    try:
        model = _get_model(model_name)
        internal_bs = min(64, max(16, _EMBED_SUBBATCH // 2))
        vectors: list[list[float]] = []

        for start in range(0, n, _EMBED_SUBBATCH):
            part = normalized[start : start + _EMBED_SUBBATCH]
            try:
                part_vecs = _encode_one_batch(model, part, internal_bs)
            except Exception as batch_err:
                _logger.warning(
                    "embed subbatch failed (start=%s len=%s): %s — fallback einzeln",
                    start,
                    len(part),
                    batch_err,
                )
                part_vecs = []
                for idx, text in enumerate(part):
                    abs_idx = start + idx
                    try:
                        one = model.encode(
                            text,
                            convert_to_numpy=True,
                            normalize_embeddings=True,
                            show_progress_bar=False,
                        )
                        row = _vectors_from_encode_output(one)
                        if len(row) != 1:
                            return {
                                "ok": False,
                                "error": f"Embedding Rueckgabe unerwartet bei chunk {abs_idx}",
                            }
                        part_vecs.append(row[0])
                    except Exception as item_err:
                        preview = text[:120].replace("\n", " ")
                        return {
                            "ok": False,
                            "error": (
                                f"Embedding fehlgeschlagen bei chunk {abs_idx}: {item_err} "
                                f"(text_preview={preview}); subbatch_error={batch_err}"
                            ),
                        }

            if len(part_vecs) != len(part):
                return {
                    "ok": False,
                    "error": (
                        f"Embedding: Teilbatch start={start} "
                        f"vektoren={len(part_vecs)} != erwartet={len(part)}"
                    ),
                }
            vectors.extend(part_vecs)
            if n > _EMBED_SUBBATCH:
                _logger.info(
                    "embed_texts Fortschritt: %s/%s Chunks",
                    min(start + _EMBED_SUBBATCH, n),
                    n,
                )

        if len(vectors) != n:
            return {
                "ok": False,
                "error": f"Embedding: Gesamtvektoren ({len(vectors)}) != Texte ({n})",
            }
        _logger.info("embed_texts fertig: %s Vektoren", len(vectors))
        return {"ok": True, "vectors": vectors}
    except Exception as exc:
        sample_type = type(normalized[0]).__name__ if normalized else "none"
        _logger.exception("embed_texts fehlgeschlagen")
        return {
            "ok": False,
            "error": f"Embedding fehlgeschlagen: {exc} (texts_count={n}, first_type={sample_type})",
        }


def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "Python Worker ist bereit."}
