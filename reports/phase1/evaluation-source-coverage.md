# Phase 1 evaluation-source coverage

This is a conservative mapping of sources retrieved by the Phase 0 live evaluation to their Phase 1 manifest dispositions. It does not replace running the evaluation against a rebuilt shadow index.

| Status | Questions |
|---|---:|
| active_source_available | 14 |
| mapped_without_active_source | 8 |
| unmapped_context | 2 |

## Questions without an active mapped source

| Row | Status | Question | Dispositions |
|---:|---|---|---|
| 6 | mapped_without_active_source | What are the four readout speeds provided by the ALFOSC detector controller (CCD3) introduced in 2011? | quarantine |
| 7 | mapped_without_active_source | What is the fundamental frequency of the pick-up noise observed with the ALFOSC controller? | quarantine |
| 8 | mapped_without_active_source | What is the measured readout noise (RON) for Amplifier A in high-gain mode for the E2V CCD42-40? | quarantine |
| 9 | mapped_without_active_source | At what temperature must the ALFOSC E2V (non-AIMO type) CCD be cooled to suppress dark current for RON-limited noise in long exposures? | quarantine |
| 11 | mapped_without_active_source | According to wavefront sensor analysis 100nm of measured astigmatism is equivalent to how many units on the Telescope Control System (TCS)?" | quarantine |
| 13 | mapped_without_active_source | During the winter period (November to April) travelers are advised not to use the ORM mountain road before and after which specific times? | quarantine |
| 16 | mapped_without_active_source | What is the focal plane scale of the Nordic Optical Telescope in arcsec/mm? | quarantine |
| 20 | unmapped_context | Explain the complete sequence of events that occurs when the teloffset program is executed while the telescope is already being autoguided. |  |
| 22 | mapped_without_active_source | Under what specific weather conditions (wind speed and humidity) must the telescope be closed immediately? | quarantine |
| 23 | unmapped_context | What should an observer do if the ALFOSC UIF fails to start with an error message? |  |

A candidate with any `mapped_without_active_source` row has a material regression risk and must not replace the live corpus before domain review, regeneration of corrupted sources, and comparative evaluation.
