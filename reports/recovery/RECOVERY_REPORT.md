# NOTBot operational recovery — 2026-09-30 to 2026-10-01

Scope: restore the documented observer/staff assistant, preserving grounding,
privacy protections and reversible source lifecycle. Recovery was developed on
`review/production-improvements-clean`, based on `7891d6a`. No push or main merge.
The separate NOTBot-documents changes remain local-only.

## Finding

The reported failures were real system regressions, not a reason to postpone
basic instrument questions or simply replace the language model. Conversion,
source selection, conversation resolution, configuration drift and claim
validation compounded one another. Passing small fixtures did not establish
operational usefulness. The earlier Phase 5 acceptance claim was too broad.

## Causes and changes

| Observed cause | Recovery change | Verification |
|---|---|---|
| Natural component follow-ups and `fivers` were treated as new subjects. | Resolve instruments from bounded user-turn history before embedding/ranking; preserve explicit topic switches; clarify ambiguous/unnamed subjects. Assistant answers are never factual evidence. | FIES definition → typo → clarification → resolution; NOTCAM → 500/1000/3000 nm; topic switch and ambiguity cases. |
| A crawled/active engineering document was treated as current operating guidance. | Source roles distinguish instrument landing pages, operator guides, command references, current references, design reports and historical sections. Old bundle/spare sections cannot override current configurations. | Four science fibers plus one calibration fiber from the current FIES cookbook; design six-fiber configuration not asserted as today's inventory. |
| FIES landing-page recognition and relevant current guide retrieval failed. | Retrieve authoritative indexed source anchors, complete inventories and exact component rows; follow bounded topic-matched links only to already-indexed official documents. | FIES #4 aperture, all science-fiber resolutions, calibration fiber purpose, unknown #99 refusal. |
| Layout tables and malformed HTML lost row/column relationships; headings were misleading. | Shared HTML5 repair/conversion in API and producer, semantic headings, rowspan/colspan reconstruction, complete small tables and repeated units/headers for larger tables. Fixed heading ancestry without H1. | Conversion and structural fixtures; repaired FIES inventories and ALFOSC grism/settings tables in the live index. |
| Short keyboard recipes were split mid-instruction; the model omitted later steps. | Preserve complete short procedural paragraphs and section boundaries; copy only complete matched procedures from current guides, keeping prerequisites and instrument scope. | NOTCAM interrupt/darks, ALFOSC slitrot and interactive OB, data download/sharing. |
| Useful operating/reference sources were quarantined, and some PDFs were damaged. | Reconvert the approved corpus from preserved raw sources; restore seven explicitly reviewed public sources; use hash-bound extraction review and one visually checked historical CCD8 excerpt. Unrepaired documents remain quarantined, not guessed. | Final v9 indexing receipt; all 482 requested documents done, 5,478 chunks, no indexing errors or unresolved CID text. |
| Phone scrubbing destroyed signed coordinates and debug logs exposed matched contact text. | Technical coordinate fixtures survive; real contact candidates remain scrubbed; producer debug logs contain types/counts rather than matched secrets. | Positive/negative API and producer privacy fixtures. |
| Runtime drifted from mxbai/topK8 to MiniLM/topK5. | Compare embeddings on identical parsed evidence, then use pinned mxbai with the required query-only prefix in an isolated 1,024-dimensional index; restore topK8 and the existing Command R 35B profile. | `embedding-comparison.json`, active vector-dimension/pointer receipt. No smaller chat model introduced. |
| Literal overlap rejected paraphrases; component #4 was mistaken for a measurement; values from the wrong row could pass. | Separate identifiers from measurements; normalize equivalent notation; bind values to component rows and inventories. Add a pinned local English entailment checker, keeping independent numeric/unit/identifier/source-policy checks and one bounded correction attempt. | Positive and adversarial fixtures; known supported questions answer while wrong IDs/units/values/polarity remain rejected. |
| A true related fact could be accepted as an answer to a different question. | Guard requested values and explicit measurement subjects; reject total telescope mass as a Cassegrain instrument load limit. Require an actual source connection for complete named-program sequences. | Cassegrain regression; unrelated autoguiding controls cannot establish the `teloffset` sequence. |
| Final legacy review found that a model could generalize a specific startup-error hardware remedy to any UIF error. | Independent troubleshooting-condition validation; source-derived clarification asks for the actual quoted error before selecting hardware actions. | A perfect-looking excerpt/NLI result cannot drop the source's error prerequisite; unspecified UIF error acceptance case requires clarification, not power cycling. |
| A report introduction was retrieved while a short value several pages later was missed; the model repeated unsupported qualifiers from the question. | Bounded within-source property lookup and source-verbatim technical excerpts. No answer constants. Unknown detector IDs are not silently bound; historical report values are labeled as reference rather than current instructions. | ALFOSC report scale/speeds/frequency and proposal duration; altered-value unit fixtures demonstrate extraction reads the source. Frequency keeps its readout-speed assumption and excludes nearby electrical experiments. |
| During final verification the physical-pixel question intermittently used a camera summary with an incomplete unit, rather than the named product datasheet. | Exact named-detector dimension extraction requires the product identity in source prose and explicit units on both dimensions; a linked product name or another detector cannot establish the property. | Parenthesized/non-parenthesized physical-pixel queries plus changed-product/value/unit fixtures. No conversion of a bare micro-prefix into an invented unit. |
| Repeated verification exposed a model/NLI-dependent false refusal on the winter mountain-road advisory. | Copy the complete matched seasonal advisory from the active site guide, including its requirement to check current road/weather conditions. This never implies live road availability or permission to travel. | Exact reported wording and paraphrase; mutated-hour fixtures, missing-condition rejection and historical-guide rejection. |
| A FIES range answer omitted the distinction between complete and extended wavelength coverage. | Resolve the instrument subject from the same landing-page paragraph and copy the range plus adjacent extended-coverage qualification. | 370–830 nm without gaps; extension to 900 nm with minor inter-order gaps. Mutated-range fixtures verify no answer constants. |
| Backend failure/unsupported claims produced meaningless requests to clarify a clear question. | Distinguish embedding/model failures, missing evidence, invalid claims and genuine ambiguity in trace/output; clarify only when the subject is actually ambiguous. | Gap, unknown component, unsupported specification, unnamed-controller tests. |
| PHP displayed irrelevant retrieved sources and localhost transport could bypass its proxy. | Same-origin PHP proxy on HTTP/HTTPS; show cited sources with stable identifiers/authority and safe original-source links; backend readiness includes the claim verifier. | Local browser conversation and expanded cited source; PHP 7.4 syntax checks and Node checks. |

