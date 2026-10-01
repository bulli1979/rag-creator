"""Bounded topic-matched reference expansion inside the existing corpus only."""
import re
from urllib.parse import urljoin,urlsplit,parse_qsl

_FILLER=set('what which how does do is are the a an of for to in on at and report documentation instrument not telescope'.split())


def canonical_key(url):
    parsed=urlsplit(url)
    if parsed.scheme not in ('http','https') or parsed.hostname not in ('www.not.iac.es','not.iac.es'):
        return None
    return (parsed.path.rstrip('/').lower(),tuple(sorted(parse_qsl(parsed.query))))


def _terms(text):
    text=re.sub(r'\b(?:second|2nd)\s*[- ]?order\b','secondorder',text,flags=re.I)
    text=re.sub(r'\b(?:fibre|fibres)\b','fiber',text,flags=re.I)
    return {w.lower().rstrip('s') for w in re.findall(r'[a-zA-Z]+',text) if len(w)>2} - _FILLER


def matching_reference_links(query,chunks,max_documents=3):
    terms=_terms(query)
    matches={}
    for chunk in chunks[:80]:
        base=chunk.get('canonicalLocation','')
        if canonical_key(base) is None:
            continue
        for label,target in re.findall(r'\[([^\]]+)\]\(([^\s)]+)\)',chunk.get('text','')):
            target=urljoin(base,target)
            key=canonical_key(target)
            if key is None or not urlsplit(target).path.lower().endswith(('.pdf','.html','.htm','.php','/')):
                continue
            score=len(terms & _terms(label))
            if score<2:
                continue
            parsed=urlsplit(target)
            slug=re.sub(r'[^a-zA-Z0-9]+','-',parsed.path.strip('/')).strip('-').lower() or 'index'
            if parsed.query:
                slug+='-'+re.sub(r'[^a-zA-Z0-9]+','-',parsed.query).strip('-').lower()
            matches[key]=(score,slug+'.md',target)
    return [(pattern,url) for _,pattern,url in sorted(matches.values(),reverse=True)[:max_documents]]
