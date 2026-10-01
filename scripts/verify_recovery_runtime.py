#!/usr/bin/env python3
"""Read-only public receipt of recovery pointer/index/runtime consistency.

Run in the API container. Never prints settings, credentials or document text.
Uses aggregate SQL in a read-only transaction and explicit public smoke input.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
sys.path.insert(0, '/app')
import psycopg2
from psycopg2 import sql
from app.config import load_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image-id', required=True)
    parser.add_argument('--expected-app-sha256', required=True)
    args = parser.parse_args()
    def call(path, payload=None):
        request = Request('http://localhost:8000'+path, data=json.dumps(payload).encode() if payload else None,
                          headers={'Content-Type':'application/json'})
        with urlopen(request, timeout=240) as response:
            return json.load(response)
    settings=load_settings()
    pg=settings.get_active_postgres()
    table=sql.Identifier(pg.db_schema,pg.db_table_name)
    digest=hashlib.sha256()
    for path in sorted(Path('/app/app').rglob('*.py')):
        digest.update(str(path.relative_to('/app')).encode()); digest.update(path.read_bytes())
    receipt={'verifiedAt':datetime.now(timezone.utc).isoformat(), 'imageId':args.image_id,
             'appPythonSha256':digest.hexdigest(),
             'environment':pg.environment_id,'table':pg.db_schema+'.'+pg.db_table_name,
             'embeddingModel':settings.embedding_model,'health':call('/api/health')}
    with psycopg2.connect(host=pg.db_host,port=pg.db_port,dbname=pg.db_name,user=pg.db_user,password=pg.db_password) as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute(sql.SQL('SELECT count(*),count(DISTINCT source_id),count(DISTINCT document_id),min(vector_dims(embedding)),max(vector_dims(embedding)) FROM {} WHERE is_active').format(table))
            receipt['activeChunks'],receipt['activeSources'],receipt['activeDocuments'],receipt['minVectorDimensions'],receipt['maxVectorDimensions']=cur.fetchone()
            cur.execute(sql.SQL('SELECT DISTINCT corpus_version FROM {} WHERE is_active').format(table))
            receipt['activeCorpusVersions']=[row[0] for row in cur.fetchall()]
            cur.execute(sql.SQL('SELECT count(*) FROM (SELECT source_id FROM {} WHERE is_active GROUP BY source_id HAVING count(DISTINCT document_id)>1) s').format(table))
            receipt['sourcesWithMultipleActiveVersions']=cur.fetchone()[0]
            cur.execute(sql.SQL('SELECT count(*)-count(DISTINCT text_content) FROM {} WHERE is_active').format(table))
            receipt['exactDuplicateIndexRows']=cur.fetchone()[0]
            cur.execute(sql.SQL('SELECT count(*) FROM {} WHERE is_active AND content_types=%s::jsonb').format(table),('["heading"]',))
            receipt['headingOnlyIndexRows']=cur.fetchone()[0]
            cur.execute(sql.SQL('SELECT count(*) FROM {} WHERE is_active AND (canonical_location ILIKE %s OR file_name ILIKE %s)').format(table),('%/csc_reports/%','%csc-report%'))
            receipt['activeCSCChunks']=cur.fetchone()[0]
            cur.execute(sql.SQL('SELECT count(*) FROM {} WHERE is_active AND text_content LIKE %s').format(table),('%(cid:%',))
            receipt['unresolvedCIDChunks']=cur.fetchone()[0]
    response=call('/api/chat',{'message':'What is the on-sky aperture of FIES fiber #4?','history':[],'language':'en'})
    receipt['smoke']={key:response.get(key) for key in ('answer','metrics')}
    receipt['smoke']['trace']={key:response.get('trace',{}).get(key) for key in ('indexId','embeddingModel','corpusVersion','model','answerMethod')}
    args.output.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
    if (digest.hexdigest()!=args.expected_app_sha256 or receipt['minVectorDimensions']!=1024
            or receipt['maxVectorDimensions']!=1024 or receipt['activeCorpusVersions']!=['recovery-2026-09-30-v9']
            or receipt['sourcesWithMultipleActiveVersions'] or receipt['activeCSCChunks']
            or receipt['unresolvedCIDChunks'] or response.get('metrics',{}).get('abstained')):
        raise RuntimeError('Runtime consistency checks failed')


if __name__=='__main__':
    main()
