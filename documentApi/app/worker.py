from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Any

import numpy as np

from .document_processing import structured_chunks
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

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # type: ignore[assignment]

_logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[str, Any] = {}
_BINARY_OFFICE_EXTENSIONS = {".pdf", ".docx", ".pptx"}

# Erste Zeilen / Kopfbereich: URL aus HTML, YAML, Markdown oder Klartext
_A_HREF_RE = re.compile(
    r'<a\s[^>]*\bhref\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE | re.DOTALL,
)
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
_BARE_URL_RE = re.compile(r"https?://[^\s<>\"'`\)\]]+")
# Erkennt "Quelle: https://..." auch wenn davor noch Text steht (z. B. "Nordic Optical Telescope Quelle: ...")
_LABEL_URL_RE = re.compile(
    r"(?:quelle|source|url)\s*:\s*(https?://[^\s<>\"'`]+)",
    re.IGNORECASE,
)


def _normalize_http_url(candidate: str) -> str | None:
    s = (candidate or "").strip().strip('"').strip("'")
    if not s:
        return None
    if s.startswith("ahttps://") or s.startswith("ahttp://"):
        s = s[1:]
    # Bei Web-Docs oft in Kopfzeilen enthalten, aber für's Öffnen ans Root-Verzeichnis gedacht.
    # Beispiel: https://www.not.iac.es/index.md -> https://www.not.iac.es/
    s = re.sub(r"/index\.(?:md|html?|htm)$", "/", s, flags=re.IGNORECASE)
    if s.startswith("https://") or s.startswith("http://"):
        return s.rstrip(".,;)")
    return None


def extract_header_canonical_url(raw_text: str, extension: str) -> str | None:
    """URL aus dem Kopf von MD/HTML/TXT (z. B. <a href=...> oben im Dokument)."""
    if extension not in {".md", ".html", ".htm", ".txt"}:
        return None
    head = raw_text[:8000]
    for m in _A_HREF_RE.finditer(head):
        u = _normalize_http_url(m.group(1))
        if u:
            return u

    # "Quelle:"/"/url:" kommt teils mid-line vor (Text davor), daher Suche im gesamten Head-String.
    m = _LABEL_URL_RE.search(head)
    if m:
        u = _normalize_http_url(m.group(1))
        if u:
            return u

    for line in head.splitlines()[:60]:
        ln = line.strip()
        if re.match(r"^(?:source|url)\s*:\s*", ln, re.I):
            rest = re.sub(r"^(?:source|url)\s*:\s*", "", ln, flags=re.I).strip()
            if "<a" in rest.lower():
                mm = _A_HREF_RE.search(rest)
                if mm:
                    u = _normalize_http_url(mm.group(1))
                    if u:
                        return u
            u = _normalize_http_url(rest)
            if u:
                return u
            parts = rest.split()
            if parts:
                u = _normalize_http_url(parts[0])
                if u:
                    return u
    for m in _MD_LINK_RE.finditer(head):
        u = _normalize_http_url(m.group(1))
        if u:
            return u
    for line in head.splitlines()[:60]:
        ln = line.strip()
        if ln.startswith("http://") or ln.startswith("https://"):
            u = _normalize_http_url(ln.split()[0])
            if u:
                return u
    m = _BARE_URL_RE.search(head)
    if m:
        return _normalize_http_url(m.group(0))
    return None


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Compatibility wrapper for callers that only need chunk text."""
    del chunk_overlap
    return [chunk.text for chunk in structured_chunks(text, target_chars=chunk_size)]


def parse_document(
    input_path: str, chunk_size: int, chunk_overlap: int, *, overlap_is_percent: bool = True
) -> dict[str, Any]:
    if not os.path.exists(input_path):
        return {"ok": False, "error": f"Datei nicht gefunden: {input_path}"}

    text = ""
    extension = os.path.splitext(input_path)[1].lower()

    if extension in {".md", ".txt"}:
        try:
            with open(input_path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            text = ""
    elif extension in {".html", ".htm"}:
        from .html_processing import html_to_markdown
        with open(input_path, "r", encoding="utf-8", errors="replace") as fh:
            text = html_to_markdown(fh.read())
    elif partition is not None and extension in {".pdf", ".docx", ".pptx"}:
        try:
            elements = partition(filename=input_path)
            text = "\n\n".join(str(el) for el in elements if str(el).strip())
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
    if '(cid:' in text or text.count('�')>=3 or re.search(r'[\x00-\x08\x0b\x0e-\x1f]',text):
        return {'ok':False,'error':'Document contains unresolved extraction/glyph damage; review the original source before indexing.'}

    # Kopf-URL aus Rohdatei lesen: unstructured kann bei MD/HTML <a href> entfernen.
    header_url: str | None = None
    if extension in {".md", ".html", ".htm"}:
        try:
            with open(input_path, "r", encoding="utf-8", errors="ignore") as fh:
                raw_head = fh.read(16000)
            header_url = extract_header_canonical_url(raw_head, extension)
        except OSError:
            header_url = extract_header_canonical_url(text, extension)
    else:
        header_url = extract_header_canonical_url(text, extension)

    del chunk_overlap
    processed = structured_chunks(
        text,
        target_chars=chunk_size,
        base_metadata={
            "sourcePath": input_path,
            "extension": extension,
            "canonicalUrl": header_url or "",
        },
    )

    chunk_objects: list[dict[str, Any]] = []
    for idx, chunk in enumerate(processed):
        meta = {
            **chunk.metadata,
            "sourcePath": input_path,
            "extension": extension,
            "sha256": hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
        }
        canonical = meta.get("canonicalSource") or header_url
        if canonical:
            meta["canonicalUrl"] = canonical
        chunk_objects.append(
            {"chunkIndex": idx, "text": chunk.text, "metadata": meta}
        )
    return {"ok": True, "chunks": chunk_objects}


def _get_model(model_name: str) -> Any:
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers ist nicht installiert.")
    if model_name not in _MODEL_CACHE:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if model_name == "mixedbread-ai/mxbai-embed-large-v1":
            from .config import get_base_directory
            _MODEL_CACHE[model_name] = SentenceTransformer(
                model_name, device=device, revision="b33106f585b9ce46904ad7443a3b52b7a63e231c",
                cache_folder=str(get_base_directory()/"model_cache"),
                local_files_only=True, trust_remote_code=False,
                model_kwargs={"use_safetensors":True})
        else:
            _MODEL_CACHE[model_name] = SentenceTransformer(model_name, device=device)
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
    model: Any, batch: list[str], internal_batch_size: int
) -> list[list[float]]:
    encoded = model.encode(
        batch,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=min(internal_batch_size, max(8, len(batch))),
    )
    return _vectors_from_encode_output(encoded)


def embed_queries(model_name: str, texts: list[str]) -> dict[str, Any]:
    # The documented retrieval instruction belongs only on queries, never on
    # documents. Raw/resolved queries remain intact in the encrypted audit.
    if model_name == "mixedbread-ai/mxbai-embed-large-v1":
        texts = ["Represent this sentence for searching relevant passages: " + text for text in texts]
    return embed_texts(model_name, texts)


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
