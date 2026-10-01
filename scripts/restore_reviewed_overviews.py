#!/usr/bin/env python3
"""Build a new private corpus generation, adding hash-bound reviewed prose only.

An isolated damaged glyph in a specification table must not suppress an intact
instrument definition. The approved paragraph is copied from the preserved raw
HTML; damaged tables are NOT reactivated. Originals and v9 are never edited.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'documentApi'))
from app.document_processing import parse_frontmatter,scrub_sensitive_text
from app.html_processing import html_to_markdown


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous',type=Path,required=True)
    parser.add_argument('--crawl',type=Path,required=True)
    parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--version',required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise ValueError('Choose a new private corpus destination')
    records=json.loads(args.review.read_text())
    def encode(metadata,body):
        metadata.update(corpus_version=args.version,content_hash=hashlib.sha256(body.encode()).hexdigest())
        return '---\n'+'\n'.join(f'{k}: {json.dumps(v,ensure_ascii=False)}' for k,v in metadata.items())+'\n---\n\n'+body
    destination=args.output/'searchable'
    destination.mkdir(parents=True,mode=0o700)
    unchanged=0
    for path in sorted((args.previous/'searchable').glob('*.md')):
        metadata,body=parse_frontmatter(path.read_text())
        (destination/path.name).write_text(encode(metadata,body))
        unchanged+=1
    restored=[]
    for record in records:
        if (destination/record['file']).exists():
            raise ValueError('Reviewed addition would overwrite a retained source')
        raw=args.crawl/record['rawPath']
        if hashlib.sha256(raw.read_bytes()).hexdigest()!=record['sourceHash']:
            raise ValueError('Reviewed raw source changed')
        paragraphs=html_to_markdown(raw.read_text(encoding='utf-8')).split('\n\n')
        matches=[' '.join(p.split()) for p in paragraphs
                 if ' '.join(p.split()).startswith(record['paragraphPrefix'])]
        if len(matches)!=1 or '\ufffd' in matches[0] or not matches[0].endswith('.'):
            raise ValueError('Reviewed paragraph is ambiguous, damaged or incomplete')
        body=scrub_sensitive_text(matches[0])+'\n'
        # Public prose is not a reason to bypass producer contact/secret filters.
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'NOTBot-documents'))
        from scrubber import scrub
        body=scrub(body,source_label=record['file'])
        metadata={'title':record['title'],'source_url':record['url'],'source_hash':record['sourceHash'],
                  'instrument':record['instrument'],'category':'instrument_documentation',
                  'authority':'tier_2_reference','status':'active','extraction_scope':'reviewed intact definition paragraph only; damaged specifications remain excluded'}
        (destination/record['file']).write_text(encode(metadata,body))
        restored.append({'file':record['file'],'url':record['url'],'sourceHash':record['sourceHash'],
                         'scope':metadata['extraction_scope']})
    receipt={'corpusVersion':args.version,'retainedDocuments':unchanged,
             'documentsBuilt':len(list(destination.glob('*.md'))),'reviewedAdditions':restored,
             'scope':'No recrawl or deleted originals; one intact public paragraph, not the damaged specification table'}
    args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':
    main()
