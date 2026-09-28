from __future__ import annotations

import json
import os
from pathlib import Path

from .models import AppSettings, ChatSettings, PostgresEnvironment, migrate_overlap_value_to_percent


def _default_app_settings() -> AppSettings:
    return AppSettings(
        active_postgres_environment_id="default",
        postgres_environments=[
            PostgresEnvironment(
                environment_id="default",
                name="Standard",
                family_id="default",
                family_name="Standard",
                vector_backend="postgres",
                db_host="localhost",
                db_port=5432,
                db_name="rag",
                db_user="postgres",
                db_password="",
                db_schema="public",
                db_table_name="rag_documents",
                sqlite_file_path="",
                qdrant_local_path="",
                embedding_model="paraphrase-multilingual-MiniLM-L12-v2",
                chunk_size=900,
                chunk_overlap=15,
                is_matrix_variant=False,
            )
        ],
        chunk_size=900,
        chunk_overlap=15,
        embedding_model="paraphrase-multilingual-MiniLM-L12-v2",
        store_markdown=True,
    )


_DEFAULT_SETTINGS = _default_app_settings()
_DEFAULT_CHAT_SETTINGS = ChatSettings()

_PROJECT_DIR = Path(__file__).resolve().parent.parent


def _optional_data_root() -> Path | None:
    """Wenn gesetzt (z. B. Docker-Volume), liegen settings, Chat-Settings und Nutzerdaten unter diesem Pfad."""
    raw = os.environ.get("RAG_DATA_ROOT", "").strip()
    return Path(raw) if raw else None


def get_base_directory() -> Path:
    root = _optional_data_root()
    if root is not None:
        return root
    return Path.home() / "RAGIngestStudio"


def get_settings_path() -> Path:
    root = _optional_data_root()
    if root is not None:
        return root / "settings.json"
    return _PROJECT_DIR / "settings.json"


def get_app_paths() -> dict[str, Path]:
    base = get_base_directory()
    return {
        "base": base,
        "files": base / "files",
        "corpus": base / "corpus",
        "database": base / "index.sqlite",
        "settings": get_settings_path(),
    }


def ensure_directories() -> None:
    paths = get_app_paths()
    paths["base"].mkdir(parents=True, exist_ok=True)
    paths["files"].mkdir(parents=True, exist_ok=True)
    paths["corpus"].mkdir(parents=True, exist_ok=True)
    (paths["base"] / "vector_sqlite").mkdir(parents=True, exist_ok=True)
    (paths["base"] / "vector_qdrant").mkdir(parents=True, exist_ok=True)


_LEGACY_DB_KEYS = frozenset(
    {
        "dbHost",
        "dbPort",
        "dbName",
        "dbUser",
        "dbPassword",
        "dbTableName",
        "dbSchema",
    }
)