## Evaluation discipline and results

The frozen immediate pre-recovery result is `before-7891d6a.json`: 12/31 acceptance
cases passed; 22/24 legacy questions abstained. This is distinct from the older
Phase 0 judge's 21 scored rows. Its aggregate correctness is not comparable to
the new deterministic acceptance checks.

Final `after-final-2026-10-01.json` is complete: **57 core + all 24 legacy rows**.
`final-comparison.json` checks the frozen common questions, both input hashes,
completion counts and the final application-source hash. An interrupted or
filtered run is rejected rather than silently summarized as final.

| Evaluation scope | Before | Final |
|---|---:|---:|
| Unchanged 31 acceptance questions | 12/31 | 30/31, no regressions |
| Expanded core acceptance suite | Not comparable | 56/57 |
| Repeated new regressions, nine questions × three runs | Not run | 27/27, all source-derived without generation |
| Original 24 diagnostic questions, manually reviewed | 22 abstentions | 20 supported answers, two clarifications, two documentation gaps |
| Exact duplicate rows in selected test contexts | Baseline separate | 0 across all 81 final responses |

The sole remaining core failure is `operational_sequence`: no approved complete
internal autoguided `teloffset` sequence was established. It remains visibly
failing, not relabeled as a passing refusal. There are no known supported-question
false refusals in this final run; that is not a guarantee for all future wording.

