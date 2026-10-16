#!/usr/bin/env python3
"""Aggregate SQL and API checks INSIDE a Phase 6 isolated restore container."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.request import Request,urlopen
sys.path.insert(0,'/app')
import psycopg2
from psycopg2 import sql
from app.config import load_settings


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=['legacy','current'],required=True)
    parser.add_argument('--image-id',required=True)
    parser.add_argument('--database-name')
    parser.add_argument('--expected-corpus-version',default='recovery-2026-09-30-v9')
    parser.add_argument('--expected-active-documents',type=int,default=482)
    parser.add_argument('--expected-active-chunks',type=int,default=5478)
    args=parser.parse_args()
    pg=load_settings().get_active_postgres()
    if pg.db_host!='notbot-phase6-restore-pg' or pg.db_name!=(args.database_name or args.mode):
        raise ValueError('Not an isolated restore target')
    def call(path,payload=None):
        req=Request('http://127.0.0.1:8000'+path,data=json.dumps(payload).encode() if payload else None,
                    headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=240) as response:
            return json.load(response)
    receipt={'mode':args.mode,'imageId':args.image_id,'health':call('/api/health')}
    digest=hashlib.sha256()
    for path in sorted(Path('/app/app').rglob('*.py')):
        digest.update(str(path.relative_to('/app')).encode()); digest.update(path.read_bytes())
    receipt['appPythonSha256']=digest.hexdigest()
    with psycopg2.connect(host=pg.db_host,port=pg.db_port,dbname=pg.db_name,user=pg.db_user,password=pg.db_password) as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            table=sql.Identifier(pg.db_schema,pg.db_table_name)
            cur.execute(sql.SQL('SELECT count(*),count(DISTINCT document_id),min(vector_dims(embedding)),max(vector_dims(embedding)) FROM {}').format(table))
            receipt['totalChunks'],receipt['totalDocuments'],receipt['minDimensions'],receipt['maxDimensions']=cur.fetchone()
            cur.execute(sql.SQL('SELECT corpus_version,count(*) FROM {} WHERE is_active GROUP BY corpus_version ORDER BY corpus_version').format(table))
            receipt['activeVersions']=cur.fetchall()
            cur.execute(sql.SQL('SELECT count(*),count(DISTINCT source_id),count(DISTINCT document_id) FROM {} WHERE is_active').format(table))
            receipt['activeChunks'],receipt['activeSources'],receipt['activeDocuments']=cur.fetchone()
            cur.execute(sql.SQL('SELECT count(*) FROM (SELECT source_id FROM {} WHERE is_active GROUP BY source_id HAVING count(DISTINCT document_id)>1) s').format(table))
            receipt['multipleActiveVersions']=cur.fetchone()[0]
    docs=call('/api/documents')
    receipt['catalogueDocuments']=len(docs)
    receipt['cataloguePending']=sum(d.get('status') in ('pending','queued','processing','indexing') for d in docs)
    smoke=[]
    for question in ('What is NOTCAM?', 'What is FIES?', 'What is the on-sky aperture of FIES fiber #4?'):
        started=time.monotonic()
        result=call('/api/chat',{'message':question,'history':[],'language':'en'})
        smoke.append({'question':question,'answer':result.get('answer'),
                      'abstained':result.get('metrics',{}).get('abstained'),
                      'elapsedMs':round((time.monotonic()-started)*1000),
                      'trace':{k:result.get('trace',{}).get(k) for k in ('indexId','embeddingModel','corpusVersion','model','answerMethod')}})
    receipt['smokes']=smoke
    args.output.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
    if not receipt['totalChunks'] or receipt['cataloguePending']:
        raise ValueError('Restore completeness checks failed')
    if args.mode=='current' and (any(s['abstained'] for s in smoke)
                                or receipt['multipleActiveVersions'] or receipt['minDimensions']!=1024
                                or receipt['maxDimensions']!=1024
                                or receipt['activeChunks']!=args.expected_active_chunks
                                or receipt['activeDocuments']!=args.expected_active_documents
                                or receipt['activeVersions']!=[(args.expected_corpus_version,args.expected_active_chunks)]):
        raise ValueError('Current recovery restore acceptance failed')


if __name__=='__main__':
    main()
