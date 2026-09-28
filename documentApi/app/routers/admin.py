from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import get_api_key_service, require_admin_key
from ..api_key_service import ApiKeyService
from ..models import ApiKeyRecord, CreateApiKeyRequest

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/keys")
async def list_api_keys(
    _admin: ApiKeyRecord = Depends(require_admin_key),
    svc: ApiKeyService = Depends(get_api_key_service),
):
    rows = svc.list_keys()
    return [row.model_dump(by_alias=True) for row in rows]


@router.post("/keys")
async def create_api_key(
    body: CreateApiKeyRequest,
    _admin: ApiKeyRecord = Depends(require_admin_key),
    svc: ApiKeyService = Depends(get_api_key_service),
):
    created = svc.create_key(label=body.label, is_admin=body.is_admin)
    return created.model_dump(by_alias=True)


@router.delete("/keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    _admin: ApiKeyRecord = Depends(require_admin_key),
    svc: ApiKeyService = Depends(get_api_key_service),
):
    ok = svc.revoke_key(key_id)
    if not ok:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="API-Key nicht gefunden oder bereits widerrufen.")
    return {"ok": True}
