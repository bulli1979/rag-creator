from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse

from .api_key_service import ApiKeyService
from .models import ApiKeyRecord

_api_key_service: ApiKeyService | None = None

PUBLIC_PATHS = frozenset({"/", "/api/auth/status"})


def set_api_key_service(svc: ApiKeyService) -> None:
    global _api_key_service
    _api_key_service = svc


def get_api_key_service() -> ApiKeyService:
    if _api_key_service is None:
        raise RuntimeError("ApiKeyService not initialized")
    return _api_key_service


def extract_api_key_from_request(request: Request) -> str | None:
    header = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if header and header.strip():
        return header.strip()
    query = request.query_params.get("api_key")
    if query and query.strip():
        return query.strip()
    return None


async def api_key_auth_middleware(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or path in PUBLIC_PATHS:
        return await call_next(request)

    svc = get_api_key_service()
    plain = extract_api_key_from_request(request)
    record = svc.verify_key(plain)
    if record is None:
        return JSONResponse(
            status_code=401,
            content={"detail": "Ungültiger oder fehlender API-Key (Header X-API-Key)."},
        )
    request.state.api_key_record = record
    return await call_next(request)


def get_current_api_key(request: Request) -> ApiKeyRecord:
    record = getattr(request.state, "api_key_record", None)
    if record is None:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert.")
    return record


def require_admin_key(request: Request) -> ApiKeyRecord:
    record = get_current_api_key(request)
    if not record.is_admin:
        raise HTTPException(status_code=403, detail="Admin-API-Key erforderlich.")
    return record
