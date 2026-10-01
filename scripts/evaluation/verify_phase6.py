#!/usr/bin/env python3
"""Bounded public acceptance repetitions and latency/concurrency receipts.

No historical audits or raw contexts are exported. This is not domain-owner
approval or a sustained production canary. Budget thresholds are proposed only.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
from urllib.request import Request, urlopen

from evaluate_operational import assess

ROOT = Path(__file__).resolve().parents[2]
CASES = Path(__file__).with_name('operational_cases.json')


def app_hash():
    digest = hashlib.sha256()
    for path in sorted([*(ROOT/'documentApi/app').rglob('*.py'),
                        *(ROOT/'chatBotPHP').glob('*.js'), *(ROOT/'chatBotPHP').glob('*.php')]):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def latency(rows):
    values = sorted(row['elapsedMs'] for row in rows)
    return ({'n': len(values), 'medianMs': statistics.median(values),
             'p95Ms': values[math.ceil(.95*len(values))-1], 'maxMs': max(values)} if values else {'n': 0})


def summarize_repeats(reports, expected_ids, expected_case_hash, expected_app_hash):
    if len(reports) < 3:
        raise ValueError('At least three complete repetitions required')
    for report in reports:
        all_rows = report.get('results', [])
        rows = [r for r in all_rows if not r.get('diagnosticOnly')]
        legacy = [r for r in all_rows if r.get('diagnosticOnly')]
        legacy_total=report.get('expectedLegacyTotal')
        if (not report.get('complete') or report.get('selectedCaseIds') is not None
                or report.get('casesSha256') != expected_case_hash
                or report.get('implementationSha256') != expected_app_hash
                or report.get('expectedCoreTotal') != len(expected_ids)
                or legacy_total not in (0,24) or len(legacy)!=legacy_total
                or legacy and ({r['id'] for r in legacy}!={f'legacy_{i:02}' for i in range(1,25)}
                               or report.get('legacyCasesSha256')!=hashlib.sha256((ROOT/'reports/phase0/evaluation-production-2026-09-28/questions_ground_truth.csv').read_bytes()).hexdigest())
                or len(rows) != len(expected_ids)
                or {row['id'] for row in rows} != set(expected_ids)):
            raise ValueError('Incomplete, filtered or identity-mismatched repetition')
    rows = [row for report in reports for row in report['results'] if not row.get('diagnosticOnly')]
    identity={key: sorted({r.get('trace',{}).get(key) for r in rows
                           if r.get('trace',{}).get(key) not in (None,'','unknown')})
              for key in ('corpusVersion','indexId','embeddingModel','model','promptVersion')}
    if any(len(values)>1 for values in identity.values()):
        raise ValueError('Runtime identity changed between repetitions')
    failures = [{'run': i+1, 'id': row['id'], 'errors': row['errors']}
                for i, report in enumerate(reports) for row in report['results'] if not row.get('diagnosticOnly') and not row['passed']]
    return {'complete': True, 'repetitions': len(reports), 'responses': len(rows),
            'passed': sum(row['passed'] for row in rows), 'failures': failures,
            'allAcceptanceCasesPassed': not failures,
            'sourceDerived': latency([r for r in rows if r['trace'].get('generationAttempts') == 0]),
            'generated': latency([r for r in rows if r['trace'].get('generationAttempts', 0)]),
            'allLatency': latency(rows), 'implementationSha256': expected_app_hash,
            'casesSha256': expected_case_hash,'runtimeIdentity': identity}


def benchmark(api, cases, repeats, workers):
    tasks = cases * repeats
    def request(case):
        started = time.monotonic()
        payload = {'message': case['question'], 'history': case.get('history', []), 'language': 'en'}
        try:
            req = Request(api.rstrip('/')+'/api/chat', data=json.dumps(payload).encode(),
                          headers={'Content-Type': 'application/json'})
            with urlopen(req, timeout=240) as response:
                result = json.load(response)
            errors = assess(case, result)
            trace = result.get('trace', {})
            row = {'id': case['id'], 'passed': not errors, 'errors': errors,
                   'elapsedMs': round((time.monotonic()-started)*1000),
                   'generationAttempts': trace.get('generationAttempts'),
                   'answerMethod': trace.get('answerMethod'), 'indexId': trace.get('indexId'),
                   'corpusVersion': trace.get('corpusVersion'), 'model': trace.get('model'),
                   'stageTimings':{k:trace.get(k) for k in ('embeddingMs','retrievalMs','generationMs','validationMs')},
                   'tokens':{k:trace.get(k) for k in ('promptTokens','completionTokens','totalTokens')},
                   'abstained': result.get('metrics', {}).get('abstained')}
        except Exception as exc:
            row = {'id': case['id'], 'passed': False, 'errors': [type(exc).__name__],
                   'elapsedMs': round((time.monotonic()-started)*1000)}
        print(json.dumps({k:row.get(k) for k in ('id','passed','errors','elapsedMs','generationAttempts')}), flush=True)
        return row
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(request, tasks))
    duration = time.monotonic()-started
    return {'workers': workers, 'repeats': repeats, 'complete': len(rows)==len(tasks),
            'expectedResponses': len(tasks), 'passed': sum(r['passed'] for r in rows),
            'elapsedSeconds': round(duration, 3), 'requestsPerSecond': round(len(rows)/duration, 3),
            'latency': latency(rows),
            'sourceDerived': latency([r for r in rows if r.get('generationAttempts') == 0]),
            'generated': latency([r for r in rows if r.get('generationAttempts', 0)]), 'results': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repetition-reports', type=Path, nargs='+')
    parser.add_argument('--api', default='http://127.0.0.1:8000')
    parser.add_argument('--benchmark', action='store_true')
    args = parser.parse_args()
    cases_bytes = CASES.read_bytes()
    cases = json.loads(cases_bytes)
    digest = app_hash()
    receipt = {'verifiedAt': datetime.now(timezone.utc).isoformat(), 'implementationSha256': digest,
               'casesSha256': hashlib.sha256(cases_bytes).hexdigest(),
               'scope': 'Bounded local testing; not domain approval, approved budgets or sustained production telemetry'}
    if args.repetition_reports:
        receipt['repetitions'] = summarize_repeats([json.loads(p.read_text()) for p in args.repetition_reports],
                                                   [c['id'] for c in cases], receipt['casesSha256'], digest)
    if args.benchmark:
        ids = {'fies_count', 'fies_aperture_reported', 'fies_calibration', 'notcam_intro',
               'notcam_wide_pixels', 'notcam_hr_pixels', 'alfosc_uses', 'safety_humidity',
               'humidity_reopen', 'notcam_abort', 'notcam_dark_calibration',
               'alfosc_slitrot_procedure', 'alfosc_interactive_target', 'data_download', 'data_sharing'}
        facts = [c for c in cases if c['id'] in ids]
        generated = [c for c in cases if c['id'] in {'corpus_gap', 'unsupported_spec', 'cassegrain_current_limit_gap'}]
        broad_bytes=(Path(__file__).with_name('phase6_broad_cases.json')).read_bytes()
        generated += [c for c in json.loads(broad_bytes)
                      if c['id'] in {'stancam_identity','polcor_identity','luckycam_identity'}]
        receipt['broadCasesSha256']=hashlib.sha256(broad_bytes).hexdigest()
        receipt['benchmarkCaseIds']={'facts':[c['id'] for c in facts],'generationCandidates':[c['id'] for c in generated]}
        receipt['benchmarks'] = [benchmark(args.api, facts, 4, 1), benchmark(args.api, facts, 4, 4),
                                 benchmark(args.api, generated, 1, 1), benchmark(args.api, generated, 1, 2)]
        receipt['proposedBudgetObservations'] = {
            'approved': False, 'sourceDerivedWarmP95LimitMs': 2000, 'generatedWarmP95LimitMs': 45000,
            'anyRequestLimitMs': 90000,
            'violations': [{'batch': i+1, 'id': r['id'], 'elapsedMs': r['elapsedMs']}
                           for i,b in enumerate(receipt['benchmarks']) for r in b['results']
                           if r['elapsedMs']>90000],
            'p95Violations': [{'batch': i+1, 'method': method, 'p95Ms': b[method]['p95Ms'], 'limitMs': limit}
                              for i,b in enumerate(receipt['benchmarks'])
                              for method,limit in (('sourceDerived',2000),('generated',45000))
                              if b[method]['n'] and b[method]['p95Ms']>limit],
            'coldStartMeasured': False}
    if app_hash() != digest:
        raise ValueError('Application changed during verification; receipt is not final')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('benchmarks','repetitions')}))


if __name__ == '__main__':
    main()
