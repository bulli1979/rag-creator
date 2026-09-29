from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "documentApi"))

from app.evidence_selection import _rerank_chunks, classify_query, select_evidence


def chunk(source: str, text: str, similarity: float, **metadata: str) -> dict:
    return {
        "documentId": source,
        "sourceId": source,
        "fileName": f"{source}.md",
        "chunkIndex": 0,
        "text": text,
        "similarity": similarity,
        "instrument": metadata.get("instrument", ""),
        "authority": metadata.get("authority", "tier_2_reference"),
        "status": metadata.get("status", "active"),
        "category": metadata.get("category", "instrument_documentation"),
    }


class RetrievalBaselineTests(unittest.TestCase):
    """Freeze known baseline behavior before the Phase 4 selector changes it."""

    def test_baseline_can_fill_context_with_one_source_and_duplicates(self) -> None:
        candidates = [
            {**chunk("alfosc", "ALFOSC slit setup procedure", 0.9), "chunkIndex": i}
            for i in range(3)
        ]
        selected = _rerank_chunks("ALFOSC slit setup", candidates, 3)
        self.assertEqual([item["chunkIndex"] for item in selected], [0, 1, 2])

    def test_baseline_does_not_prefer_current_over_historical(self) -> None:
        candidates = [
            chunk("old", "ALFOSC startup procedure", 0.9, status="historical"),
            chunk("current", "ALFOSC startup procedure", 0.8, status="active"),
        ]
        selected = _rerank_chunks("ALFOSC startup procedure", candidates, 2)
        self.assertEqual([item["documentId"] for item in selected], ["old", "current"])


class EvidenceSelectionTests(unittest.TestCase):
    def test_exact_and_near_duplicates_are_removed_and_source_cap_applies(self) -> None:
        long_text = " ".join(f"step{i}" for i in range(25))
        candidates = [
            {**chunk("manual", long_text, 0.95), "chunkIndex": 0},
            {**chunk("mirror", long_text, 0.94), "chunkIndex": 0},
            {**chunk("mirror2", long_text + ".", 0.93), "chunkIndex": 0},
            {**chunk("manual", "ALFOSC setup details", 0.92), "chunkIndex": 1},
            {**chunk("manual", "ALFOSC calibration details", 0.91), "chunkIndex": 2},
            chunk("guide", "ALFOSC setup checklist", 0.90),
        ]
        selected = select_evidence("ALFOSC setup", candidates, 5)
        self.assertEqual(len(selected), 4)
        self.assertEqual(sum(item["documentId"] == "manual" for item in selected), 2)
        self.assertEqual(sum("step0" in item["text"] for item in selected), 1)
        self.assertIn("guide", {item["documentId"] for item in selected})
        self.assertTrue(all("retrievalScore" in item for item in selected))

    def test_near_duplicate_keeps_changed_technical_values(self) -> None:
        common = " ".join(f"step{i}" for i in range(24))
        candidates = [
            chunk("limit5", common + " pressure 5 mbar", 0.91),
            chunk("limit6", common + " pressure 6 mbar", 0.90),
        ]
        selected = select_evidence("pressure limit", candidates, 2)
        self.assertEqual({item["documentId"] for item in selected}, {"limit5", "limit6"})

    def test_case_sensitive_commands_are_not_collapsed(self) -> None:
        common = " ".join(f"instruction{i}" for i in range(22))
        candidates = [
            chunk("upper", common + " run START", 0.90),
            chunk("lower", common + " run start", 0.89),
        ]
        selected = select_evidence("run command", candidates, 2)
        self.assertEqual(len(selected), 2)

    def test_instrument_distractors_are_removed_when_matching_evidence_exists(self) -> None:
        candidates = [
            chunk("notcam", "NOTCAM filter wheel", 0.95, instrument="NOTCAM"),
            chunk("alfosc", "ALFOSC filter wheel", 0.70, instrument="ALFOSC"),
            chunk("general", "Filter wheel maintenance", 0.65),
        ]
        selected = select_evidence("ALFOSC filter wheel", candidates, 3)
        self.assertEqual([item["documentId"] for item in selected], ["alfosc", "general"])
        self.assertEqual(classify_query("Historical ALFOSC safety procedure").categories,
                         frozenset({"safety", "procedure"}))

    def test_current_guidance_precedes_history_unless_history_is_requested(self) -> None:
        candidates = [
            chunk("old", "ALFOSC old startup process", 0.90, status="historical"),
            chunk("current", "ALFOSC current startup process", 0.82, status="active", authority="tier_1_authoritative"),
        ]
        current = select_evidence("ALFOSC startup process", candidates, 2)
        historical = select_evidence("historical ALFOSC startup process", candidates, 2)
        self.assertEqual(current[0]["documentId"], "current")
        self.assertEqual(historical[0]["documentId"], "old")


    def test_low_similarity_corpus_gap_has_no_evidence(self) -> None:
        candidates = [
            chunk("unrelated1", "The NOT telescope has an ALFOSC filter wheel", 0.39),
            chunk("unrelated2", "Mars rover data is not covered here", 0.33),
        ]
        self.assertEqual(select_evidence("NOT quantum teleporter", candidates, 5, min_similarity=0.43), [])
        supported = select_evidence(
            "ALFOSC filter wheel", [chunk("manual", "ALFOSC filter wheel", 0.62)],
            5, min_similarity=0.43,
        )
        self.assertEqual([item["documentId"] for item in supported], ["manual"])


if __name__ == "__main__":
    unittest.main()
