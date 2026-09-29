# NOTBot Improvement Implementation Plan

This document is the implementation source of truth for improving NOTBot. Update it in the same pull request as each implementation change so that task status, test evidence, metrics, and decisions remain synchronized with the code.

## Plan metadata

| Field | Value |
|---|---|
| Overall status | Phase 3 processing implemented; structured shadow corpus built and audited; vector rebuild/evaluation and Phase 1 domain review remain pending |
| Plan owner | NOTBot maintainers |
| Created | 2026-09-28 |
| Last updated | 2026-09-29 |
| Working branch | `review/production-improvements-clean` |
| Code baseline | `0c47411` (`Integrate mainline evaluation improvements`) |
| Review input | Local `NOTBOT_QUALITY_REVIEW.md`, dated 2026-08-26 |
| Production rollout | Not started |

## How to maintain this plan

Use the following task states:

- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete and verified
- `[-]` Intentionally deferred or rejected; record the reason in the decision log

A task is complete only when its implementation, automated tests, relevant smoke tests, and documentation are complete. Add links or command output summaries to the Evidence column. Do not mark an entire phase complete while any required acceptance gate remains open.

For every implementation pull request:

1. Update the relevant task states and the `Last updated` field.
2. Record the test commands and results in the test evidence log.
3. Record before/after corpus or evaluation metrics when behavior changes.
4. Add architectural or corpus-policy decisions to the decision log.
5. Record newly discovered work in the backlog rather than silently expanding a task.

## Objective and release gates

The primary goal is to make NOTBot more accurate and grounded by reducing noisy evidence, enforcing latest-only source indexing, preserving technical document structure, and improving evidence selection before considering a production model change.

The first production-ready corpus release must meet all of these gates:

- [ ] Active chunk count is reduced by at least 35% from the confirmed baseline, unless evaluation evidence supports a documented alternative.
- [ ] No stale version of an updated source is returned by retrieval.
- [ ] No exact duplicate chunks are passed to the answering model.
- [ ] No navigation-only or boilerplate-only chunks are active.
- [ ] Dynamic or query-generated sources are excluded unless explicitly allowlisted.
- [ ] Technical numbers, units, coordinates, dates, times, filenames, and instrument identifiers survive PII processing.
- [ ] Existing technical evaluation performance does not regress.
- [ ] There are no safety-critical evaluation regressions.
- [ ] Citation precision is at least 95% on the expanded evaluation set.
- [ ] Questions without adequate evidence cause abstention or a useful clarification request.
- [ ] The previous index remains available for rollback during rollout.

Phase 0 confirmed 1,043 processed source documents and 44,419 chunks, including 15,205 duplicate rows beyond the first copy. The 35% active-chunk reduction gate therefore targets no more than 28,872 chunks, subject to the quality gates above.

## Current capability baseline

The working branch already contains capabilities that this plan should reuse:

- Docker and PostgreSQL/pgvector deployment support.
- Configurable environments and corpus roots.
- Hybrid embedding, lexical, and numeric retrieval scoring.
- Configurable source boosts and wider candidate retrieval.
- Input and conversation-history bounds.
- Batch testing and restored evaluation scripts/results.
- OCR and batch folder-ingestion utilities.

Known gaps from the quality review remain:

- Content hashes are used as document identity, allowing superseded versions to remain searchable.
- The corpus contains exact duplicates, near duplicates, boilerplate, dynamic pages, and sources of uncertain retrieval value.
- PII replacement corrupts some legitimate technical values.
- Fixed character chunking destroys headings, lists, tables, and procedural structure.
- Retrieval lacks useful category, instrument, authority, validity, and status metadata.
- Retrieval lacks reliable source diversity, learned reranking, and an evidence threshold.
- Runtime records do not fully identify corpus, index, prompt, and model versions.

## Implementation roadmap

### Phase 0 — Reproduce the baseline

Goal: create a repeatable picture of current corpus and chatbot quality before changing behavior.

