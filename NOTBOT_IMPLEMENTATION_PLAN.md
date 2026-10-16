# NOTBot Improvement Implementation Plan

> **danka branch:** This tracker was written on the review branch. Its evidence links into `reports/` and the JSON policy/boost files (`config/corpus_policy.v1.json`, `documentApi/source_boosts.json`) point to files that are intentionally not part of the `danka` branch; keep them from the original review branch. Task statuses describe the review branch and were not re-evaluated after merging with upstream.

This document is the implementation source of truth for improving NOTBot. Update it in the same pull request as each implementation change so that task status, test evidence, metrics, and decisions remain synchronized with the code.

## Plan metadata

| Field | Value |
|---|---|
| Overall status | Operational recovery running in the local testing canary; expanded evaluation and rollback implemented; domain-owner/source-gap and production release gates remain open |
| Plan owner | NOTBot maintainers |
| Created | 2026-09-28 |
| Last updated | 2026-10-15 |
| Working branch | `review/production-improvements-clean` |
| Code baseline | `0c47411` (`Integrate mainline evaluation improvements`) |
| Review input | Local `NOTBOT_QUALITY_REVIEW.md`, dated 2026-08-26 |
| Production rollout | Local testing canary only; review-branch publication requested; no main merge or production cutover; remote PHP deployment not verified |

Recovery details: [NOTBOT_RECOVERY_PLAN.md](NOTBOT_RECOVERY_PLAN.md) and
[measured recovery report](reports/recovery/RECOVERY_REPORT.md). Earlier evidence
rows remain as history, not claims that their runtime/corpus is still active.

Current review entry point: [NOTBOT_HANDOFF.md](NOTBOT_HANDOFF.md), prepared
2026-10-15 for the requested review-branch commit/push. Fresh checks:123 backend
fixtures,24 evaluation-tooling fixtures and JS frontend fixtures pass; API health,
Qwen profile, deployed/local app hash and active483-document/5479-chunk v10 index
are reverified without runtime changes. Full HTTP/PHP/model-quality results retain
their original dates; P6.15/P6.16 and other release gates remain open. See
[handoff verification receipt](reports/handoff/2026-10-15-verification.json).

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
| P4.1 | Classify or extract query attributes such as instrument, procedure, troubleshooting, safety, and current/historical intent. | [x] | `evidence_selection.classify_query`; fixture tests |
| P4.2 | Apply metadata filters or boosts for instrument, category, authority, validity, and status. | [~] | Instrument/category/authority/status selection implemented; separate validity field is not yet persisted |
| P4.3 | Collapse exact and near-duplicate retrieval results. | [x] | Exact and formatting-only variants collapse; changed technical values survive; 0/116 duplicate context rows in 24-question probe |
| P4.4 | Apply a configurable per-source chunk cap, initially two chunks per source. | [x] | Primary selection cap2; documented recovery override allows at most two additional same-source/version structural neighbors globally, so a source may contribute up to four chunks to complete a procedure/table |
| P4.5 | Add authority and current-status preference without hiding explicitly requested historical material. | [x] | Landing/operator/command/design/historical roles; current FIES inventory beats obsolete design; explicitly scoped historical CCD8/report questions answer with labels; owner review remains P1.5 |
| P4.6 | Add controlled neighboring-section expansion after final evidence selection. | [x] | Same document/version, adjacent index, matched heading/child table, no heading-only rows; globally bounded to two additions with exact/formatting-only deduplication |
| P4.7 | Add an evidence threshold that triggers abstention or clarification. | [x] | Recovery mxbai floor0.30; only server-identified exact references/inventories bypass it; expanded gap/unknown-component/ambiguity cases; not claimed to be an optimal universal threshold |
| P4.8 | Evaluate a cross-encoder reranker against the existing hybrid heuristic after the clean index is stable. | [ ] | |

Acceptance gates:

- [x] Exact duplicate chunks never appear in final model context.
- [x] The per-source cap is enforced unless a documented query mode overrides it.
- [x] Instrument-specific queries do not retrieve unrelated instrument material when relevant evidence exists.
- [x] Current authoritative guidance outranks obsolete designs in evaluated live queries; explicit historical/reference questions retain access to their evidence.
- [x] Expanded live gap/unknown-component/ambiguous-subject cases abstain or clarify appropriately; broader domain coverage remains a release gate.
- [ ] The selected reranking approach improves the agreed retrieval metrics without unacceptable latency.

