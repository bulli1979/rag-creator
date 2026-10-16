"""Resolve narrow instrument follow-ups without treating chat history as evidence."""

from dataclasses import dataclass
import re

from .evidence_selection import classify_query


_REFERENCE = re.compile(r"\b(?:it|its|this instrument|that instrument|the instrument|dieses instrument|das instrument|es)\b", re.I)
_ELLIPSIS = re.compile(r"^(?:and\b|what about\b|how about\b|und\b)", re.I)
_COMPONENT = re.compile(
    r"\b(?:fib(?:er|re)s?|fivers?|camera|detector|pixel|field|imaging|spectro\w*|"
    r"wavelength|resolution|resolving|aperture|diameter|scale|grism|slit|filter|"
    r"exposure|readout|calibrat\w*|gain|noise|focus|mode|available|size|"
    r"faser\w*|durchmesser|auflösung|bogensekund\w*|kamera|spektr\w*)\b", re.I)
_NEW_TOPIC = re.compile(
    r"\b(?:weather|road|travel|hotel|flight|proposal|telescope|TCS|ORM|mountain|"
    r"politics|recipe|football|wetter|straße|reise)\b", re.I)
_COMPONENT_SUBJECT = re.compile(r"\b(?:fib(?:er|re)s?|fivers?|camera|detector|grism|slit|filter|faser\w*|kamera)\b", re.I)


def _topic_switch(query: str) -> bool:
    return bool(_NEW_TOPIC.search(query) and not (_REFERENCE.search(query) or _COMPONENT_SUBJECT.search(query)))


def normalize_query(query: str, *, instrument_context: bool = False) -> str:
    """Normalize common terminology without modifying commands or identifiers."""
    query = re.sub(r"\bfibres\b", "fibers", query, flags=re.I)
    query = re.sub(r"\bfibre\b", "fiber", query, flags=re.I)
    if instrument_context:
        query = re.sub(r"\bfivers\b", "fibers", query, flags=re.I)
        query = re.sub(r"\bfiver\b", "fiber", query, flags=re.I)
    # Retrieval uses the English source corpus; the original request still sets
    # the response language. Preserve identifiers and quantities unchanged.
    terms = {"Faser": "fiber", "Fasern": "fibers", "Durchmesser": "diameter",
             "Bogensekunden": "arcseconds", "Bogensekunde": "arcsecond",
             "Auflösung": "resolution", "Wellenlänge": "wavelength"}
    for german, english in terms.items():
        query = re.sub(r"\b" + german + r"\b", english, query, flags=re.I)
    return query


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
        # A subject-only clarification answers the preceding question; it is not
        # a new request for an instrument definition. User turns supply intent,
        # never answer facts. A new explicit question is left unchanged.
        clarification = re.match(r"^(?:i mean|i meant|ich meine)\s+(.+)", query.strip(), re.I)
        if clarification and len(named) == 1 and not re.search(r"\b(?:what|which|how|why|when|wie|was|welche)\b", clarification[1], re.I):
            prior = next((str(m.get("content", "")) for m in reversed(history) if m.get("role") == "user"), "")
            if prior:
                previous_named = classify_query(prior).instruments
                if len(previous_named) <= 1:
                    for old in previous_named:
                        prior = re.sub(re.escape(old), next(iter(named)), prior, flags=re.I)
                    resolved = next(iter(named)) + ": " + normalize_query(prior, instrument_context=True)
                    return RetrievalContext(resolved, named, "clarified")
        return RetrievalContext(normalize_query(query, instrument_context=True), named, "explicit")
    if _topic_switch(query) or not (_REFERENCE.search(query) or _ELLIPSIS.search(query) or _COMPONENT.search(query)):
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
            resolved, count = _REFERENCE.subn(instrument, normalize_query(query, instrument_context=True))
            if not count:
                resolved = f"{instrument}: {resolved}"
            return RetrievalContext(resolved, named, "inherited")
        if _topic_switch(previous) or not (_REFERENCE.search(previous) or _ELLIPSIS.search(previous) or _COMPONENT.search(previous)):
            break
    # Generic 'it' can refer to something other than an instrument. Do not force
    # instrument clarification for every pronoun in a standalone question.
    unresolved = bool(re.search(r"\b(?:the|this|that|das|dieses) instrument\b|\b(?:the|this|that) (?:new )?(?:detector controller|camera|detector)\b", query, re.I))
    return RetrievalContext(query, frozenset(), "unresolved" if unresolved else "standalone")