| ID | Task | Status | Evidence |
|---|---|---:|---|
| P0.1 | Add a corpus-audit command with machine-readable JSON and human-readable Markdown output. | [x] | `scripts/corpus_audit.py`; 3 audit tests pass |
| P0.2 | Count input files, canonical sources, document records, chunks, exact duplicate groups, and duplicate rows. | [x] | `reports/phase0/production-2026-09-28.{json,md}` |
| P0.3 | Report multiple active versions per canonical source. | [x] | 1,041 filenames have multiple IDs; maximum 86 |
| P0.4 | Report category, instrument, source type, query-parameter URL, boilerplate, PII replacement, empty-text, short-text, and OCR-quality distributions. | [x] | Machine-readable file records and aggregate baseline report |
| P0.5 | Run the existing technical evaluation and save results with application commit, configuration, prompt, model, corpus, and index identifiers. | [x] | `reports/phase0/evaluation-production-2026-09-28/`; 24/24 generated and judged |
| P0.6 | Review a stratified sample of audit findings and approve the baseline report. | [x] | `reports/phase0/production-2026-09-28-review.md` |

Acceptance gates:

- [x] Running the audit twice against unchanged inputs produces identical counts and classifications.
- [x] Every reported metric includes the corpus snapshot and application commit.
- [x] The current evaluation can be rerun from documented commands.

### Phase 1 — Curate and reduce the corpus

Goal: construct a smaller, versioned, reversible, and intentionally selected searchable corpus.

#### Corpus dispositions

Every discovered source must receive exactly one disposition:

- `active`: authoritative and suitable for ordinary retrieval.
- `historical`: useful for explicitly historical or diagnostic questions, but not allowed to override current guidance.
- `quarantine`: malformed, low quality, ambiguous, or awaiting human review.
- `excluded`: duplicate, superseded, irrelevant, generated, navigational, or otherwise unsuitable.

#### Initial selection policy

- Retain current manuals, safety documentation, operating procedures, command references, and authoritative instrument guides.
- Retain fault reports only when they provide unique diagnostic knowledge; label and route them as historical or instrument-specific.
- Review internal operational documents individually and assign an explicit authority tier.
- Exclude navigation pages, empty stubs, page chrome, calendars, news/event pages, and boilerplate-only sources.
- Exclude generated/live status pages and query or sort variants unless explicitly allowlisted.
- Collapse mirrored, exact-duplicate, and approved near-duplicate sources to one canonical source.
- Make only the latest approved version active while retaining prior source material outside the searchable index.
- Quarantine damaged OCR rather than indexing text whose technical meaning cannot be trusted.

| ID | Task | Status | Evidence |
|---|---|---:|---|
| P1.1 | Define a versioned corpus-policy configuration with deterministic rules and explicit allowlists. | [x] | `config/corpus_policy.v1.json`; fixture and live validation passed |
| P1.2 | Generate a manifest containing stable source ID, canonical location, content hash, version, disposition, reason, category, instrument, authority, validity, duplicate cluster, and quality flags. | [x] | `reports/phase1/corpus-manifest.v1.json`; all 1,006 fresh-crawl sources classified |
| P1.3 | Implement exact duplicate detection and a reviewable near-duplicate report. | [x] | `reports/phase1/near-duplicates.json`; 7 review candidates |
| P1.4 | Identify dynamic/query variants, boilerplate-only sources, empty stubs, and damaged conversions. | [x] | Policy flags and manifest reasons; fixture matrix passed |
| P1.5 | Review borderline fault-report and internal-operations sources with a domain owner. | [~] | Review queue generation implemented; owner decisions pending |
| P1.6 | Produce a dry-run report showing every inclusion and exclusion and the projected document/chunk reduction. | [x] | `reports/phase1/dry-run.md`; 478 active / 216 historical / 283 quarantine / 29 excluded; CSC absent |
| P1.7 | Build the curated corpus in a shadow location without deleting original source material. | [x] | `/home/llmrunner/NOTBot-shadow/fresh-crawl-2026-09-29-curated-v2`; 694 files metadata-enriched and hash-verified |

Acceptance gates:

- [x] Every input source has exactly one disposition and a reason.
- [x] No active canonical source has multiple active versions.
- [x] No excluded or quarantine source is present in the searchable build.
- [x] No non-allowlisted query-variant or generated live page is active.
- [~] The proposed reduction meets the numeric target, but 8/24 evaluation questions have only quarantined mapped sources and comparative shadow evaluation remains pending.
- [x] Exclusions are reversible from the manifest and retained source snapshot.

### Phase 2 — Implement stable source identity and latest-only indexing

Goal: separate source identity from content-version identity and make updates transactional.

Proposed data concepts:

- `source_id`: stable identity derived from canonical source location and environment.
- `content_hash`: immutable identity of one content version.
- `version`: ordered source version.
- `is_active`: whether a version can be retrieved.
- `corpus_version`: manifest/build that admitted the version.

