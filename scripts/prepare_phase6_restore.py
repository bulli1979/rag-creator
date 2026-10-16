#!/usr/bin/env python3
"""Prepare private settings/catalogue/files for an isolated restore drill.

Run in an API utility container with the original data volume READ ONLY at
/snapshot, a private new directory at /restore, and the original SQLite backup
at /backup/index.sqlite. Never reads chat_audit or decrypts existing conversations.
Only aggregate counts and hashes go in the public receipt.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['legacy','current'],required=True)
    parser.add_argument('--database-name',help='Distinct database in the isolated restore container')
    args=parser.parse_args()
    root=Path('/restore')
    if (root/'settings.json').exists():
        raise ValueError('Restore destination must be new')
    os.umask(0o077)
    settings_name='settings.before-recovery.json' if args.mode=='legacy' else 'settings.json'
    chat_name='chat_settings.before-recovery.json' if args.mode=='legacy' else 'chat_settings.json'
    settings=json.loads((Path('/snapshot')/settings_name).read_text())
    active=settings['activePostgresEnvironmentId']
    pg=next(e for e in settings['postgresEnvironments'] if e['id']==active)
    pg.update(dbHost='notbot-phase6-restore-pg',dbPort=5432,dbName=args.database_name or args.mode,
              dbUser='postgres',dbPassword='',vectorBackend='postgres')
    # Never retain a fallback pointing at the real database in the test config.
    settings['postgresEnvironments']=[pg]
    (root/'settings.json').write_text(json.dumps(settings,indent=2)+'\n')
    (root/'chat_settings.json').write_bytes((Path('/snapshot')/chat_name).read_bytes())
    boosts=Path('/snapshot/source_boosts.json')
    if boosts.is_file():
        (root/'source_boosts.json').write_bytes(boosts.read_bytes())
    source=Path('/backup/index.sqlite') if args.mode=='legacy' else Path('/snapshot/index.sqlite')
    with sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True) as src:
        with sqlite3.connect(root/'index.sqlite') as dst:
            src.backup(dst)
    for name in ('files','corpus'):
        path=Path('/snapshot')/name
        if path.is_dir():
            shutil.copytree(path,root/name)
    # Shared model caches are mounted read-only; no runtime model download.
    (root/'model_cache').symlink_to('/snapshot/model_cache',target_is_directory=True)
    with sqlite3.connect(root/'index.sqlite') as conn:
        status=dict(conn.execute('SELECT status,count(*) FROM documents WHERE environmentId=? GROUP BY status',(active,)))
        records=conn.execute('SELECT filePath FROM documents WHERE environmentId=?',(active,)).fetchall()
        missing=sum(not (root/Path(path).relative_to('/data')).is_file()
                    if Path(path).is_relative_to('/data') else not Path(path).is_file()
                    for path, in records)
        integrity=conn.execute('PRAGMA integrity_check').fetchone()[0]
    if any(status.get(s,0) for s in ('queued','processing','pending','indexing')):
        raise ValueError('Catalogue snapshot contains unfinished ingestion; do not start restore API')
    report={'mode':args.mode,'environment':active,'table':pg['dbSchema']+'.'+pg['dbTableName'],
            'embeddingModel':settings['embeddingModel'],'catalogueStatuses':status,
            'catalogueIntegrity':integrity,'missingCatalogueFiles':missing,
            'privateSettingsMode':oct((root/'settings.json').stat().st_mode & 0o777),
            'catalogueSha256':hashlib.sha256((root/'index.sqlite').read_bytes()).hexdigest(),
            'isolation':'Distinct PostgreSQL container/database; sole environment points only at restore target',
            'limitations':'Document file directories recovered from retained live store, not an immutable dated file backup; historical audits excluded'}
    (root/'preparation-receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    if integrity!='ok':
        raise ValueError('SQLite integrity check failed')


if __name__=='__main__':
    main()
