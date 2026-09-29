# Phase 1 corpus-policy dry run

Policy: `1.0.2`
Corpus version: `fresh-crawl-2026-09-29-curated-v2`
Source snapshot: `3d61f7d209f8d63a025f656a34f572e14c449fb82337892a62104c91b5767d3a`

## Outcome

| Disposition | Documents | Projected legacy chunks |
|---|---:|---:|
| active | 478 | 4357 |
| excluded | 29 | 704 |
| historical | 216 | 4325 |
| quarantine | 283 | 6933 |

Projected default-search active chunks: **4,357**, a **90.2%** reduction from the 44,419 live-row baseline. This projection removes stale versions as well as policy-excluded sources; it is not an evaluation result.

Domain-owner review queue: **499 documents**.
Near-duplicate candidate pairs: **7**.

## Dispositions by category

| Category | Active | Historical | Quarantine | Excluded |
|---|---:|---:|---:|---:|
| education | 0 | 0 | 0 | 7 |
| fault_report | 0 | 201 | 0 | 0 |
| general_info | 0 | 0 | 0 | 4 |
| instrument_configuration | 1 | 0 | 0 | 0 |
| instrument_documentation | 411 | 15 | 60 | 14 |
| internal_operations | 0 | 0 | 216 | 0 |
| news | 0 | 0 | 0 | 1 |
| observing_guide | 45 | 0 | 3 | 3 |
| sequencer_reference | 1 | 0 | 0 | 0 |
| telescope_info | 20 | 0 | 4 | 0 |

## Decision reasons

| Reason | Documents |
|---|---:|
| policy_default_active | 478 |
| historical_fault_record_requires_domain_review | 201 |
| internal_operations_requires_domain_review | 189 |
| encoding_or_conversion_damage | 48 |
| pii_redaction_may_corrupt_technical_values | 31 |
| retired_instrument_documentation | 15 |
| short_content_requires_review | 15 |
| redundant_query_variant | 14 |
| non_operational_category | 12 |
| generated_or_live_page | 3 |

## Readiness

The shadow corpus is a policy candidate, not a production-ready replacement. Domain-owner decisions and comparative retrieval/answer evaluation remain required before rollout.
