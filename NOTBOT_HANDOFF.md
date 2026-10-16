# NOTBot review-branch handoff

Prepared 2026-10-15 for Danuta's team. This is a **review/testing handoff, not a
production release**. The user requested publishing the current work to
`origin/review/production-improvements-clean`; do not merge it into `main` as
part of this handoff.

## Start here

NOTBot is intended to answer English questions from NOT observers/staff about
instruments, observing procedures, troubleshooting, data handling and site
operations, with current authoritative sources and preserved conversation
context. The frontend in use for this branch is **`chatBotPHP`**, targeting
PHP 7.4, not the Electron chat application.

The local testing backend is running and core instrument questions are much
better covered than during the reported regression. However, **Phase 6 is not
complete**. Generated answers can still falsely refuse supported questions or
accept contradictory instrument-specific instructions. Do not treat passing
core/source-derived answers as general model or procedural-safety approval.

Read these next:

1. [Implementation tracker](NOTBOT_IMPLEMENTATION_PLAN.md): task IDs and release gates.
2. [Qwen profile and rollback](docs/qwen-testing-profile.md): current testing configuration.
3. [Generator quality findings](reports/model-evaluation/qwen27-quality-v1/RESULTS.md): failures hidden by ordinary source-derived routes.
4. [Independent domain review](reports/phase6/DOMAIN_REVIEW_CHECKLIST.md): required owner judgments.

## What is being handed over

The handoff includes the six local commits after the previously published
review branch, ending at `adbb715`, plus the subsequent model-evaluation,
Qwen-profile and handoff work. Use `git log` for the final handoff commit ID;
`adbb715` identifies the earlier Phase 6 baseline, not all current changes.

| Area | Implemented | Qualifications |
|---|---|---|
| Corpus policy | Versioned dispositions, manifest, quarantine/historical separation, crawler/producer improvements | Borderline exclusions still need owner review; producer repository/data are separate |
| Source lifecycle | Stable source identity, versioned document identity, latest-only replacement, idempotency and failure rollback | Retained inactive/history data are intentional, not all stale storage to delete |
| Processing | Technical-value-safe contact redaction, boilerplate removal, structured tables/lists/procedures and heading metadata | Existing source snapshots and review history must be preserved |
| Retrieval | Instrument/current-status/authority preference, lexical/numeric signals, deduplication, source cap and bounded neighbours | No new learned reranker; validity metadata and scope-preserving retrieval experiments remain open |
| Conversation | Instrument follow-up resolution, explicit topic switches and ambiguity handling | History is context, never a replacement for source evidence |
| Answering | Checked source-derived reference/table/range/procedure routes plus grounded JSON generation, stable citations, mechanical/NLI checks and bounded repair | Source-derived success is not model-generation success; verifier limitations remain critical |
| Audit | Encrypted persistent backend audit; PHP conversation/feedback logging is a separate layer | Back up keys securely; do not publish logs or assume PHP/browser storage is encrypted |
| Evaluation | Repeated operational suites, diagnostics, isolated restores, model screening and recovered/hash-verified Qwen comparisons | No independent domain sign-off, approved latency SLO or production cutover |

No new architecture, live CodeRepo/database MCP retrieval, model fine-tuning or
static knowledge-compilation pipeline is implemented by this handoff. The
discussion of a separate successor project remains a proposal. Keep raw MCP
source/database content outside this corpus and Git until an explicit
secret-scrubbing, authorization and provenance workflow is agreed.

## Runtime rechecked on 2026-10-15

| Item | Observed value |
|---|---|
| Branch | `review/production-improvements-clean` |
| API container/image | `observatory-document-api` / `observatory-document-api:qwen-testing-20261006` |
| API image ID | `sha256:b9a5c6a3c865d560ecc454c05b6c02f0673d605f8a593bdeebb79298564296c2` |
| App Python SHA-256 | `2bf49adf38c857f8bd05a5a44c3e9ad9618fabab26d489e6cb1edfd8d79db70f` |
| Health | PostgreSQL, vector database, Python worker and claim verifier all `ok` |
| Model | `notbot-qwen27:testing-32k`, based on installed standard Qwen27 Q4_K_M |
| Request profile | Temperature 0; output 2,048; no-thinking request; timeout 180s per generation attempt; SDK automatic retries 0 |
| Actual model context | 32,768 tokens, observed in Ollama `/api/ps` |
| Active corpus | `phase6-2026-10-01-v10` |
| Index | Environment `recovery-mxbai`; table `public.rag_recovery_mxbai_20260930` |
| Embeddings | `mixedbread-ai/mxbai-embed-large-v1`, 1,024 dimensions |
| Active population | 483 documents / 5,479 chunks; zero multiple-active-version sources; zero CSC chunks |
| Retrieval settings | `topK=8`, primary cap 2/source, similarity floor 0.3; bounded neighbour expansion can add evidence |
| Frontend | No local listener on 8092 or 8093; actual target PHP/browser deployment is not verified |

