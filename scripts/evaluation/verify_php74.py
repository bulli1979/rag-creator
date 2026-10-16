#!/usr/bin/env python3
"""Programmatic integration of a separate PHP7.4 CLI fixture, not a browser test."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.request import Request,urlopen


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='http://127.0.0.1:8093')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    checks=[]
    def call(data=None,method='POST',content_type='application/json',raw=None):
        body=raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
        request=Request(args.base+'/proxy.php',data=body,method=method,headers={'Content-Type':content_type})
        try:
            response=urlopen(request,timeout=240)
        except HTTPError as exc:
            response=exc
        with response:
            text=response.read().decode()
            return response.status,json.loads(text),response.headers.get('X-Powered-By','')
    for name,kwargs,expected in (
        ('non_POST',{'method':'GET'},405),
        ('non_JSON_content_type',{'raw':b'{}','content_type':'text/plain'},400),
        ('malformed_JSON',{'raw':b'{'},400),
        ('body_limit',{'raw':b'x'*65537},413),
        ('API_validation_error',{'data':{'message':[],'history':[]}},422)):
        status,body,version=call(**kwargs)
        checks.append({'id':name,'passed':status==expected,'status':status,'phpHeader':version})
    status,health,version=call({'health_check':True})
    checks.append({'id':'PHP74_health_proxy','passed':status==200 and version.startswith('PHP/7.4.')
                   and health.get('pythonWorker',{}).get('status')=='ok','status':status,'phpHeader':version})
    chains=[[
        ('fies_intro','What is FIES?',r'FIES.*spectrograph'),
        ('fies_typo','how many fivers are available?',r'four|4'),
        ('fies_aperture','And the diameter on the sky of fibre number 4?',r'1\.3'),
    ],[
        ('notcam_intro','What is NOTCAM?',r'infrared|SWIR'),
        ('notcam_followup','can the instrument be used to observer at 500nm?',r'below|outside|cannot|no'),
        ('topic_switch','What is FIES?',r'FIES.*spectrograph'),
    ]]
    for chain in chains:
        history=[]
        for name,question,pattern in chain:
            status,result,version=call({'message':question,'history':history,'language':'en'})
            answer=result.get('answer','')
            cites=set(re.findall(r'\[(D-[a-f0-9]+-C\d+)\]',answer))
            supplied={c.get('citationId') for c in result.get('contextChunks',[])}
            checks.append({'id':name,'passed':status==200 and bool(re.search(pattern,answer,re.I|re.S))
                           and bool(cites) and cites.issubset(supplied) and not result.get('metrics',{}).get('abstained'),
                           'status':status,'answer':answer,'citationIds':sorted(cites),
                           'trace':{k:result.get('trace',{}).get(k) for k in ('indexId','corpusVersion','contextResolution')}})
            history.extend([{'role':'user','content':question},{'role':'assistant','content':answer}])
    status,result,version=call({'action':'log','entries':[{'id':'phase6-public-fixture','q':'What is NOTCAM?',
                                                       'a':'Public synthetic logging integration fixture.','feedback':'up'}]})
    checks.append({'id':'isolated_public_log_and_feedback','passed':status==200 and result.get('ok') is True,'status':status})
    receipt={'verifiedAt':datetime.now(timezone.utc).isoformat(),'complete':True,'checks':checks,
             'passed':sum(c['passed'] for c in checks),'total':len(checks),
             'scope':'Separate PHP7.4 CLI fixture/proxy; not the actual target server, not a browser or visual-history check'}
    args.output.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
    return 0 if all(c['passed'] for c in checks) else 1


if __name__=='__main__':
    raise SystemExit(main())
