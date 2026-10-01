#!/usr/bin/env python3
"""Compare frozen common acceptance cases; never score diagnostic rows as passes."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics


def latency(rows):
    values=sorted(row['elapsedMs'] for row in rows)
    return {'n':len(values),'medianMs':statistics.median(values) if values else None,
            'p95Ms':values[max(0,math.ceil(.95*len(values))-1)] if values else None,
            'maxMs':values[-1] if values else None}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',type=Path,required=True)
    parser.add_argument('--after',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    before=json.loads(args.before.read_text()); after=json.loads(args.after.read_text())
    if not after.get('complete') or after.get('selectedCaseIds'):
        raise ValueError('Final comparison requires a complete, unfiltered evaluation')
    if after['coreTotal']!=after['expectedCoreTotal'] or sum(bool(r['diagnosticOnly']) for r in after['results'])!=after['expectedLegacyTotal']:
        raise ValueError('Final evaluation case counts are inconsistent')
    old={row['id']:row for row in before['results'] if not row['diagnosticOnly']}
    core=[row for row in after['results'] if not row['diagnosticOnly']]
    new={row['id']:row for row in core}
    shared=old.keys() & new.keys()
    if len(shared)!=len(old) or any(old[key]['question']!=new[key]['question'] for key in shared):
        raise ValueError('Frozen baseline questions were removed or changed')
    root=Path(__file__).resolve().parents[2]
    cases_path=Path(__file__).with_name('operational_cases.json')
    if (after['expectedCoreTotal']!=len(json.loads(cases_path.read_text()))
            or after['expectedLegacyTotal']!=24
            or after['casesSha256']!=hashlib.sha256(cases_path.read_bytes()).hexdigest()
            or after.get('legacyCasesSha256')!=hashlib.sha256((root/'reports/phase0/evaluation-production-2026-09-28/questions_ground_truth.csv').read_bytes()).hexdigest()):
        raise ValueError('Final comparison requires the current full case set and all 24 diagnostics')
    digest=hashlib.sha256()
    for path in sorted([*(root/'documentApi/app').rglob('*.py'),*(root/'chatBotPHP').glob('*.js'),*(root/'chatBotPHP').glob('*.php')]):
        digest.update(str(path.relative_to(root)).encode()); digest.update(path.read_bytes())
    if digest.hexdigest()!=after['implementationSha256']:
        raise ValueError('Final report does not match the application source')
    summary={'beforeReport':str(args.before),'afterReport':str(args.after),
             'implementationSha256':digest.hexdigest(),'corePassed':after['corePassed'],'coreTotal':after['coreTotal'],
             'commonCases':len(shared),'beforeCommonPassed':sum(old[key]['passed'] for key in shared),
             'afterCommonPassed':sum(new[key]['passed'] for key in shared),
             'commonRegressions':[key for key in sorted(shared) if old[key]['passed'] and not new[key]['passed']],
             'failedCoreCases':[row['id'] for row in core if not row['passed']],
             'beforeCommonLatency':latency(list(old.values())),
             'afterCommonLatency':latency([new[key] for key in shared]),'afterCoreLatency':latency(core),
             'afterAllLatency':latency(after['results']),
             'afterLegacyLatency':latency([row for row in after['results'] if row['diagnosticOnly']]),
             'sourceDerivedNoGenerationLatency':latency([row for row in core if row['trace'].get('generationAttempts')==0]),
             'modelGenerationLatency':latency([row for row in core if (row['trace'].get('generationAttempts') or 0)>0]),
             'exactDuplicateContextRows':sum(row.get('exactDuplicateContextRows',0) for row in after['results']),
             'legacyDiagnosticRows':sum(row['diagnosticOnly'] for row in after['results']),
             'legacyDiagnosticAbstentions':sum(row['diagnosticOnly'] and bool(row['abstained']) for row in after['results']),
             'legacyScore':'Unscored; see manual review in RECOVERY_REPORT.md'}
    args.output.write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