### Phase 5 — Ground answers and validate citations

Goal: make evidence boundaries, authority, and citations explicit to the answering model and user.

| ID | Task | Status | Evidence |
|---|---|---:|---|
| P5.1 | Define a structured context format containing document ID, title, instrument, authority, status, section, source, and content. | [x] | `app.grounding.prepare_evidence`; title falls back to a humanized filename |
| P5.2 | Update the prompt to use the structured evidence format and prohibit unsupported claims. | [x] | `build_system_prompt`; JSON claim-and-excerpt contract and untrusted-evidence boundary |
| P5.3 | Require citations to stable supplied document IDs. | [x] | Stable alias from versioned document ID plus chunk index; server renders supplied citations |
| P5.4 | Validate that citations refer to supplied evidence and support their associated claims. | [~] | Mechanical guards plus pinned English NLI/subject/value/identifier/source-policy checks implemented. New Qwen full-generator review found correct derived counts rejected and contradictory NOTCAM command applicability accepted despite exact quotes. Those source/proof regressions need scoped repair (P6.15/P6.16);95% independent semantic precision remains unestablished. Existing source-derived/core receipts remain historical, not universal validation certification |
| P5.5 | Clearly label historical and lower-authority evidence in generated answers. | [x] | Historical/reference/unreviewed labels; historical-only claims are rejected when current evidence is supplied unless the query explicitly requests history |
| P5.6 | Log prompt, model, corpus, index, retrieval scores, abstention state, latency, and token counts. | [x] | Structured trace plus encrypted append-only audit in the persistent API data volume; private permissions and key persistence verified across restart |
| P5.7 | Preserve instrument context for follow-up retrieval and allow checked wavelength comparisons from supplied ranges. | [x] | User-turn subject resolution before embedding/reranking; explicit topic switches override history; ambiguity clarifies. Direct range answers and Decimal interval comparisons cite current reviewed evidence and retain the derivation in encrypted audit. 46 fixtures and 8/8 live multi-turn checks pass. |

Acceptance gates:

- [~] Mechanical and local English entailment checks reject unsupported claims in expanded fixtures; verifier is fallible and broader human semantic support assessment remains open.
- [ ] Citation precision is at least 95% on the expanded evaluation suite.
- [x] Invalid or fabricated citation identifiers are rejected or removed.
- [x] Historical-only claims are labeled and cannot override supplied current evidence unless historical intent is explicit.

### Phase 6 — Operational acceptance, stability and safe rollout

Goal: demonstrate useful, correct, repeatable answers for observers/staff on the
actual PHP frontend, close essential documentation gaps, and validate a reversible
deployment. This phase is not an opportunity to defer basic instrument questions
or add features before the repaired pipeline is accepted. A local canary is not
production acceptance.

