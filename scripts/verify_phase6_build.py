#!/usr/bin/env python3
"""Offline package/source identity and import receipt inside a clean image."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image-id',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    modules=['torch','sentence_transformers','unstructured.partition.auto','psycopg2','app.main']
    imported=[]
    for name in modules:
        importlib.import_module(name); imported.append(name)
    check=subprocess.run(['python','-m','pip','check'],capture_output=True,text=True)
    digest=hashlib.sha256()
    for path in sorted(Path('/app/app').rglob('*.py')):
        digest.update(str(path.relative_to('/app')).encode()); digest.update(path.read_bytes())
    receipt={'verifiedAt':datetime.now(timezone.utc).isoformat(),'imageId':args.image_id,
             'python':platform.python_version(),'architecture':platform.machine(),
             'appPythonSha256':digest.hexdigest(),'criticalImports':imported,
             'pipCheckPassed':check.returncode==0,'pipCheck':check.stdout.strip(),
             'resolvedPackages':{d.metadata['Name']:d.version for d in sorted(distributions(),key=lambda d:d.metadata['Name'].lower())},
             'buildProvenance':'Dockerfile dependency stages built with --pull --no-cache from python:3.12-slim-bookworm; final COPY uses those fresh stages, not the retained recovery image',
             'scope':'Host architecture build only; no assertion that floating dependency ranges reproduce the same versions on another date'}
    args.output.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='resolvedPackages'}))
    if check.returncode:
        raise RuntimeError('Clean build dependency consistency failed')


if __name__=='__main__':
    main()