| ID | Task | Status | Evidence |
|---|---|---:|---|
| P2.1 | Design and document the database migration and rollback strategy. | [x] | `docs/source-lifecycle-migration.md`; backup/restore smoke passed |
| P2.2 | Add stable source, version, active-status, canonical-location, and corpus-version fields and constraints. | [x] | Metadata and all vector backends carry lifecycle fields; one-active-source metadata constraint |
| P2.3 | Extend the vector-store protocol and implementations with source-oriented replacement, removal, and metadata filtering. | [x] | Protocol plus PostgreSQL, SQLite, Qdrant, and unavailable implementations updated |
| P2.4 | Make changed-source ingestion transactional: write new chunks, activate the new version, then deactivate the old version. | [x] | PostgreSQL/SQLite atomic transactions; Qdrant activation-first with compensation |
| P2.5 | Make identical re-ingestion idempotent. | [x] | Stable source+content document ID and row-count regression test |
| P2.6 | Prevent an ingestion failure from deactivating the last valid version. | [x] | Replacement rollback test injects a write failure and confirms v1 remains searchable |
| P2.7 | Add an explicit cleanup/migration command for stale legacy vectors. | [x] | `scripts/source_lifecycle_admin.py`; backup-first migrate, optional cleanup, explicit rollback |

Acceptance gates:

- [x] Ingesting source v1 and then v2 makes only v2 searchable.
- [x] Re-ingesting unchanged v2 does not increase document or chunk counts.
- [x] Failed v2 ingestion leaves v1 active and searchable.
- [x] Two different sources with the same filename remain distinct.
- [x] Database and vector-store migrations have a tested rollback procedure.

### Phase 3 — Improve conversion, PII handling, and chunking

Goal: retain technical meaning and document structure while removing non-content noise.

| ID | Task | Status | Evidence |
|---|---|---:|---|
| P3.1 | Add fixture-based regression tests for technical-value-safe PII handling. | [x] | `scripts/tests/test_document_processing.py`; contact and technical-value fixtures pass |
| P3.2 | Correct PII rules so real contact details are removed while technical values are preserved. | [x] | Runtime processor plus producer patch `docs/notbot-documents-phase3.patch`; both smoke-tested |
| P3.3 | Remove navigation and repeated page boilerplate before Markdown conversion and chunking. | [x] | Producer pre-conversion cleanup plus runtime Markdown cleanup; zero flagged shadow chunks |
| P3.4 | Replace whitespace-collapsing character windows with heading-aware structured chunking. | [x] | `documentApi/app/document_processing.py` integrated into `worker.py` |
| P3.5 | Preserve numbered procedures, warnings, tables, lists, code blocks, and section heading paths. | [x] | Structure fixture passes; fresh shadow audit records 181 code, 3,719 list, 1,208 table, and 715 warning chunks |
| P3.6 | Add parent-section and neighboring-section metadata for controlled context expansion. | [x] | Metadata emitted by parser, stored by all vector backends, and round-trip tested in SQLite |
| P3.7 | Rebuild and audit the shadow index with the new conversion pipeline. | [~] | Fresh structured shadow built at `/home/llmrunner/NOTBot-shadow/fresh-crawl-2026-09-29-structured-v2`; 478-document embedding index and chat retrieval smoke passed; comparative evaluation pending |

Acceptance gates:

- [x] Phone/contact fixtures are redacted.
- [x] Wavelengths, units, coordinates, dates, times, filenames, and instrument identifiers remain unchanged.
- [x] No chunk consists only of navigation or modification boilerplate.
- [x] Procedure steps and table rows remain coherent in representative fixtures.
- [x] Every chunk has canonical source, section, authority, status, and corpus-version metadata.

### Phase 4 — Improve retrieval and evidence selection

Goal: return a small, diverse, authoritative evidence set and recognize insufficient evidence.

| ID | Task | Status | Evidence |
|---|---|---:|---|
| P4.1 | Classify or extract query attributes such as instrument, procedure, troubleshooting, safety, and current/historical intent. | [ ] | |
| P4.2 | Apply metadata filters or boosts for instrument, category, authority, validity, and status. | [ ] | |
| P4.3 | Collapse exact and near-duplicate retrieval results. | [ ] | |
| P4.4 | Apply a configurable per-source chunk cap, initially two chunks per source. | [ ] | |
| P4.5 | Add authority and current-status preference without hiding explicitly requested historical material. | [ ] | |
| P4.6 | Add controlled neighboring-section expansion after final evidence selection. | [ ] | |
| P4.7 | Add an evidence threshold that triggers abstention or clarification. | [ ] | |
| P4.8 | Evaluate a cross-encoder reranker against the existing hybrid heuristic after the clean index is stable. | [ ] | |