| ID | Task | Status | Evidence |
|---|---|---:|---|
| P6.1 | Add rated production failures and corrected expected behavior to the evaluation set. | [x] | 57 acceptance cases, including exact ALFOSC false-refusal wording, natural paraphrase, detector-size parentheses, winter-road advisory and conditional-error safety; original 24 technical questions retained as unscored diagnostics |
| P6.2 | Add safety, procedures, current-versus-historical, ambiguous-instrument, numeric/unit, citation, multi-turn, and corpus-gap cases. | [x] | All categories represented, including complete recipes, unsafe bypass, requested-value/subject mismatch and unsupported program sequence; unknown sequence remains a visible failure |
| P6.3 | Define automated correctness, groundedness, citation, abstention, retrieval, and latency metrics. | [~] | Deterministic facets/forbidden content/abstention/supplied-ID checks, source recall/MRR, duplicates and latency; manual review supplements them. General semantic precision and a latency budget remain open |
| P6.4 | Run baseline-versus-shadow comparative evaluation and review every regression. | [x] | Phase6 final-v10 complete run: 56/57 core; frozen pre-recovery common 12/31 → 30/31, zero regressions; all 24 diagnostics reviewed again (20 supported, 2 clarifications, 2 gaps). Only teloffset fails; this is NOT a pre-Phase0 comparison. Hashes/counts verified in reports/phase6/final-comparison.json |
| P6.5 | Test an end-to-end empty-database ingestion and question-answer flow. | [x] | New empty PostgreSQL environment/table built for mxbai, versioned ingestion through v9, 482/482 done; live queries/health/latest-only checks. This is an empty index in an existing database, not full backup restore |
| P6.6 | Perform a canary rollout using an explicit index/configuration pointer. | [~] | Local testing pointer recovery-mxbai/v10; exact image/app/corpus/config/model identity recorded. Bounded tests are not sustained telemetry or remote frontend cutover |
| P6.7 | Verify rollback to the prior index and document the operator procedure. | [x] | Retained default/MiniLM/v3 pointer rollback and exact settings restoration passed; instructions in recovery report. Phase6 also restores original dump/catalogue/settings with old compatible image, and final-v10 backup with final image in isolated databases; original dated document-file bundle is unavailable, retained files resolve all catalogue entries |
| P6.8 | Evaluate faster local models on frozen evidence; promote only after quality gates and explicit approval. | [~] | Expanded English round complete 2026-10-01: five artifacts downloaded; nine-model generator screen180/180 and in-process service224/224 complete. Qwen27 service55/56 matches control; earlier generated median7.22s vs23.44s (n5 each, not formal SLO). Initial temperature screen60 and full40-case ×3 ×3 temperatures360 now complete, zero request errors;485 attempt hashes verified after interruption.0 score99/120 (supported57/75),0.1 97/120,0.3 91/120; medians9.56/9.67/9.93s, mixed-cache sequential blocks not SLO. All settings retain false refusals and actual contradictory NOTCAM commands; no deployable winner. qwen27-quality-v1/RESULTS.md tracks recovery/reviews.24 offline fixtures pass. Task-owned engines stopped, weights retained; live app/settings/model/agents unchanged. API/PHP, post-repair control/candidate comparison, formal load/concurrency and independent domain review pending; resident256K Qwen trial separate. P6.15–P6.17 track required proof/scope repair and isolated retrieval experiments. No promotion/release approval |
| P6.9 | Repeat supported core facts, natural paraphrases and conversation chains on the same build. | [x] | Three COMPLETE unfiltered final-v10 57-case runs: 168/171; same teloffset source gap fails each run, all other core cases pass. No supported-question false refusals/context loss in this sample. NOTCam interruption now preserves exposure-completion instruction; broader MOSCA refusal repaired with reviewed intact paragraph and scoped link routing. reports/phase6/repetition-summary.json |
| P6.10 | Close essential operational source gaps and resolve conflicting current specifications. | [~] | User-supplied sequencer entry83 checked: X/Y offset description already indexed, not complete autoguided sequence. NOTCam counterweight0.95 recorded as owner context, not approved kg limit. Current load approval and FIES resolving-power reconciliation remain open. Conditional UIF recipe stays guarded; do not change teloffset expected answer into abstention to make suite green |
| P6.11 | Conduct independent domain-owner answer, citation and procedural-completeness review. | [ ] | Cover every currently supported operational instrument, observing/calibration workflows, data access and site/weather guidance, not only FIES/NOTCAM. At least 95% semantic citation precision on a representative stratified sample; publish denominators. All safety/procedure cases require supported complete steps/prerequisites, correct instrument/version, and no unsafe invented action. Legacy diagnostic flags are not scores |
| P6.12 | Establish response-time budgets and sustained local-canary monitoring before cutover. | [~] | Bounded warm serial/concurrent benchmark separates source-derived and generated answers, supported questions and gaps; stage timing/token receipts exclude prompt bodies. Final diagnostics and repeated gap questions can exceed90s. Cold machine/model starts, agreed budgets and sustained telemetry remain open. Proposed warm p95 ≤2s fact/reference, ≤45s generated, ≤90s any request are NOT approved or achieved release gates |
| P6.13 | Reproduce a clean dependency build and full isolated backup restore. | [~] | --pull --no-cache dependency build completed; imports, offline fixtures, CUDA smoke and restored-v9 API pass, but pip check rejects nvidia-cusparselt-cu13 0.8.1 ARM platform tag. Clean image NOT promoted. Original and current-v10 private full PostgreSQL/catalogue/settings/files restore drills pass in separate isolated databases; final483 sources/5479 active chunks verified. See reports/phase6/DEPENDENCY_BUILD_FINDINGS.md and final-restore.json |
| P6.14 | Verify actual PHP7.4 deployment and record exact release identity. | [~] | Final PHP7.4.33 isolated proxy integration13/13, PHP/JS lint and JS history/context/escaping fixtures pass; NOT an actual target/browser check. Remote server identity/access absent; browser URL policy not bypassed. Image/app/case/corpus/index/model/config receipts bind COMPLETE final evaluation; interrupted/filtered runs cannot be final reports |
| P6.15 | Align generator claims with typed source proofs and legitimate question intent without weakening checks. | [~] | Initial31-attempt review preserved; final44-attempt replay reproduces every saved rejection:16 correct count assertions match supplied derivedFacts/exact quotes but NLI rejects,14 range claims lack lexical-topic overlap. Implement/retest scoped complete-table/range/intent proof contract; wrong roles/counts/units/IDs, incomplete sources, unsupported extras and fake citations must remain rejected. qwen27-quality-v1/rejection-review-final.json and REVIEW_FINDINGS.md; no live repair yet |
| P6.16 | Bind procedural claims to explicit instrument applicability/exceptions and reject contradictory instructions. | [~] | Final18-answer diagnostic plus seven-answer manual review confirms real positive contradictory NOTCAM abort instructions at all temperatures (0.3:3,0.1:1,0:3), not negation-regex false positives. Generic appendix source contains explicit instrument exclusion; accepted warning and conflicting command coexist. Add/retest scoped ordinary/unsafe/negated/mixed-context fixtures and obtain independent procedure review before promotion. qwen27-quality-v1/procedure-review-final.json and PROCEDURE_REVIEW.md; no live repair yet |
| P6.17 | Evaluate scope-preserving chunks, retrieval completeness and model-aware evidence budgets in isolated A/B tests. | [ ] | Read-only inspection and NOTBOT_RETRIEVAL_OPTIMIZATION_PLAN.md complete. Active mxbai/exact pgvector search has no ANN index; topK8, max2/source, bounded neighbour expansion. Structured parser ignores overlap; imported corpus rows can bypass re-chunking. Shadow-only experiments must retain full tables/procedures/instrument exceptions, fixed source snapshots and independent P6.15/P6.16 proof gates. No reindex/live changes yet |

