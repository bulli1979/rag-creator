"""Kuratierte Sentence-Transformer-Modelle fuer Ingest/Chat (kompatibel zu Vector-Dim 384)."""

from __future__ import annotations

from typing import Any

# Qdrant embedded ist auf 384 Dimensionen konfiguriert — nur passende Modelle anbieten.
EMBEDDING_MODEL_CATALOG: list[dict[str, Any]] = [
    {
        "id": "paraphrase-multilingual-MiniLM-L12-v2",
        "label": "Multilingual MiniLM L12",
        "dimensions": 384,
        "languages": "de, en, multilingual",
        "recommended": True,
        "description": "Empfohlen für Deutsch (Flexion/Tempus) und gemischte Corpora.",
    },
    {
        "id": "all-MiniLM-L6-v2",
        "label": "MiniLM L6 (Englisch)",
        "dimensions": 384,
        "languages": "en",
        "recommended": False,
        "description": "Schnell, vor allem Englisch — bisheriger Projekt-Default.",
    },
    {
        "id": "all-MiniLM-L12-v2",
        "label": "MiniLM L12 (Englisch)",
        "dimensions": 384,
        "languages": "en",
        "recommended": False,
        "description": "Etwas stärker als L6, weiterhin englisch-lastig.",
    },
    {
        "id": "paraphrase-MiniLM-L6-v2",
        "label": "Paraphrase MiniLM L6",
        "dimensions": 384,
        "languages": "en",
        "recommended": False,
        "description": "Gut für semantische Ähnlichkeit / Paraphrasen (EN).",
    },
    {
        "id": "intfloat/multilingual-e5-small",
        "label": "E5 Small (multilingual)",
        "dimensions": 384,
        "languages": "de, en, multilingual",
        "recommended": False,
        "description": "Stark multilingual; etwas langsamer beim ersten Download.",
    },
]

_ALLOWED_IDS = {str(entry["id"]) for entry in EMBEDDING_MODEL_CATALOG}
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def list_embedding_models() -> list[dict[str, Any]]:
    return [dict(entry) for entry in EMBEDDING_MODEL_CATALOG]


def is_allowed_embedding_model(model_id: str) -> bool:
    return bool(model_id) and model_id.strip() in _ALLOWED_IDS


def normalize_embedding_model(model_id: str | None, *, fallback: str | None = None) -> str:
    cleaned = (model_id or "").strip()
    if is_allowed_embedding_model(cleaned):
        return cleaned
    fb = (fallback or DEFAULT_EMBEDDING_MODEL).strip()
    if is_allowed_embedding_model(fb):
        return fb
    return DEFAULT_EMBEDDING_MODEL
