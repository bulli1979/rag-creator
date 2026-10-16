#!/usr/bin/env python3
"""Backup-first migration, inactive-vector cleanup, and rollback for SQLite stores."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "documentApi"))


def backup_sqlite(source: Path, backup_dir: Path) -> Path:
    source = source.resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{source.name}.{int(time.time())}.bak"
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    return target


def restore_sqlite(backup: Path, target: Path) -> None:
    if not backup.is_file():
        raise FileNotFoundError(f"Backup nicht gefunden: {backup}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(backup) as src, sqlite3.connect(target) as dst:
        src.backup(dst)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    migrate = commands.add_parser("migrate", help="Back up and migrate SQLite lifecycle columns")
    migrate.add_argument("--vector-db", required=True, type=Path)
    migrate.add_argument("--table", default="rag_documents")
    migrate.add_argument("--index-db", type=Path)
    migrate.add_argument("--backup-dir", required=True, type=Path)
    migrate.add_argument("--cleanup-inactive", action="store_true")
    rollback = commands.add_parser("rollback", help="Restore one SQLite database from a backup")
    rollback.add_argument("--backup", required=True, type=Path)
    rollback.add_argument("--target", required=True, type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "rollback":
        restore_sqlite(args.backup, args.target)
        print(json.dumps({"status": "restored", "backup": str(args.backup), "target": str(args.target)}))
        return 0

    from app.database import IndexDatabase
    from app.vector_store.sqlite_embedded import SqliteEmbeddedVectorStore

    backups: dict[str, str] = {}
    if args.vector_db.exists():
        backups["vector"] = str(backup_sqlite(args.vector_db, args.backup_dir))
    if args.index_db and args.index_db.exists():
        backups["index"] = str(backup_sqlite(args.index_db, args.backup_dir))
        IndexDatabase(args.index_db)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.table):
        raise ValueError(f"Invalid table name: {args.table}")
    store = SqliteEmbeddedVectorStore(args.vector_db)
    store.ensure_schema(args.table)
    removed = store.cleanup_inactive_versions(args.table) if args.cleanup_inactive else 0
    with sqlite3.connect(args.vector_db) as conn:
        inactive = int(conn.execute(
            f'SELECT count(*) FROM "{args.table}" WHERE is_active = 0'
        ).fetchone()[0])
    print(json.dumps({
        "status": "migrated", "backups": backups, "inactiveRemaining": inactive,
        "inactiveRemoved": removed, "cleanupApplied": bool(args.cleanup_inactive),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