Suggested order: close source gaps/conflicts (P6.10), repeat critical conversations
and obtain independent domain review (P6.9/P6.11), establish measured latency and
canary budgets (P6.12), verify clean build/restore and the actual PHP target
(P6.13/P6.14), then complete sustained canary/cutover (P6.6). Following the user's
latency objection, P6.8 is reopened as an ISOLATED experiment now: compare models
on the same reviewed evidence and acceptance cases, keeping corpus/retrieval and
validation fixed. See NOTBOT_MODEL_EVALUATION_PLAN.md. Benchmarking does not
authorize a live model switch or waive remaining release gates.

Owner subsequently narrowed the alternative-model work to Qwen27. Chat-parameter
screening is complete:60 responses at temperatures0.3/0.1/0, scores12/20,
13/20,14/20 respectively; no request errors. Temperature0 is a provisional
quality candidate,0.1 a latency challenger, not optimized/approved replacements.
Shared refusal/contract failures persist; zero-temperature procedure tails~40s.
The five inspected standard coding tags share base weights/template; request
temperature/output already belong to NOTBot settings. A lightweight runner
profile can pin32K/draft defaults without new weights or changing coding tags.
See `reports/model-evaluation/qwen27-chat-tuning-v1/RESULTS.md`; full English
quality, source/contract review, independent domain and load/PHP gates remain
open. Live fingerprints unchanged, owned engines stopped; no commit/push.