Acceptance gates:

- [ ] Exact duplicate chunks never appear in final model context.
- [ ] The per-source cap is enforced unless a documented query mode overrides it.
- [ ] Instrument-specific queries do not retrieve unrelated instrument material when relevant evidence exists.
- [ ] Current authoritative guidance outranks superseded instructions.
- [ ] Corpus-gap questions abstain or request clarification.
- [ ] The selected reranking approach improves the agreed retrieval metrics without unacceptable latency.

### Phase 5 — Ground answers and validate citations

Goal: make evidence boundaries, authority, and citations explicit to the answering model and user.

| ID | Task | Status | Evidence |
|---|---|---:|---|
| P5.1 | Define a structured context format containing document ID, title, instrument, authority, status, section, source, and content. | [ ] | |
| P5.2 | Update the prompt to use the structured evidence format and prohibit unsupported claims. | [ ] | |
| P5.3 | Require citations to stable supplied document IDs. | [ ] | |
| P5.4 | Validate that citations refer to supplied evidence and support their associated claims. | [ ] | |
| P5.5 | Clearly label historical and lower-authority evidence in generated answers. | [ ] | |
| P5.6 | Log prompt, model, corpus, index, retrieval scores, abstention state, latency, and token counts. | [ ] | |

Acceptance gates:

- [ ] Every evaluated factual claim has supporting supplied evidence or the answer abstains.
- [ ] Citation precision is at least 95% on the expanded evaluation suite.
- [ ] Invalid or fabricated citation identifiers are rejected or removed.
- [ ] Historical evidence cannot silently override current authoritative instructions.

### Phase 6 — Expand evaluation and roll out safely

Goal: validate the complete pipeline against representative questions and deploy it with a fast rollback path.

| ID | Task | Status | Evidence |
|---|---|---:|---|
| P6.1 | Add rated production failures and corrected expected behavior to the evaluation set. | [ ] | |
| P6.2 | Add safety, procedures, current-versus-historical, ambiguous-instrument, numeric/unit, citation, multi-turn, and corpus-gap cases. | [ ] | |
| P6.3 | Define automated correctness, groundedness, citation, abstention, retrieval, and latency metrics. | [ ] | |
| P6.4 | Run baseline-versus-shadow comparative evaluation and review every regression. | [ ] | |
| P6.5 | Test an end-to-end empty-database ingestion and question-answer flow. | [ ] | |
| P6.6 | Perform a canary rollout using an explicit index/configuration pointer. | [ ] | |
| P6.7 | Verify rollback to the prior index and document the operator procedure. | [ ] | |
| P6.8 | Consider a smaller production model only after corpus and retrieval gates pass. | [ ] | |

Acceptance gates:

- [ ] Existing technical evaluation performance is maintained or improved.
- [ ] No safety-critical case regresses.
- [ ] All corpus, retrieval, citation, and abstention release gates pass.
- [ ] Canary telemetry shows no unexplained error, latency, or abstention regression.
- [ ] Rollback is exercised successfully before full cutover.

## Required smoke tests

These tests are part of the definition of done. Exact commands should be added as the test files and scripts are implemented.

