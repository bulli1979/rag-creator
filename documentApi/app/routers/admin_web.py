from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ..auth import require_admin_key
from ..database import IndexDatabase
from ..dependencies import get_index_database
from ..models import (
    AdminWebClientUpsert,
    AdminWebConnectionUpsert,
    AdminWebEventCreate,
    AdminWebPreferenceUpsert,
    ApiKeyRecord,
)

router = APIRouter(prefix="/api/admin-web", tags=["admin-web"])


def _require_client_id(x_admin_web_client_id: str | None = Header(None, alias="X-Admin-Web-Client-Id")) -> str:
    client_id = (x_admin_web_client_id or "").strip()
    if not client_id:
        raise HTTPException(
            status_code=400,
            detail="Header X-Admin-Web-Client-Id ist erforderlich.",
        )
    return client_id


@router.post("/clients")
async def register_client(
    body: AdminWebClientUpsert,
    _admin: ApiKeyRecord = Depends(require_admin_key),
    db: IndexDatabase = Depends(get_index_database),
):
    client_id = (body.client_id or "").strip() or str(uuid.uuid4())
    return db.upsert_admin_web_client(
        client_id=client_id,
        label=body.label,
        user_agent=body.user_agent,
    ).model_dump(by_alias=True)


@router.get("/clients/me")
async def get_my_client(
    client_id: str = Depends(_require_client_id),
    _admin: ApiKeyRecord = Depends(require_admin_key),
    db: IndexDatabase = Depends(get_index_database),
):
    row = db.get_admin_web_client(client_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Admin-Web-Client nicht gefunden.")
    return row.model_dump(by_alias=True)


@router.get("/connections")
async def list_connections(
    client_id: str = Depends(_require_client_id),
    _admin: ApiKeyRecord = Depends(require_admin_key),
    db: IndexDatabase = Depends(get_index_database),
):
    db.upsert_admin_web_client(client_id=client_id)
    return [row.model_dump(by_alias=True) for row in db.list_admin_web_connections(client_id)]


@router.put("/connections")
async def upsert_connection(
    body: AdminWebConnectionUpsert,
    client_id: str = Depends(_require_client_id),
    _admin: ApiKeyRecord = Depends(require_admin_key),
    db: IndexDatabase = Depends(get_index_database),
):
    db.upsert_admin_web_client(client_id=client_id)
    connection_id = (body.connection_id or "").strip() or str(uuid.uuid4())
    return db.upsert_admin_web_connection(
        connection_id=connection_id,
        client_id=client_id,
        name=body.name,
        api_base_url=body.api_base_url,
        api_key=body.api_key,
        is_default=body.is_default,
    ).model_dump(by_alias=True)


@router.delete("/connections/{connection_id}")
async def delete_connection(
    connection_id: str,
    client_id: str = Depends(_require_client_id),
    _admin: ApiKeyRecord = Depends(require_admin_key),
    db: IndexDatabase = Depends(get_index_database),
):
    ok = db.delete_admin_web_connection(connection_id, client_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Verbindung nicht gefunden.")
    return {"ok": True}


@router.get("/preferences")
async def list_preferences(
    client_id: str = Depends(_require_client_id),
    _admin: ApiKeyRecord = Depends(require_admin_key),
    db: IndexDatabase = Depends(get_index_database),
):
    db.upsert_admin_web_client(client_id=client_id)
    return [row.model_dump(by_alias=True) for row in db.list_admin_web_preferences(client_id)]


@router.put("/preferences")
async def upsert_preference(
    body: AdminWebPreferenceUpsert,
    client_id: str = Depends(_require_client_id),
    _admin: ApiKeyRecord = Depends(require_admin_key),
    db: IndexDatabase = Depends(get_index_database),
):
    db.upsert_admin_web_client(client_id=client_id)
    try:
        return db.upsert_admin_web_preference(
            client_id=client_id,
            pref_key=body.pref_key,
            pref_value=body.pref_value,
        ).model_dump(by_alias=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/events")
async def create_event(
    body: AdminWebEventCreate,
    client_id: str = Depends(_require_client_id),
    _admin: ApiKeyRecord = Depends(require_admin_key),
    db: IndexDatabase = Depends(get_index_database),
):
    db.upsert_admin_web_client(client_id=client_id)
    return db.insert_admin_web_event(
        event_id=str(uuid.uuid4()),
        client_id=client_id,
        event_type=body.event_type,
        payload=body.payload,
    ).model_dump(by_alias=True)


@router.get("/events")
async def list_events(
    client_id: str = Depends(_require_client_id),
    limit: int = Query(100, ge=1, le=500),
    _admin: ApiKeyRecord = Depends(require_admin_key),
    db: IndexDatabase = Depends(get_index_database),
):
    return [
        row.model_dump(by_alias=True)
        for row in db.list_admin_web_events(client_id=client_id, limit=limit)
    ]
