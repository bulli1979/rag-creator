from __future__ import annotations

import re
from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .file_store import create_sha256

_FRONTMATTER_URL_RE = re.compile(
    r"(?im)^\s*(?:source_url|canonical_url|canonicalUrl|url)\s*:\s*[\"']?([^\n\r\"']+)"
)
_FRONTMATTER_CORPUS_VERSION_RE = re.compile(
    r"(?im)^\s*(?:corpus_version|corpusVersion)\s*:\s*[\"']?([^\n\r\"']+)"
)


def canonicalize_location(value: str) -> str:
    raw = (value or "").strip().replace("\\", "/")
    if raw.lower().startswith(("http://", "https://")):
        parts = urlsplit(raw)
        path = re.sub(r"/+", "/", parts.path or "/")
        query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))
    return str(PurePosixPath(raw)).lstrip("./").lower()


def resolve_source_identity(
    *, environment_id: str, file_name: str, content: bytes, source: str
) -> tuple[str, str]:
    """Return a stable source ID and its inspectable canonical location."""
    text = content[:131072].decode("utf-8", errors="ignore")
    match = _FRONTMATTER_URL_RE.search(text)
    explicit = match.group(1).strip() if match else ""
    canonical = canonicalize_location(explicit)
    if not canonical:
        namespace = canonicalize_location(source) or "local"
        canonical = f"{namespace}:{canonicalize_location(file_name)}"
    return create_sha256(f"{environment_id}\n{canonical}"), canonical


def resolve_corpus_version(content: bytes, requested: str = "") -> str:
    if requested.strip():
        return requested.strip()
    text = content[:131072].decode("utf-8", errors="ignore")
    match = _FRONTMATTER_CORPUS_VERSION_RE.search(text)
    return match.group(1).strip() if match else ""


def create_document_version_id(source_id: str, content_hash: str) -> str:
    return create_sha256(f"{source_id}\n{content_hash}")
