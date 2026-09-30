from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "documentApi"))

from app.chat_service import ChatService
from app.crypto_service import CryptoService
from app.models import ChatRequest, ChatSettings


class ChatCorrectionTests(unittest.IsolatedAsyncioTestCase):
    async def run_chat(self, outputs: list[str], message="what is NOTCAM?", history=None):
        source = "NOTCam is a short-wave infrared instrument covering 0.8 to 2.5µm."
        vs = MagicMock()
        vs.similarity_search.return_value = [{
            "documentId": "a" * 64, "chunkIndex": 0,
            "fileName": "instruments-notcam-overview-html.md", "text": source,
            "instrument": "NOTCAM", "status": "active", "authority": "tier_2_reference",
            "similarity": 0.7, "corpusVersion": "test-corpus",
        }]
        vs.search_by_filename.return_value = []
        completions = [SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=raw))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        ) for raw in outputs]
        worker = AsyncMock(side_effect=[{"ok": True, "vectors": [[0.1, 0.2]]}, *completions])
        crypto = CryptoService()
        with patch("app.chat_service.load_chat_settings", return_value=ChatSettings()), \
                patch("app.chat_service.load_source_boosts", return_value={}), \
                patch("app.chat_service.OpenAI"), \
                patch("app.chat_service.run_in_worker_pool", worker):
            service = ChatService(vs, crypto)
            response = await service.chat(ChatRequest(message=message, language="en", history=history or []))
        return response, worker, crypto

    @staticmethod
    def output(unit: str) -> str:
        return json.dumps({"claims": [{
            "text": f"NOTCam is a short-wave infrared instrument covering 0.8 to 2.5{unit}.",
            "evidence": [{"citationId": "D-aaaaaaaaaaaaaaaa-C0", "quote":
                          "NOTCam is a short-wave infrared instrument covering 0.8 to 2.5µm."}],
        }]})

    async def test_rejected_claim_is_corrected_once_and_audited(self) -> None:
        outputs = [self.output("mm"), self.output("μm")]
        response, worker, crypto = await self.run_chat(outputs)
        self.assertFalse(response.metrics["abstained"])
        self.assertEqual(response.trace["generationAttempts"], 2)
        self.assertEqual(response.trace["initialRejectedClaims"], 1)
        self.assertEqual(response.trace["acceptedClaims"], 1)
        self.assertEqual(response.metrics["totalTokens"], 60)
        self.assertEqual(worker.await_count, 3)
        self.assertEqual(crypto.decrypt_json(response.encrypted_payload)["modelOutputs"], outputs)

    async def test_followup_embeds_resolved_subject_and_checks_range(self) -> None:
        history = [{"role": "user", "content": "what is NOTCAM?"},
                   {"role": "assistant", "content": "NOTCam is an infrared instrument."}]
        response, worker, crypto = await self.run_chat(
            [], "can the instrument be used to observer at 500nm?", history)
        self.assertFalse(response.metrics["abstained"])
        self.assertTrue(response.answer.startswith("No. 500nm (= 0.5 µm)"))
        self.assertEqual(worker.await_count, 1)
        self.assertEqual(worker.await_args_list[0].args[2], ["can NOTCAM be used to observer at 500nm?"])
        self.assertEqual(response.trace["contextResolution"], "inherited")
        self.assertEqual(response.trace["generationAttempts"], 0)
        private = crypto.decrypt_json(response.encrypted_payload)
        self.assertEqual(private["derivation"]["relation"], "below")
        self.assertEqual(private["query"], "can the instrument be used to observer at 500nm?")

    async def test_ambiguous_followup_clarifies_without_retrieving(self) -> None:
        response, worker, _ = await self.run_chat(
            [], "Can it observe at 500nm?", [{"role": "user", "content": "Compare NOTCAM and ALFOSC"}])
        self.assertTrue(response.metrics["abstained"])
        self.assertIn("Which instrument", response.answer)
        self.assertEqual(worker.await_count, 0)

    async def test_range_followup_does_not_depend_on_model_wording(self) -> None:
        response, worker, _ = await self.run_chat(
            [], "Which wavelength range does it cover?", [{"role": "user", "content": "What is NOTCAM?"}])
        self.assertFalse(response.metrics["abstained"])
        self.assertIn("0.8–2.5 µm", response.answer)
        self.assertEqual(worker.await_count, 1)
        self.assertEqual(response.trace["generationAttempts"], 0)

    async def test_resolved_followup_is_also_used_for_model_prompt(self) -> None:
        response, worker, crypto = await self.run_chat(
            [self.output("µm")], "Tell me about its wavelength range.",
            [{"role": "user", "content": "What is NOTCAM?"}])
        self.assertFalse(response.metrics["abstained"])
        self.assertEqual(worker.await_count, 2)
        messages = crypto.decrypt_json(response.encrypted_payload)["messages"]
        self.assertIn("resolves to NOTCAM", messages[0]["content"])
        self.assertIn("its wavelength range", messages[-1]["content"])

    async def test_deliberate_empty_claims_does_not_retry(self) -> None:
        response, worker, _ = await self.run_chat(['{"claims":[]}'])
        self.assertTrue(response.metrics["abstained"])
        self.assertEqual(response.trace["generationAttempts"], 1)
        self.assertEqual(worker.await_count, 2)

    async def test_failed_correction_still_abstains_and_stops(self) -> None:
        response, worker, _ = await self.run_chat([self.output("mm"), self.output("mm")])
        self.assertTrue(response.metrics["abstained"])
        self.assertEqual(response.trace["generationAttempts"], 2)
        self.assertEqual(response.trace["acceptedClaims"], 0)
        self.assertEqual(worker.await_count, 3)


if __name__ == "__main__":
    unittest.main()
