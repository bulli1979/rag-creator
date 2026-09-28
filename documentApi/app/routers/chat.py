from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..chat_service import ChatService
from ..dependencies import get_chat_service
from ..models import ChatFeedbackRequest, ChatRequest, ChatResponse, ChatSettings

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    svc: ChatService = Depends(get_chat_service),
):
    try:
        response = await svc.chat(request)
        return response.model_dump(by_alias=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/requests")
async def list_chat_requests(
    limit: int = Query(default=100, ge=1, le=500),
    environment_id: str | None = Query(default=None, alias="environmentId"),
    svc: ChatService = Depends(get_chat_service),
):
    rows = svc.list_chat_requests(environment_id=environment_id, limit=limit)
    return [row.model_dump(by_alias=True) for row in rows]


@router.post("/requests/{request_id}/feedback")
async def submit_chat_feedback(
    request_id: str,
    feedback: ChatFeedbackRequest,
    svc: ChatService = Depends(get_chat_service),
):
    try:
        saved = svc.submit_feedback(request_id, feedback)
        return saved.model_dump(by_alias=True)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/settings")
async def get_chat_settings(
    svc: ChatService = Depends(get_chat_service),
):
    return svc.get_chat_settings().model_dump(by_alias=True)


@router.put("/settings")
async def save_chat_settings(
    settings: ChatSettings,
    svc: ChatService = Depends(get_chat_service),
):
    svc.update_chat_settings(settings)
    return svc.get_chat_settings().model_dump(by_alias=True)