| Test ID | Scenario | Expected result | Status | Evidence |
|---|---|---|---:|---|
| ST-01 | Audit the same unchanged corpus twice. | Reports and classifications are identical. | [x] | Byte-identical JSON and Markdown confirmed with `cmp` |
| ST-02 | Classify a fixture containing a current manual, old version, exact duplicate, query variant, empty stub, navigation page, damaged OCR, and unique fault report. | Each source receives the expected disposition and reason. | [x] | `scripts.tests.test_corpus_curate` |
| ST-03 | Ingest v1 and then changed v2 of the same source. | Only v2 is searchable; row growth matches the new active version. | [x] | `test_latest_only_and_idempotent_reingestion` |
| ST-04 | Re-ingest unchanged v2. | Document and chunk counts do not increase. | [x] | `test_latest_only_and_idempotent_reingestion` |
| ST-05 | Force parsing/storage failure during v2 ingestion. | v1 remains active and searchable. | [x] | SQLite trigger injects replacement failure; v1 remains searchable |
| ST-06 | Ingest two distinct sources with the same filename. | Both retain distinct source identities. | [x] | `test_same_filename_different_canonical_sources_are_distinct` |
| ST-07 | Process contact and technical-number fixtures. | Contact data is removed; technical values remain intact. | [x] | `SafePiiTests`; runtime and producer smoke tests |
| ST-08 | Chunk a manual containing headings, warnings, steps, tables, and code. | Structures remain coherent and heading paths are attached. | [x] | `StructuredChunkTests`; runtime parser fixture |
| ST-09 | Retrieve from duplicate and near-duplicate sources. | Final context contains no duplicate evidence and obeys the source cap. | [ ] | |
| ST-10 | Ask an instrument-specific question with distractor instruments present. | Relevant instrument evidence wins. | [ ] | |
| ST-11 | Ask a current procedure question with conflicting historical evidence. | Current authoritative evidence wins and history is not presented as current. | [ ] | |
| ST-12 | Ask a plausible question with no supporting corpus evidence. | The chatbot abstains or asks a useful clarification question. | [ ] | |
| ST-13 | Generate answers for citation fixtures. | Every citation is supplied and supports its claim. | [ ] | |
| ST-14 | Start with an empty PostgreSQL/pgvector environment, ingest the curated fixture, query it, update a source, and query again. | Health, ingestion, latest-only retrieval, answer, and citation flow all pass. | [ ] | |
| ST-15 | Switch from shadow index to prior index. | Rollback succeeds without data reconstruction. | [ ] | |

## Metrics history

Add one row for each material corpus or retrieval iteration. Never overwrite an earlier row.

| Date | Commit | Corpus/index version | Active sources | Active chunks | Exact duplicate rows | Stale active versions | Evaluation score | Citation precision | Median latency | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-09-28 | `0c47411` | Review baseline; confirmation pending | 1,042 reported | 40,663 reported | 13,392 reported | Unknown | Pending rerun | Pending | Pending | Figures from local quality review; P0 must confirm. |
| 2026-09-29 | `0c47411` | `production-2026-09-28` / `bb70f53a` | 1,043 filenames | 44,419 | 15,205 | 1,041 filenames have multiple IDs | Correctness 0.7567 (21/24 scored) | Not measured by seed suite | Not instrumented | Approved reproducible baseline; not a production-quality approval. |
| 2026-09-29 | Working tree | `phase1-candidate-2026-09-29` | 381 active + 215 isolated historical | 2,964 projected active | 0 source-body exact duplicates | One version per active source ID | Not run; 8 coverage risks identified | Not measured | Not measured | Candidate only; domain review and rebuilt-index evaluation pending. |
| 2026-09-29 | Working tree | `phase1-candidate-2026-09-29-structured-v1` | 371 active + 215 isolated historical; 10 damaged active conversions quarantined | 1,934 active + 9,549 historical | 9 active rows beyond first | 0 by source lifecycle | Not run; no damaged-PDF URL occurs in seed contexts | Not measured | Not measured | Deterministic structured shadow corpus; 7 context-aware contact redactions are historical-only; no pre-existing phone placeholder remained in the Phase 1 candidate. |
| 2026-09-29 | Working tree | `fresh-crawl-2026-09-29-curated-v2` | 478 active + 216 isolated historical; 283 quarantined; 29 excluded | 4,997 live active chunks | 161 live rows beyond first | 0 | Chat smoke passed; full suite pending | Not measured | 8,375 ms smoke | Fresh crawl/index; 1,006 processed sources; 28 CID-damaged files quarantined; zero CSC documents; all live chunks versioned and classified. |

## Test evidence log

Record concise, reproducible evidence. Link to durable reports when available.

