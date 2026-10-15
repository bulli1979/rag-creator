"""Offline Qwen profile inspection and tuning receipt integrity checks."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import inspect_qwen_profiles as inspection
import run_qwen_chat_tuning as tuning
import review_qwen_rejections as rejection_review
import review_qwen_procedure_scope as procedure_review
from compare_models import atomic_json, sha


class QwenTuningTests(unittest.TestCase):
    def test_inspection_omits_prompt_and_non_numeric_options(self):
        text = 'temperature 1\nnum_ctx 262144\ntop_p 0.95\nsystem private-text\nstop "private-text"\napi_key 12345\n'
        self.assertEqual({"temperature": 1, "num_ctx": 262144, "top_p": 0.95}, inspection.safe_options(text))

    def receipt(self):
        return {"explicitProfileParameters": {"num_ctx": 32768, "num_predict": 2048, "temperature": .3, "draft_num_predict": 4},
            "baseManifestDigest": tuning.PINS["qwen38-27b"], "casesSha256": "cases", "frozenSha256": "frozen",
            "appPythonSha256": "app", "harnessSha256": "harness", "caseIds": ["case"], "repeats": 1,
            "complete": True, "requestErrors": 0, "noReasoningOutputObserved": True, "profile": "test",
            "profileManifestDigest": "profile", "results": [{"id": "case", "pass": 1, "category": "supported",
            "passed": False, "abstained": True, "generationAttempts": 1, "elapsedMs": 10, "errors": ["refused"]}]}

    def test_false_refusal_stays_failed_and_missing_variant_incomplete(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tuning, "REPORTS", Path(directory)):
            atomic_json(Path(directory) / "t03.json", self.receipt())
            result = tuning.summarize(["t03", "t01"])
            self.assertFalse(result["allComplete"])
            self.assertEqual(0, result["models"][0]["passed"])
            self.assertEqual(1, result["models"][0]["falseRefusals"])
            self.assertFalse(result["qualityApproved"])

    def test_duplicate_or_wrong_parameter_receipts_rejected(self):
        for mutation in ("duplicate", "temperature", "weights"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory, patch.object(tuning, "REPORTS", Path(directory)):
                receipt = self.receipt()
                if mutation == "duplicate":
                    receipt["results"] *= 2
                elif mutation == "temperature":
                    receipt["explicitProfileParameters"]["temperature"] = 1
                else:
                    receipt["baseManifestDigest"] = "different"
                atomic_json(Path(directory) / "t03.json", receipt)
                with self.assertRaises(ValueError):
                    tuning.summarize(["t03"])

    def full_receipt(self):
        receipt = self.receipt()
        bank = tuning.ROOT / "scripts/evaluation/model_cases_en_v2.json"
        cases = json.loads(bank.read_text())
        receipt.update({"caseIds": [c["id"] for c in cases], "repeats": 3, "casesSha256": sha(bank.read_bytes()),
            "results": [{"id": c["id"], "pass": r, "category": c["category"], "passed": True, "abstained": False,
            "generationAttempts": 1, "elapsedMs": 10, "errors": []} for r in (1,2,3) for c in cases]})
        return receipt

    def test_full_quality_requires_the_unchanged_bank_three_times(self):
        for mutation in (None, "missing_case", "two_repeats"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory, patch.object(tuning, "REPORTS", Path(directory)):
                receipt = self.full_receipt()
                if mutation == "missing_case":
                    receipt["caseIds"] = receipt["caseIds"][:-1]
                elif mutation == "two_repeats":
                    receipt["repeats"] = 2
                atomic_json(Path(directory)/"t03.json", receipt)
                if mutation:
                    with self.assertRaises(ValueError):
                        tuning.summarize(["t03"], full=True)
                else:
                    result = tuning.summarize(["t03"], full=True)
                    self.assertTrue(result["allComplete"])
                    self.assertEqual(120, result["models"][0]["responses"])
                    self.assertFalse(result["qualityApproved"])

    def test_full_rejection_review_rejects_partial_or_duplicate_receipts(self):
        receipt = self.full_receipt()
        rejection_review.validate_receipt(receipt, full=True)
        for mutation in ("missing", "duplicate", "wrong_bank"):
            with self.subTest(mutation=mutation):
                changed = self.full_receipt()
                if mutation == "missing":
                    changed["results"].pop()
                elif mutation == "duplicate":
                    changed["results"].append(changed["results"][0])
                else:
                    changed["casesSha256"] = "wrong"
                with self.assertRaises(ValueError):
                    rejection_review.validate_receipt(changed, full=True)

    def test_empty_review_fails_before_model_or_private_data_access(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = ["review", "--private", directory, "--receipts", directory,
                    "--output", str(Path(directory)/"unused.json")]
            for module in (rejection_review, procedure_review):
                with self.subTest(module=module.__name__), patch("sys.argv", argv), patch.object(module, "app_modules") as model_access:
                    with self.assertRaises(ValueError):
                        module.main()
                    model_access.assert_not_called()


if __name__ == "__main__":
    unittest.main()
