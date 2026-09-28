from __future__ import annotations

from .api_key_service import ApiKeyService
from .chat_service import ChatService
from .database import IndexDatabase
from .ingest_service import IngestService

_ingest_service: IngestService | None = None
_chat_service: ChatService | None = None
_api_key_service: ApiKeyService | None = None
_index_database: IndexDatabase | None = None


def set_ingest_service(svc: IngestService) -> None:
    global _ingest_service
    _ingest_service = svc


def get_ingest_service() -> IngestService:
    if _ingest_service is None:
        raise RuntimeError("IngestService not initialized")
    return _ingest_service


def set_chat_service(svc: ChatService) -> None:
    global _chat_service
    _chat_service = svc


def get_chat_service() -> ChatService:
    if _chat_service is None:
        raise RuntimeError("ChatService not initialized")
    return _chat_service


def set_api_key_service(svc: ApiKeyService) -> None:
    global _api_key_service
    _api_key_service = svc


def get_api_key_service() -> ApiKeyService:
    if _api_key_service is None:
        raise RuntimeError("ApiKeyService not initialized")
    return _api_key_service


def set_index_database(db: IndexDatabase) -> None:
    global _index_database
    _index_database = db


def get_index_database() -> IndexDatabase:
    if _index_database is None:
        raise RuntimeError("IndexDatabase not initialized")
    return _index_database
