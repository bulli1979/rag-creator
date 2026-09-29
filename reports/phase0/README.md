# Phase 0 baseline reproduction

Phase 0 snapshots the live deployment without modifying its corpus, metadata, vector index, settings, or model. Run commands from the repository root.

## 1. Snapshot live SQLite metadata

Ask SQLite to make a consistent backup in the running API container, then copy it to a temporary host path:

```bash
docker exec observatory-document-api python -c "import sqlite3; source=sqlite3.connect('/data/index.sqlite'); target=sqlite3.connect('/tmp/notbot-phase0-index.sqlite'); source.backup(target); target.close(); source.close()"
docker cp observatory-document-api:/tmp/notbot-phase0-index.sqlite /tmp/notbot-phase0-index.sqlite
```

## 2. Run the corpus/index audit

The values passed through `--metadata` are non-secret identifiers and hashes. Obtain current values from the deployment rather than copying stale values from an older report.

```bash
python3 scripts/corpus_audit.py \
  --source-dir /home/llmrunner/NOTBot-documents/data/processed \
  --metadata-sqlite /tmp/notbot-phase0-index.sqlite \
  --postgres-container observatory-postgres \
  --postgres-user postgres \
  --postgres-db rag \
  --postgres-schema public \
  --postgres-table rag_documents \
  --snapshot-label production-YYYY-MM-DD \
  --metadata model=MODEL_NAME \
  --metadata modelDigest=MODEL_DIGEST \
  --metadata promptSha256=PROMPT_HASH \
  --metadata appSettingsSha256=APP_SETTINGS_HASH \
  --metadata chatSettingsSha256=CHAT_SETTINGS_HASH \
  --metadata embeddingModel=EMBEDDING_MODEL \
  --metadata chunkSize=900 \
  --metadata chunkOverlap=150 \
  --json-out reports/phase0/production-YYYY-MM-DD.json \
  --markdown-out reports/phase0/production-YYYY-MM-DD.md
```

Run the command a second time with different output paths and compare the files to test determinism:

```bash
cmp reports/phase0/production-YYYY-MM-DD.json /tmp/notbot-phase0-repeat.json
cmp reports/phase0/production-YYYY-MM-DD.md /tmp/notbot-phase0-repeat.md
```

## 3. Run the technical evaluation

The evaluation sends questions to the live local API and uses the configured local judge. It does not modify the corpus or index.

The generated `questions_qa.csv` contains retrieved corpus excerpts and is intentionally ignored by Git. Keep it local unless it has received a separate disclosure review. Aggregate and row-level scoring outputs do not contain the retrieved context column.

```bash
OPENAI_API_KEY=ollama python3 scripts/evaluation/run_rag_eval_from_ground_truth.py \
  --ground-truth-file batchTest/questions_ground_truth.csv \
  --api-base-url http://127.0.0.1:8000 \
  --system-version production-COMMIT-MODEL-CORPUS \
  --outdir reports/phase0/evaluation-production-YYYY-MM-DD \
  --timeout-sec 600 \
  --eval-base-url http://127.0.0.1:11434/v1 \
  --eval-model MODEL_NAME \
  --eval-temperature 0
```

Re-run the audit with `--evaluation-summary` pointing to the resulting `fragerunden_eval_by_system.csv` to bind the scores to the corpus/index report.

## 4. Run audit unit tests

```bash
python3 -m unittest scripts.tests.test_corpus_audit
```

## Review checklist

- Confirm source and database counts are plausible.
- Inspect samples for duplicates, query-parameter sources, short files, boilerplate, and encoding damage.
- Inspect all evaluation failures and safety-sensitive answers, not only aggregate scores.
- Record accepted metrics and review notes in `NOTBOT_IMPLEMENTATION_PLAN.md`.
