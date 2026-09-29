# Phase 0 baseline review

Review date: 2026-09-29
Snapshot: `production-2026-09-28`
Application baseline: `0c4741170eb9b80e5e2e46023612bd348126fed2`
Corpus snapshot: `bb70f53a833d0f5d61d6b2bed64c06b134952c84769bb9e871a2e72b313ba208`

## Disposition

Approved as the reproducible pre-improvement baseline. This approval establishes comparison data; it is not an approval of current production quality. The baseline has material evidence-lifecycle, corpus-quality, retrieval, and evaluation limitations that must be addressed in later phases.

## Confirmed baseline

- 1,043 processed Markdown sources representing 838 populated canonical source URLs.
- 2,834 SQLite document records, all marked `done`, for 1,043 filenames.
- 44,419 live vector chunks and 2,834 document IDs.
- 1,041 of 1,043 filenames have multiple document IDs; the maximum is 86.
- 8,766 exact duplicate chunk groups containing 15,205 redundant rows beyond the first copy.
- Duplicate rows comprise 34.23% of the live vector index.
- 2,273 live chunks contain `[phone removed]`.
- 1,072 live chunks contain `Back to top`; 1,072 contain `Last modified`.
- All 44,419 vector chunks use the same generic `not-telescope` and `scrubbed` tags.

Compared with the August review, the index has grown from 40,663 to 44,419 chunks and redundant duplicate rows have grown from 13,392 to 15,205. This confirms that stale-version accumulation is active rather than historical.

## Stratified corpus review

### Dynamic/query sources

The 21 query-parameter URLs require policy by parameter purpose:

- Fourteen filter-table URLs are display/sort variants and are strong candidates for canonical consolidation.
- Two Aladin pages are generated views; each now has 86 indexed document versions and should be excluded or normalized.
- Instrument-specific cookbook URLs use a meaningful `instrument` parameter and should remain distinct, authoritative sources.

A blanket rule that removes every query-string URL would therefore delete useful documentation.

### Short sources

The 19 bodies under 100 non-whitespace characters are mixed:

- Some are useful atomic references, such as NOTCam mechanism-position definitions.
- Some are image captions without the underlying informational image.
- Some are blank operational forms with little retrieval value.

Short length is a review flag, not an automatic exclusion rule.

### PII corruption

Sampled `[phone removed]` occurrences confirm both legitimate contact removal and destructive false positives. Corrupted examples include wavelength ranges, detector overscan ranges, observation dates, FITS identifiers, scientific table values, filenames, and contract/version identifiers. The numeric-safe scrubber work remains a prerequisite for the clean corpus rebuild.

### High-growth sources

- Three Aladin variants each have 86 versions and about 513-516 chunks.
- `instruments-fies-standards-html.md` has 84 versions and 504 chunks.
- `faults_active_alfosc_2026.md` has 34 versions and 1,806 chunks.
- `optic_elements.md` has 34 versions and 2,720 chunks.

These sources demonstrate why stable source identity and latest-only indexing must accompany corpus curation.

## Evaluation review

The existing 24-question suite completed against the live API and a local Command R 35B judge:

| Metric | Count | Mean |
|---|---:|---:|
| Answer relevance | 24 | 0.9250 |
| Context relevance | 24 | 0.9833 |
| Groundedness | 24 | 0.9000 |
| Answer correctness | 21 | 0.7567 |

Three answers received no numeric correctness score from the judge, so correctness coverage is 21/24. Four of the 21 scored answers received correctness `0.0`.

Representative failures support the review's retrieval diagnosis:

- ALFOSC plate scale: `0.109` returned instead of `0.19` arcsec/pixel.
- Amplifier A RON: `3.00` returned instead of `3.25 ± 0.05 e-`.
- Telescope field of view: an instrument mode's `3.93` arcmin returned instead of the telescope's `30` arcmin.
- ALFOSC focus: `1610` returned instead of `26630`; TV focus was correct.
- Large Proposal duration, teloffset sequence, and OB interactive target identification missed the requested fact or procedure.
- The safety-sensitive weather answer returned 100% humidity instead of the expected 90% threshold.

The judge assigned very high context relevance even to several objectively wrong answers. Aggregate local-judge scores are useful for comparison but cannot replace deterministic numeric checks and human review of safety cases.

## Phase 1 implications

1. Start with a versioned manifest and reversible dispositions.
2. Canonicalize query parameters by explicit policy, preserving instrument-specific cookbooks.
3. Make stale version removal a lifecycle change, not a one-time duplicate deletion.
4. Treat short length as one signal among authority, uniqueness, structure, and evaluation coverage.
5. Protect technical numeric spans before applying phone-number redaction.
6. Add deterministic expected-value checks and safety gates to the evaluation suite.
