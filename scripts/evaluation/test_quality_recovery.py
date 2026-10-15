"""Offline recovery must fail on missing or tampered saved outputs."""
import json
from pathlib import Path
import tempfile
import unittest

from compare_models import sha
from finish_qwen_quality_review import verify_outputs


class QualityRecoveryTests(unittest.TestCase):
    def fixture(self, work):
        entry = {"case": {"id": "case"}, "messages": [], "evidence": []}
        frozen = {"appPythonSha256": "app", "cases": [entry]}
        record = {"raw": "{}", "validatedAnswer": "answer"}
        (work / "outputs").mkdir()
        (work / "outputs/1-case-1.json").write_text(json.dumps(record))
        row = {"id": "case", "pass": 1, "requestError": None,
               "promptSha256": sha([]), "evidenceSha256": sha([]),
               "generationAttempts": 1, "answerSha256": sha(b"answer"),
               "passed": True, "attempts": [{"attempt": 1, "rawOutputSha256": sha(b"{}")}]}
        receipt = {"complete": True, "requestErrors": 0, "frozenSha256": sha(frozen),
                   "appPythonSha256": "app", "rawOutputsRelativeDirectory": "outputs",
                   "results": [row], "passed": 1}
        return receipt, frozen

    def test_complete_saved_output_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt, frozen = self.fixture(Path(directory))
            self.assertEqual(1, verify_outputs(Path(directory), receipt, frozen))

    def test_corrupt_incomplete_or_escaped_receipts_rejected(self):
        for field, value in (("complete", False), ("requestErrors", 1),
                             ("frozenSha256", "wrong"), ("appPythonSha256", "wrong"),
                             ("rawOutputsRelativeDirectory", "../outside"), ("passed", 0)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                receipt, frozen = self.fixture(Path(directory))
                receipt[field] = value
                with self.assertRaises(ValueError):
                    verify_outputs(Path(directory), receipt, frozen)

    def test_missing_or_tampered_answer_raw_and_evidence_rejected(self):
        for change in ("missing", "raw", "answer", "evidence", "attempts"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                receipt, frozen = self.fixture(work)
                path = work / "outputs/1-case-1.json"
                if change == "missing":
                    path.unlink()
                elif change in {"raw", "answer"}:
                    record = json.loads(path.read_text())
                    record["raw" if change == "raw" else "validatedAnswer"] = "tampered"
                    path.write_text(json.dumps(record))
                elif change == "evidence":
                    receipt["results"][0]["evidenceSha256"] = "wrong"
                else:
                    receipt["results"][0]["generationAttempts"] = 2
                with self.assertRaises((ValueError, FileNotFoundError)):
                    verify_outputs(work, receipt, frozen)
