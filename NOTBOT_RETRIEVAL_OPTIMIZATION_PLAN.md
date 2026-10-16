# NOTBot retrieval and evidence optimization experiment

> **danka branch:** Experiment plan from the review branch; referenced `reports/` files are not included in `danka`.

Date: 2026-10-01. Owner suggestion: optimize vector retrieval/chunking for the
Qwen27 chatbot. Status: **inspection and plan only; no reindex or live change**.
This is separate from the completed frozen 360-response temperature comparison.
Its saved outputs were verified after interruption; no setting is quality-approved.

## What we know

Read-only inspection of the running final app found:

- Embeddings: `mixedbread-ai/mxbai-embed-large-v1`; these, not Qwen's generator
  weights, define document/query vector similarity. Keep them fixed initially.
- Active index: `public.rag_recovery_mxbai_20260930`; live catalog shows only
  primary-key, document-id and source/active B-tree indexes. Cosine-distance
  ordering is exact, not HNSW/IVFFlat approximate search. There is no observed
  ANN recall defect to fix by increasing an ANN search parameter.
- Live `topK=8`, `maxChunksPerSource=2`, `minEvidenceSimilarity=0.3`.
  Candidate retrieval widens before source-aware selection; bounded neighbour
  expansion can add two chunks. Eight is not a hard final packet-size limit.
- Live parse settings are `chunkSize=900` characters, `chunkOverlap=150`.
  `worker.py` deliberately ignores overlap with the structured parser.
  Structured parsing follows headings and semantic blocks; tables up to 6000
  characters stay whole, and some keyboard-interaction paragraphs up to 2400
  stay whole. These are not Qwen tokenizer budgets.
- Ingestion first reuses stored JSONL corpus rows if available. Changing the
  parse setting alone does not guarantee those imported rows are re-chunked.
  A shadow rebuild must establish the actual raw-source-to-chunk lineage.
- Evidence preparation has a per-item character bound; this is not an aggregate
  input-token cap, and metadata/history also occupy context.

Current code evidence: `documentApi/app/{worker,document_processing,ingest_service,
chat_service,evidence_selection,grounding}.py` and
`documentApi/app/vector_store/postgres_store.py`. Existing v10 receipts identify
483 sources/5479 active chunks, not a new corpus count performed for this plan.
No read of historical encrypted conversations was needed.

The completed refusal review already found correct FIES inventory evidence and
NOTCAM wavelength evidence in the supplied packets. Those cases need a typed
proof/relevance fix, not simply more retrieval. The NOTCAM procedure failure is
also not just a missing exception: the cited item already contains it, but a
generic instruction is accepted in conflict with the instrument exception.
Better source scope can help; validation must enforce that scope too. See
[review findings](reports/model-evaluation/qwen27-quality-v1/REVIEW_FINDINGS.md).

## Proposed sequence and tracking

| ID | Experiment/work | State |
|---|---|---|
| R0 | Inspect active settings, exact/ANN status and chunking code | Done, read-only |
| R1 | Finish frozen Qwen quality run; retain all failures and exact identities | Complete360/360,485 attempt hashes verified; release blocked |
| R2 | Repair/retest typed proof and instrument applicability contracts, P6.15/P6.16 | Required; not implemented |
| R3 | Establish retrieval/packet measurements and labelled source expectations | Planned |
| R4 | Shadow section/scope-preserving chunk variants | Planned |
| R5 | Packet selection/order/token-budget A/B tests | Planned |
| R6 | Database acceleration or new embeddings only if evidence warrants it | Conditional |
| R7 | Repeat whole-service, HTTP/PHP, safety and concurrency acceptance | Required before promotion |

R3 can begin as read-only analysis before R2, but retrieval improvements cannot
be declared a chatbot fix while R2's shared verifier defects remain. Never edit
the current frozen evidence or app underneath R1. A revised app has its own
versioned baseline/control run, not retrospectively improved R1 scores.

### R3: attribute the bottleneck and coverage

Use fresh, consented English test queries, not historical audits. Record query
embedding, candidate search, filename/reference augmentation, selection,
neighbour expansion, prompt evaluation, generation, repair and validation times
separately. The existing `retrievalMs` combines several retrieval steps; it is
not database-only timing. Measure complete validated answer latency and errors,
not just first token or vector-search speed.

Label required source sections/table rows, explicit instrument exclusions,
ordered prerequisites/recovery steps and genuine documentation gaps for every
case. Measure required-evidence recall, rank, duplication, obsolete/conflicting
source exposure, exception retention, table completeness, total packet tokens
and actual prompt-evaluation token counts. Inspect the embedding tokenizer's
input truncation too: an intact large table can exceed embedding input capacity.
Retain full provenance and full source proof separately from any short search
representation; do not certify completeness from a truncated representation.

