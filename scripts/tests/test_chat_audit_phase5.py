from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "documentApi"))

from app.chat_audit import ChatAudit


class ChatAuditTests(unittest.TestCase):
    def test_private_record_survives_restart_without_plaintext_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "chat_audit"
            audit = ChatAudit(root)
            audit.append({"promptSha256": "abc", "abstained": False}, {"prompt": "private telescope question"})
            records = list(root.glob("chat-*.jsonl"))
            self.assertEqual(len(records), 1)
            raw = records[0].read_text(encoding="utf-8")
            self.assertNotIn("private telescope question", raw)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((root / "audit.key").stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(records[0].stat().st_mode), 0o600)
            restored = ChatAudit(root)
            entry = json.loads(raw)
            self.assertEqual(entry["trace"]["promptSha256"], "abc")
            self.assertEqual(
                restored.crypto.decrypt_json(entry["encryptedPayload"])["prompt"],
                "private telescope question",
            )

    def test_external_key_does_not_write_a_key_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            key = ChatAudit(Path(temp) / "source").crypto.key_b64
            root = Path(temp) / "external"
            audit = ChatAudit(root, key)
            audit.append({"abstained": True}, {"query": "secret"})
            self.assertFalse((root / "audit.key").exists())

    def test_world_readable_existing_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "chat_audit"
            root.mkdir()
            key = root / "audit.key"
            key.write_text(ChatAudit(Path(temp) / "source").crypto.key_b64, encoding="ascii")
            key.chmod(0o644)
            with self.assertRaises(PermissionError):
                ChatAudit(root)


if __name__ == "__main__":
    unittest.main()
