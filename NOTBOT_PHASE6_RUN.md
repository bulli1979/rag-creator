# Phase 6 execution — 2026-10-01

> **danka branch:** Historical run record from the review branch. Referenced `reports/` files (including `reports/phase6/*` and `reports/recovery/RECOVERY_REPORT.md`) and `sequencer_reference.md` are not included in `danka`.

Scope: started from commit `314c41e`, with the working-tree repairs below;
final application hashes identify what was actually tested. Local testing only. No push,
main merge, model replacement or remote cutover. The production API/index/settings
must not be overwritten by build/restore experiments. Public questions and
receipts only; private corpus, settings, dumps and historical audits stay out of Git.

Technical run finished. Release acceptance remains OPEN. Canonical machine-readable
handoff: `reports/phase6/final-verification.json`. Final-v10 stays active; no commit
or push. Both repaired failures are covered by final-image tests.

| Gate | State | Evidence / next action |
|---|---|---|
| P6.9 repeated critical facts/procedures/chains | Completed technical repetition | Three COMPLETE final-v10 runs: 168/171; only the same unsourced teloffset procedure fails each run. reports/phase6/repetition-summary.json |
| P6.10 source gaps/conflicts | Investigated; needs owner input | Entry 83 supplies offset description already indexed, not internal autoguided sequence. Counterweight 0.95 is owner context, not a kg limit. FIES resolving-power conflict remains |
| P6.11 independent domain review | Pending | Technical checks and agent review cannot substitute for independent instrument-owner approval |
| P6.12 latency/concurrency/canary | Bounded warm benchmark complete; release gate open | 132/132 outcomes pass; generated p95 at two workers 76.836s exceeds proposed 45s. Cold starts, sustained telemetry and approved thresholds remain open |
| P6.13 clean build and isolated restore | Partial; dependency gate failed | Fresh build/imports/fixtures/CUDA/API smoke pass; pip check rejects ARM wheel tag. Original and final-v10 PostgreSQL/catalogue/settings/files isolated restore drills pass. Clean dependency image NOT promoted |
| P6.14 PHP7.4 target | Local technical checks pass; actual target pending | Final PHP7.4.33 proxy integration 13/13 plus lint and JS function fixtures. Actual server identity/access absent; previous browser URL denial not bypassed |
| P6.6 sustained canary/cutover | Pending | Bounded local tests are not a sustained operational observation period or production cutover |
| P6.8 smaller model | Deferred | Preserve the reviewed evidence and existing Command R weights |

## Source-review notes

