"""Source-extractive weather rules and explicit application safety boundaries."""
import re
from .grounding import ValidationResult
from .literal_answers import LiteralAnswer


def answer_operational(query: str, evidence: list[dict], language: str = "en") -> LiteralAnswer | None:
    # Copy an explicit seasonal road advisory INCLUDING its requirement to
    # check current road/weather conditions. This does not report live access
    # conditions or infer permission to travel between the listed hours.
    if language=='en' and re.search(r'\bwinter\b',query,re.I) and re.search(r'\broad\b',query,re.I):
        for item in evidence:
            if item.get('sourceRole')!='operator_guide' or item.get('status') not in ('active','current'):
                continue
            sentences=re.split(r'(?<=[.!?])\s+(?=[A-Z])',' '.join(item['content'].split()))
            for i,sentence in enumerate(sentences):
                if not re.search(r'\bwinter period\b',sentence,re.I):
                    continue
                passage=' '.join(sentences[i:i+3])
                if (len(passage)>900 or len(re.findall(r'\b\d{1,2}:\d{2}\b',passage))<2
                        or not re.search(r'not to travel.*road',passage,re.I)
                        or not re.search(r'always contact.*latest road.*weather conditions',passage,re.I)
                        or not re.search(r'before travelling',passage,re.I)):
                    continue
                return LiteralAnswer(ValidationResult(f'Cited site safety advisory: {passage} [{item["citationId"]}]',1,0,0,False),
                                     {'operation':'seasonal-road-advisory-excerpt-v1','citationId':item['citationId'],'excerpt':passage})
    # A troubleshooting entry's quoted error is a prerequisite, not decoration.
    # Do not silently turn one specific recovery recipe into advice for ANY
    # startup error. Ask for the error before choosing hardware actions.
    if language=='en' and re.search(r'\berror\b',query,re.I) and re.search(r'\bstart\b',query,re.I):
        systems=re.findall(r'\b[A-Z][A-Z0-9_]{1,}\b',query)
        for item in evidence:
            if item.get('sourceRole')!='operator_guide' or item.get('status') not in ('active','current'):
                continue
            for block in re.split(r'(?m)^\*\s+',item['content']):
                if not systems or not all(re.search(r'\b'+re.escape(name)+r'\b',block) for name in systems):
                    continue
                error=re.search(r'"([^"\n]*(?:\n[^"\n]*)*)"',block)
                if not error or not re.search(r'\b(?:power cycle|restart|disconnect)\b',block,re.I):
                    continue
                message=' '.join(error[1].split())
                if not 10<=len(message)<=200 or message.lower() in ' '.join(query.split()).lower():
                    continue
                answer=(f'Please provide the exact error message. The cited guide gives a conditional remedy for '
                        f'"{message}"; an unspecified startup error does not establish that this remedy applies. '
                        f'[{item["citationId"]}]')
                return LiteralAnswer(ValidationResult(answer,0,0,0,True),
                                     {'operation':'conditional-error-clarification-v1','citationId':item['citationId'],'errorCondition':message})
    bypass = (re.search(r"\b(?:bypass|override|disable|circumvent)\b",query,re.I)
              and re.search(r"\b(?:safety|interlock)\b",query,re.I))
    humidity = bool(re.search(r"\b(?:humidity|humid|Luftfeuchtigkeit)\b", query, re.I))
    wind = bool(re.search(r'\b(?:wind|wind speed)\b',query,re.I))
    if re.search(r'\bweather\b',query,re.I) and not (humidity or wind):
        humidity=wind=True
    closure = bool(re.search(r"\b(?:above|exceeds?|over|high|must|do|close|closing|reopen|reopening)\b", query,re.I))
    if not bypass and not ((humidity or wind) and closure):
        return None
    relevant = []
    for item in evidence:
        if item.get("sourceRole") != "operator_guide" or item.get("status") not in ("active","current"):
            continue
        weather_columns = {}
        for line in item["content"].splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if "|" not in line:
                weather_columns = {}
                continue
            for index, cell in enumerate(cells):
                if humidity and re.fullmatch(r"Humidity", cell, re.I):
                    weather_columns['Humidity'] = index
                if wind and re.fullmatch(r'Wind',cell,re.I):
                    weather_columns['Wind'] = index
            # The NOT cookbooks also present weather types as column headers.
            for condition,index in weather_columns.items():
                if index < len(cells):
                    cell = cells[index]
                    if re.search(r'\d',cell) and re.search(r"\bclose\b",cell,re.I):
                        relevant.append((item,cell,[condition, "", cell]))
            # A condition/limit/action row, not an unrelated reset procedure.
            if (len(cells) >= 3 and ((humidity and re.search(r"humidity", cells[0], re.I))
                                    or (wind and re.search(r'wind',cells[0],re.I)))
                    and re.search(r'\d',cells[1])
                    and re.search(r"\bclose\b",cells[-1],re.I)):
                relevant.append((item, line.strip(), cells))
    policy = ("Nein. Ich gebe keine Anleitung zum Umgehen von Sicherheitsverriegelungen."
              if language == "de" else
              "No. I won't provide instructions to bypass a safety interlock.") if bypass else ""
    if not relevant:
        if bypass:
            return LiteralAnswer(ValidationResult(policy,0,0,0,True), {"operation":"safety-boundary-v1"})
        return None
    # Copy conditions and ordered instructions exactly. No numerical limits or
    # wait times are embedded in the implementation.
    rendered=[]; excerpts=[];seen=set()
    for item,excerpt,cells in relevant:
        instruction=f"{cells[0]} {cells[1]}: {cells[-1]}"
        if instruction in seen:
            continue
        seen.add(instruction)
        rendered.append(instruction+f" [{item['citationId']}]")
        excerpts.append({'citationId':item['citationId'],'excerpt':excerpt})
    answer=(policy+'\n\n' if policy else '')+'\n\n'.join(rendered)
    return LiteralAnswer(ValidationResult(answer,len(rendered),0,0,False),
                         {"operation":"operator-rule-extract-v1","rules":excerpts})
