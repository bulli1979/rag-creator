"""Private, restart-safe encrypted audit records for chat requests.

The key and records live in the API data volume, never in the repository or the
public API trace. Operators may supply NOTBOT_AUDIT_KEY instead of a local key.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from .crypto_service import CryptoService


class ChatAudit:
    def __init__(self, root: Path, key: str | None = None) -> None:
        self.root = root
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Audit root must be a real directory")
        os.chmod(root, 0o700)
        self.crypto = CryptoService(key or self._load_or_create_key())

    def _load_or_create_key(self) -> str:
        path = self.root / "audit.key"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            pass
        else:
            try:
                value = CryptoService.generate_key()
                os.write(fd, value.encode("ascii"))
                os.fsync(fd)
            finally:
                os.close(fd)
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise PermissionError("Audit key must be a private regular file")
        if not path.is_file():
            raise ValueError("Audit key must be a regular file")
        return path.read_text(encoding="ascii").strip()

    def append(self, trace: dict, private: dict) -> None:
        """Append one encrypted payload plus non-sensitive telemetry."""
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self.root / f"chat-{day}.jsonl"
        record = {
            "at": datetime.now(timezone.utc).isoformat(),
            "trace": trace,
            "encryptedPayload": self.crypto.encrypt_json(private),
        }
        data = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            info = os.fstat(fd)
            if stat.S_IMODE(info.st_mode) & 0o077 or not stat.S_ISREG(info.st_mode):
                raise PermissionError("Audit records must be private regular files")
            if os.write(fd, data) != len(data):
                raise OSError("Incomplete chat audit write")
            os.fsync(fd)
        finally:
            os.close(fd)
