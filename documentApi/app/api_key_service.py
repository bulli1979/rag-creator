from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
import uuid

from .database import IndexDatabase
from .models import ApiKeyCreated, ApiKeyRecord

logger = logging.getLogger(__name__)

_KEY_PREFIX = "rag_"


def hash_api_key(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return f"{_KEY_PREFIX}{secrets.token_urlsafe(32)}"


class ApiKeyService:
    def __init__(self, database: IndexDatabase) -> None:
        self._db = database

    def ensure_bootstrap_keys(self) -> dict[str, str | None]:
        """
        Legt beim ersten Start einen Client- und einen Admin-Key an.
        Env-Overrides: RAG_DEFAULT_API_KEY, RAG_ADMIN_API_KEY (Klartext).
        Gibt neu erzeugte Keys einmalig zurück (sonst None).
        """
        created: dict[str, str | None] = {"default": None, "admin": None}
        if self._db.count_active_api_keys() > 0:
            return created

        default_plain = os.environ.get("RAG_DEFAULT_API_KEY", "").strip() or generate_api_key()
        admin_plain = os.environ.get("RAG_ADMIN_API_KEY", "").strip() or generate_api_key()

        self._db.insert_api_key(
            key_id=str(uuid.uuid4()),
            key_hash=hash_api_key(default_plain),
            label="default",
            is_admin=False,
        )
        self._db.insert_api_key(
            key_id=str(uuid.uuid4()),
            key_hash=hash_api_key(admin_plain),
            label="admin",
            is_admin=True,
        )
        created["default"] = default_plain
        created["admin"] = admin_plain
        logger.warning(
            "API-Keys initial erzeugt — Client-Key und Admin-Key stehen einmalig in den Logs."
        )
        logger.warning("Default API key (client): %s", default_plain)
        logger.warning("Admin API key: %s", admin_plain)
        return created

    def verify_key(self, plain: str | None) -> ApiKeyRecord | None:
        if not plain or not plain.strip():
            return None
        key_hash = hash_api_key(plain.strip())
        record = self._db.get_api_key_by_hash(key_hash)
        if record is None or record.revoked_at is not None:
            return None
        self._db.touch_api_key_last_used(record.key_id)
        return record

    def create_key(self, *, label: str, is_admin: bool = False) -> ApiKeyCreated:
        plain = generate_api_key()
        key_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        self._db.insert_api_key(
            key_id=key_id,
            key_hash=hash_api_key(plain),
            label=label.strip() or "unnamed",
            is_admin=is_admin,
        )
        return ApiKeyCreated(
            keyId=key_id,
            label=label.strip() or "unnamed",
            isAdmin=is_admin,
            apiKey=plain,
            createdAt=now,
        )

    def list_keys(self) -> list[ApiKeyRecord]:
        return self._db.list_api_keys()

    def revoke_key(self, key_id: str) -> bool:
        return self._db.revoke_api_key(key_id)
