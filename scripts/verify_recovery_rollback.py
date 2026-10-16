#!/usr/bin/env python3
"""Exercise a reversible local index/embedding pointer switch, then restore it.

Run in the API container only after indexing finishes. The pre-switch settings
backup may contain credentials and is written mode 0600 under /data. The public
receipt contains only index identifiers, status and a public test answer.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.request import Request,urlopen


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-settings',type=Path,required=True)
    parser.add_argument('--private-backup',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--api',default='http://127.0.0.1:8000')
    args=parser.parse_args()
    if args.private_backup.exists():
        raise ValueError('Private backup already exists; choose a new path')
    def call(path,payload=None,method=None):
        request=Request(args.api+path,data=json.dumps(payload).encode() if payload is not None else None,
                        headers={'Content-Type':'application/json'},method=method)
        with urlopen(request,timeout=240) as response:
            return json.load(response)
    current=call('/api/settings')
    if any(d.get('status') in ('pending','queued','processing','indexing') for d in call('/api/documents')):
        raise ValueError('Wait for indexing before switching the pointer')
    old=json.loads(args.old_settings.read_text())
    if old['activePostgresEnvironmentId']==current['activePostgresEnvironmentId']:
        raise ValueError('Backup is not a different index pointer')
    fd=os.open(args.private_backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as handle:
        json.dump(current,handle)
    rollback={**current,'activePostgresEnvironmentId':old['activePostgresEnvironmentId'],
              'embeddingModel':old['embeddingModel']}
    old_environment=next(e for e in old['postgresEnvironments'] if e['id']==old['activePostgresEnvironmentId'])
    rollback['postgresEnvironments']=[e for e in current['postgresEnvironments'] if e['id']!=old_environment['id']]+[old_environment]
    receipt={'rollbackEnvironment':old_environment['id'],'rollbackEmbeddingModel':old['embeddingModel']}
    def smoke():
        result=call('/api/chat',{'message':'What is the on-sky aperture of FIES fiber #4?','history':[],'language':'en'})
        return {'answer':result['answer'],'abstained':result.get('metrics',{}).get('abstained'),
                'indexId':result.get('trace',{}).get('indexId'),'corpusVersion':result.get('trace',{}).get('corpusVersion')}
    try:
        call('/api/settings',rollback,'PUT')
        receipt['rollbackConnection']=call('/api/database/test-connection',{},'POST').get('status')
        receipt['rollbackSmoke']=smoke()
    finally:
        call('/api/settings',current,'PUT')
        receipt['originalSettingsRestored']=call('/api/settings')==current
    receipt['restoredConnection']=call('/api/database/test-connection',{},'POST').get('status')
    receipt['restoredSmoke']=smoke()
    args.report.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
    if not receipt['originalSettingsRestored'] or receipt['restoredConnection']!='ok' or receipt['restoredSmoke']['abstained']:
        raise RuntimeError('Restored index verification failed; consult the private settings backup')


if __name__=='__main__':
    main()
