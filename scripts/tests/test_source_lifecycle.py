from __future__ import annotations

import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "documentApi"))

try:
    import psycopg2  # noqa: F401
except ImportError:
    pg = types.ModuleType("psycopg2")
    pool = types.ModuleType("psycopg2.pool")
    extras = types.ModuleType("psycopg2.extras")
    pool.SimpleConnectionPool = object
    extras.execute_batch = lambda *args, **kwargs: None
    pg.pool = pool
    sys.modules.update({"psycopg2": pg, "psycopg2.pool": pool, "psycopg2.extras": extras})

from app.database import IndexDatabase
from app.models import DocumentStatus
from app.source_identity import create_document_version_id, resolve_source_identity
from app.vector_store.sqlite_embedded import SqliteEmbeddedVectorStore
from scripts.source_lifecycle_admin import backup_sqlite, restore_sqlite


def payload(source_id: str, doc_id: str, version: int, text: str) -> dict:
    return {
        "documentId": doc_id, "chunkIndex": 0, "sourcePath": "/tmp/source.md",
        "sourceModifiedUnixSeconds": 1, "text": text, "tags": [], "source": "test",
        "fileName": "same.md", "sourceId": source_id, "contentHash": doc_id,
        "version": version, "canonicalLocation": f"https://example.test/{source_id}",
        "corpusVersion": "test-v1",
    }


class SourceIdentityTests(unittest.TestCase):
    def test_same_filename_different_canonical_sources_are_distinct(self) -> None:
        a, _ = resolve_source_identity(
            environment_id="test", file_name="same.md",
            content=b"---\nsource_url: https://a.example/manual\n---\ntext", source="web",
        )
        b, _ = resolve_source_identity(
            environment_id="test", file_name="same.md",
            content=b"---\nsource_url: https://b.example/manual\n---\ntext", source="web",
        )
        self.assertNotEqual(a, b)
        self.assertNotEqual(create_document_version_id(a, "hash"), create_document_version_id(b, "hash"))


class LifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / "vectors.sqlite"
        self.store = SqliteEmbeddedVectorStore(self.path)
        self.store.ensure_schema("docs")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_latest_only_and_idempotent_reingestion(self) -> None:
        self.store.replace_source_chunks(
            "docs", "source", "v1", [[1.0, 0.0]], [payload("source", "v1", 1, "old")]
        )
        self.store.replace_source_chunks(
            "docs", "source", "v2", [[1.0, 0.0]], [payload("source", "v2", 2, "new")]
        )
        self.assertEqual(self.store.similarity_search("docs", [1.0, 0.0])[0]["documentId"], "v2")
        self.store.replace_source_chunks(
            "docs", "source", "v2", [[1.0, 0.0]], [payload("source", "v2", 2, "new")]
        )
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM docs").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT count(*) FROM docs WHERE is_active = 1").fetchone()[0], 1)

    def test_structural_metadata_round_trip(self) -> None:
        item = payload("source", "v1", 1, "procedure")
        item.update({
            "category": "procedure", "instrument": "ALFOSC", "authority": "tier_1_official",
            "documentStatus": "active", "section": "Startup",
            "headingPath": ["Manual", "Startup"], "parentSection": "Manual",
            "previousSection": "Safety", "nextSection": "Shutdown",
            "contentTypes": ["warning", "list"],
        })
        self.store.replace_source_chunks("docs", "source", "v1", [[1.0, 0.0]], [item])
        result = self.store.similarity_search("docs", [1.0, 0.0])[0]
        self.assertEqual(result["instrument"], "ALFOSC")
        self.assertEqual(result["authority"], "tier_1_official")
        self.assertEqual(result["headingPath"], ["Manual", "Startup"])
        self.assertEqual(result["contentTypes"], ["warning", "list"])
        self.assertEqual(result["previousSection"], "Safety")
        self.assertEqual(result["nextSection"], "Shutdown")

    def test_failed_replacement_leaves_v1_active(self) -> None:
        self.store.replace_source_chunks(
            "docs", "source", "v1", [[1.0, 0.0]], [payload("source", "v1", 1, "old")]
        )
        with sqlite3.connect(self.path) as conn:
            conn.execute("""CREATE TRIGGER reject_v2 BEFORE INSERT ON docs
                WHEN NEW.document_id = 'v2-fail'
                BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.replace_source_chunks(
                "docs", "source", "v2-fail", [[1.0, 0.0]],
                [payload("source", "v2-fail", 2, "broken")],
            )
        self.assertEqual(self.store.similarity_search("docs", [1.0, 0.0])[0]["documentId"], "v1")

    def test_backup_and_rollback_restore_pre_migration_database(self) -> None:
        legacy = self.root / "legacy.sqlite"
        with sqlite3.connect(legacy) as conn:
            conn.execute("CREATE TABLE legacy (value TEXT)")
            conn.execute("INSERT INTO legacy VALUES ('before')")
        backup = backup_sqlite(legacy, self.root / "backups")
        with sqlite3.connect(legacy) as conn:
            conn.execute("UPDATE legacy SET value = 'after'")
        restore_sqlite(backup, legacy)
        with sqlite3.connect(legacy) as conn:
            self.assertEqual(conn.execute("SELECT value FROM legacy").fetchone()[0], "before")

    def test_metadata_activation_is_latest_only(self) -> None:
        db = IndexDatabase(self.root / "index.sqlite")
        for version, doc_id in ((1, "v1"), (2, "v2")):
            db.upsert_document(
                environment_id="test", doc_id=doc_id, file_name="same.md", file_path=f"/{doc_id}",
                file_hash=doc_id, file_type="md", status=DocumentStatus.queued, tags=[], source="test",
                corpus_path=f"/{doc_id}.jsonl", size_bytes=1, source_id="source",
                content_hash=doc_id, version=version, is_active=False,
                canonical_location="https://example.test/source", corpus_version="test-v1",
            )
            db.set_document_index_result(doc_id, 1)
        self.assertFalse(db.get_document("v1", "test").is_active)
        self.assertTrue(db.get_document("v2", "test").is_active)


if __name__ == "__main__":
    unittest.main()