Measured core median/p95: **0.125s / 23.070s**. The 51 source-derived core answers
have median/p95 **0.106s / 0.190s**; the six generated core responses have
median/p95 **20.074s / 33.987s**. The slowest legacy response is **93.712s** on a
genuine unsupported load-limit query; legacy p95 is **58.811s**. These are observed
test samples, not controlled load/cold-start benchmarks or sustained-canary
acceptance. Fast factual extraction does not make all model responses fast.

Final image: `sha256:72251c9be6666ec2dcef3d2f373f2e140d5dff6c11d91cecbbd7e05115b631cb`.
Application/PHP/JS source hash:
`0811e1499069111ec73690c2b6ebbebd9693b7cccdb5aef7ae186e47e05de095`.
`runtime-consistency-final.json` independently matches the running Python code
to its expected hash after restart, checks health/persisted index/model state,
and verifies a fresh FIES#4 answer. `final-build-verification.json` records
**113 passing API fixtures**, **5 passing producer fixtures**, byte-identical
HTML helpers, Node syntax and actual PHP7.4 CLI lint on both PHP entry points.

The 24 legacy rows are **diagnostic only**: their `passed` flag does not score
correctness. They require the separate manual assessment below. Report hashes
identify the exact case set and application source; an uncommitted Git HEAD alone
cannot identify this build. Intermediate and interrupted runs are retained and
must not be cited as the final result.

Automated acceptance checks cover expected facets, forbidden content, abstention,
supplied citation identity, selected stale-source URLs and exact context repeats.
They do not establish general truth or 95% semantic citation precision. The
local NLI model is a fallible English verifier, not an answer oracle. German
generation retains deterministic guards, not an unvalidated English NLI score.

## Known source conflicts and gaps

### Manual assessment of the original 24 questions

This is a source-aware review, not the legacy script's unscored `passed` flags.
Twenty questions now have supported answers to their requested facts. Two need
clarification (instrument or exact error) and two remain operational documentation gaps.
This is not a claim that all twenty describe today's hardware or all policies:
the explicitly historical/reference cases are qualified accordingly.

| Legacy case | Assessment | Supported value / remaining issue |
|---|---|---|
| 01 | Supported current reference; old key obsolete | ALFOSC grism18: 4360 Å, 0.93 Å/pixel, not the old 4300/0.918 setup. |
| 02 | Supported technical report | Grism4 severe second-order contamination beyond approximately 5800 Å. |
| 03 | Supported, explicitly report-scoped | 1 pixel = 0.19 arcsec in the cited contamination report; not today's CCD14 scale. |
| 04 | Supported detector reference | SITe SI-003A physical pixel: 24 microns. |
| 05 | Supported, presentation repaired | PolCor 0.12 arcsec/pixel, now a complete source sentence rather than a broken PDF line. |
| 06 | Supported reference | PolCor coronagraphic disks: 1.5/3/6 arcsec. |
| 07 | Supported historical technical report | Controller speeds: 113/200/400/800 kpix/sec; not asserted as current controller settings or an unsupported introduction-date claim. |
| 08 | Supported controller report | Pick-up fundamental frequency: 13.28 kHz, assuming the 200/400 kpix/sec readout speeds are precise. Historical/technical scope, not electrical repair advice. |
| 09 | Supported, historical | September2003 CCD8 amplifierA/high gain RON: 3.25 ± 0.05 electrons. |
| 10 | Supported, historical | Non-AIMO CCD in that report: −120°C; not current CCD14 cooling advice. |
| 11 | Supported telescope reference | Focal plane scale: 7.33 arcsec/mm. |
| 12 | Supported WFS report | 100 nm astigmatism corresponds to −0.43 TCS units in the cited analysis; not a new operational command recommendation. |
| 13 | Current operational source gap | Old SCS design250 kg is not established as today's safe limit; wrong43-ton telescope answer rejected. |
| 14 | Supported site guide | Winter road advice: avoid before09:30/after18:00. |
| 15 | Supported requested initial duration, reference-qualified | Cited proposal rules: maximum3 years initially; extension/eligibility policy is not certified. Partial PDF continuation is not rendered as a hanging sentence. Quotation marks are not required. |
| 16 | Supported telescope reference | Total field: 30 arcmin. |
| 17 | Supported telescope reference | 7.33 arcsec/mm. |
| 18 | Legitimate ambiguity | No instrument/controller named and no prior history: ask which instrument. |
| 19 | Supported reference | PolCor 1.5/3/6 arcsec disk diameters. |
| 20 | Supported current settings table | ALFOSC telescope foc-pos26630 / tv-foc510; not unrelated internal focus1610. |
| 21 | Genuine missing complete procedure | Internal autoguided teloffset sequence not established; retained failing acceptance case. |
| 22 | Supported complete, instrument-qualified recipe | ALFOSC OB: guiding, first target selection(a+q or x+q), second selection, slit check, Enter TWICE or repeat. Other instruments explicitly may differ. |
| 23 | Supported cookbook rules | Humidity>90% closes telescope; reopen only after20min<90%. Wind12m/s closes sideports/lower hatch;20m/s closes telescope. No20-minute delay before closure. |
| 24 | Legitimate exact-error clarification | Current guide has a remedy for a specific quoted startup error; a generic UIF failure does not establish that prerequisite. Ask for the message, do not generalize hardware actions. |

