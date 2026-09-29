from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "corpus_curate.py"
SPEC = importlib.util.spec_from_file_location("corpus_curate", SCRIPT_PATH)
assert SPEC and SPEC.loader
corpus_curate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(corpus_curate)


def write_doc(root: Path, name: str, url: str, category: str, body: str, instrument: str = "") -> None:
    fields = ["---", f'title: "{name}"', f'source_url: "{url}"', f'category: "{category}"']
    if instrument:
        fields.append(f'instrument: "{instrument}"')
    fields.extend(["---", "", body])
    (root / name).write_text("\n".join(fields), encoding="utf-8")


class CorpusCurateTests(unittest.TestCase):
    def test_policy_manifest_and_shadow_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source"
            source.mkdir()
            useful = "Operational manual with detailed steps and values. " * 8
            write_doc(source, "manual.md", "https://example.test/instruments/a.html", "instrument_documentation", useful + " manual", "ALFOSC")
            write_doc(source, "faults_2020.md", "", "fault_report", useful + " fault")
            write_doc(source, "internal.md", "https://example.test/intranot/engineer/procedures/a.html", "internal_operations", useful + " internal")
            write_doc(source, "news.md", "https://example.test/news/a.html", "news", useful + " news")
            write_doc(source, "damaged.md", "https://example.test/instruments/b.html", "instrument_documentation", useful + " damaged \ufffd")
            write_doc(source, "cid-damaged.md", "https://example.test/instruments/cid.pdf", "instrument_documentation", useful + (" (cid:123)" * 20))
            write_doc(source, "manual-copy.md", "https://example.test/news/manual-copy.html", "news", useful + " manual", "ALFOSC")
            write_doc(source, "empty.md", "https://example.test/instruments/empty.html", "instrument_documentation", "")
            write_doc(source, "navigation.md", "https://example.test/general/index.html", "general_info", "Back to top navigation only")
            write_doc(source, "aladin.md", "https://www.not.iac.es/observing/tools/aladin/aladinAG.php?gp", "observing_guide", useful + " generated")
            write_doc(source, "csc.md", "https://www.not.iac.es/intranot/management/csc_reports/CSCR27/example.pdf", "internal_operations", useful + " meeting report")
            write_doc(source, "filter-canonical.md", "https://www.not.iac.es/instruments/filters/filters.php?ord=name&sel=def", "instrument_documentation", useful + " canonical filter")
            write_doc(source, "filter-variant.md", "https://www.not.iac.es/instruments/filters/filters.php?ord=size&sel=def", "instrument_documentation", useful + " filter variant")

            audit = corpus_curate.corpus_audit.audit_sources(source)
            policy = json.loads((Path(__file__).resolve().parents[2] / "config" / "corpus_policy.v1.json").read_text())
            policy["expectedCorpusSnapshotSha256"] = audit["snapshotSha256"]
            manifest, pairs = corpus_curate.build_manifest(source, policy)
            corpus_curate.validate_manifest(manifest)
            decisions = {item["sourcePath"]: item["disposition"] for item in manifest["documents"]}
            self.assertEqual(decisions["manual.md"], "active")
            self.assertEqual(decisions["faults_2020.md"], "historical")
            self.assertEqual(decisions["internal.md"], "quarantine")
            self.assertEqual(decisions["news.md"], "excluded")
            self.assertEqual(decisions["damaged.md"], "quarantine")
            self.assertEqual(decisions["cid-damaged.md"], "quarantine")
            self.assertEqual(decisions["manual-copy.md"], "excluded")
            copy_entry = next(item for item in manifest["documents"] if item["sourcePath"] == "manual-copy.md")
            self.assertEqual(copy_entry["reasons"], ["exact_duplicate_processed_body"])
            self.assertEqual(decisions["empty.md"], "quarantine")
            self.assertEqual(decisions["navigation.md"], "excluded")
            self.assertEqual(decisions["aladin.md"], "excluded")
            self.assertEqual(decisions["csc.md"], "excluded")
            csc_entry = next(item for item in manifest["documents"] if item["sourcePath"] == "csc.md")
            self.assertEqual(csc_entry["reasons"], ["policy_excluded_path"])
            self.assertEqual(decisions["filter-canonical.md"], "active")
            self.assertEqual(decisions["filter-variant.md"], "excluded")
            self.assertGreaterEqual(len(pairs), 0)

            shadow = base / "shadow"
            corpus_curate.build_shadow(source, shadow, manifest)
            self.assertTrue((shadow / "searchable" / "manual.md").is_file())
            curated_manual = (shadow / "searchable" / "manual.md").read_text(encoding="utf-8")
            self.assertIn('authority: "tier_2_reference"', curated_manual)
            self.assertIn('status: "active"', curated_manual)
            self.assertIn(f'corpus_version: "{policy["corpusVersion"]}"', curated_manual)
            self.assertTrue((shadow / "historical" / "faults_2020.md").is_file())
            self.assertFalse((shadow / "searchable" / "internal.md").exists())
            self.assertFalse((shadow / "searchable" / "news.md").exists())
            self.assertFalse((shadow / "searchable" / "manual-copy.md").exists())
            self.assertFalse((shadow / "searchable" / "csc.md").exists())
            self.assertFalse((shadow / "searchable" / "filter-variant.md").exists())
            validation = corpus_curate.validate_shadow(source, shadow, manifest)
            self.assertEqual(validation["status"], "ok")
            self.assertEqual(validation["quarantineOrExcludedFilesInShadow"], 0)

    def test_near_duplicate_detection(self) -> None:
        common = " ".join(f"token{index}" for index in range(100))
        pairs, clusters = corpus_curate.find_near_duplicates(
            {"a.md": common, "b.md": common + " extra", "c.md": "unrelated words only"},
            threshold=0.8,
            max_distance=12,
        )
        self.assertEqual(len(pairs), 1)
        self.assertEqual(clusters["a.md"], clusters["b.md"])
        self.assertNotIn("c.md", clusters)


if __name__ == "__main__":
    unittest.main()
