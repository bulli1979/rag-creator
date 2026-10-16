from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "corpus_audit.py"
SPEC = importlib.util.spec_from_file_location("corpus_audit", SCRIPT_PATH)
assert SPEC and SPEC.loader
corpus_audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(corpus_audit)


class CorpusAuditTests(unittest.TestCase):
    def test_source_audit_is_deterministic_and_flags_noise(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            common = """---
title: "Current manual"
source_url: "https://example.test/manual?view=full"
category: "instrument_documentation"
instrument: "ALFOSC"
source_hash: "stable-source"
---

# Procedure

Back to top. Last modified yesterday. [phone removed]
"""
            (root / "manual.md").write_text(common, encoding="utf-8")
            (root / "manual-copy.md").write_text(common, encoding="utf-8")
            (root / "empty.md").write_text(
                "---\ntitle: Empty\n---\n", encoding="utf-8"
            )

            first = corpus_audit.audit_sources(root)
            second = corpus_audit.audit_sources(root)

            self.assertEqual(first, second)
            self.assertEqual(first["fileCount"], 3)
            self.assertEqual(first["exactFileDuplicates"]["groups"], 1)
            self.assertEqual(first["normalizedBodyDuplicates"]["groups"], 1)
            self.assertEqual(first["canonicalUrlsWithMultipleFiles"]["groups"], 1)
            self.assertEqual(first["queryParameterSourceCount"], 2)
            self.assertEqual(first["phoneRemovedOccurrences"], 2)
            self.assertEqual(first["boilerplate"]["backToTop"]["fileCount"], 2)
            self.assertEqual(first["emptyBodyFileCount"], 1)
            self.assertEqual(
                first["sourceTypeCounts"],
                {"dynamic_web": 2, "web_or_generated_markdown": 1},
            )

    def test_source_audit_flags_pdf_cid_damage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "damaged.md").write_text("---\ntitle: Damaged\n---\n" + "(cid:123)" * 20, encoding="utf-8")
            result = corpus_audit.audit_sources(root)
            self.assertEqual(result["strongEncodingDamageFlags"]["cidArtifactFileCount"], 1)
            self.assertIn("cid_artifact", result["files"][0]["qualityFlags"])

    def test_sqlite_audit_reports_versions_status_and_tags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "index.sqlite"
            connection = sqlite3.connect(database)
            connection.execute(
                """
                CREATE TABLE documents (
                    docId TEXT, environmentId TEXT, fileName TEXT, chunkCount INTEGER,
                    status TEXT, tags TEXT
                )
                """
            )
            connection.executemany(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("v1", "default", "manual.md", 2, "done", '["scrubbed"]'),
                    ("v2", "default", "manual.md", 3, "done", '["scrubbed"]'),
                    ("other", "default", "other.md", 1, "error", "[]"),
                ],
            )
            connection.commit()
            connection.close()

            result = corpus_audit.audit_metadata_sqlite(database)

            self.assertEqual(result["documentCount"], 3)
            self.assertEqual(result["distinctFileNames"], 2)
            self.assertEqual(result["filenamesWithMultipleDocumentIds"], 1)
            self.assertEqual(result["maximumDocumentIdsPerFilename"], 2)
            self.assertEqual(result["declaredChunkCount"], 6)
            self.assertEqual(result["statusCounts"], {"done": 2, "error": 1})
            self.assertEqual(result["tagCounts"], {"scrubbed": 2})

    def test_frontmatter_and_url_canonicalization(self) -> None:
        metadata, body = corpus_audit.parse_frontmatter(
            '---\ntitle: "A title"\nsource_url: "https://EXAMPLE.test/a/?b=2&a=1#x"\n---\nBody\n'
        )
        self.assertEqual(metadata["title"], "A title")
        self.assertEqual(body, "Body\n")
        self.assertEqual(
            corpus_audit.canonicalize_url(metadata["source_url"]),
            "https://example.test/a?a=1&b=2",
        )


if __name__ == "__main__":
    unittest.main()
