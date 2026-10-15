"""English screening integrity checks without inference or private data."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_english_models as driver
from compare_models import sha
from review_english_facets import text_errors


class EnglishSummaryTests(unittest.TestCase):
    def test_citation_identifier_is_not_a_numeric_fact(self):
        self.assertTrue(text_errors({"expect": ["four|4"]}, "There are six fibres. [D-abcdef4abcdefabcd-C0]"))
        self.assertEqual([], text_errors({"expect": ["four|4"]}, "There are four science fibres. [D-abcdef4abcdefabcd-C0]"))

    def test_procedure_count_is_not_citation_chunk_number(self):
        self.assertTrue(text_errors({"expect": ["N.*3|3.*N"]}, "NOTCAM uses dark frames. [D-abcdefabcdefabcd-C3]"))
        self.assertEqual([], text_errors({"expect": ["N.*3|3.*N"]}, "Take at least three dark frames."))

    def test_notcam_name_is_not_a_negative_answer(self):
        case = {"expect": ["no|cannot|can't|below|outside"]}
        self.assertTrue(text_errors(case, "NOTCAM covers 0.8 to 2.5 micrometres."))
        self.assertEqual([], text_errors(case, "No. That wavelength is below NOTCAM's range."))

    def fixture(self, folder):
        cases_path = driver.ROOT / "scripts/evaluation/model_cases_en_v2.json"
        ids = [c["id"] for c in json.loads(cases_path.read_text()) if c.get("pilot")]
        capture = {"casesSha256": sha(cases_path.read_bytes()), "frozenSha256": "evidence-pin", "appPythonSha256": "app-pin"}
        (folder / "frozen-capture.json").write_text(json.dumps(capture))
        stage = folder / "pilot"
        stage.mkdir()
        rows = [{"id": i, "pass": r, "category": "supported", "passed": True, "abstained": False,
                 "generationAttempts": 1, "elapsedMs": 1000, "errors": []} for r in (1, 2) for i in ids]
        report = {**capture, "harnessSha256": "harness-pin", "caseIds": ids, "repeats": 2,
            "complete": True, "results": rows, "requestErrors": 0, "baseManifestDigest": "model-pin",
            "noReasoningOutputObserved": True, "context": 32768}
        (stage / "pilot-control.json").write_text(json.dumps(report))
        return stage, report

    def test_complete_matching_bank(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage, _ = self.fixture(root)
            with patch.object(driver, "REPORTS", root):
                result = driver.summarize(stage, ["control"], "pilot")
            self.assertTrue(result["allComplete"])
            self.assertEqual(20, result["models"][0]["responses"])
            self.assertIsNone(result["approvedWinner"])

    def test_duplicate_response_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage, report = self.fixture(root)
            report["results"][1] = report["results"][0]
            (stage / "pilot-control.json").write_text(json.dumps(report))
            with patch.object(driver, "REPORTS", root), self.assertRaises(ValueError):
                driver.summarize(stage, ["control"], "pilot")

    def test_missing_model_is_not_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage, _ = self.fixture(root)
            with patch.object(driver, "REPORTS", root):
                result = driver.summarize(stage, ["control", "ministral3-8b"], "pilot")
            self.assertFalse(result["allComplete"])


if __name__ == "__main__":
    unittest.main()