- FIES operator guide lists R=25,000/45,000/65,000; its landing page lists
  25,000/46,000/67,000. The bot shows the sourced discrepancy when applicable,
  rather than inventing a reconciliation. Instrument-owner confirmation is needed.
- The complete internal `teloffset` autoguided sequence is not established by
  the approved available documentation. Its expected-answer acceptance case
  remains a visible failure. Unrelated GUI controls and MOSCA offset descriptions
  must not be substituted. A reviewed current procedure is needed.
- The 2009 SCS design requirement mentions approximately 250 kg at Cassegrain,
  but does not establish today's safe instrument load limit. The bot must not
  answer 43 tons (the telescope's moving weight), or promote the old design value
  as a current safety limit.
- An unspecified ALFOSC UIF startup error does not justify the old test key's
  power-cycle/motor-cable diagnosis. The current guide DOES contain that remedy
  for the specific message “The ALFOSC UIF did not start. Restart the observing
  system.” Earlier recovery notes incorrectly described this as absent guidance.
  Obtain the actual error; do not strip the condition or invent/generalize actions.
- Three damaged PDF conversions remain quarantined: DIPOL journal article,
  FIES Telting 2014 paper, and WFS report 3. Original files are retained. Restoring
  them needs reliable extraction or visual review, not removal of bad glyphs to
  conceal uncertainty.

## Running local canary and persistence

- API: `observatory-document-api`, localhost port 8000; PostgreSQL:
  `observatory-postgres`, Compose project `observatory`.
- Active pointer: `recovery-mxbai`, table
  `public.rag_recovery_mxbai_20260930`, corpus `recovery-2026-09-30-v9`.
- Corpus mount is read-only from the private ignored shadow corpus; no raw or
  processed document tree is added to Git.
- Embeddings: `mixedbread-ai/mxbai-embed-large-v1`, revision
  `b33106f585b9ce46904ad7443a3b52b7a63e231c`, query-prefix applied only to queries.
- Local entailment: `cross-encoder/nli-deberta-v3-base`, revision
  `6c749ce3425cd33b46d187e45b92bbf96ee12ec7`, safetensors, CPU, cache under `/data`.
  Both recovery models are provisioned explicitly; requests do not download them.
- Chat remains the original Command R 35B weights via `command-r-rag:35b`;
  Ollama profile context 32,768/output 4,096. API topK8, source cap2, evidence
  similarity floor0.30, API maxTokens2,048, temperature0.3.
- `runtime-consistency-final.json`: 482 active sources/documents, 5,478 rows,
  all vectors 1,024-dimensional, one active corpus generation, zero sources with
  multiple active versions, zero CSC chunks, zero unresolved CID chunks.
  There are still **379 exact duplicate index rows and 167 heading-only rows**.
  The selector filters headings/duplicates and neighbor expansion also deduplicates;
  this is not a claim that the stored index is noise-free. Physical cleanup is not
  performed without a reviewed backup/retention decision.

## Reproducibility, backups and rollback

The fast verified container build layers the changed app and markdownify1.2.2
onto `observatory-document-api:before-recovery-2026-09-30`. The ordinary Dockerfile
and dependency declarations contain the converter dependencies, but a clean
dependency-resolving build was **not** completed: the existing broad ML/office
dependencies caused a large slow download. Do not claim a fresh-host build has
been verified. Current tested packages include sentence-transformers3.4.1,
transformers4.57.6, torch2.14.0, beautifulsoup4 4.15.0, html5lib1.1 and markdownify1.2.2.
The producer's separate environment uses its supported markdownify<1 range;
the identical helper was tested in both environments.

Private backups, mode0600, are retained outside Git: PostgreSQL custom dump
`/home/llmrunner/NOTBot-shadow/notbot-before-recovery-2026-09-30.dump`, original
catalogue snapshot, and `/data/settings.before-recovery.json`,
`/data/chat_settings.before-recovery.json`, `/data/settings.before-mxbai-recovery.json`.
Old source versions/vectors remain inactive rather than deleted.

`rollback-verification.json` records an actual reversible settings-pointer test
repeated on the FINAL image after the full evaluation:
switch to the retained `default`/MiniLM/v3 index and matching embedding model,
verify connection and FIES#4, restore the exact complete original settings,
verify recovery connection and FIES#4 again. This tests **pointer rollback**, not
a full PostgreSQL dump restore. Do not restore old settings or run retirement
scripts blindly while indexing is active.

Operator rollback: pause ingestion; privately back up the current settings;
select the retained environment together with its compatible embedding model;
verify connection/health and known instrument questions. To return, restore the
complete saved recovery settings and repeat the checks. The explicit script is
`scripts/verify_recovery_rollback.py`; its backup destination must be new/private.
For new deployments, provision the pinned model caches explicitly, create a new
empty environment/table when changing embedding dimensions, ingest a versioned
reviewed corpus, verify all jobs, then promote its pointer. Never reuse old vectors
with a different embedding space. The original old image is retained for code rollback.

## Privacy and scope limits

Tests use public questions and public-source answers. Existing encrypted audit
decryption was stopped when approval review prohibited further access; this work
did not bypass that restriction. Fresh unaudited diagnostics do not read historic
conversations or print credentials. Corpus reconstruction preserves producer and
API redaction; shadow/transcription directories and settings/backups are private.
No documents, credentials or raw audit records belong in the recovery commit.

Encrypted API audits do not mean end-to-end privacy: the PHP frontend still logs
plaintext conversations and browser storage retains history. This is not an
endpoint authentication/encryption/exposure certification or a claim of 100%
privacy. Hardening those layers requires its own scoped verification.

Browser testing covers the local PHP preview at `http://127.0.0.1:8092/`, serving
a temporary copy of this branch through its proxy. It does not establish that an
unknown remote PHP deployment has this code. The local host uses PHP8.3; the actual
PHP7.4 CLI image separately passes lint on both PHP entry points.
The fresh browser recheck on 2026-10-01 was blocked by the browser tool's URL
policy. No alternate browser surface or other bypass was attempted. The earlier
NOTCAM/FIES UI checks and screenshot are retained, but are not a fresh final-image
browser receipt; target PHP7.4 browser/deployment verification remains open.

## Outstanding release gates

The reported core instrument regressions are repaired, but this is a local
testing canary, not general production acceptance. Keep domain-owner corpus
review, FIES specification reconciliation, reviewed missing operational procedures,
representative human citation/safety review, a sustained telemetry/latency budget,
fresh dependency build and full backup-restore testing open. Smaller-model
comparison remains deferred; it must reuse the same evidence and acceptance set.
