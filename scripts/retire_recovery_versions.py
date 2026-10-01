#!/usr/bin/env python3
"""Retire named recovery/pre-recovery generations after verified indexing.

Run inside the API container, after database/catalogue backups. Never deletes
documents, vectors, files or audit records. All targets are explicit versions.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, "/app")
import psycopg2
from psycopg2 import sql
from app.config import load_settings, get_app_paths

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--current", required=True)
parser.add_argument("--expected-sources", type=int, required=True)
parser.add_argument("--retire", action="append", required=True)
args = parser.parse_args()
if args.current in args.retire:
    raise ValueError("Current version cannot be retired")
pg = load_settings().get_active_postgres()
if pg.vector_backend != "postgres":
    raise ValueError("This recovery retirement targets the PostgreSQL test index only")
conn = psycopg2.connect(host=pg.db_host,port=pg.db_port,dbname=pg.db_name,user=pg.db_user,password=pg.db_password)
table = sql.Identifier(pg.db_schema, pg.db_table_name)
cur = conn.cursor()
cur.execute(sql.SQL("SELECT count(DISTINCT source_id) FROM {} WHERE is_active AND corpus_version=%s").format(table), (args.current,))
if cur.fetchone()[0] != args.expected_sources:
    raise ValueError("Current source count does not match verified recovery corpus")
cur.execute(sql.SQL("SELECT DISTINCT document_id,file_name FROM {} WHERE is_active AND corpus_version=ANY(%s)").format(table), (args.retire,))
targets = cur.fetchall()
cur.execute(sql.SQL("UPDATE {} SET is_active=false WHERE is_active AND corpus_version=ANY(%s)").format(table), (args.retire,))
retired_chunks = cur.rowcount
with sqlite3.connect(get_app_paths()["database"]) as catalogue:
    catalogue.executemany('UPDATE documents SET isActive=0 WHERE docId=? AND environmentId=?',
                          [(doc_id, pg.environment_id) for doc_id, _ in targets])
conn.commit()
print(json.dumps({"retiredDocuments":len(targets), "retiredChunks":retired_chunks,
                  "versions":args.retire,"files":[name for _,name in targets]}))
conn.close()
