from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "run_rag_eval_from_ground_truth.py"
)
SPEC = importlib.util.spec_from_file_location("run_rag_eval", SCRIPT_PATH)
assert SPEC and SPEC.loader
run_rag_eval = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_rag_eval)


class EvaluationInputTests(unittest.TestCase):
    def test_csv_allows_whitespace_before_quoted_answer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "questions.csv"
            path.write_text(
                'question,ground_truth\nQuestion?, "One, two, and three."\n',
                encoding="utf-8",
            )

            self.assertEqual(
                run_rag_eval.load_ground_truth_pairs(path),
                [("Question?", "One, two, and three.")],
            )


if __name__ == "__main__":
    unittest.main()
