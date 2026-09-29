# Phase 1 corpus-policy dry run

Policy: `1.0.0`
Corpus version: `phase1-candidate-2026-09-29`
Source snapshot: `bb70f53a833d0f5d61d6b2bed64c06b134952c84769bb9e871a2e72b313ba208`

## Outcome

| Disposition | Documents | Projected legacy chunks |
|---|---:|---:|
| active | 381 | 2964 |
| excluded | 29 | 704 |
| historical | 215 | 4320 |
| quarantine | 418 | 8978 |

Projected default-search active chunks: **2,964**, a **93.3%** reduction from the 44,419 live-row baseline. This projection removes stale versions as well as policy-excluded sources; it is not an evaluation result.

Domain-owner review queue: **633 documents**.
Near-duplicate candidate pairs: **11**.

## Dispositions by category

| Category | Active | Historical | Quarantine | Excluded |
|---|---:|---:|---:|---:|
| [missing] | 0 | 0 | 2 | 0 |
| education | 0 | 0 | 0 | 7 |
| fault_report | 0 | 201 | 0 | 0 |
| general_info | 0 | 0 | 0 | 4 |
| instrument_configuration | 1 | 0 | 0 | 0 |
| instrument_documentation | 333 | 14 | 139 | 14 |
| internal_operations | 0 | 0 | 250 | 0 |
| news | 0 | 0 | 0 | 1 |
| observing_guide | 36 | 0 | 13 | 3 |
| sequencer_reference | 1 | 0 | 0 | 0 |
| telescope_info | 10 | 0 | 14 | 0 |

## Decision reasons

| Reason | Documents |
|---|---:|
| policy_default_active | 381 |
| pii_redaction_may_corrupt_technical_values | 208 |
| historical_fault_record_requires_domain_review | 201 |
| internal_operations_requires_domain_review | 173 |
| encoding_or_conversion_damage | 20 |
| short_content_requires_review | 15 |
| redundant_query_variant | 14 |
| retired_instrument_documentation | 14 |
| non_operational_category | 12 |
| generated_or_live_page | 3 |
| missing_required_metadata | 2 |

## Readiness

The shadow corpus is a policy candidate, not a production-ready replacement. Domain-owner decisions and comparative retrieval/answer evaluation remain required before rollout.