The deployed app hash matches local code, and the database settings file is
byte-identical to the recorded October 6 snapshot. The current Qwen manifest
matches [the profile receipt](docs/qwen-testing-profile.md). No restart, model
switch, reindex, ingestion or service configuration change was needed for this
handoff's checks. Unrelated coding-agent model services were left alone.

The stored index is **not duplicate-free**: the earlier v10 report records 379
duplicate rows and 167 heading-only rows. Selected-context deduplication is a
separate property. The active-count and CSC checks above do not certify every
stored row's usefulness or source approval.

## Evidence: distinguish fresh checks from historical acceptance

| Date/scope | Result | Interpretation |
|---|---|---|
| Oct 15 offline backend fixtures | 123/123 pass | Fresh container run, network disabled, repository read-only |
| Oct 15 offline model-tooling fixtures | 24/24 pass | Fresh recovery/hash/facet/profile harness tests, no inference |
| Oct 15 frontend function fixtures | Pass | JavaScript proxy/history/bounds/context/clear/escaping; not a browser test |
| Oct 15 runtime verification | Health, image/app identity, selected model settings and read-only index aggregates pass | Current snapshot, not a new complete operational evaluation |
| Oct 6 Qwen HTTP operational bank | 56/57; English subset 55/56 | Sole failure is the known teloffset source gap; one historical German case retained |
| Oct 6 isolated PHP 7.4.33 integration | 13/13 | Fixture proxy, not the actual target or browser |
| Oct 1 Phase 6 Command R repetition | 168/171 across three complete runs | Same teloffset failure each time; preserve original receipts |
| Oct 1 Qwen forced-generator comparison | Temperature 0: 99/120; 0.1: 97/120; 0.3: 91/120 | Different bank/path from core service tests; do not pool scores |

Fresh non-sensitive snapshot: [verification receipt](reports/handoff/2026-10-15-verification.json).
The full HTTP/generator/PHP suites were **not rerun on Oct 15**. Their dates and
qualifications above are intentional, not a claim of fresh whole-service acceptance.

In the earlier small matched service-generation sample, Qwen's median was
7.22s versus Command R's 23.44s (five generated answers/model). That supported
the owner-authorized **testing-only** switch, not equal-quality certification.
Most core answers bypass generation; overall fast core timings cannot establish
generator latency. Load, cold-start, concurrency and shared-agent contention
remain unapproved/unmeasured release gates for the Qwen deployment.

## Remaining work, in suggested order

| Priority / tracker | Required next action | Completion evidence |
|---|---|---|
| Critical — P6.16 | Bind procedural claims to instrument applicability/exclusions and cross-claim consistency | Reject contradictory NOTCAM interruption instructions, including ordinary requests, paraphrases, negations and mixed histories; independent owner review |
| High — P6.15 | Repair typed count/range proof and legitimate-question intent handling without relaxing support checks | Correct FIES counts and NOTCAM wavelength inferences accepted; wrong roles/counts/units, incomplete tables and invented citations remain rejected |
| High — P6.10 / P1.5 | Obtain owner-approved sources and corpus decisions | Complete autoguided teloffset sequence, current Cassegrain load guidance, reconciled current FIES resolving powers, reviewed borderline source exclusions |
| High — P6.8 / P6.9 | Capture a new versioned baseline after repairs and compare Qwen with Command R | Complete repeated English generator and whole-service runs on the exact final app; no rewritten frozen expectations or hidden failures |
| High — P6.11 | Independent instrument-owner review across all supported areas | Published sampling method/denominators; at least 95% semantic citation precision and 100% safety/procedure completeness |
| High — P6.13 | Establish supported, reproducible ARM/GPU dependencies | Resolve `nvidia-cusparselt-cu13` platform-tag/package-consistency failure; exact clean image passes imports, package check, CUDA, fixtures and acceptance |
| High — P6.12 / P6.14 / P6.6 | Complete measured rollout acceptance | Approved latency budgets, cold/warm/concurrency and shared-GPU tests, actual PHP 7.4 target/browser, sustained canary and reversible cutover |
| Separate experiment — P6.17 | Run measured shadow-only scope/chunk/packet A/Bs | Same immutable sources and fixed model/verifier; preserve complete tables, exceptions and procedure prerequisites; no automatic live reindex |

The forced-generator NOTCAM failures are **accepted contradictory actions**, not
just false refusals or harmless mentions of a forbidden command. Every tested
temperature exhibits this issue. The ordinary source-derived route can pass
the same topic while masking it. Do not close P6.16 because the core bank is
nearly green, or weaken quotation/NLI/citation guards to close P6.15.

Useful starting points: [source/proof review](reports/model-evaluation/qwen27-quality-v1/REVIEW_FINDINGS.md),
[procedure review](reports/model-evaluation/qwen27-quality-v1/PROCEDURE_REVIEW.md),
[clean-build findings](reports/phase6/DEPENDENCY_BUILD_FINDINGS.md),
[retrieval experiment plan](NOTBOT_RETRIEVAL_OPTIMIZATION_PLAN.md).

## Code map

- `documentApi/app/chat_service.py`: retrieval/selection, source-derived routing,
  model requests, repair, validation, metrics and audit orchestration.