def _migrate_settings_dict(data: dict) -> dict:
    """Alte flache DB-Felder in postgresEnvironments / activePostgresEnvironmentId ueberfuehren."""
    envs = data.get("postgresEnvironments")
    global_emb = str(data.get("embeddingModel") or "paraphrase-multilingual-MiniLM-L12-v2")
    try:
        global_chunk = int(data.get("chunkSize") or 900)
    except (TypeError, ValueError):
        global_chunk = 900
    try:
        raw_global_overlap = int(data.get("chunkOverlap") if data.get("chunkOverlap") is not None else 15)
    except (TypeError, ValueError):
        raw_global_overlap = 15
    already_percent = str(data.get("chunkOverlapUnit") or "").lower() == "percent"
    global_overlap = (
        max(0, min(90, raw_global_overlap))
        if already_percent
        else migrate_overlap_value_to_percent(raw_global_overlap, global_chunk)
    )

    if isinstance(envs, list) and len(envs) > 0:
        merged = {**data}
        active = merged.get("activePostgresEnvironmentId")
        if not active:
            first = envs[0]
            if isinstance(first, dict) and first.get("id"):
                merged["activePostgresEnvironmentId"] = str(first["id"])
            else:
                merged["activePostgresEnvironmentId"] = "default"
        # Pro-Env family/embedding/chunk nachziehen
        fixed_envs: list[dict] = []
        for env in envs:
            if not isinstance(env, dict):
                continue
            e = dict(env)
            eid = str(e.get("id") or "default")
            if not str(e.get("familyId") or "").strip():
                e["familyId"] = eid
            if not str(e.get("familyName") or "").strip():
                e["familyName"] = str(e.get("name") or eid)
            if not str(e.get("embeddingModel") or "").strip():
                e["embeddingModel"] = global_emb
            if e.get("chunkSize") is None or e.get("chunkSize") == "":
                e["chunkSize"] = global_chunk
            try:
                env_chunk = int(e.get("chunkSize") or global_chunk)
            except (TypeError, ValueError):
                env_chunk = global_chunk
            if e.get("chunkOverlap") is None or e.get("chunkOverlap") == "":
                e["chunkOverlap"] = global_overlap
            else:
                try:
                    raw_ov = int(e.get("chunkOverlap"))
                except (TypeError, ValueError):
                    raw_ov = global_overlap
                e["chunkOverlap"] = (
                    max(0, min(90, raw_ov))
                    if already_percent
                    else migrate_overlap_value_to_percent(raw_ov, env_chunk)
                )
            if "isMatrixVariant" not in e:
                e["isMatrixVariant"] = False
            fixed_envs.append(e)
        merged["postgresEnvironments"] = fixed_envs
        merged["chunkOverlap"] = global_overlap
        merged["chunkOverlapUnit"] = "percent"
        return merged

    defaults = _DEFAULT_SETTINGS.model_dump(by_alias=True)
    merged_flat = {**defaults, **data}
    env = {
        "id": "default",
        "name": str(merged_flat.get("environmentDisplayName") or "Standard"),
        "familyId": "default",
        "familyName": str(merged_flat.get("environmentDisplayName") or "Standard"),
        "dbHost": merged_flat.get("dbHost", "localhost"),
        "dbPort": int(merged_flat.get("dbPort", 5432)),
        "dbName": merged_flat.get("dbName", "rag"),
        "dbUser": merged_flat.get("dbUser", "postgres"),
        "dbPassword": merged_flat.get("dbPassword", ""),
        "dbSchema": merged_flat.get("dbSchema", "public"),
        "dbTableName": merged_flat.get("dbTableName", "rag_documents"),
        "embeddingModel": global_emb,
        "chunkSize": global_chunk,
        "chunkOverlap": global_overlap,
        "isMatrixVariant": False,
    }
    rest = {
        k: v
        for k, v in merged_flat.items()
        if k not in _LEGACY_DB_KEYS and k != "environmentDisplayName"
    }
    rest["postgresEnvironments"] = [env]
    rest["activePostgresEnvironmentId"] = "default"
    rest["chunkOverlap"] = global_overlap
    rest["chunkOverlapUnit"] = "percent"
    return rest


def load_settings() -> AppSettings:
    settings_path = get_app_paths()["settings"]
    try:
        raw = settings_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        migrated = _migrate_settings_dict(data)
        base = _DEFAULT_SETTINGS.model_dump(by_alias=True)
        return AppSettings(**{**base, **migrated})
    except Exception:
        save_settings(_DEFAULT_SETTINGS)
        return _DEFAULT_SETTINGS


def save_settings(settings: AppSettings) -> AppSettings:
    settings_path = get_app_paths()["settings"]
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    synced = settings.sync_globals_from_active_env()
    payload = synced.model_dump(by_alias=True)
    payload["chunkOverlapUnit"] = "percent"
    settings_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return synced


def get_chat_settings_path() -> Path:
    root = _optional_data_root()
    if root is not None:
        return root / "chat_settings.json"
    return _PROJECT_DIR / "chat_settings.json"


def load_chat_settings() -> ChatSettings:
    path = get_chat_settings_path()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        settings = ChatSettings(
            **{**_DEFAULT_CHAT_SETTINGS.model_dump(by_alias=True), **data}
        )
    except Exception:
        settings = _DEFAULT_CHAT_SETTINGS.model_copy()
        env_url = os.environ.get("LLM_BASE_URL", "").strip()
        if env_url:
            settings = settings.model_copy(update={"llm_base_url": env_url})
        save_chat_settings(settings)
    else:
        env_url = os.environ.get("LLM_BASE_URL", "").strip()
        if env_url:
            settings = settings.model_copy(update={"llm_base_url": env_url})
    return settings


def save_chat_settings(settings: ChatSettings) -> ChatSettings:
    path = get_chat_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(settings.model_dump(by_alias=True), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return settings
