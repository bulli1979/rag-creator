from __future__ import annotations

import json
import os
from pathlib import Path

from .models import AppSettings, ChatSettings, PostgresEnvironment


def _env_str(name: str, fallback: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return fallback
    value = value.strip()
    return value if value else fallback


def _env_int(name: str, fallback: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return fallback
    try:
        return int(raw.strip())
    except Exception:
        return fallback


def _default_app_settings() -> AppSettings:
    backend = _env_str("VECTOR_BACKEND", "postgres")
    return AppSettings(
        active_postgres_environment_id="default",
        postgres_environments=[
            PostgresEnvironment(
                environment_id="default",
                name="Standard",
                vector_backend=backend,
                db_host=_env_str("POSTGRES_HOST", "localhost"),
                db_port=_env_int("POSTGRES_PORT", 5432),
                db_name=_env_str("POSTGRES_DB", "rag"),
                db_user=_env_str("POSTGRES_USER", "postgres"),
                db_password=_env_str("POSTGRES_PASSWORD", ""),
                db_schema=_env_str("POSTGRES_SCHEMA", "public"),
                db_table_name=_env_str("POSTGRES_TABLE", "rag_documents"),
                sqlite_file_path="",
                qdrant_local_path="",
            )
        ],
        chunk_size=900,
        chunk_overlap=150,
        embedding_model="all-MiniLM-L6-v2",
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
    if isinstance(envs, list) and len(envs) > 0:
        merged = {**data}
        active = merged.get("activePostgresEnvironmentId")
        if not active:
            first = envs[0]
            if isinstance(first, dict) and first.get("id"):
                merged["activePostgresEnvironmentId"] = str(first["id"])
            else:
                merged["activePostgresEnvironmentId"] = "default"
        return merged

    defaults = _DEFAULT_SETTINGS.model_dump(by_alias=True)
    merged_flat = {**defaults, **data}
    env = {
        "id": "default",
        "name": str(merged_flat.get("environmentDisplayName") or "Standard"),
        "dbHost": merged_flat.get("dbHost", "localhost"),
        "dbPort": int(merged_flat.get("dbPort", 5432)),
        "dbName": merged_flat.get("dbName", "rag"),
        "dbUser": merged_flat.get("dbUser", "postgres"),
        "dbPassword": merged_flat.get("dbPassword", ""),
        "dbSchema": merged_flat.get("dbSchema", "public"),
        "dbTableName": merged_flat.get("dbTableName", "rag_documents"),
    }
    rest = {
        k: v
        for k, v in merged_flat.items()
        if k not in _LEGACY_DB_KEYS and k != "environmentDisplayName"
    }
    rest["postgresEnvironments"] = [env]
    rest["activePostgresEnvironmentId"] = "default"
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
    settings_path.write_text(
        json.dumps(settings.model_dump(by_alias=True), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return settings


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


def get_source_boosts_path() -> Path:
    """Path to source_boosts.json — lives alongside settings.json."""
    root = _optional_data_root()
    if root is not None:
        return root / "source_boosts.json"
    return _PROJECT_DIR / "source_boosts.json"


def load_source_boosts() -> dict[str, float]:
    """Load fileName-substring → score-multiplier map from source_boosts.json.

    Keys are matched as case-insensitive substrings of chunk fileNames during reranking.
    A multiplier > 1.0 boosts a source; < 1.0 demotes it; 1.0 is a no-op.
    The file is re-read on every call so edits take effect without restarting the service.
    Returns an empty dict (no boosts) if the file is absent or malformed.
    """
    path = get_source_boosts_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        result: dict[str, float] = {}
        for k, v in data.items():
            try:
                result[str(k)] = float(v)
            except (TypeError, ValueError):
                pass  # skip non-numeric entries (e.g. _comment)
        return result
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
