from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_chat_service
from ..chat_service import ChatService
from ..ollama_utils import ollama_origin_from_openai_base_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/ollama/models")
async def list_ollama_models(svc: ChatService = Depends(get_chat_service)):
    """
    Liefert die lokal bei Ollama installierten Modelle (GET …/api/tags).
    Die Ollama-Adresse wird aus den Chat-Einstellungen (llmBaseUrl) abgeleitet.
    """
    chat = svc.get_chat_settings()
    try:
        origin = ollama_origin_from_openai_base_url(chat.llm_base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    url = f"{origin.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url)
    except httpx.RequestError as exc:
        logger.warning("Ollama tags request failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Ollama nicht erreichbar unter {origin}. Läuft der Dienst? ({exc})",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama antwortete mit {response.status_code} für {url}",
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Ungültige JSON-Antwort von Ollama") from exc

    raw_models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(raw_models, list):
        raw_models = []

    models: list[dict[str, object]] = []
    for entry in raw_models:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or entry.get("model")
        if not isinstance(name, str) or not name.strip():
            continue
        size = entry.get("size")
        size_out: int | None = int(size) if isinstance(size, (int, float)) else None
        modified = entry.get("modified_at")
        modified_out = modified if isinstance(modified, str) else None
        models.append(
            {
                "name": name.strip(),
                "size": size_out,
                "modifiedAt": modified_out,
            }
        )

    return {
        "ollamaBaseUrl": origin,
        "models": models,
    }