- [FIES landing page](https://www.not.iac.es/instruments/fies/) lists low/medium/high
  resolving powers 25,000/46,000/67,000; the
  [current FIES cookbook](https://www.not.iac.es/observing/cookbook/current/Cookbook.php?instrument=FIES)
  lists 25,000/45,000/65,000. Do not invent a reconciliation.
- [TCS commands](https://www.not.iac.es/observing/seq/tcs-seq-commands.html) and
  [TCS scripts](https://www.not.iac.es/observing/seq/tcs-seq-scripts.html) describe
  individual controls, but do not establish the requested complete internal
  autoguided teloffset sequence. Keep its acceptance case visibly failing.
- The user supplied [ALFOSC teloffset entry 83](https://www.not.iac.es/observing/seq/new/seq-command.php?i=83).
  Direct retrieval confirms only the X/Y arcsecond offset description; it is
  already represented in `sequencer_reference.md`. It does not describe the
  internal autoguiding transition sequence. The user also reports NOTCAM uses
  counterweight setting 0.95, near the current system's capacity. Record this as
  owner-supplied context, not a derivation of an approved kilogram limit.
- [Telescope properties](https://www.not.iac.es/telescope/tti/proptxt.html),
  [2004 adapter design](https://www.not.iac.es/instruments/development/NOT_adapter_may04.pdf)
  and [2009 SCS requirements](https://www.not.iac.es/instruments/development/SCS.pdf)
  describe historical 250 kg design limits. A recent crawl date is not evidence
  of current engineering approval. No load/teloffset source was promoted from this search.

## Repairs and current runtime

- NOTCam interruption could return only Ctrl-C, omitting the documented wait for
  the ongoing exposure to finish. Complete bulleted current command-reference
  extraction and a procedural-completeness guard now preserve that constraint.
  It is copied from retrieved evidence, not a hard-coded answer.
- MOSCA's whole overview was quarantined due to one damaged filter-name character
  elsewhere on the page. Restore only its hash-reviewed intact definition
  paragraph; damaged specifications remain excluded. Recognize the official
  mosaic/MOSCA directory and same-instrument overview link without following
  arbitrary hosts, crossing instruments or promoting design pages.
- New private generation: 483/483 documents indexed, 5479 active chunks, 1024 vector
  dimensions, 0 multiple active source versions, 0 CSC chunks, 0 unresolved CID
  markers. Original raw sources and v9 are retained. 379 exact duplicate rows and
  167 heading-only rows remain stored; selected contexts contain 0 duplicates in
  the complete final evaluation. Do not describe the stored index as duplicate-free.
- Running API image:
  `sha256:999eefe41c1c724b2e56c8671a6edb6dd63882f1fe1cba9aaa339d262ffe3787`.
  Python application hash:
  `24223a4f6bec3af34efb13c27cce79dc6f325365fec127c13189602f647a769b`.
  Application/PHP/JS hash:
  `78253c20415146eff6ed4f7bc447e9394a291ee4afbacaf69d6cbebf30f67c0a`.
- Corpus: `phase6-2026-10-01-v10`; environment: `recovery-mxbai`;
  table: `public.rag_recovery_mxbai_20260930`.
  Command R35B weights unchanged, profile: `command-r-rag:35b`, num_ctx 32768.
  `final-identity.json` binds model/weight digests, retrieval settings and verifier
  pins without publishing credentials, endpoints or prompt bodies.

## Completed evaluation and restore evidence

- `after-final.json`: complete 57 core + 24 unscored diagnostics; 56/57 core.
  `final-comparison.json`: frozen pre-recovery 31 cases 12/31 → 30/31, no regressions.
  This is not an equivalent pre-Phase0 baseline comparison.
- `repeat-final-2.json`, `repeat-final-3.json`: complete 57 cases each; 56/57 each.
  All three share application/case/index/corpus/model identities. Unknown corpus
  traces on instrument-clarification turns have no retrieved evidence, not a
  changed active pointer. Summary rejects incomplete/filtered or mixed-runtime runs.
- Fresh review of all 24 diagnostic answers matches the source-aware assessment
  table in `reports/recovery/RECOVERY_REPORT.md`: 20 supported/reference-qualified,
  2 legitimate clarifications, 2 documentation gaps. Supplied-ID checks do not
  establish independent semantic citation precision.
- `final-fixtures.json`: 120/120 offline API and verification-harness fixtures.
  Producer tests: 5/5 offline in the existing dependency image; system Python lacks
  bs4, so the first bare-host command could not import the producer. No host
  installation or producer modifications were needed. PHP/JS lint and JS
  proxy/history/context/clear/bounds/escaping function fixtures pass.
- `php74-final.json`: 13/13 separate PHP7.4.33 CLI fixture/proxy checks; not a
  browser test or the actual remote server.
- `broad-final.json`: 9/9 additional instrument/control questions, including the
  formerly refusing MOSCA definition and DIPol-UF passband follow-up.
- `legacy-restore.json`: original private dump/catalogue/settings with original
  compatible image; 4997 chunks, 478 documents, 384 dimensions restored. The old
  FIES#4 refusal reproduces old behavior, not new-build quality acceptance.
- `final-restore.json`: final image + final private dump/catalogue/settings/files;
  39536 retained modern chunks, 3373 retained documents; 483 active sources, 5479
  active chunks, only v10, 0 queued, 0 duplicate active versions. All 3 public
  NOTCam/FIES smokes pass. Test databases are separate and have no published ports;
  the live database was never overwritten. Historical audits excluded.
- Private backups/restored files remain under the 700-permission directory
  `/home/llmrunner/NOTBot-shadow/phase6-restore-20261001-J8CT9j`;
  dumps/settings are 600. Original recovery file trees were not an immutable
  dated backup: the original drill uses retained files, with 0 missing catalogue
  paths. Final-v10 has a fresh private file/catalogue snapshot after indexing
  completed. Do not claim crash-consistent concurrent-ingestion backup testing.
- Clean build/package issue details:`reports/phase6/DEPENDENCY_BUILD_FINDINGS.md`.
  Keep unsuccessful intermediate runs/harness attempts visible; they are not
  substituted for final receipts.

## Warm latency and concurrency — measured, not release approval

`latency-concurrency.json` records every outcome, method, stage timing and token
count without exporting prompt or context text. Batches run serially; the complete
acceptance suites finish before this separate benchmark begins.

| Group | Workers | Responses passing checks | Median | p95 / maximum |
|---|---:|---:|---:|---:|
| Source-derived facts/procedures, 15 cases × 4 | 1 | 60/60 | 0.117s | 0.141s / 0.186s |
| Same source-derived cases | 4 | 60/60 | 0.424s | 0.617s / 0.764s |
| Generated supported instrument answers + genuine gaps, 6 cases | 1 | 6/6 | 17.206s | 37.236s / 37.236s |
| Same generated cases | 2 | 6/6 | 39.195s | 76.836s / 76.836s |

No benchmark request exceeded 90s, but the COMPLETE evaluation has a 97.970s
legacy load-gap response and repeated core gaps reach 96.430s. Do not hide those
tails by quoting only the benchmark. Proposed generated warm p95≤45s is exceeded
under two-request concurrency. Small generated sample (n=6 per batch) is not a
robust sustained-service p95. True cold machine/model starts were not measured;
the initial restored-process smoke uses cached model files, not a cold host.
Correct abstentions still incur generation/retry latency. No approved budget,
production SLO, throughput guarantee or sustained-canary pass is claimed.

## Startup and local rollback

The ignored local `.env` mounts the private v10 searchable folder. Use the tracked
Phase6 override; plain base Compose can select a different image tagged `latest`.

```sh
docker compose --env-file .env -p observatory -f docker-compose.yml -f docker-compose.phase6.yml up -d --no-build --no-deps document-api
```

For this local layered canary ONLY, retain base image
`observatory-document-api:phase6-base-20261001`, ID
`sha256:72251c9be6666ec2dcef3d2f373f2e140d5dff6c11d91cecbbd7e05115b631cb`.
The recorded recipe is:

```sh
docker build --build-arg PHASE6_BASE_IMAGE=observatory-document-api:phase6-base-20261001 -f documentApi/Dockerfile.phase6-canary -t observatory-document-api:phase6-final-20261001 documentApi
```

Always verify the resulting image/hash and rerun acceptance after rebuilding.
This recipe does not close the fresh dependency build gate. For pointer rollback,
follow `scripts/verify_recovery_rollback.py` and the recovery report; preserve
the 0600 settings snapshot and restore the exact current settings in a finally
block. Original image/dump rollback restores original faulty behavior, so it is
disaster recovery, not an approved observing configuration.

The final-image pointer switch, both FIES#4 smokes and exact settings restoration
pass in `final-rollback.json`. A subsequent restart through the tracked override
passes `final-persistence.json`; post-restart public configuration fingerprint
matches `final-identity.json`. Only task-owned verification containers were stopped;
backups/restored data are retained. Final Git-visible secret-pattern smoke finds
no matches and `git diff --check` passes; this is not a security certification.

## Gates that cannot be self-approved

Independent owner review checklist:`reports/phase6/DOMAIN_REVIEW_CHECKLIST.md`.
Close source gaps/conflicts, establish 95% semantic citation precision with a
published representative denominator and 100% safety/procedure completeness,
approve latency budgets, measure true cold starts/sustained canary, resolve the
ARM dependency gate, and verify the actual PHP7.4 target/browser before cutover.
Model replacement remains deferred. No commit, push, main merge or production
cutover performed by this Phase6 run.

Receipts under `reports/phase6/` distinguish incomplete runs, repeated failures,
local integration and release gates. They must not imply domain-owner sign-off.