- `conversation_context.py`, `evidence_selection.py`, `source_policy.py` and
  `reference_focus.py`: subject resolution, evidence scope and authority.
- `grounding.py`, `semantic_support.py`, `table_facts.py`,
  `wavelength_reasoning.py`, `sourced_procedures.py`: claim support and checked
  derivations/procedural extraction. Inspect both routes when diagnosing a failure.
- `worker.py`, `document_processing.py`, `html_processing.py`, `source_identity.py`,
  `ingest_service.py` and `vector_store/`: conversion, lifecycle, storage and ingestion.
- `chatBotPHP/`: observer-facing UI/proxy; local `config.php` is intentionally ignored.
- `config/corpus_policy.v1.json`, `scripts/corpus_curate.py`,
  `scripts/build_structured_shadow.py`: manifest-driven corpus/shadow tooling.
- `scripts/tests/`, `scripts/evaluation/`: regression fixtures and acceptance/model
  harnesses. Frozen evidence/attempt identities must survive interruption/recovery.
- `NOTBot-documents` is a **separate local-only repository**. Its crawler/data and
  `NOTBot-shadow` trees are not packaged or published by pushing this repository.

Except where prefixed, backend filenames above are under `documentApi/app/`.

## Running and verifying safely

Start with [the Qwen runbook](docs/qwen-testing-profile.md). Its Compose overlay
is required for the current testing image; plain base Compose may select a
different image. The `.env`, private corpus mount and existing data volumes are
host-local prerequisites, not recreated by a Git clone. The layered image also
depends on a retained local Phase 6 base image; it is not a portable clean build.

Fresh offline verification, from the repository root:

```sh
docker run --rm --network none -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e PYTHONPATH=/work:/app -v "$PWD:/work:ro" --entrypoint python observatory-document-api:qwen-testing-20261006 -m unittest discover -s /work/scripts/tests -p 'test_*.py'
docker run --rm --network none -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e PYTHONPATH=/work:/app:/work/scripts/evaluation -v "$PWD:/work:ro" --entrypoint python observatory-document-api:qwen-testing-20261006 -m unittest discover -s /work/scripts/evaluation -p 'test_*.py'
node scripts/tests/test_php_frontend_phase6.cjs
```

For a new complete operational run, use an explicit private output directory:

```sh
NOTBOT_REVIEW_OUTPUT=$(mktemp -d /tmp/notbot-review.XXXXXX)
python3 scripts/evaluation/evaluate_operational.py --output "$NOTBOT_REVIEW_OUTPUT/operational.json"
```

Expect a nonzero exit while teloffset remains unresolved; inspect the actual
case failure and retain it. Do not use `--only` output as full acceptance. New
API tests create fresh normal audit entries and generated cases use the shared
GPU. Schedule full quality/load tests separately; do not silently stop agents.
The PHP verifier requires a separately configured isolated PHP 7.4 fixture;
its synthetic logging check must not target the real conversation log tree.

Rollback is documented in [the Qwen profile](docs/qwen-testing-profile.md).
Restore the private pre-switch chat-settings backup before reverting the API
image. An image-only revert leaves persisted Qwen settings in place. Index and
full data restore instructions/evidence are historical in
[the recovery report](reports/recovery/RECOVERY_REPORT.md) and
[Phase 6 runbook](NOTBOT_PHASE6_RUN.md); update the expected corpus/hash to the
intended snapshot. Do not restore a database over the active one for a test.

## Security and publication boundaries

- Current Docker mappings publish API 8000, PostgreSQL 5432 and Ollama 11434,
  11435 and 11911 on all IPv4/IPv6 interfaces. External reachability/firewall,
  TLS and authentication were not established by the handoff checks. Restrict
  exposure and review backend/settings access before use beyond trusted testing.
  PHP reverse-DNS gating does not by itself secure the directly exposed backend.
- Never publish real `.env`/PHP config, settings, passwords, MCP bearer tokens,
  audit keys/logs, database dumps, private corpus or raw model evidence/output.
  Use example configuration and transfer necessary secrets/backups separately.
- Backend audit encryption is distinct from PHP logs, browser local storage,
  Docker/model-service logging and transport privacy. Keep those controls separate.
- Common credential/private-key-pattern checks of outgoing text objects and
  local changes found no matches during preparation. Public model JSON structure
  checks found no raw prompt/document/credential payload fields. These are
  bounded smoke checks, **not** a complete secret/privacy certification.
- `outputs/` is ignored now but contains pre-existing tracked evaluation files.
  An ignore rule does not remove tracked files or Git history. Do not assume
  ignoring a path sanitizes it. No history or accepted author metadata was rewritten.
- Full fresh answers and the October 6 rollback settings stay outside Git in the
  restricted location referenced by the Qwen runbook. They are not part of the
  review-branch push. Producer repository/data remain local-only.

## Reviewer decisions requested

Please review this as recoverable experimental work, not an observing-system
release. Assign owners for P6.15/P6.16, the source conflicts and independent
instrument review; decide whether to complete those repairs here or preserve
this branch as the reference for a separately scoped successor. No successor
implementation, production deployment or main-branch merge is authorized by
publishing this handoff.
