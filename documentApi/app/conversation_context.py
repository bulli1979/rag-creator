"""Resolve narrow instrument follow-ups without treating chat history as evidence."""

from dataclasses import dataclass
import re

from .evidence_selection import classify_query


_REFERENCE = re.compile(r"\b(?:it|its|this instrument|that instrument|the instrument|dieses instrument|das instrument|es)\b", re.I)
_ELLIPSIS = re.compile(r"^(?:and\b|what about\b|how about\b|und\b)", re.I)


@dataclass(frozen=True)
class RetrievalContext:
    query: str
    instruments: frozenset[str]
    resolution: str


def resolve_retrieval_context(query: str, history: list[dict]) -> RetrievalContext:
    """Explicit subjects override history; ambiguous subjects must not be guessed.

    Use only user turns to establish the subject. Assistant prose/citations can be
    wrong and are never reused as factual evidence. Stop at a new unrelated topic.
    """
    named = classify_query(query).instruments
    if named:
        return RetrievalContext(query, named, "explicit")
    if not (_REFERENCE.search(query) or _ELLIPSIS.search(query)):
        return RetrievalContext(query, named, "standalone")
    for message in reversed(history):
        if message.get("role") != "user":
            continue
        previous = str(message.get("content", ""))
        named = classify_query(previous).instruments
        if len(named) > 1:
            return RetrievalContext(query, frozenset(), "ambiguous")
        if named:
            instrument = next(iter(named))
            resolved, count = _REFERENCE.subn(instrument, query)
            if not count:
                resolved = f"{instrument}: {query}"
            return RetrievalContext(resolved, named, "inherited")
        if not (_REFERENCE.search(previous) or _ELLIPSIS.search(previous)):
            break
    # Generic 'it' can refer to something other than an instrument. Do not force
    # instrument clarification for every pronoun in a standalone question.
    unresolved = bool(re.search(r"\b(?:the|this|that|das|dieses) instrument\b", query, re.I))
    return RetrievalContext(query, frozenset(), "unresolved" if unresolved else "standalone")
