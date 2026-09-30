"""Deterministic retrieval ranking and evidence selection.

Keep this module free of network and model dependencies so the selection policy can
be measured against fixed candidate sets before changing the live index.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_\-/\.]+")
_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
_INSTRUMENTS = ("ALFOSC", "NOTCAM", "FIES", "STANCAM", "DIPOL-UF", "SOFIN", "SIRCA", "POLCOR", "MOSCA", "LUCKYCAM", "TURPOL")
_HISTORICAL_RE = re.compile(r"\b(historical|history|old|previous|former|archived|superseded|in the past|fr[uü]her|historisch|alt(?:e|en|er|es)?|ehemalig)\b", re.I)
_PROCEDURE_RE = re.compile(r"\b(procedure|steps|how to|start|startup|shutdown|operate|calibrat|verfahren|anleitung|schritte)\w*\b", re.I)
_TROUBLE_RE = re.compile(r"\b(fault|error|fail|troubleshoot|problem|st[oö]rung|fehler)\w*\b", re.I)
_SAFETY_RE = re.compile(r"\b(safety|warning|danger|hazard|safe|sicher|gefahr|warnung)\w*\b", re.I)


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text or "") if len(token) > 1}


def _extract_numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text or ""))


@dataclass(frozen=True)
class QueryIntent:
    instruments: frozenset[str]
    historical: bool
    categories: frozenset[str]


def classify_query(query: str) -> QueryIntent:
    instruments = frozenset(
        name for name in _INSTRUMENTS
        if re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", query, re.I)
    )
    categories: set[str] = set()
    if _PROCEDURE_RE.search(query):
        categories.add("procedure")
    if _TROUBLE_RE.search(query):
        categories.add("troubleshooting")
    if _SAFETY_RE.search(query):
        categories.add("safety")
    if (instruments and re.search(r"\b(?:can|could|kann|könnte)\b", query, re.I)
            and re.search(r"\b(?:observ\w*|detect\w*|used|wavelength\w*|wellenlänge\w*)\b", query, re.I)
            and re.search(r"\d\s*(?:nm|[µμu]m|(?:nano|micro)met(?:er|re)s?)\b", query, re.I)):
        categories.add("overview")
    for instrument in instruments:
        name = re.escape(instrument)
        if any(re.fullmatch(pattern, query.strip(), re.I) for pattern in (
            rf"(?:what is|what's|describe|tell me about) (?:the )?{name}[?.!]*",
            rf"what is (?:the )?{name} used for[?.!]*",
            rf"(?:what|which) wavelengths?(?: range)? does {name} (?:cover|observe|detect)[?.!]*",
        )):
            categories.add("overview")
    return QueryIntent(instruments, bool(_HISTORICAL_RE.search(query)), frozenset(categories))


def _base_score(query_tokens: set[str], query_numbers: set[str], chunk: dict) -> float:
    text = str(chunk.get("text", ""))
    similarity = float(chunk.get("similarity", 0.0) or 0.0)
    lexical = len(query_tokens & _tokenize(text)) / len(query_tokens) if query_tokens else 0.0
    numeric = len(query_numbers & _extract_numbers(text)) / len(query_numbers) if query_numbers else 0.0
    return 0.65 * similarity + 0.25 * lexical + 0.10 * numeric


def _boosted_score(score: float, chunk: dict, source_boosts: dict[str, float] | None) -> float:
    if source_boosts:
        name = str(chunk.get("fileName", "")).lower()
        for pattern, multiplier in source_boosts.items():
            if multiplier != 1.0 and pattern.lower() in name:
                return score * multiplier
    return score


def _rerank_chunks(
    query: str,
    chunks: list[dict],
    top_k: int,
    source_boosts: dict[str, float] | None = None,
) -> list[dict]:
    """Original hybrid ranking, retained for baseline comparisons."""
    tokens, numbers = _tokenize(query), _extract_numbers(query)
    scored = [
        (_boosted_score(_base_score(tokens, numbers, chunk), chunk, source_boosts), chunk)
        for chunk in chunks
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:max(1, top_k)]]


def _source_key(chunk: dict) -> str:
    for name in ("sourceId", "canonicalLocation", "sourcePath", "documentId"):
        value = str(chunk.get(name, "")).strip()
        if value:
            return value
    return str(chunk.get("fileName", ""))


def _duplicate_key(chunk: dict) -> str:
    normalized = " ".join(str(chunk.get("text", "")).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _near_duplicate(text: str, other: str) -> bool:
    """Collapse punctuation/formatting variants without losing changed instructions.

    Token order and values must match exactly; a changed number or a single
    different procedure verb is not safe to treat as duplicate evidence.
    """
    first = re.findall(r"\w+", text)
    second = re.findall(r"\w+", other)
    return len(first) >= 20 and first == second


def select_evidence(
    query: str,
    chunks: list[dict],
    top_k: int,
    *,
    max_chunks_per_source: int = 2,
    min_similarity: float = 0.0,
    source_boosts: dict[str, float] | None = None,
) -> list[dict]:
    """Select diverse evidence with conservative metadata preferences.

    Instrument filtering is applied only if the pool contains a matching tagged
    source. Unknown or general instrument tags remain eligible. Historical sources
    are still eligible for ordinary queries, but ranked behind current guidance.
    """
    intent = classify_query(query)
    tokens, numbers = _tokenize(query), _extract_numbers(query)
    matching_instrument = bool(intent.instruments) and any(
        str(chunk.get("instrument", "")).upper() in intent.instruments for chunk in chunks
    )
    scored: list[tuple[float, int, dict]] = []
    for position, chunk in enumerate(chunks):
        if not str(chunk.get("text", "")).strip():
            continue
        if float(chunk.get("similarity", 0.0) or 0.0) < min_similarity:
            continue
        instrument = str(chunk.get("instrument", "")).upper()
        if matching_instrument and instrument not in intent.instruments and instrument not in ("", "[MISSING]", "GENERAL"):
            continue
        score = _boosted_score(_base_score(tokens, numbers, chunk), chunk, source_boosts)
        status = str(chunk.get("status", "active")).lower()
        authority = str(chunk.get("authority", "")).lower()
        if intent.instruments and instrument in intent.instruments:
            score += 0.10
        if ("overview" in intent.categories and instrument in intent.instruments
                and status in ("active", "current") and authority.startswith(("tier_1", "tier_2"))
                and re.search(r"(?:^|[-_/])overview(?:[-_.]|$)", str(chunk.get("fileName", "")), re.I)):
            score += 0.25
        if status in ("active", "current"):
            score += 0.04 if not intent.historical else 0.0
        elif status in ("historical", "superseded"):
            score += 0.04 if intent.historical else -0.12
        if authority.startswith("tier_1"):
            score += 0.04
        elif authority.startswith("tier_2"):
            score += 0.01
        if "troubleshooting" in intent.categories and str(chunk.get("category", "")) == "fault_report":
            score += 0.04
        scored.append((score, position, chunk))
    scored.sort(key=lambda item: (-item[0], item[1]))

    selected: list[dict] = []
    source_counts: Counter[str] = Counter()
    exact_seen: set[str] = set()
    for score, _, chunk in scored:
        source = _source_key(chunk)
        if source_counts[source] >= max(1, max_chunks_per_source):
            continue
        duplicate = _duplicate_key(chunk)
        if duplicate in exact_seen or any(_near_duplicate(str(chunk.get("text", "")), str(existing.get("text", ""))) for existing in selected):
            continue
        selected.append({**chunk, "retrievalScore": round(score, 6)})
        source_counts[source] += 1
        exact_seen.add(duplicate)
        if len(selected) >= max(1, top_k):
            break
    return selected
