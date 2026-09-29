from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_FRONTMATTER_BOUNDARY = re.compile(r"^---\s*$")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+] |\d+[.)] )")
_FENCE = re.compile(r"^\s*(```|~~~)")
_EMAIL = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+\b")
_PHONE_CANDIDATE = re.compile(
    r"(?<![\w.])(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}(?![\w.])"
)
_CONTACT_CONTEXT = re.compile(
    r"(?:tel(?:ephone)?|phone|mobile|cell|fax|contact|call|ring|whatsapp)\s*[:.]?\s*$",
    re.IGNORECASE,
)
_ROLE_EMAILS = {
    "astro@not.iac.es", "serviceobs@not.iac.es", "notayuda@not.iac.es",
    "helpdesk@not.iac.es", "notcam@not.iac.es", "alfosc@not.iac.es",
    "fies@not.iac.es", "webmaster@not.iac.es",
}
_NAV_LINK = re.compile(
    r"\[(?:back to top|top|home|previous|next|contents?|contact|instruments?)\]\([^)]*\)",
    re.IGNORECASE,
)
_LAST_MODIFIED = re.compile(
    r"(?:\|\s*)?last\s+modified\s*:\s*[^|\n]*(?:\s*\|)?", re.IGNORECASE
)
_STANDALONE_BRAND = re.compile(r"^\s*(?:#+\s*)?Nordic Optical Telescope\s*$", re.IGNORECASE)


@dataclass
class MarkdownBlock:
    text: str
    heading_path: list[str]
    kind: str


@dataclass
class StructuredChunk:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines()
    if not lines or not _FRONTMATTER_BOUNDARY.match(lines[0]):
        return {}, normalized
    end = next((i for i in range(1, len(lines)) if _FRONTMATTER_BOUNDARY.match(lines[i])), None)
    if end is None:
        return {}, normalized
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, "\n".join(lines[end + 1 :]).strip()


def scrub_sensitive_text(text: str) -> str:
    """Redact contact data without treating arbitrary technical numbers as phones."""
    def email_sub(match: re.Match[str]) -> str:
        address = match.group(0)
        return address if address.lower() in _ROLE_EMAILS else "[email removed]"

    text = _EMAIL.sub(email_sub, text)

    def phone_sub(match: re.Match[str]) -> str:
        value = match.group(0)
        digits = re.sub(r"\D", "", value)
        if not 8 <= len(digits) <= 15:
            return value
        prefix = text[max(0, match.start() - 32) : match.start()]
        explicit_context = bool(_CONTACT_CONTEXT.search(prefix))
        international_format = (
            value.lstrip().startswith("+")
            and len(digits) >= 9
            and len(re.findall(r"[\s()-]", value)) >= 2
        )
        if not (explicit_context or international_format):
            return value
        return "[phone removed]"

    return _PHONE_CANDIDATE.sub(phone_sub, text)


