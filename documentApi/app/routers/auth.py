from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import get_current_api_key
from ..models import ApiKeyRecord

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
async def auth_status():
    return {"authRequired": True, "header": "X-API-Key"}


@router.get("/me")
async def auth_me(
    record: ApiKeyRecord = Depends(get_current_api_key),
):
    return record.model_dump(by_alias=True)
