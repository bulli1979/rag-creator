"""Bounded within-document lookup for explicitly scoped reference questions.

A retrieved report introduction may miss a value several pages later. Select
at most two topically identified sources, then locate the requested property.
No answer values or filenames are encoded. Safety/procedures stay out of scope.
"""
import re
from .source_policy import annotate_source
from .evidence_selection import classify_query

_FILLER = set('what which how is are does did do the a an of for from at in on with by to and not telescope instrument report mentioned according allowed initial maximum minimum total new introduced observing'.split())
_PROPERTIES = set('plate pixel scale duration period years speeds readout provided four'.split())


def terms(text):
    text = re.sub(r'\bpick[ -]?up\b', 'pickup', text, flags=re.I)
    text = re.sub(r'\b(?:2nd|second)[ -]order\b', 'secondorder', text, flags=re.I)
    return {w.lower().rstrip('s') for w in re.findall(r'[a-zA-Z]+', text) if len(w)>2}


def frequency_query(query):
    """Only a factual pick-up noise measurement, never a repair instruction."""
    return bool(re.search(r'\bfundamental frequency\b', query, re.I)
                and re.search(r'\bpick[ -]?up noise\b', query, re.I)
                and not re.search(r'\b(?:how|fix|repair|safe|bypass|override|disconnect|should|procedure|steps)\b', query, re.I))


def property_match(query, text):
    if frequency_query(query):
        return bool(re.search(r'\bfundamental frequency of (?:the )?(?:pick[ -]?up )?noise is\s*\d+(?:\.\d+)?\s*(?:[kM]?Hz)\b', text, re.I))
    if re.search(r'\b(?:plate|pixel) scale\b', query, re.I):
        return bool(re.search(r'\b1\s+pixel\s*=\s*\d+(?:\.\d+)?\s*arcsec\b|\d+(?:\.\d+)?\s*arcsec\s*/\s*pixel', text, re.I))
    if re.search(r'\breadout speeds?\b', query, re.I):
        # A single noise/gain test at one speed is not the available inventory.
        return bool(re.search(r'\b\d+\s+(?:different\s+|readout\s+)?speeds\b', text, re.I)
                    and re.search(r'\d+\s*kpix\s*/\s*sec', text, re.I))
    if re.search(r'\b(?:duration|period)\b', query, re.I):
        return bool(re.search(r'\b(?:initially|maximum)\b', text, re.I) and re.search(r'\d+\s*years?\b', text, re.I))
    return False


def focused_sources(query, candidates):
    if not (frequency_query(query) or re.search(r'\breport\b|\bintroduced in\b', query, re.I)
            or re.search(r'"[^"\n]+"', query)
            or (re.search(r'\b(?:proposal|policy|allocation|rules)\b',query,re.I)
                and re.search(r'\b(?:duration|period)\b',query,re.I))):
        return []
    topics = terms(query) - _FILLER - _PROPERTIES
    if not topics:
        return []
    ranked = {}
    instruments = classify_query(query).instruments
    for original in candidates:
        item = annotate_source(original)
        named = item.get('instrument', '').upper()
        if instruments and named not in instruments:
            # Development URLs need not contain an /alfosc/ directory. A
            # source's explicit title/heading can establish the instrument;
            # general body mentions and the user's question cannot.
            from .source_policy import INSTRUMENTS
            heading_names=classify_query(item.get('title','')+' '+' '.join(item.get('headingPath',[]))).instruments
            if named in INSTRUMENTS or len(heading_names)!=1 or not heading_names.issubset(instruments):
                continue
        if item.get('sourceRole') in ('operator_guide', 'command_reference'):
            continue
        scope = item.get('title','') + ' ' + ' '.join(item.get('headingPath', [])) + ' ' + item.get('text','')
        overlap = topics & terms(scope)
        if len(overlap) < min(2, len(topics)):
            continue
        key = item.get('fileName','')
        if key:
            ranked[key] = max(ranked.get(key, 0), len(overlap)/len(topics))
    return [name for name, _ in sorted(ranked.items(), key=lambda pair: (-pair[1], pair[0]))[:2]]
