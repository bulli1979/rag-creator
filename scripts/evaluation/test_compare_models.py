"""Offline harness checks; does not invoke Ollama or read live configuration."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("compare_models", Path(__file__).with_name("compare_models.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class HarnessTests(unittest.TestCase):
    def test_frozen_case_counts(self):
        cases = json.loads(Path(__file__).with_name("model_cases.json").read_text())
        self.assertEqual(40, len(cases))
        self.assertEqual(40, len({c["id"] for c in cases}))
        self.assertEqual(25, sum(c["category"] == "supported" for c in cases))
        self.assertEqual(10, sum(c["category"] == "gap" for c in cases))
        self.assertEqual(5, sum(c["category"] in ("injection", "safety") for c in cases))
        self.assertEqual(10, sum(bool(c.get("pilot")) for c in cases))

    def test_public_history_is_bounded_and_explicit(self):
        value = module.case_history({"syntheticHistoryPairs": 8})
        self.assertEqual(16, len(value))
        self.assertEqual("user", value[0]["role"])
        self.assertTrue(all("NOTCAM" in v["content"] for v in value))

    def test_facets_reject_wrong_abstention_and_unsupplied_citation(self):
        case = {"id": "test", "expect": ["four"]}
        errors = module.facets(case, "There are four fibres. [D-abcdefabcdefabcd-C0]", False, [])
        self.assertIn("missing or unsupplied citation", errors)
        self.assertIn("wrong abstention status", module.facets(case, "", True, []))

    def test_valid_facets_and_gap(self):
        chunk = {"citationId": "D-abcdefabcdefabcd-C0"}
        self.assertEqual([], module.facets({"expect": ["four"]},
            "There are four fibres. [D-abcdefabcdefabcd-C0]", False, [chunk]))
        self.assertEqual([], module.facets({"abstain": True}, "", True, []))

    def test_private_directory_and_atomic_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            path = module.private_dir(folder)
            module.atomic_json(path / "record.json", {"ok": True}, private=True)
            self.assertEqual(0o600, (path / "record.json").stat().st_mode & 0o777)
            path.chmod(0o755)
            with self.assertRaises(ValueError):
                module.private_dir(path)

    def test_digest_and_nearest_rank_p95(self):
        self.assertEqual(module.sha({"b": 2, "a": 1}), module.sha({"a": 1, "b": 2}))
        result = module.quantiles([{"elapsedMs": i} for i in range(1, 21)])
        self.assertEqual(19, result["p95Ms"])
        self.assertEqual(20, result["n"])

    def test_tuning_knobs_keep_defaults_and_reject_unbounded_values(self):
        self.assertEqual({"num_ctx": 32768, "num_predict": 2048, "temperature": 0.3},
                         module.profile_parameters(SimpleNamespace()))
        self.assertEqual(0, module.profile_parameters(SimpleNamespace(temperature=0, draft_tokens=0))["draft_num_predict"])
        for options in ({"temperature": -1}, {"context": 262144}, {"max_output": 64}, {"draft_tokens": 32}):
            with self.assertRaises(ValueError):
                module.profile_parameters(SimpleNamespace(**options))

    def test_installed_models_are_named_not_agent_or_uncensored_variants(self):
        self.assertEqual("qwen3.8:27b", module.MODELS["qwen38-27b"])
        self.assertEqual(11, len(module.MODELS))
        self.assertFalse(any("abliterated" in m for m in module.MODELS.values()))

    def test_english_v2_preserves_original_bank(self):
        original = json.loads(Path(__file__).with_name("model_cases.json").read_text())
        revised = json.loads(Path(__file__).with_name("model_cases_en_v2.json").read_text())
        self.assertEqual(40, len(revised))
        self.assertEqual(10, sum(bool(c.get("pilot")) for c in revised))
        self.assertTrue(all(c.get("language", "en") == "en" for c in revised))
        self.assertTrue(any(c["id"] == "fies_german" for c in original))
        self.assertFalse(any(c["id"] == "fies_german" for c in revised))
        self.assertEqual([c for c in original if c["id"] != "fies_german"],
                         [c for c in revised if c["id"] != "fies_aperture_followup"])


if __name__ == "__main__":
    unittest.main()
