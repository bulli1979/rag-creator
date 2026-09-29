# Phase 1 corpus curation

Phase 1 applies a versioned, deterministic policy to the immutable Phase 0 source snapshot. It does not delete or modify the original corpus.

## Reproduce the candidate

```bash
python3 scripts/corpus_curate.py \
  --source-dir /home/llmrunner/NOTBot-documents/data/processed \
  --policy config/corpus_policy.v1.json \
  --manifest-out reports/phase1/corpus-manifest.v1.json \
  --report-out reports/phase1/dry-run.md \
  --review-queue-out reports/phase1/domain-review-queue.csv \
  --near-duplicates-out reports/phase1/near-duplicates.json \
  --shadow-dir /home/llmrunner/NOTBot-shadow/phase1-candidate-2026-09-29
```

The command refuses to overwrite an existing shadow directory. Use a new versioned directory for every policy iteration.

## Shadow layout

- `searchable/`: only `active` documents for default retrieval.
- `historical/`: isolated historical records for explicit historical/troubleshooting retrieval.
- `manifest.json`: every source and its reversible policy decision.
- `validation.json`: membership and SHA-256 verification results.

No quarantine or excluded document is copied into either corpus tree.

## Domain review workflow

Open `domain-review-queue.csv` and complete `ownerDecision` and `ownerNotes`. Allowed decisions are `active`, `historical`, `quarantine`, and `excluded`. Prioritize the evaluation-dependent sources listed in `evaluation-source-coverage.md`, then safety/procedure documents, current fault records, and the remaining internal-operation records.

Policy changes must be made in `config/corpus_policy.v1.json`; do not hand-edit the generated manifest. Increment `policyVersion` and `corpusVersion`, regenerate into a new shadow directory, rerun tests and coverage, and retain the previous candidate for comparison.

## Verification

```bash
python3 -m unittest scripts.tests.test_corpus_audit scripts.tests.test_corpus_curate

python3 scripts/evaluation/check_corpus_coverage.py \
  --manifest reports/phase1/corpus-manifest.v1.json \
  --qa reports/phase0/evaluation-production-2026-09-28/questions_qa.csv \
  --csv-out reports/phase1/evaluation-source-coverage.csv \
  --markdown-out reports/phase1/evaluation-source-coverage.md
```

The raw Phase 0 `questions_qa.csv` remains local and Git-ignored because it contains retrieved corpus excerpts. The coverage outputs contain questions, source counts, and dispositions but no retrieved text.