| Date | Commit | Scope | Command or workflow | Result | Report |
|---|---|---|---|---|---|
| 2026-09-28 | `0c47411` | Plan creation | Documentation-only change | Not run | N/A |
| 2026-09-29 | `0c47411` | Corpus audit | `python3 -m unittest scripts.tests.test_corpus_audit` | 3 passed | `reports/phase0/production-2026-09-28.{json,md}` |
| 2026-09-29 | `0c47411` | Audit determinism | Repeat audit followed by `cmp` on JSON and Markdown | Passed | `reports/phase0/production-2026-09-28.{json,md}` |
| 2026-09-29 | `0c47411` | Evaluation input regression | `/tmp/notbot-phase0-venv/bin/python -m unittest scripts.tests.test_evaluation_input` | 1 passed; 24 ground-truth rows load | `scripts/tests/test_evaluation_input.py` |
| 2026-09-29 | `0c47411` | Live technical baseline | 24 questions through live API and local Command R judge | 24 generated; 24 judged; correctness available for 21 | `reports/phase0/evaluation-production-2026-09-28/` |
| 2026-09-29 | Working tree | Phase 1 policy fixtures | `python3 -m unittest scripts.tests.test_corpus_audit scripts.tests.test_corpus_curate` | 5 passed | `scripts/tests/` |
| 2026-09-29 | Working tree | Phase 1 determinism | Regenerate manifest, report, review queue, and near-duplicate report followed by `cmp` | All four artifacts byte-identical | `reports/phase1/` |
| 2026-09-29 | Working tree | Phase 1 shadow integrity | Manifest membership plus SHA-256 comparison | 596 files checked; zero forbidden files | `/home/llmrunner/NOTBot-shadow/phase1-candidate-2026-09-29/validation.json` |
| 2026-09-29 | Working tree | Evaluation-source coverage | `scripts/evaluation/check_corpus_coverage.py` | 14 active-covered; 8 quarantine-only; 2 unmapped | `reports/phase1/evaluation-source-coverage.md` |
| 2026-09-29 | Working tree | Phase 2 source lifecycle | `/home/llmrunner/NOTBot-documents/venv/bin/python -m unittest scripts.tests.test_source_lifecycle -v` | 5 passed: latest-only, idempotency, failure rollback, distinct sources, DB rollback | `scripts/tests/test_source_lifecycle.py` |
| 2026-09-29 | Working tree | Phase 2 legacy migration | `scripts/source_lifecycle_admin.py migrate` against an isolated pre-lifecycle SQLite table | Backup created; six fields added; legacy row preserved and active | `docs/source-lifecycle-migration.md` |
| 2026-09-29 | Working tree | Phase 3 processing fixtures | `/home/llmrunner/NOTBot-documents/venv/bin/python -m unittest scripts.tests.test_document_processing -v` | 5 passed: PII safety, boilerplate, structures, metadata, runtime parser | `scripts/tests/test_document_processing.py` |
| 2026-09-29 | Working tree | Phase 3 vector metadata | `scripts.tests.test_source_lifecycle` | 6 passed including structural metadata round trip | `scripts/tests/test_source_lifecycle.py` |
| 2026-09-29 | Working tree | Phase 3 structured shadow | Build twice and compare tree/report SHA-256 | 586 documents; 11,483 chunks; deterministic; 0 missing metadata; 0 navigation chunks | `reports/phase3/structured-shadow-2026-09-29.{json,md}` |
| 2026-09-29 | Local producer repository + portable patch | Producer PII/conversion smoke | Contact/technical fixture plus HTML navigation fixture | Passed; local-only repository records producer changes | `docs/notbot-documents-phase3.patch` |
| 2026-09-29 | Working tree | Fresh crawl and curation | Empty crawl tree; crawl, convert, DB export, audit, curate | 929 resources fetched; 1,006 processed sources; 478 active; zero CSC | `reports/fresh-crawl/source-audit-2026-09-29.{json,md}` |
| 2026-09-29 | Working tree | Fresh embedding index | Empty API/PostgreSQL volumes; ingest curated searchable corpus | 478/478 done; 4,997 active chunks; zero errors; zero CSC; no unclassified chunks | PostgreSQL + `/api/documents` smoke |
| 2026-09-29 | Working tree | End-to-end retrieval | Ask `What is ALFOSC used for?` through `/api/chat` | Five relevant contexts; cited answer; 8,375 ms | Local smoke result |

## Decision log

