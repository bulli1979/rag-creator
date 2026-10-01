import importlib.util
from pathlib import Path
import sys
import unittest

EVAL = Path(__file__).resolve().parents[1]/'evaluation'
sys.path.insert(0, str(EVAL))
from verify_phase6 import latency, summarize_repeats


class Phase6Tests(unittest.TestCase):
    def report(self):
        return {'complete':True, 'selectedCaseIds':None, 'casesSha256':'cases',
                'implementationSha256':'app', 'expectedCoreTotal':2, 'expectedLegacyTotal':0,
                'results':[{'id':'supported','passed':True,'errors':[], 'elapsedMs':100,
                            'trace':{'generationAttempts':0}},
                           {'id':'source_gap','passed':False,'errors':['missing procedure'],
                            'elapsedMs':20000,'trace':{'generationAttempts':1}}]}

    def test_repeat_summary_preserves_real_source_gap_failure(self):
        summary = summarize_repeats([self.report() for _ in range(3)],
                                    ['supported','source_gap'],'cases','app')
        self.assertEqual(summary['passed'],3)
        self.assertEqual(len(summary['failures']),3)
        self.assertFalse(summary['allAcceptanceCasesPassed'])
        self.assertEqual(summary['generated']['n'],3)

    def test_repeat_summary_rejects_identity_and_completeness_errors(self):
        for update in ({'complete':False}, {'selectedCaseIds':['supported']},
                       {'implementationSha256':'old'}, {'casesSha256':'changed'},
                       {'expectedLegacyTotal':24}, {'expectedCoreTotal':1}):
            reports = [self.report() for _ in range(3)]
            reports[0].update(update)
            with self.assertRaises(ValueError):
                summarize_repeats(reports,['supported','source_gap'],'cases','app')
        reports = [self.report() for _ in range(3)]
        reports[0]['results'].pop()
        with self.assertRaises(ValueError):
            summarize_repeats(reports,['supported','source_gap'],'cases','app')

    def test_latency_reports_tail_and_empty_sample(self):
        self.assertEqual(latency([]),{'n':0})
        result=latency([{'elapsedMs':n} for n in range(1,21)])
        self.assertEqual(result['p95Ms'],19)
        self.assertEqual(result['maxMs'],20)

    def test_repeat_summary_rejects_changed_runtime_pointer(self):
        reports=[self.report() for _ in range(3)]
        for report in reports:
            report['results'][0]['trace']['corpusVersion']='reviewed-v1'
            report['results'][1]['trace']['corpusVersion']='unknown'
        summary=summarize_repeats(reports,['supported','source_gap'],'cases','app')
        self.assertEqual(summary['runtimeIdentity']['corpusVersion'],['reviewed-v1'])
        reports[-1]['results'][0]['trace']['corpusVersion']='unreviewed-v2'
        with self.assertRaises(ValueError):
            summarize_repeats(reports,['supported','source_gap'],'cases','app')


if __name__=='__main__':
    unittest.main()
