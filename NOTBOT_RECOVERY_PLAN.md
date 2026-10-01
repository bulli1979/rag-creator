# NOTBot operational recovery

Started: 2026-09-30. Baseline: `7891d6a`. No production/main merge or push is authorized by this work.

Updated: 2026-10-01. Recovery is running as a local testing canary on corpus
`recovery-2026-09-30-v9` / environment `recovery-mxbai`. See
[recovery report](reports/recovery/RECOVERY_REPORT.md) for causes, limitations,
test receipts and rollback. This does not certify a remote frontend deployment
or close all production release gates.

## Intended usage and completion criteria

The PHP frontend README defines NOTBot as a conversational assistant for NOT observers and staff: instruments, observing procedures, data handling and site logistics. The quality review additionally requires exact technical values, actionable sourced procedures, honest information gaps, and no invented safety diagnoses. Basic answer availability is a release requirement, not something to defer until after grounding work.

Recovery must preserve privacy, source lifecycle, PII protection and stable citations while correcting false refusals, misleading historical answers and lost conversation context. No answers may be hard-coded from evaluation expectations. Actual retrieved documentation must support them. Model replacement is out of scope unless evidence establishes it is necessary.

## Work tracking

| ID | Investigation / implementation | Status | Acceptance evidence |
|---|---|---|---|
| R0 | Capture runtime/config/index baseline, compare phases 0–5, and reproduce reported failures | Complete | Frozen `before-7891d6a.json`: 12/31 core; runtime/index/config inspected; source-recall comparison uses identical evidence |
| R1 | Establish representative operational and original 24-question evaluations, with meaningful answer/citation/completeness checks | Complete | 57 acceptance cases plus 24 diagnostic questions; legacy expected answers are reviewed, not blindly scored; final-report completeness is checked |
| R2 | Preserve ordinary conversational subjects, spelling variants and explicit topic switches | Complete | Reported FIES/NOTCAM chains, identifiers, topic switch, ambiguous and unnamed subjects pass |
| R3 | Restore current-document hierarchy and coherent source structure, including tables and historical scope | Complete, source gaps retained | Shared repaired converter; 482-source v9 rebuilt; 7 reviewed public additions; 3 unresolved damaged PDFs remain quarantined |
| R4 | Correct evidence retrieval, neighbor expansion, numerical identifiers and configuration drift | Complete | Pinned mxbai/query prefix and isolated 1024-dimension index; exact source-derived inventories/rows; topic-matched bounded report lookup; deduplicated neighbors |
| R5 | Replace brittle grounding rejection with evidence-backed paraphrase/reasoning checks and accurate failure reporting | Complete for recovery scope | Local pinned English NLI plus independent guards; deterministic source extraction/checked inference; subject/value/procedure regressions covered; verifier remains fallible |
| R6 | Verify full pipeline and PHP frontend against the baseline, review every failed or ambiguous case | API/evaluation/review complete; fresh browser check blocked | 56/57 core; common 12/31 → 30/31, no regressions; all 24 diagnostics reviewed (20 supported, 2 clarifications, 2 gaps); 113 API + 5 producer fixtures; 27/27 repeated checks; final-image/hash/persistence receipt and PHP7.4 lint. Browser URL policy blocks fresh UI access; remote deployment unknown |
| R7 | Update original plan, document remaining limitations and rollback; leave a clear handoff | Complete for local recovery handoff | Phase6 operational acceptance requirements/order updated; complete final results and limitations recorded. Pointer rollback passed; full backup restore, actual target browser check, source-owner review and production acceptance remain open |

## Established causes (audit-backed)

- Instrument follow-ups containing component nouns (`different fibers`) or spelling errors (`fivers`) were marked standalone even when their user history unambiguously named FIES.
- FIES landing-page fibre documentation is indexed, but lost to design PDFs in final ranking. Filename-based overview preference does not recognize the landing page.
- Source disposition was equated with factual currency: design PDFs and old bundle sections carried `active` / `tier_2_reference` metadata indistinguishable from operational pages.
- Fibre #4 aperture answer was generated correctly twice but rejected: identifier `4` was treated as an unsupported measurement, and literal term overlap punished `fibre`/`fiber` and `high-res`/`high-resolution`.
- Wrong six-fibre answer was rejected when concise but accepted after adding irrelevant words. Lexical overlap is not a reliable semantic verifier.
- D3 and spare-bundle tables were flattened and split; generic site-brand headings obscured section identity.
- Intended earlier configuration: mxbai embedding model / topK 8. The pre-recovery runtime had drifted to MiniLM / topK 5. Recovery restores pinned mxbai / topK 8 after an identical-evidence comparison.
- Existing tests did not measure operational correctness or full before/after answer quality sufficiently. The prior Phase 5 acceptance claims were too broad.

## Evaluation discipline

Persist public test questions, outcomes, timing and source identity only; do not export keys, private logs or raw internal corpus material. Retain encrypted detailed runtime audits. Freeze the before snapshot prior to implementation. Distinguish correct answers, partial answers, wrong/outdated answers, genuine gaps, source conflicts, failed validation and model errors. Review safety outcomes directly rather than trusting an LLM judge alone.

## Remaining release work

- Supply a reviewed current internal `teloffset` autoguiding sequence; keep its
  unanswered acceptance case visibly failing until evidence exists.
- Resolve FIES guide/landing-page resolving-power discrepancies with a domain owner.
- Obtain current Cassegrain load limits and review the UIF guide's specific-error
  conditions; do not use historical design constraints or recommend a conditional
  hardware remedy for an unspecified error.
- Finish domain-owner corpus review, representative human citation/safety review,
  sustained canary telemetry and an agreed latency budget.
- Verify a fresh dependency-resolving build and a full backup restore on an
  isolated database. Tested index-pointer rollback is not that restore test.
- Keep model replacement deferred until these quality gates are understood.
