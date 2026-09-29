# Phase 4 retrieval baseline and first selector

Corpus: `fresh-crawl-2026-09-29-curated-v2`, 478 active documents and 4,997 live chunks. Tested against the 24 questions in `reports/phase0/evaluation-production-2026-09-28/questions_ground_truth.csv`, using the local PostgreSQL index, the existing embedding model, top K 5, and 40 vector candidates per query. The old hybrid ranker and new selector received the same candidate lists. This measures evidence selection, not answer correctness.

| Metric across 24 questions | Old ranker | Phase 4 selector |
|---|---:|---:|
| Final context chunks | 120 | 116 |
| Exact duplicate text rows beyond first | 3 | 0 |
| Rows beyond two per stable source | 14 | 0 |
| Chunks tagged for an unrelated instrument in instrument-specific queries | 6 | 0 |
| Questions with no evidence | 0 | 0 |

The new selector uses stable source IDs, removes exact text duplicates and formatting-only variants, and caps each source at two chunks. It recognizes explicit instrument names and historical intent. Current and higher-authority material receives a modest score preference; technical numbers and word order are preserved in duplicate comparisons.

The initial evidence floor is raw vector similarity 0.43. Two supported ALFOSC questions had top similarities of 0.617 and 0.689. Two deliberately unsupported questions had top similarities of 0.331 and 0.390; the rebuilt chat API abstained on both without calling the answer model. `What is ALFOSC used for?` returned five distinct sources and a cited answer in 9,786 ms. This floor is provisional and needs a larger corpus-gap and paraphrase evaluation before release.

Focused tests: `python3 -m unittest scripts.tests.test_retrieval_phase4 -v` (8 passed) and `/home/llmrunner/NOTBot-documents/venv/bin/python -m unittest scripts.tests.test_source_lifecycle -v` (7 passed). The test fixtures cover exact and formatting-only duplicates, changed technical values, source caps, instrument distractors, current versus historical intent, and an unsupported query.

Limitations: The active index deliberately excludes historical documents, so historical routing is fixture-tested but not validated against live historical retrieval. Validity is represented by active/historical status in the current vector schema; the separate `validity` frontmatter value is not yet persisted. Neighbor expansion, answer-level comparative evaluation, and a cross-encoder experiment remain open. Frontend typecheck could not run locally because `npm` is unavailable.