2026-10-06 owner-authorized exception: the existing **testing** API on this review
branch now uses `notbot-qwen27:testing-32k` (installed standard Qwen27 weights,
32K context, temperature0, output2048, explicit no-thinking,180s/request and
zero SDK automatic retries). This is not a production promotion or a finding
of equal general quality. P6.8's earlier unchanged-runtime statement describes
the frozen evaluation, not the current testing runtime. All123 offline fixtures
pass; the complete HTTP bank is56/57 with the same teloffset gap (English55/56;
one historical German case retained). Isolated PHP7.4 proxy13/13 and JS fixtures
pass; actual target/browser verification remains open. Settings survive API
restart; active483 documents/5479 chunks, embeddings, corpus/index and database
settings are unchanged. Source-derived successes do not close P6.15/P6.16;
accepted contradictory generator procedures still block release. No commit/push.
Profile, private receipt locations and exact rollback are recorded in
[Qwen testing profile](docs/qwen-testing-profile.md).

Acceptance gates:

- [ ] No frozen-baseline regressions; all essential supported facts/procedures pass, including repeated paraphrases and multi-turn chains. Resolve remaining teloffset failure rather than hiding it.
- [ ] No safety-critical case regresses.
- [ ] All corpus, retrieval, citation, and abstention release gates pass.
- [ ] Agreed latency budgets and sustained canary telemetry pass, including model-generation tails and cold starts.
- [ ] Clean build, full isolated backup restore, actual PHP7.4 target verification and tested rollback pass before full cutover.
- [ ] Domain owners approve corpus coverage and current-specification conflicts; 95% citation precision and 100% safety/procedure review gates pass.

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
| ST-09 | Retrieve from duplicate and near-duplicate sources. | Final context contains no duplicate evidence and obeys the source cap. | [x] | Phase 4 fixtures and 24-question retrieval probe |
| ST-10 | Ask an instrument-specific question with distractor instruments present. | Relevant instrument evidence wins. | [x] | Fixture plus 0 unrelated-instrument rows in 24-question probe |
| ST-11 | Ask a current procedure question with conflicting historical evidence. | Current authoritative evidence wins and history is not presented as current. | [x] | FIES operational configuration beats old design; historical CCD8/report values explicitly scoped; FIES current/current resolution conflict is shown, not silently resolved |
| ST-12 | Ask a plausible question with no supporting corpus evidence. | The chatbot abstains or asks a useful clarification question. | [x] | Teleporter, unknown fiber, unsupported precision/load limit abstain; ambiguous/unnamed instruments clarify; missing real teloffset procedure remains an unmet useful-answer case |
| ST-13 | Generate answers for citation fixtures. | Every citation is supplied and supports its claim. | [~] | 9 grounding fixtures, 3 audit fixtures, and 3 live Command R cited claims; expanded semantic citation precision remains Phase 6 |
| ST-14 | Start with an empty PostgreSQL/pgvector environment, ingest the curated fixture, query it, update a source, and query again. | Health, ingestion, latest-only retrieval, answer, and citation flow all pass. | [x] | New isolated mxbai index ingested and updated through v9; 482 active sources, no multiple active versions; live cited instrument answers and health pass |
| ST-15 | Switch from shadow index to prior index. | Rollback succeeds without data reconstruction. | [x] | `reports/recovery/rollback-verification.json`; default/MiniLM/v3 and restored recovery/v9 connections and FIES#4 answers pass; exact settings restored |

## Metrics history

Add one row for each material corpus or retrieval iteration. Never overwrite an earlier row.

