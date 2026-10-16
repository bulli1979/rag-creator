"""Operational source hierarchy shared by retrieval and grounding.

An active crawl/version is not proof of current operating status. Roles below are
derived from canonical documentation URLs and section scope, not answer values.
"""
import re
from urllib.parse import urlsplit, parse_qs

INSTRUMENTS = ("ALFOSC", "NOTCAM", "FIES", "STANCAM", "DIPOL-UF", "SOFIN", "SIRCA", "POLCOR", "MOSCA", "LUCKYCAM", "TURPOL")


def source_role(chunk: dict) -> str:
    url = str(chunk.get("canonicalLocation") or chunk.get("source") or chunk.get("sourcePath") or "")
    path = urlsplit(url).path.lower()
    heading = " / ".join(chunk.get("headingPath", [])) + " / " + str(chunk.get("section", ""))
    if re.search(r"\b(?:decommissioned|old bundle|spare|former|outdated|superseded|historical)\b", heading, re.I):
        return "historical_section"
    if re.search(r"technical papers describing|table of contents", heading, re.I):
        return "reference_index"
    if chunk.get("status", "").lower() in ("historical", "superseded"):
        return "historical_section"
    if "/observing/cookbook/current/" in path:
        return "operator_guide"
    if '/current/' in path and path.endswith('/ccd-commands.pdf'):
        return 'command_reference'
    if path.startswith('/observing/tools/') and chunk.get('category') == 'observing_guide':
        return 'operator_guide'
    if "/observing/seq/" in path or chunk.get("category") == "sequencer_reference":
        return "command_reference"
    landing=re.fullmatch(r"/instruments/([a-z0-9_-]+)(?:/(?:index\.html?)?)?", path)
    if landing and (landing[1].upper() in INSTRUMENTS or landing[1]=='mosaic'):
        return "instrument_landing"
    if re.search(r"/(?:quickrefguide[^/]*|[^/]*cookbook[^/]*|[^/]*manual[^/]*|[^/]*safety[^/]*)", path):
        return "operator_guide"
    if re.search(r"/(?:devel|development|bundled)/|/(?:council|stc)[^/]*|(?:council|stc)[-_]?rep|/(?:milestones|mounting)(?:[./]|$)|/[^/]*design[^/]*\.pdf$", path):
        return "design_reference"
    if path.endswith("/fies-comm.html"):
        return "historical_section"
    if path=='/telescope/technical-details.html':
        return 'current_reference'
    # Some instrument overview pages use '<instrument>over.html', not
    # 'overview.html'. Still exclude development/design paths above.
    if re.fullmatch(r'/instruments/[a-z0-9_-]+/[a-z0-9_-]+over\.html?',path):
        return 'current_reference'
    if re.search(r"/(?:overview|fies-commd|fixed_setup|grisms|slits|spectroscopy)(?:[./]|$)", path):
        return "current_reference"
    if re.search(r"(?:^|[-_/])overview(?:[-_.]|$)", str(chunk.get("fileName", "")), re.I):
        return "current_reference"
    return "reference"


def annotate_source(chunk: dict) -> dict:
    role = source_role(chunk)
    result = {**chunk, "sourceRole": role}
    if str(result.get("instrument", "")).upper() not in INSTRUMENTS:
        url = str(chunk.get("canonicalLocation") or chunk.get("source") or "")
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        named = next(iter(query.get("instrument", [])), "").upper()
        if named in INSTRUMENTS:
            result["instrument"] = named
        elif parsed.path.lower().startswith('/instruments/mosaic/'):
            result['instrument']='MOSCA'
        else:
            names = [name for name in INSTRUMENTS if re.search(r"/"+re.escape(name.lower())+r"(?:/|$|-seq-)",parsed.path.lower())]
            if len(names) == 1:
                result["instrument"] = names[0]
    # Aggregated catalogues can contain unrelated instruments in the same
    # source. An explicit per-entry label is stronger than a document default.
    explicit = re.search(r"(?:^|\n)\s*[-*]?\s*(?:\*\*)?Instrument(?:\*\*)?:\s*(?:\*\*)?([A-Z][A-Z0-9_-]+)",str(chunk.get("text","")),re.I)
    if explicit and explicit[1].upper() in INSTRUMENTS:
        result["instrument"] = explicit[1].upper()
    heading_instruments={str(h).strip().upper() for h in chunk.get('headingPath',[]) if str(h).strip().upper() in INSTRUMENTS}
    if len(heading_instruments)==1:
        result['instrument']=next(iter(heading_instruments))
    if role in ("operator_guide", "command_reference", "instrument_landing"):
        result["authority"] = "tier_1_authoritative"
    if role == "historical_section":
        result.update(status="historical", authority="tier_3_historical_record")
    elif role == "design_reference":
        # Engineering material remains retrievable for explicit reference/history
        # questions, but cannot masquerade as the current observing configuration.
        result.update(status="reference_only", authority="tier_2_design_reference")
    return result


def operational_priority(chunk: dict, *, reference_intent: bool = False) -> float:
    role = chunk.get("sourceRole") or source_role(chunk)
    if reference_intent:
        # A technical/report question must not be overwhelmed by the observing
        # cookbook's operational boost. Currency is still shown and validated.
        return {"design_reference":.12,"historical_section":.08,
                "operator_guide":.03,"command_reference":.03,
                "reference_index":-.25}.get(role,0.0)
    return {"operator_guide": .24, "command_reference": .22,
            "instrument_landing": .22, "current_reference": .16,
            "design_reference": -.28, "historical_section": -.35, "reference_index": -.25}.get(role, 0.0)