| ID | Date | Decision | Reason | Revisit when |
|---|---|---|---|---|
| D-001 | 2026-09-28 | Prioritize corpus curation and source lifecycle before changing the production LLM. | The review identifies evidence duplication, stale versions, conversion corruption, and retrieval noise as the dominant quality risks. | Clean-index evaluation is complete. |
| D-002 | 2026-09-28 | Quarantine or exclude sources through a versioned manifest instead of permanently deleting them. | Corpus reduction must be auditable and reversible. | Retention policy is formally approved. |
| D-003 | 2026-09-28 | Use a 35% initial active-chunk reduction gate, subject to quality evaluation. | Exact duplicate rows alone account for about 33% of the reviewed index. | P0 establishes the current baseline. |
| D-004 | 2026-09-28 | Build and test changes in a shadow index. | This enables comparative evaluation and fast rollback without merging into or mutating the production index. | Full rollout is approved. |
| D-005 | 2026-09-29 | Use 44,419 active chunks as the confirmed reduction baseline and 28,872 as the initial 35% target. | Phase 0 replaced the older review estimate with a deterministic live snapshot. | Corpus policy dry run and quality comparison are complete. |
| D-006 | 2026-09-29 | Treat query parameters and short documents as review signals, not automatic exclusion rules. | Stratified samples contain both noisy variants and useful instrument-specific or atomic reference content. | Phase 1 policy validation provides stronger evidence. |
| D-007 | 2026-09-29 | Keep historical sources physically separate from the default searchable shadow corpus. | Fault reports can retain diagnostic value without overriding current authoritative instructions. | Metadata-routed historical retrieval is implemented and evaluated. |
| D-008 | 2026-09-29 | Quarantine documents with potentially destructive phone redactions in the first policy candidate. | Phase 0 confirmed that the placeholder replaces scientific and operational values as well as genuine contact data. | Numeric-safe regeneration is complete. |
| D-009 | 2026-09-29 | Derive source identity from environment plus canonical location and derive version document IDs from source ID plus content hash. | Content bytes alone cannot distinguish logical sources, while filenames alone cannot identify updates safely. | Canonical-source policy changes. |
| D-010 | 2026-09-29 | Retain superseded vectors as inactive until an explicit backup-first cleanup. | Latest-only retrieval and rollback safety should not depend on immediate destructive deletion. | Storage retention limits are approved. |
| D-011 | 2026-09-29 | Redact numeric phone candidates only with an explicit contact label or international phone formatting. | Digit count alone destroyed legitimate wavelengths, dates, coordinates, identifiers, and table values. | A tested higher-recall PII detector is available. |
| D-012 | 2026-09-29 | Quarantine ten `(cid:...)`-damaged PDF conversions and keep contact-redacted fault records historical-only. | Inventing missing technical values is unsafe; none of the damaged PDF URLs appear in seed evaluation contexts. | Clean source PDFs are reconverted and reviewed. |

## Risks and controls

| Risk | Control |
|---|---|
| Useful rare documents are removed. | Quarantine first, retain originals, sample exclusions, and run coverage/evaluation checks. |
| Historical fault reports override current procedures. | Explicit status/authority metadata, query routing, and current-authority preference. |
| Stable-source migration causes data loss. | Transactional updates, backups, dry-run migration, shadow index, and tested rollback. |
| PII corrections expose genuine contact data. | Positive and negative fixtures plus sampled audit of transformed documents. |
| A smaller corpus lowers recall. | Measure retrieval recall by category and instrument; restore justified sources through the manifest. |
| New reranking increases latency. | Benchmark against the existing heuristic and enforce an agreed latency budget. |
| Sparse feedback gives misleading quality signals. | Expand curated evaluations and retain human review for safety and corpus-policy decisions. |

## Backlog discovered during implementation

Add new work here with a proposed phase and priority before incorporating it into scope.

| ID | Date | Finding | Proposed phase | Priority | Disposition |
|---|---|---|---|---|---|
| B-001 | 2026-09-29 | The local judge omitted correctness for 3/24 rows and overrated context relevance for some wrong answers. | Phase 6 | High | Add deterministic numeric/unit checks and mandatory safety review. |
| B-002 | 2026-09-29 | Evaluation CSV readers failed on whitespace before a quoted field. | Phase 0 | Complete | Readers now use `skipinitialspace=True`; regression test added. |
| B-003 | 2026-09-29 | The `NOTBot-documents` producer workspace has no Git metadata, so its Phase 3 fixes cannot travel with the NOTBot branch directly. | Phase 3 | High | Portable patch saved at `docs/notbot-documents-phase3.patch`; apply it in the producer source repository. |
| B-004 | 2026-09-29 | The Phase 3 structured corpus is built, but a real embedding-backed shadow index and comparative evaluation are still required. | Phase 3/6 | High | P3.7 remains in progress; do not promote this corpus yet. |
