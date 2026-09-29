# Source lifecycle migration and rollback

Phase 2 separates stable `source_id` from immutable `content_hash`. A logical document version uses `sha256(source_id + content_hash)`. Metadata and vector rows also carry `version`, `is_active`, `canonical_location`, and `corpus_version`.

## Deployment order

1. Stop ingestion workers and keep the current index available to chat.
2. Back up the metadata database and vector database. For SQLite, use the command below; it uses SQLite's online backup API so WAL data is included.
3. Run the migration without cleanup. Existing rows are retained and backfilled as independent legacy sources, so migration cannot incorrectly collapse unrelated sources.
4. Start the new application and run the v1/v2, unchanged-v2, and injected-failure smoke tests.
5. Only after validation, rerun with `--cleanup-inactive` to remove superseded vector rows. Source files and corpus artifacts are not deleted.

```bash
python scripts/source_lifecycle_admin.py migrate \
  --index-db /path/to/index.sqlite \
  --vector-db /path/to/vectors.sqlite \
  --table rag_documents \
  --backup-dir /path/to/backups
```

PostgreSQL uses additive columns through `ensure_schema`; take a database-native snapshot before deployment. Qdrant receives lifecycle payloads on newly indexed points; legacy points remain active under their document IDs until reindexed. Do not run cleanup until replacement smoke tests pass.

## Cleanup

Cleanup is explicit and irreversible without the backup. Add `--cleanup-inactive` to the migration command only after validation.

## Rollback

Stop writers, restore both recorded backup paths, then deploy the previous application version:

```bash
python scripts/source_lifecycle_admin.py rollback \
  --backup /path/to/backups/vectors.sqlite.TIMESTAMP.bak \
  --target /path/to/vectors.sqlite
```

Repeat for the metadata database. Never restore over a live database while writers are running. The backup/restore procedure is covered by an isolated smoke test.
