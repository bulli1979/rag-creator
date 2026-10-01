"""Conservative verbatim fallback for tightly matched factual documentation.

This is not synthesized knowledge: when generation fails, a short relevant
source paragraph can still be useful. Never use this path for safety decisions,
complete procedures, unnamed component values or current design-paper claims.
"""
import re
from .grounding import ValidationResult, _question_topics, _identifier_numbers
from .literal_answers import LiteralAnswer
from .evidence_selection import classify_query


def answer_excerpt(query,evidence,language='en'):
    if language!='en' or re.search(r'\b(?:how|sequence|procedure|steps|must|safe|bypass|override|interlock|fault|error)\b',query,re.I):
        return None
    intent=classify_query(query)
    topics=_question_topics(query)-set('observed mentioned provided introduced physical specific fundamental'.split())
    if len(topics)<2:
        return None
    products=re.findall(r'\b(?:SI[- ]?\d+[A-Z]?|CCD\d+-\d+)\b',query,re.I)
    requested_ids=_identifier_numbers(query)
    options=[]
    for item in evidence:
        reference='technical_reference' in intent.categories or intent.historical
        role=item.get('sourceRole','')
        if item.get('status') not in ('active','current','historical','reference_only'):
            continue
        if role in ('historical_section','design_reference') and not reference:
            continue
        if intent.instruments and item.get('instrument','').upper() not in intent.instruments:
            continue
        scope=item.get('title','')+' '+item.get('section','')+' '+item['content']
        if products and not all(re.search(re.escape(product),scope,re.I) for product in products):
            continue
        for paragraph in re.split(r'\n\s*\n',item['content']):
            paragraph=paragraph.strip()
            if (not 30<=len(paragraph)<=850 or paragraph.startswith(('#','|','```'))
                    or not re.search(r'\d',paragraph) or not requested_ids.issubset(_identifier_numbers(paragraph))):
                continue
            overlap=len(topics & _question_topics(paragraph))
            if overlap<max(3,.70*len(topics)):
                continue
            options.append((overlap/len(topics),item,paragraph))
    if not options:
        return None
    options.sort(key=lambda option:option[0],reverse=True)
    _,item,text=options[0]
    prefix='Documentation excerpt: '
    if item.get('status')=='historical' or item.get('sourceRole')=='historical_section':
        prefix='Historical record (not current guidance): '
    elif item.get('sourceRole')=='design_reference':
        prefix='Technical report (not current operating guidance): '
    return LiteralAnswer(ValidationResult(prefix+text+f" [{item['citationId']}]",1,0,0,False),
                         {'operation':'matched-verbatim-reference-fallback-v1','citationId':item['citationId'],'excerpt':text})
