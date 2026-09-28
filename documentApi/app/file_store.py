from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path


def create_sha256(payload: bytes | str) -> str:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def to_safe_file_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9.\-_]", "_", name)


def _upload_display_name(source_path: str) -> str:
    """Dateiname fuer Metadaten: bei relativem Pfad (Ordner-Upload) ganzen Pfad, sonst nur Basename."""
    s = (source_path or "unknown").strip()
    if not s:
        return "unknown"
    if os.path.isabs(s):
        return os.path.basename(s)
    return s.replace("\\", "/")


class FileStore:
    def __init__(self, files_dir: Path, corpus_dir: Path) -> None:
        self._files_dir = files_dir
        self._corpus_dir = corpus_dir

    def get_corpus_path(self, doc_id: str, environment_id: str | None = None) -> str:
        if environment_id:
            env_dir = self._corpus_dir / to_safe_file_name(environment_id)
            env_dir.mkdir(parents=True, exist_ok=True)
            return str(env_dir / f"{doc_id}.jsonl")
        return str(self._corpus_dir / f"{doc_id}.jsonl")

    def write_corpus_jsonl(
        self, doc_id: str, lines: list[str], *, environment_id: str | None = None, corpus_path: str | None = None
    ) -> str:
        path = corpus_path or self.get_corpus_path(doc_id, environment_id)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def write_corpus_markdown(
        self, doc_id: str, markdown: str, *, environment_id: str | None = None
    ) -> str:
        if environment_id:
            env_dir = self._corpus_dir / to_safe_file_name(environment_id)
            env_dir.mkdir(parents=True, exist_ok=True)
            md_path = str(env_dir / f"{doc_id}.md")
        else:
            md_path = str(self._corpus_dir / f"{doc_id}.md")
        Path(md_path).write_text(markdown, encoding="utf-8")
        return md_path

    def copy_to_managed_storage(
        self, source_path: str, file_bytes: bytes | None = None
    ) -> dict:
        if file_bytes is not None:
            content = file_bytes
        else:
            content = Path(source_path).read_bytes()

        file_hash = create_sha256(content)
        doc_id = file_hash
        file_name = _upload_display_name(source_path)
        leaf = file_name.split("/")[-1]
        extension = os.path.splitext(leaf)[1].lower()
        safe_name = to_safe_file_name(leaf)

        dest_dir = self._files_dir / doc_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"original{extension}_{safe_name}"
        dest_path.write_bytes(content)

        return {
            "docId": doc_id,
            "destinationPath": str(dest_path),
            "fileName": file_name,
            "extension": extension.lstrip("."),
            "fileHash": file_hash,
            "sizeBytes": len(content),
        }

    def read_text_file(self, file_path: str) -> str:
        return Path(file_path).read_text(encoding="utf-8")

    def delete_document_artifacts(self, doc_id: str, *, environment_id: str | None = None) -> None:
        if environment_id:
            corpus_path = Path(self.get_corpus_path(doc_id, environment_id))
            md_path = corpus_path.with_suffix(".md")
            corpus_path.unlink(missing_ok=True)
            md_path.unlink(missing_ok=True)
            return
        file_dir = self._files_dir / doc_id
        corpus_path = self._corpus_dir / f"{doc_id}.jsonl"
        md_path = self._corpus_dir / f"{doc_id}.md"
        shutil.rmtree(file_dir, ignore_errors=True)
        corpus_path.unlink(missing_ok=True)
        md_path.unlink(missing_ok=True)
