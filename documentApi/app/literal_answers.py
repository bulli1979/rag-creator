"""Constrained extractive answers from current instrument reference prose.

Keeps native technical notation intact when a model would merely copy a source
definition, capability list or pixel-scale line. No values or modes are encoded.
All other questions stay on the model's grounded synthesis path.
"""
from dataclasses import dataclass
import re
from .evidence_selection import classify_query
from .grounding import ValidationResult, _identifier_numbers


@dataclass(frozen=True)
class LiteralAnswer:
    validation: ValidationResult
    derivation: dict


def answer_literal(query: str, evidence: list[dict], language: str = "en") -> LiteralAnswer | None:
    # A named detector's physical pixel dimensions are an exact datasheet
    # property, not an inference from another camera's plate-scale summary.
    # Require the product identity in source prose (not just a linked title)
    # and explicit complete units on BOTH dimensions.
    products=re.findall(r'\bSI[- ]?\d+[A-Z]?\b',query,re.I)
    if (language=='en' and len(products)==1 and re.search(r'\bphysical pixel size\b',query,re.I)
            and not re.search(r'\b(?:how|why|fix|safe|should|procedure)\b',query,re.I)):
        requested=re.sub(r'[- ]','',products[0]).upper()
        for item in evidence:
            if item.get('status') not in ('active','current'):
                continue
            text=re.sub(r'\[[^\]]*\]\([^)]*\)','',item['content'])
            identities={re.sub(r'[- ]','',p).upper() for p in re.findall(r'\bSI[- ]?\d+[A-Z]?\b',text+' '+item.get('title',''),re.I)}
            if identities!={requested}:
                continue
            match=re.search(r'\b(?:Pixel Size|pixel measures)\s+\d+(?:\.\d+)?\s*[µμ]m\s*[x×]\s*\d+(?:\.\d+)?\s*[µμ]m\b', ' '.join(text.split()),re.I)
            if match:
                excerpt=match[0]
                return LiteralAnswer(ValidationResult(f"Cited detector specification ({products[0]}): {excerpt}. [{item['citationId']}]",1,0,0,False),
                                     {'operation':'named-detector-pixel-dimensions-v1','citationId':item['citationId'],'excerpt':excerpt})
    # Explicitly scoped technical/policy reference questions can copy a complete
    # property paragraph. Identity is established within the bounded SAME source
    # expansion; never bind an unknown detector from another document. The
    # excerpt does not claim an introduction date or today's operating setup.
    from .reference_focus import frequency_query, property_match
    if language == 'en' and (frequency_query(query) or re.search(r'\breadout speeds?\b|\b(?:duration|period)\b',query,re.I)):
        for item in evidence:
            if (not item.get('focusedReference') or not _identifier_numbers(query).issubset(set(item.get('focusedScopeIdentifiers', [])))):
                continue
            if frequency_query(query):
                instruments = classify_query(query).instruments
                from .source_policy import INSTRUMENTS
                named=item.get('instrument','').upper()
                heading_names=classify_query(item.get('title','')+' '+' '.join(item.get('headingPath',[]))).instruments
                if (not instruments or (named not in instruments and
                        (named in INSTRUMENTS or len(heading_names)!=1 or not heading_names.issubset(instruments)))):
                    continue
                if not re.search(r'\bpick[ -]?up\b', item.get('section','')+' '+' '.join(item.get('headingPath',[]))+' '+item['content'], re.I):
                    continue
            blocks = re.split(r'\n\s*\n|\n(?=\s*[-*•]\s+)', item['content'])
            for block in blocks:
                text=' '.join(block.strip(' -*•\n').split())
                if frequency_query(query):
                    # The next report sentence can describe experimental
                    # electrical changes. Copy only the measurement sentence,
                    # including its parenthetical assumptions, not a recipe.
                    text=next((sentence for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z])',text)
                               if property_match(query,sentence)), '')
                if 30 <= len(text) <= 900 and property_match(query,text):
                    suffix=''
                    if re.search(r'\b(?:duration|period)\b',query,re.I) and not re.search(r'[.!?]$',text):
                        # Some PDF extraction separates a parenthetical
                        # continuation into a layout table. Return only the
                        # complete initial-duration clause, never a hanging
                        # 'but they might be extended' or invented conditions.
                        clause=re.search(r'^.*?\bmaximum(?: of)?\s+\d+\s*years?\b',text,re.I)
                        if not clause:
                            continue
                        text=clause[0]+'.'
                        suffix=' This establishes the initial duration only; consult the complete rules for extensions.'
                    prefix='Cited reference (not a statement of current operating policy): '
                    if item.get('sourceRole') == 'design_reference' or item.get('status') == 'historical':
                        prefix='Historical/technical report (not current operating guidance): '
                    return LiteralAnswer(ValidationResult(prefix+text+f" [{item['citationId']}]"+suffix,1,0,0,False),
                                         {'operation':'scoped-reference-property-excerpt-v1','citationId':item['citationId'],'excerpt':text})
    # A literal dimensional identity in an explicitly requested report is not
    # a current detector specification. Copy the identity, with no extrapolation.
    if language == 'en' and re.search(r'\breport\b', query, re.I) and re.search(r'\b(?:plate|pixel) scale\b', query, re.I):
        for item in evidence:
            if not item.get('focusedReference'):
                continue
            if not _identifier_numbers(query).issubset(_identifier_numbers(item['content'] + ' ' + item.get('section',''))):
                continue
            identity = re.search(r'\b1\s+pixel\s*=\s*\d+(?:\.\d+)?\s*arcsec\b', item['content'], re.I)
            if identity:
                text = 'In the cited report (not a current detector specification): ' + identity[0] + '.'
                return LiteralAnswer(ValidationResult(text + f" [{item['citationId']}]",1,0,0,False),
                                     {'operation':'scoped-report-dimensional-identity-v1','citationId':item['citationId'],'excerpt':identity[0]})
    # Named command definitions are exact reference lookups, not recipes. The
    # instrument comes from the entry's heading ancestry, never another system.
    if language=='en' and re.search(r'\bwhat does\b',query,re.I):
        for item in evidence:
            command=item.get('section','').strip('` ')
            if (item.get('sourceRole')!='command_reference' or item.get('status') not in ('active','current')
                    or not re.fullmatch(r'[a-z][a-z0-9_.-]+',command,re.I)
                    or not re.search(r'(?<!\w)'+re.escape(command)+r'(?!\w)',query,re.I)):
                continue
            intent = classify_query(query)
            if intent.instruments and item.get('instrument','').upper() not in intent.instruments:
                continue
            paragraphs=re.split(r'\n\s*\n',item['content'])
            definition=next((p for p in paragraphs if not p.lstrip().startswith(('#','-','*','`','|'))), '')
            if definition and len(definition)<700:
                return LiteralAnswer(ValidationResult(f"{command}: {definition.strip()} [{item['citationId']}]",1,0,0,False),
                                     {'operation':'current-command-definition-v1','citationId':item['citationId'],'excerpt':definition})
    # Generic two-column property/value lookup, with a strong exact property
    # match. This is not a template for arbitrary multi-component tables.
    if language == "en" and re.search(r"\bwhat is\b", query, re.I) and not re.search(r"\b(?:can|why|historical|used|fiber|fibre)\b",query,re.I):
        query_terms = set(re.findall(r"[a-z]+",query.lower()))
        for item in evidence:
            if item.get("status") not in ("active","current") or item.get("sourceRole") in ("design_reference","historical_section"):
                continue
            intent=classify_query(query)
            if intent.instruments and item.get('instrument','').upper() not in intent.instruments:
                continue
            products=re.findall(r'\b(?:SI[- ]?\d+[A-Z]?|CCD\d+-\d+)\b',query,re.I)
            if products and not all(re.search(re.escape(p),item['content']+' '+item.get('title',''),re.I) for p in products):
                continue
            if re.search(r'\btelescope\b',query,re.I) and not classify_query(query).instruments and '/instruments/' in item.get('source',''):
                continue
            for line in item["content"].splitlines():
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) != 2:
                    continue
                property_terms = set(re.findall(r"[a-z]+", cells[0].lower()))-{'total','of','the'}
                if len(property_terms) < 2 or not property_terms.issubset(query_terms) or not re.search(r"\d", cells[1]):
                    continue
                value = re.sub(r'(\d(?:\.\d+)?)"',r'\1 arcsec',cells[1])
                value = re.sub(r"(\d(?:\.\d+)?)'",r'\1 arcmin',value)
                answer = f"{cells[0].rstrip(':')}: {value} [{item['citationId']}]"
                return LiteralAnswer(ValidationResult(answer,1,0,0,False),
                                     {"operation":"current-property-extract-v1","citationId":item['citationId'],"excerpt":line.strip()})
    intent = classify_query(query)
    if len(intent.instruments) != 1 or intent.historical or language != "en":
        return None
    instrument = next(iter(intent.instruments))
    definition = bool(re.fullmatch(r"(?:what is|what's) (?:the )?"+re.escape(instrument)+r"[?.!]*", query.strip(), re.I))
    capabilities = bool(re.search(r"\bused for\b|\bcapabilities\b", query, re.I))
    pixel_scale = bool(re.search(r"\bpixel scale\b|\bplate scale\b", query, re.I))
    if not (definition or capabilities or pixel_scale):
        return None
    if re.search(r"\b(?:why|safe|not|cannot|can|historical|old|calibrat\w*)\b", query, re.I):
        return None
    for item in evidence:
        if (item.get("instrument", "").upper() != instrument or item.get("status") not in ("active","current")
                or item.get("sourceRole") not in ("current_reference","instrument_landing","operator_guide")):
            continue
        content = item["content"]
        text = ""
        if definition:
            sentences = [s for p in re.split(r"\n\s*\n", content) for s in re.split(r"(?<=[.!?])\s+", " ".join(p.split()))]
            text = next((s for s in sentences if re.match(re.escape(instrument)+r"\s+is\s+(?:a|an|the)\b",s,re.I)), "")
        elif capabilities:
            match = re.search(r"\bcapable of:\s*\n((?:\s*[-*] [^\n]+\n?)+)", content, re.I)
            if match:
                text = instrument + " is capable of:\n" + match[1].strip()
            else:
                paragraphs=[' '.join(p.split()) for p in re.split(r'\n\s*\n',content)]
                text=next((p for p in paragraphs if len(p)<700
                           and re.match(re.escape(instrument)+r'\b',p,re.I)
                           and re.search(r'\b(?:used for|capable of|can perform)\b',p,re.I)), '')
        elif pixel_scale:
            # PDF line wrapping must not turn a complete source sentence into
            # 'of 0.12 arcsec/pixel. Only shift-and-add ... improves'. Preserve
            # complete prose sentences; retain atomic capability/list entries.
            lines = []
            for paragraph in re.split(r'\n\s*\n', content):
                if paragraph.lstrip().startswith(('-', '*', '|')):
                    candidates = [s.strip(' -*') for s in paragraph.splitlines()]
                else:
                    candidates = re.split(r'(?<=[.!?])\s+(?=[A-Z])', ' '.join(paragraph.split()))
                lines.extend(s for s in candidates if len(s) <= 400 and re.search(r'\d.*(?:/pixel|per pixel)', s, re.I))
            wide = bool(re.search(r"wide[ -]field|\bWF\b",query,re.I))
            high = bool(re.search(r"high[ -]resolution|\bHR\b",query,re.I))
            if wide:
                lines = [s for s in lines if re.search(r"wide[ -]field|\bWF\b",s,re.I)]
            elif high:
                lines = [s for s in lines if re.search(r"high[ -]resolution|\bHR\b",s,re.I)]
            if len(lines) == 1:
                text = instrument + " — " + lines[0]
        if text:
            citation = item["citationId"]
            return LiteralAnswer(ValidationResult(f"{text} [{citation}]",1,0,0,False),
                                 {"operation":"current-reference-extract-v1","citationId":citation,"source":item.get("source",''),"excerpt":text})
    return None
