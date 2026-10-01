# Independent operational review — still required

Technical evaluation is not independent instrument-owner approval. Do not turn
the diagnostic script's `passed` flags into a correctness or citation score.
Review final-v10 answers against their cited source AND current operations.

| Coverage | Technical evidence | Required owner judgment |
|---|---|---|
| FIES | Frozen instrument/fibre/follow-up cases and PHP conversation | Four science fibres versus calibration; #4 aperture; reconcile cookbook/landing resolving powers |
| NOTCam | Range, pixel scales, dark recipe, interruption, conversation | Completeness of Ctrl-C plus waiting for exposure completion; current calibration prerequisites |
| ALFOSC | Grisms, detector reports, acquisition, slitrot, focus, error conditions | Correct detector/version; full acquisition prerequisites; no generic hardware remedy for an unspecified error |
| MOSCA / StanCam | Additional overview cases | Current availability and operations; MOSCA restoration contains ONLY the intact definition paragraph, not damaged specifications |
| DIPol-UF / PolCor / LuckyCam | Additional instrument/reference cases | Visitor/common-user status, current availability, historical versus operational specifications |
| Sequencer | Failing `operational_sequence`, legacy21 | Supply and approve the complete autoguided teloffset sequence; offset syntax is not that sequence |
| Telescope / load | Legacy13 and current-limit gap | Approve current load guidance; counterweight 0.95 user context is not a kilogram limit |
| Site / weather / safety | Humidity, reopening, interlocks, winter-road cases | Conditions and immediate closure requirements; confirm current instructions |
| Data / proposals | Download, PI sharing, initial-duration cases | Access rules, current policy and reference-only qualifications |

- [ ] Use a representative stratified sample across these groups, not only fast
  deterministic answers. Include generated answers, paraphrases and real chains.
- [ ] Record reviewed claims/citations, supported claims/citations, failures and
  sampling method; publish the denominator. At least 95% semantic citation
  precision is required, not established by supplied-ID validation alone.
- [ ] Review every safety/procedure case for complete steps/prerequisites,
  correct instrument/version and no invented or unsafe action (100% pass gate).
- [ ] Resolve the three explicit source issues before calling operational
  acceptance complete: autoguided teloffset, current load guidance, FIES resolution.
- [ ] Record reviewer, date, approved source version and remaining qualifications.

User supplied entry 83 and NOTCam counterweight 0.95 context on 2026-10-01. This is
useful source direction, but is not sign-off on the final answers or all procedures.