### R4: chunk semantics, not arbitrary smaller windows

Build versioned **shadow** corpus/indexes from the same immutable source snapshot
and allowlist. Do not crawl new documents, delete originals, activate the shadow
index or rewrite imported JSONL in place.

First compare the existing chunker with a scope-preserving variant at the same
900-character target. Commands need their applicable instrument/mode and linked
exclusions; procedures need prerequisites, ordered steps, interruption/recovery
and safety conditions. Preserve table headers, units, full inventory identity,
version and proof of completeness. Carry exception scope across headings when
authoritative source structure demands it; mere adjacency is insufficient.
Do not join different versions or configurations to manufacture completeness.

Then test 600/1200-character targets one at a time, treating targets as soft
budgets. Keep coherent safety/procedure/table units intact or use a short child
search representation linked to the complete bounded parent evidence. Reject
overflow/truncation visibly instead of quietly dropping a warning or table row.
The generator may receive scoped excerpts, but exact quotes/IDs must still map
to immutable original source offsets. Exceptions cannot be removed to make a
generic command appear applicable.

Re-embed changed shadow chunks with the same pinned mxbai model. Changing
chunk boundaries changes vectors, source/chunk IDs and retrieval; capture new
evidence packets under a new identity. Compare against an unchanged control
using the same source snapshot, query bank and fixed generator parameters.

### R5: selection and prompt packaging

Only after R3 establishes completeness, compare one factor at a time:

1. Existing selection versus scope-aware parent/child evidence selection.
2. Eight selected chunks versus four/six with measured aggregate token budgets;
   retain all required exceptions, table rows and procedure steps. A packet that
   cannot fit must report a coverage gap, not claim unsupported completeness.
3. Authority/conflict handling and deduplication while preserving legitimate
   current technical-reference coverage. Do not blanket-exclude design documents
   needed for the question; mark historical/spare configurations explicitly.
4. Evidence ordering: authoritative applicable answer plus exception first,
   compared with current order. Keep source IDs stable and explicit boundaries.
5. A reranker only if labelled recall/ranking justifies its extra CPU/GPU cost.

Use Qwen's actual tokenizer/context accounting for packet budgets, not character
counts alone. Keep the generator weights, temperature, output cap, sampler,
reasoning mode and verifier fixed within each A/B pair. Leave sufficient output
room for complete procedures; don't create speed gains by truncating answers.

### R6: vector database and embeddings

Benchmark exact search first with read-only query plans/timings on the current
corpus. Add HNSW only if database time materially limits complete-answer latency;
compare filtered recall against exact search for instrument/status/source rules.
Approximate search trades recall for speed; index creation is a separate shadow
change, not a generator-specific optimization.

An alternative embedding model is a later independent experiment requiring
complete shadow re-embedding, matched query instructions, new dimensionality/
index identities and source-recall checks. Do not put Qwen generator vectors
into the current mxbai index or mix embedding families.

Primary references: [pgvector search and indexing documentation](https://github.com/pgvector/pgvector)
documents exact versus approximate search and filtered ANN constraints.
[Lost in the Middle](https://arxiv.org/abs/2307.03172) motivates testing evidence
position, but does not establish a Qwen27-specific result; our local A/B test must.

## Acceptance and reporting

Freeze and hash source snapshots, chunker code/settings, embedding revision,
index identity, app/verifier, query bank, prompt/profile and Qwen weights. Store
private new prompts/evidence/outputs in restricted storage; public reports use
hashes and metrics. Original 360-run receipts are immutable historical evidence.

Use all 40 English generator cases with three repeats plus the whole-service
English bank and added source-scope cases. Include FIES count/resolution/fibre4
aperture, NOTCAM 500nm/in-range follow-ups, complete dark/interruption sequences,
unsafe/negated command requests, long/mixed histories, citation injection,
obsolete/spare designs and true gaps. Independently inspect operational answers,
including apparent passes and regex-based failures.

Release requires zero critical wrong instrument actions, no accepted wrong
counts/units/IDs, complete required procedures, and no unexplained regression
in supported-answer usefulness/citation support. Predeclare latency targets and
review thresholds before running R4/R5; publish matched sample sizes, per-case
outcomes, first-load versus warm conditions, median/p95/tails, repairs and errors.
Treat accuracy as a gate, not something averaged away by faster refusals.

No model/index switch or corpus purge is authorized by this plan. Promotion
requires owner approval after API/PHP final-build, restart/rollback and shared-
GPU concurrency verification. No automatic commit or push.
