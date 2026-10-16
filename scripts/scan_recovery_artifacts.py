#!/usr/bin/env python3
"""Narrow secret-pattern check of Git-visible changed/untracked text artifacts.

Does not inspect ignored settings, audits or corpus directories; never prints
matching secret text. This is a leak smoke check, not a security certification.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    paths=set()
    for command in (['git','diff','--name-only','-z'],['git','ls-files','--others','--exclude-standard','-z']):
        paths.update(name for name in subprocess.check_output(command,cwd=root).decode().split('\0') if name)
    patterns={
        'private-key':re.compile(r'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----'),
        'github-token':re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b'),
        'api-token':re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}\b'),
        'credential-url':re.compile(r'\b(?:postgres(?:ql)?|mysql|https?)://[^\s/:]+:[^\s/@]+@'),
    }
    scanned=0; hits=[]
    for name in sorted(paths):
        path=root/name
        if not path.is_file() or path.suffix.lower() not in ('.py','.js','.php','.json','.md','.txt','.yml','.yaml','.toml','.patch'):
            continue
        text=path.read_text(errors='replace'); scanned+=1
        for label,pattern in patterns.items():
            if pattern.search(text):
                hits.append({'file':name,'pattern':label})
    report={'scannedTextArtifacts':scanned,'patternMatches':hits,'scope':'Git-visible changed/untracked text only; ignored runtime/corpus data excluded','certification':False}
    args.output.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report))
    if hits:
        raise SystemExit(1)


if __name__=='__main__':
    main()
