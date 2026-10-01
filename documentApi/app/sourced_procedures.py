"""Copy complete, tightly matched procedural sections without model omission."""
import re
from collections import defaultdict
from .literal_answers import LiteralAnswer
from .grounding import ValidationResult
from .evidence_selection import classify_query


def _terms(text):
    text=re.sub(r'\bdownload(?:ing)?\b','get',text,flags=re.I)
    text=re.sub(r'\bsharing\b','share',text,flags=re.I)
    text=re.sub(r'\b(?:abort|interrupt)(?:ing|ed)?\b','interrupt',text,flags=re.I)
    filler=set('how should would what your their with from when while already being event sequence procedure step take frame'.split())
    return {word.rstrip('s') for word in re.findall(r'[a-z]+',text.lower()) if len(word)>3 or word=='get'}-filler


def answer_procedure(query: str,evidence:list[dict],language:str='en') -> LiteralAnswer | None:
    if language != 'en' or not re.search(r'\b(?:how|procedure|process|identify|steps|sequence|share)\b',query,re.I):
        return None
    if re.search(r'\b(?:bypass|override|disable|interlock|fault|error|historical)\b',query,re.I):
        return None
    intent=classify_query(query)
    if intent.instruments:
        evidence=[item for item in evidence if item.get('instrument','').upper()
                  in (*intent.instruments, '', '[MISSING]', 'GENERAL')]
    if re.search(r'\bidentify\b',query,re.I) and re.search(r'\b(?:target|object|star)\b',query,re.I):
        for item in evidence:
            if (item.get('sourceRole')!='operator_guide' or item.get('status') not in ('active','current')
                    or item.get('contentTruncated') or not item.get('sectionBoundariesKnown')
                    or 'fragment' in item.get('contentTypes',[])):
                continue
            for paragraph in re.split(r'\n\s*\n',item['content']):
                if (not 60<=len(paragraph)<=2400 or not re.search(r'\b[a-z]\+[a-z]\b',paragraph,re.I)
                        or not re.search(r'\bidentify\b',paragraph,re.I)
                        or not re.search(r'\b(?:target|object|star)\b',paragraph,re.I)):
                    continue
                if re.search(r'\bOB\b',query,re.I) and not re.search(r'\bOB(?:s|\b)',paragraph,re.I):
                    continue
                text=paragraph.strip()
                if item.get('instrument'):
                    text=f"{item['instrument']} operator-guide instructions:\n\n"+text
                return LiteralAnswer(ValidationResult(text+f" [{item['citationId']}]",1,0,0,False),
                                     {'operation':'complete-keyboard-interaction-v1','citationId':item['citationId'],'excerpt':paragraph.strip()})
    if re.search(r'\bdata\b',query,re.I) and re.search(r'\b(?:share|sharing|team|principal investigator|PI)\b',query,re.I):
        # Access-policy questions need the complete policy, not just its first
        # sentence. Copy a short complete paragraph from the actual data guide.
        for item in evidence:
            if item.get('sourceRole')!='operator_guide' or item.get('status') not in ('active','current'):
                continue
            for p in re.split(r'\n\s*\n',item['content']):
                if (len(p)<900 and re.search(r'principal investigators?',p,re.I)
                        and re.search(r'shar(?:ed|ing|e).*link|link.*shar',p,re.I)):
                    return LiteralAnswer(ValidationResult(p.strip()+f" [{item['citationId']}]",1,0,0,False),
                                         {'operation':'data-access-policy-extract-v1','citationId':item['citationId'],'excerpt':p.strip()})
    # A single control action is often one item in a much longer setup guide.
    # Copy that complete item, not unrelated surrounding startup operations.
    if re.search(r'\b(?:interrupt|abort|cancel)\b',query,re.I):
        wanted=_terms(query)
        options=[]
        for item in evidence:
            if (item.get('sourceRole')!='operator_guide' or item.get('status') not in ('active','current')
                    or item.get('contentTruncated')):
                continue
            for match in re.finditer(r'(?ms)^\d+[.)]\s+.*?(?=^\d+[.)]\s+|^#{1,6}\s|\Z)',item['content']):
                excerpt=match[0].strip()
                # An item cut at a chunk boundary is not a complete instruction.
                if match.end()==len(item['content']) and item.get('nextSection')==item.get('section'):
                    continue
                terms=_terms(excerpt)
                if 'interrupt' in terms and len(wanted & terms)>=max(2,.8*len(wanted)):
                    options.append((len(wanted & terms),item,excerpt))
        if options:
            _,item,text=max(options,key=lambda row:row[0])
            return LiteralAnswer(ValidationResult(text+f" [{item['citationId']}]",1,0,0,False),
                                 {'operation':'complete-control-instruction-v1','citationId':item['citationId'],'excerpt':text})
    groups=defaultdict(list)
    for item in evidence:
        if (item.get('status') in ('active','current') and item.get('sourceRole') in
                ('operator_guide','command_reference','current_reference','reference')
                and item.get('sectionBoundariesKnown') and not item.get('contentTruncated')
                and item.get('authority','').startswith(('tier_1','tier_2'))):
            groups[(item['documentId'],tuple(item.get('headingPath',[])))].append(item)
    for items in groups.values():
        items.sort(key=lambda item:item['chunkIndex'])
        section=items[0]['section']
        # Must have the entire contiguous section, not selected fragments.
        if (not section or items[0]['previousSection']==section or items[-1]['nextSection']==section
                or any(b['chunkIndex'] != a['chunkIndex']+1 for a,b in zip(items,items[1:]))):
            continue
        body='\n\n'.join(item['content'] for item in items)
        if len(body)>3500:
            continue
        commands=re.findall(r'(?:\*\*|`)([a-z][a-z0-9_.-]{3,})(?:\*\*|`)',body,re.I)
        requested_commands=[c for c in commands if re.search(r'(?<!\w)'+re.escape(c)+r'(?!\w)',query,re.I)]
        numbered=list(re.finditer(r'(?m)^\d+[.)]\s+',body))
        text=''
        heading_terms=_terms(section)-{'observing','guide','start','information','general','document','manual'}
        question_terms=_terms(query)
        named_section=bool(heading_terms and heading_terms.issubset(question_terms)
                           and len(question_terms & _terms(body+' '+section))>=.65*len(question_terms))
        if (requested_commands or named_section) and numbered:
            numbers=[int(re.match(r'\d+',m.group())[0]) for m in numbered]
            # Some original guides start at 2; preserve their numbering, never
            # invent a missing step. Internal gaps are unsafe to extract.
            if numbers != list(range(numbers[0],numbers[0]+len(numbers))):
                continue
            # End after the numbered block, preserving wrapped continuations.
            tail=body[numbered[-1].start():]
            end=re.search(r'\n\s*\n(?=[^\s\d])',tail)
            text=body[numbered[0].start():numbered[-1].start()] + (tail[:end.start()] if end else tail)
            if named_section:
                # Preserve prerequisites/policy before a named procedure.
                text=body[:numbered[0].start()]+text
                for prerequisite in evidence:
                    if (prerequisite['documentId']==items[0]['documentId']
                            and prerequisite['section']=='NOT data server'
                            and not prerequisite.get('contentTruncated')):
                        text=prerequisite['content']+'\n\n'+text
                        items=[prerequisite,*items]
                        break
        else:
            # Short, complete, specifically named recipes with actual commands
            # (e.g. a calibration section), not broad chapter dumps.
            if (len(items)==1 and named_section
                    and re.search(r'\b[a-z]+\.[a-z]+\b',body,re.I)
                    and re.search(r'\b(?:take|run|type|give|use)\b',body,re.I)):
                text=body
        if not text or len(text)>4500:
            continue
        citations=' '.join(f"[{item['citationId']}]" for item in items)
        return LiteralAnswer(ValidationResult(f'{text.strip()}\n\n{citations}',1,0,0,False),
                             {'operation':'complete-procedure-extract-v1','citationIds':[item['citationId'] for item in items],
                              'section':section,'excerpt':text})
    return None
