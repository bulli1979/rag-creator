"""Exact property lookup in indexed current numbered component tables."""
import re
from .grounding import ValidationResult
from .literal_answers import LiteralAnswer
from .evidence_selection import classify_query


def answer_component_table(query,evidence,language='en'):
    if language!='en' or re.search(r'\b(?:why|can|safe|contamination)\b',query,re.I):
        return None
    intent=classify_query(query)
    if 'technical_reference' in intent.categories or intent.historical:
        products=re.findall(r'\b(?:SI[- ]?\d+[A-Z]?|CCD\d+-\d+)\b',query,re.I)
        terms=set(re.findall(r'[a-z0-9]+',query.lower()))
        for item in evidence:
            if item.get('status') not in ('active','current','historical','reference_only'):
                continue
            if intent.instruments and item.get('instrument','').upper() not in intent.instruments:
                continue
            if products and not all(re.search(re.escape(p),item.get('title','')+' '+item['content'],re.I) for p in products):
                continue
            lines=item['content'].splitlines()
            for i,line in enumerate(lines[:-1]):
                if not line.strip().startswith('|') or not re.match(r'^\s*\|\s*:?-',lines[i+1]):
                    continue
                header=[c.strip() for c in line.strip().strip('|').split('|')]
                columns=[j for j,h in enumerate(header) if j and len(re.findall(r'[a-z0-9]+',h.lower()))>=2
                         and set(re.findall(r'[a-z0-9]+',h.lower())).issubset(terms)]
                if len(columns)!=1:
                    continue
                rows=[]
                for row in lines[i+2:]:
                    if not row.strip().startswith('|'):
                        break
                    cells=[c.strip() for c in row.strip().strip('|').split('|')]
                    row_terms=set(re.findall(r'[a-z0-9]+',cells[0].lower()))
                    if len(cells)==len(header) and len(row_terms)>=2 and row_terms.issubset(terms) and re.search(r'\d',cells[columns[0]]):
                        rows.append(cells)
                if len(rows)==1:
                    row=rows[0]; column=columns[0]
                    prefix='Historical record (not current guidance): ' if item.get('status')=='historical' else 'Technical reference: '
                    text=f"{prefix}{header[column]}, {row[0]}: {row[column]}. [{item['citationId']}]"
                    return LiteralAnswer(ValidationResult(text,1,0,0,False),
                                         {'operation':'scoped-matrix-cell-lookup-v1','citationId':item['citationId'],'row':row,'column':header[column]})
        return None
    if re.search(r'\b(?:history|report)\b',query,re.I):
        return None
    instruments=classify_query(query).instruments
    if len(instruments)==1:
        instrument=next(iter(instruments))
        for item in evidence:
            if item.get('sourceRole') not in ('operator_guide','current_reference') or item.get('status') not in ('active','current'):
                continue
            lines=item['content'].splitlines()
            for i,line in enumerate(lines):
                header=[c.strip() for c in line.strip().strip('|').split('|')]
                if not line.strip().startswith('|') or header[0].lower()!='instrument':
                    continue
                indices=[j for j,h in enumerate(header) if j and re.fullmatch(r'[a-z]+(?:-[a-z]+)+',h,re.I)
                         and re.search(r'(?<!\w)'+re.escape(h)+r'(?!\w)',query,re.I)]
                if not indices:
                    continue
                for row in lines[i+1:]:
                    if not row.strip().startswith('|'):
                        break
                    cells=[c.strip() for c in row.strip().strip('|').split('|')]
                    if len(cells)==len(header) and cells[0].upper()==instrument and all(cells[j] for j in indices):
                        values='; '.join(f'{header[j]}: {cells[j]}' for j in indices)
                        return LiteralAnswer(ValidationResult(f'{instrument} — {values}. [{item["citationId"]}]',1,0,0,False),
                                             {'operation':'instrument-setting-table-lookup-v1','citationId':item['citationId'],'row':cells,'header':header})
    match=re.search(r'\b(grism|filter)\s*(?:#|number\s*)?(\d+)\b|\bG#(\d+)\b',query,re.I)
    if not match:
        return None
    entity=(match[1] or 'grism').lower(); identifier=match[2] or match[3]
    properties=[p for p in ('central','dispersion','resolution','diameter') if re.search(r'\b'+p+r'\b',query,re.I)]
    if not properties:
        return None
    for item in evidence:
        if item.get('sourceRole')!='current_reference' or item.get('status') not in ('active','current'):
            continue
        lines=item['content'].splitlines()
        for i,line in enumerate(lines):
            if not line.strip().startswith('|'):
                continue
            header=[c.strip() for c in line.strip().strip('|').split('|')]
            if not header or header[0].lower()!=entity:
                continue
            indices=[j for j,label in enumerate(header) if any(re.search(r'\b'+p+r'\b',label,re.I) for p in properties)]
            if not all(any(re.search(r'\b'+p+r'\b',header[j],re.I) for j in indices) for p in properties):
                continue
            units={}; rows=[]
            for row in lines[i+1:]:
                if not row.strip().startswith('|'):
                    break
                cells=[c.strip() for c in row.strip().strip('|').split('|')]
                if len(cells)!=len(header):
                    break
                if cells[0].lower()==entity:
                    units={j:cells[j] for j in indices if re.fullmatch(r'\[[^\]]+\]',cells[j])}
                if re.fullmatch(re.escape(identifier)+r'(?:\s+[a-z])?',cells[0],re.I):
                    rows.append(cells)
            if len(rows)!=1 or any(not rows[0][j] for j in indices):
                continue
            values='; '.join(f"{header[j]}: {rows[0][j]} {units.get(j,'')}".strip() for j in indices)
            text=f"{item.get('instrument','')} {entity} #{identifier} — {values}. [{item['citationId']}]".strip()
            return LiteralAnswer(ValidationResult(text,1,0,0,False),
                                 {'operation':'current-component-table-lookup-v1','citationId':item['citationId'],
                                  'identifier':identifier,'header':header,'row':rows[0]})
    return None