def clean_markdown_boilerplate(text: str) -> str:
    """Remove navigation/footer fragments while preserving technical Markdown."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned: list[str] = []
    in_fence = False
    fence_token = ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        fence = _FENCE.match(line)
        if fence:
            token = fence.group(1)
            if not in_fence:
                in_fence, fence_token = True, token
            elif token == fence_token:
                in_fence, fence_token = False, ""
            cleaned.append(line)
            continue
        if in_fence:
            cleaned.append(line)
            continue
        if _STANDALONE_BRAND.match(line):
            continue
        line = _NAV_LINK.sub("", line)
        line = _LAST_MODIFIED.sub("", line)
        if re.fullmatch(r"\s*(?:\|\s*)+", line):
            continue
        if not line.strip():
            cleaned.append("")
            continue
        plain = re.sub(r"[|#*_`~\[\]()]", " ", line)
        if not " ".join(plain.split()):
            continue
        cleaned.append(line.rstrip())
    result = "\n".join(cleaned)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result


def _block_kind(lines: list[str]) -> str:
    if lines and _HEADING.match(lines[0]):
        return "heading"
    if lines and _FENCE.match(lines[0]):
        return "code"
    if any(_TABLE_SEPARATOR.match(line) for line in lines):
        return "table"
    if lines and _LIST_ITEM.match(lines[0]):
        upper = " ".join(lines[:2]).upper()
        return "warning" if re.search(r"\b(?:WARNING|CAUTION|DANGER|IMPORTANT)\b", upper) else "list"
    upper = " ".join(lines[:2]).upper()
    if re.search(r"\b(?:WARNING|CAUTION|DANGER|IMPORTANT)\b", upper):
        return "warning"
    return "paragraph"


def markdown_blocks(text: str, default_title: str = "Document") -> list[MarkdownBlock]:
    lines = text.splitlines()
    blocks: list[MarkdownBlock] = []
    headings: list[str] = [default_title]
    current: list[str] = []
    in_fence = False
    fence_token = ""

    def flush() -> None:
        nonlocal current
        value = "\n".join(current).strip()
        if value:
            blocks.append(MarkdownBlock(value, list(headings), _block_kind(current)))
        current = []

    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        heading = _HEADING.match(line)
        if heading and not in_fence:
            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if headings == [default_title] and level == 1:
                headings = [title]
            else:
                base = [] if headings == [default_title] else headings[: level - 1]
                headings = base + [title]
            blocks.append(MarkdownBlock(line, list(headings), "heading"))
            index += 1
            continue
        fence = _FENCE.match(line)
        if fence:
            token = fence.group(1)
            if not in_fence:
                flush()
                in_fence, fence_token = True, token
                current = [line]
            else:
                current.append(line)
                if token == fence_token:
                    in_fence, fence_token = False, ""
                    flush()
            index += 1
            continue
        if in_fence:
            current.append(line)
            index += 1
            continue
        if not line.strip():
            flush()
            index += 1
            continue
        if "|" in line and index + 1 < len(lines) and _TABLE_SEPARATOR.match(lines[index + 1]):
            flush()
            table = [line, lines[index + 1].rstrip()]
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                table.append(lines[index].rstrip())
                index += 1
            blocks.append(MarkdownBlock("\n".join(table), list(headings), "table"))
            continue
        if _LIST_ITEM.match(line):
            flush()
            listing = [line]
            index += 1
            while index < len(lines):
                candidate = lines[index].rstrip()
                if not candidate.strip() or _HEADING.match(candidate) or _FENCE.match(candidate):
                    break
                if _LIST_ITEM.match(candidate) or candidate[:1].isspace():
                    listing.append(candidate)
                    index += 1
                else:
                    break
            blocks.append(MarkdownBlock("\n".join(listing), list(headings), _block_kind(listing)))
            continue
        current.append(line)
        index += 1
    flush()
    return blocks


def _split_words(text: str, target_chars: int) -> list[str]:
    words = text.split()
    pieces: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        if current and length + len(word) + 1 > target_chars:
            pieces.append(" ".join(current))
            current, length = [], 0
        current.append(word)
        length += len(word) + (1 if length else 0)
    if current:
        pieces.append(" ".join(current))
    return pieces


def _pack_units(
    units: list[str], block: MarkdownBlock, target_chars: int, prefix: list[str] | None = None
) -> list[MarkdownBlock]:
    prefix = prefix or []
    prefix_text = "\n".join(prefix)
    pieces: list[str] = []
    current: list[str] = list(prefix)
    current_len = len(prefix_text)
    for unit in units:
        extra = len(unit) + (1 if current else 0)
        if len(current) > len(prefix) and current_len + extra > target_chars:
            pieces.append("\n".join(current))
            current = list(prefix)
            current_len = len(prefix_text)
        current.append(unit)
        current_len += extra
    if len(current) > len(prefix):
        pieces.append("\n".join(current))
    return [MarkdownBlock(piece, block.heading_path, block.kind) for piece in pieces]


def _split_large_prose(block: MarkdownBlock, target_chars: int) -> list[MarkdownBlock]:
    if len(block.text) <= target_chars or block.kind == "heading":
        return [block]
    lines = block.text.splitlines()
    if block.kind == "code":
        opener = lines[0] if lines and _FENCE.match(lines[0]) else "```"
        closer = lines[-1] if len(lines) > 1 and _FENCE.match(lines[-1]) else opener[:3]
        content_lines = lines[1:-1] if lines and _FENCE.match(lines[0]) and len(lines) > 1 and _FENCE.match(lines[-1]) else lines
        pieces: list[MarkdownBlock] = []
        current: list[str] = []
        current_len = len(opener) + len(closer) + 2
        for line in content_lines:
            if current and current_len + len(line) + 1 > target_chars:
                pieces.append(MarkdownBlock("\n".join([opener, *current, closer]), block.heading_path, "code"))
                current, current_len = [], len(opener) + len(closer) + 2
            current.append(line)
            current_len += len(line) + 1
        if current:
            pieces.append(MarkdownBlock("\n".join([opener, *current, closer]), block.heading_path, "code"))
        return pieces or [block]
    if block.kind == "table":
        if any(len(line) > target_chars * 2 for line in lines):
            cells = [
                " ".join(cell.split())
                for line in lines
                for cell in line.split("|")
                if " ".join(cell.split()) and not re.fullmatch(r"[:\- ]+", cell)
            ]
            result: list[MarkdownBlock] = []
            for cell in cells:
                prose = MarkdownBlock(cell, block.heading_path, "paragraph")
                result.extend(_split_large_prose(prose, target_chars))
            return result
        prefix = lines[:2] if len(lines) > 1 and _TABLE_SEPARATOR.match(lines[1]) else []
        return _pack_units(lines[len(prefix):], block, target_chars, prefix) or [block]
    if block.kind == "list":
        items: list[str] = []
        current: list[str] = []
        for line in lines:
            if _LIST_ITEM.match(line) and current:
                items.append("\n".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            items.append("\n".join(current))
        return _pack_units(items, block, target_chars) or [block]
    raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", block.text)
    sentences = [piece for sentence in raw_sentences for piece in (
        _split_words(sentence, target_chars) if len(sentence) > target_chars else [sentence]
    )]
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + 1 + len(sentence) > target_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return [MarkdownBlock(piece, block.heading_path, block.kind) for piece in pieces]


def structured_chunks(
    text: str,
    target_chars: int = 1200,
    base_metadata: dict[str, Any] | None = None,
) -> list[StructuredChunk]:
    frontmatter, body = parse_frontmatter(text)
    body = scrub_sensitive_text(clean_markdown_boilerplate(body))
    title = frontmatter.get("title") or (base_metadata or {}).get("title") or "Document"
    blocks: list[MarkdownBlock] = []
    for block in markdown_blocks(body, str(title)):
        blocks.extend(_split_large_prose(block, max(400, target_chars)))

    groups: list[list[MarkdownBlock]] = []
    current: list[MarkdownBlock] = []
    current_len = 0
    for block in blocks:
        heading_changed = current and block.heading_path != current[-1].heading_path
        too_large = current and current_len + len(block.text) + 2 > target_chars
        if heading_changed or too_large:
            groups.append(current)
            current, current_len = [], 0
        current.append(block)
        current_len += len(block.text) + 2
    if current:
        groups.append(current)

    metadata_source = {**frontmatter, **(base_metadata or {})}
    chunks: list[StructuredChunk] = []
    for group in groups:
        heading_path = group[-1].heading_path or [str(title)]
        chunk_text = "\n\n".join(block.text for block in group).strip()
        meaningful = re.sub(r"[^A-Za-z0-9]+", "", chunk_text)
        if len(meaningful) < 8:
            continue
        kinds = sorted({block.kind for block in group if block.kind != "heading"}) or ["heading"]
        metadata = {
            **metadata_source,
            "canonicalSource": metadata_source.get("source_url")
            or metadata_source.get("canonicalUrl")
            or metadata_source.get("canonicalSource", ""),
            "section": heading_path[-1],
            "headingPath": heading_path,
            "parentSection": heading_path[-2] if len(heading_path) > 1 else "",
            "contentTypes": kinds,
            "authority": metadata_source.get("authority", "unclassified"),
            "status": metadata_source.get("status") or metadata_source.get("disposition", "active"),
            "corpusVersion": metadata_source.get("corpus_version")
            or metadata_source.get("corpusVersion", "unversioned"),
        }
        chunks.append(StructuredChunk(chunk_text, metadata))

    for index, chunk in enumerate(chunks):
        chunk.metadata["previousSection"] = chunks[index - 1].metadata["section"] if index else ""
        chunk.metadata["nextSection"] = chunks[index + 1].metadata["section"] if index + 1 < len(chunks) else ""
        chunk.metadata["chunkIndex"] = index
    return chunks