| Date | Commit | Corpus/index version | Active sources | Active chunks | Exact duplicate rows | Stale active versions | Evaluation score | Citation precision | Median latency | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-09-28 | `0c47411` | Review baseline; confirmation pending | 1,042 reported | 40,663 reported | 13,392 reported | Unknown | Pending rerun | Pending | Pending | Figures from local quality review; P0 must confirm. |
| 2026-09-29 | `0c47411` | `production-2026-09-28` / `bb70f53a` | 1,043 filenames | 44,419 | 15,205 | 1,041 filenames have multiple IDs | Correctness 0.7567 (21/24 scored) | Not measured by seed suite | Not instrumented | Approved reproducible baseline; not a production-quality approval. |
| 2026-09-29 | Working tree | `phase1-candidate-2026-09-29` | 381 active + 215 isolated historical | 2,964 projected active | 0 source-body exact duplicates | One version per active source ID | Not run; 8 coverage risks identified | Not measured | Not measured | Candidate only; domain review and rebuilt-index evaluation pending. |
| 2026-09-29 | Working tree | `phase1-candidate-2026-09-29-structured-v1` | 371 active + 215 isolated historical; 10 damaged active conversions quarantined | 1,934 active + 9,549 historical | 9 active rows beyond first | 0 by source lifecycle | Not run; no damaged-PDF URL occurs in seed contexts | Not measured | Not measured | Deterministic structured shadow corpus; 7 context-aware contact redactions are historical-only; no pre-existing phone placeholder remained in the Phase 1 candidate. |
| 2026-09-29 | Working tree | `fresh-crawl-2026-09-29-curated-v2` | 478 active + 216 isolated historical; 283 quarantined; 29 excluded | 4,997 live active chunks | 161 live rows beyond first | 0 | Chat smoke passed; full suite pending | Not measured | 8,375 ms smoke | Fresh crawl/index; 1,006 processed sources; 28 CID-damaged files quarantined; zero CSC documents; all live chunks versioned and classified. |
| 2026-09-29 | Working tree | `fresh-crawl-2026-09-29-curated-v2` / Phase 4 selector | 478 active | 4,997 live active chunks | 161 in index; 0 in selected seed contexts | 0 | Retrieval-only: 24/24 seed questions retain evidence; answer quality pending | Not measured | 9,786 ms one ALFOSC chat smoke | 3 to 0 exact context repeats, 14 to 0 over-cap rows, 6 to 0 instrument distractors; two live gaps abstained. |
| 2026-09-29 | Working tree | `fresh-crawl-2026-09-29-curated-v2` / Phase 5 grounding | 478 active | 4,997 live active chunks | 161 in index | 0 | 2 supported Command R smoke answers validated; 2 abstentions | Semantic precision pending; 0 invalid IDs in live smoke | 18,129 ms first model load; 9,825 ms warm smoke | JSON claim/excerpt contract, server-rendered stable citations, structured trace. |
| 2026-10-01 | `7891d6a` + app hash `0811e1499069` | `recovery-2026-09-30-v9` / `recovery-mxbai` | 482 | 5,478 | 379 in index; 0 selected contexts | 0 | Core56/57; unchanged common12/31 →30/31; original24 individually reviewed | General semantic precision/owner sign-off pending | Core125ms median /23,070ms p95 | 51 core source-derived answers median106ms; model tails remain (legacy max93,712ms). Only core failure: missing teloffset sequence. |
| 2026-10-01 | `314c41e` + working app hash `78253c204151` | `phase6-2026-10-01-v10` / `recovery-mxbai` | 483 | 5,479 | 379 in index; 0 selected contexts | 0 | 3 complete core runs168/171 (same teloffset gap); broad9/9; common12/31 →30/31, no regressions; 24 diagnostics reviewed again | Independent semantic precision/owner sign-off still pending | Warm fact p95:141ms serial /617ms at4 workers; generated p95:37,236ms serial /76,836ms at2 workers | 132/132 benchmark outcomes; generator latency target missed under concurrency; full final restore and PHP7.4 fixture pass; clean build's ARM NVIDIA wheel tag gate fails. Same chat-model weights. |

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
| 2026-09-29 | Working tree | Phase 4 evidence selection | `python3 -m unittest scripts.tests.test_retrieval_phase4 -v`; live 24-question retrieval-only comparison and three chat smoke questions | 8 fixtures passed; 0 duplicate/over-cap/distractor rows; 2/2 unsupported questions abstained | `reports/phase4/retrieval-baseline-2026-09-29.md` |
| 2026-09-30 | Working tree | Phase 5 grounding and PHP frontend | `python3 -m unittest scripts.tests.test_chat_audit_phase5 scripts.tests.test_grounding_phase5 scripts.tests.test_retrieval_phase4 -v`; PHP/Node syntax checks; live Command R smoke; API restart | 20 fixtures passed; cited answer validated; zero invalid IDs; encrypted audit/key survived restart; frontend filters to cited sources | `reports/phase5/grounding-2026-09-29.md` |
| 2026-09-30 | Working tree | NOTCAM false-abstention correction | 24 grounding/audit/retrieval fixtures; 3 mocked service tests in API container; `scripts/evaluation/smoke_core_instruments.py` | 27 fixtures passed; 7/7 live checks passed: definitions, capabilities, wavelength range, ALFOSC, FIES, and corpus-gap abstention; correction is bounded to one retry | `reports/phase5/core-instrument-smoke-2026-09-30-validated.json` |
| 2026-09-30 | Working tree | NOTCAM follow-up context and grounded inference | 39 pure fixtures; 7 mocked service tests; `scripts/evaluation/smoke_followup_context.py` | 46 fixtures passed; 8/8 live checks passed. Exact user follow-up cites NOTCAM overview and rejects 500nm as below range without model generation. Direct range queries also use checked extraction; the intermediate model-wording regression is preserved. | `reports/phase5/followup-context-2026-09-30.json` |
| 2026-10-01 | App hash `0811e1499069` | Final-image recovery evaluation/review | `scripts/evaluation/evaluate_operational.py --legacy`; `summarize_recovery.py` | COMPLETE57+24 run; core56/57, frozen common30/31 with no regressions; all24 diagnostics reviewed. Teloffset remains failing. | `reports/recovery/after-final-2026-10-01.json`, `final-comparison.json`, `RECOVERY_REPORT.md` |
| 2026-10-01 | Same final image | Repeated false-refusal/condition tests | Nine cases × three API runs | 27/27 pass, generationAttempts0; preserves frequency assumptions, detector identity/units, road conditions, complete/extended FIES coverage and exact-error clarification | `reports/recovery/targeted-final-repeat-{1,2,3}.json` |
| 2026-10-01 | Same final image | Fixtures, frontend syntax and persistence | Full container unittest discovery; producer tests; Node check; PHP7.4 CLI lint; read-only runtime verifier | 113 API +5 producer pass; PHP7.4/Node pass; image/code hash, health and persisted v9/1024-dimension index verified. Fresh browser check blocked by URL policy, not bypassed. | `reports/recovery/final-build-verification.json`, `runtime-consistency-final.json` |
| 2026-10-01 | Same final image | Index-pointer rollback and restoration | `scripts/verify_recovery_rollback.py`; repeat runtime verifier after restoration | Prior default/MiniLM/v3 and restored recovery/mxbai/v9 connections +FIES#4 smokes pass; exact settings restored, private0600 backup retained. Not a full dump restore. | `reports/recovery/rollback-verification.json`, `runtime-consistency-final.json` |

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
| D-013 | 2026-10-01 | Reframe Phase6 as operational acceptance/stability; preserve visible source-gap failures and repeat natural phrasings. | Repeated verification found additional false refusals and a dropped troubleshooting prerequisite despite earlier passing runs. One happy-path run and citation-ID validity are insufficient. | Domain-owner review, repeated critical conversations, latency, clean-build/restore and actual PHP target gates pass. |

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
| B-005 | 2026-09-30 | `what is NOTCAM?` falsely abstained despite retrieving the overview: equivalent micro glyphs and repaired list layout failed exact quote comparison; broader probes missed overview evidence or produced invalid claims. | Phase 5 | Fixed | Canonicalize equivalent notation; preserve value/unit checks; retrieve and prefer current reference overviews for broad instrument questions; permit one validated correction attempt; 27 fixtures and 7/7 live checks pass. |
| B-007 | 2026-09-30 | Follow-up `can the instrument be used to observer at 500nm?` retrieved LuckyCam/FIES instead of NOTCAM despite receiving the correct conversation history. Strict quote-only numeric checks also prohibited derived unit conversion and negative range conclusions. | Phase 5 / Phase 6 | Fixed, broader evaluation pending | Resolve user-turn instrument references before embedding and reranking; keep chat history separate from evidence. Checked wavelength inference uses only an unambiguous current reviewed source interval, cites that interval, and records arithmetic privately. 46 fixtures and 8/8 multi-turn smoke checks pass. |
| B-006 | 2026-09-30 | NOTCAM retrieval includes 2001/2002 commissioning report link pages, a mounting photo gallery, and a 2013 milestones entry labeled active reference. | Phase 1/6 | High | Revisit corpus classification and regenerate the reviewed manifest/index; add current-versus-historical and overview-noise evaluation cases. |
