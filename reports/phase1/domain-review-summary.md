# Phase 1 domain-review handoff

The policy candidate requires 633 domain-owner decisions:

- 201 fault-report documents are isolated as historical pending confirmation of their diagnostic value and validity.
- 250 internal-operation documents are quarantined pending authority/currentness review.
- 208 documents are quarantined because `[phone removed]` may have destroyed technical values; some overlap internal operations.
- 20 documents contain strong conversion/encoding damage signals.
- 15 short documents require a value-versus-noise decision.
- 14 TURPOL documents are historical because the crawler configuration identifies it as retired.
- 2 documents lack required frontmatter.

The complete queue is `domain-review-queue.csv`. Review priority is:

1. Eight evaluation cases whose mapped evidence is entirely quarantined, listed in `evaluation-source-coverage.md`.
2. Safety and emergency material, including the weather-closing threshold and ORM travel rules.
3. Current procedures and troubleshooting under `/intranot/engineer/procedures/`, `/intranot/engineer/troubleshooting/`, and `/intranot/safety/`.
4. Current-year fault reports with unique diagnostic content.
5. Engineering documentation and older fault records.
6. Remaining internal administrative and meeting material.

This first policy candidate must not replace production. Its projected 93.3% active-chunk reduction exceeds the target but has eight known evaluation-source coverage risks and two unmapped fault-context cases. Regenerate corrupted sources and apply owner decisions before building the comparable shadow index.
