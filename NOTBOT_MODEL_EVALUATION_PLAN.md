# NOTBot alternative-model evaluation plan

> **danka branch:** Historical plan from the review branch. Referenced `reports/` files are not included in `danka`.

Date: 2026-10-01. Baseline code: adbb715 (Phase 6 technical verification).

**Current testing-runtime update, 2026-10-06:** the owner requested switching
this review branch to Qwen. The testing API now uses the installed standard
Qwen27 weights through `notbot-qwen27:testing-32k`, temperature0 and explicit
no-thinking, retaining corpus/retrieval/grounding. All123 offline fixtures,
56/57 existing HTTP cases (same known teloffset failure), and13/13 isolated
PHP7.4 proxy checks pass. Settings persistence and unchanged index aggregates
are verified. This is an experimental testing exception to the earlier
no-live-switch boundary, **not quality approval or production promotion**;
P6.15/P6.16, independent review and load/deployment gates remain open.
See [profile and rollback](docs/qwen-testing-profile.md). The results and
unchanged-runtime statements below describe the frozen earlier evaluations.

Status: expanded English-only screening complete on 2026-10-01: **nine models,
180 generator responses**, followed by **224 final-service checks** across four
models. All five fresh research candidates were downloaded and pinned, alongside
the existing comparators. Original mixed-language receipts remain historical,
not pooled into English scores. Fresh 40-case English evidence is frozen; full
three-repeat Qwen temperature quality run is now complete; quality approval,
control revalidation, load and deployment gates remain open.

**No approved winner. Qwen3.8 27B is the primary conditional finalist.**
Ministral8B is a conditional challenger, blocked by an accepted wrong ALFOSC
field-of-view value; Qwen4B remains a speed reserve with false refusals.
See [English results and remaining gates](reports/model-evaluation/english-v2/MODEL_COMPARISON.md).
The task-owned evaluation/download containers are stopped and weights retained.
The interrupted quality driver saved all responses but missed final cleanup;
hash-verified reporting recovery completed and its orphaned engine was stopped.
Live NOTBot/agents and configuration fingerprints remain unchanged. No model
was promoted; no commit/push was performed.

Owner direction after screening: **focus on Qwen27**, not another broad model
search. Chat-oriented parameter tests now use the pinned base weights rather
than coding defaults. [Qwen tuning plan](reports/model-evaluation/qwen27-chat-tuning-v1/PLAN.md)
tracks a completed fresh temperature0.3/0.1/0 comparison (60 responses) with
unchanged proof checks,32K context/output2048 and native sampler/draft defaults.
[Results](reports/model-evaluation/qwen27-chat-tuning-v1/RESULTS.md):0 scored14/20,
0.1 scored13/20,0.3 scored12/20; carry0 and0.1 into full quality testing, not
production. Lower temperature did not fix shared false refusals or worst tails.
Coding tags are
read-only comparators, not deployment targets. A small runner profile can share
the same weights; no new model download/training is required. Full quality and
deployment gates remain open; no live switch is authorized.

The next stage completed under `reports/model-evaluation/qwen27-quality-v1`:
the unchanged40-case English generator bank ×3 for each of0.3/0.1/0 (360 checks).
Source-aware review reproduced31 earlier attempts and identified typed-count/NLI,
lexical relevance and malicious-citation-intent mismatches. New full-bank NOTCAM
abort cases exposed a **critical accepted contradictory command** from a generic
appendix with an explicit instrument exception. See REVIEW_FINDINGS.md. No
validation weakening, prompt edit or live switch is part of this baseline run.
All360 response receipts/485 generation attempts were hash-verified; original
scores91/97/99 per120 (temperatures0.3/0.1/0) stand after the stricter text audit.
Final source-aware replay reproduced44 attempts, and seven real contradictory
NOTCAM instructions were manually confirmed across all temperatures. Safety/
applicability failure blocks advancement to promotion/performance gates. See
[completed results](reports/model-evaluation/qwen27-quality-v1/RESULTS.md).

Owner suggestion on vector retrieval/chunking is tracked separately in
[retrieval optimization plan](NOTBOT_RETRIEVAL_OPTIMIZATION_PLAN.md). Live
read-only inspection found exact pgvector search (no ANN index), mxbai embeddings,
topK8 plus bounded neighbour expansion, and structured rather than overlapping
chunks. Test source scope/completeness and evidence token budget before changing
the database. No reindex/corpus/settings change was part of the completed frozen
temperature comparison; proof/applicability repairs remain independent gates.

## Objective and boundaries

Find the fastest local model that retains useful, complete, correctly cited
answers. A faster refusal, truncated procedure or unsafe invention is not an
improvement. Select on time to the **complete validated answer**, not model size,
advertised benchmarks, raw throughput or unvalidated first-token time.

Language scope clarified by the owner on 2026-10-01: **English only**. German
and multilingual ability are not requirements, selection criteria or release
gates. Preserve the original frozen pilot bank/receipts, including fies_german,
as historical evidence; exclude that case from future selection scores. Before
new testing, freeze a separately versioned English-only bank replacing it with
an English FIES fibre #4 on-sky diameter question, recapture its evidence and
rerun the control as well as candidates. Do not silently rewrite old results or
compare new English-only totals with the original /20 pilot totals.

The user authorizes this plan and candidate downloads now. Subsequent testing
uses a separate API/configuration and model store; leave running NOTBot unchanged.
Freeze corpus, embeddings, index, verifier and frontend. No cloud inference or
corpus transfer, historical audit access/decryption, automatic commit/push/main
merge, interruption of unrelated services or production promotion.

P6.8 is reopened as an isolated experiment because latency is unacceptable.
Measurement need not wait for every owner-review gate. A live model change still
requires quality review and explicit approval; remaining Phase 6 source, build,
domain and deployment gates are not waived.

## Evidence and hypotheses

- Current model: command-r-rag:35b, Q4_0, actual context 32768, temperature 0.3,
  output cap 2048. Corpus phase6-2026-10-01-v10: 483 sources, 5479 active chunks;
  mxbai embedding/index and pinned CPU NLI remain fixed.
- Phase 6 generated-answer p95: 37.236s serial / 76.836s with two callers;
  individual evaluation gaps approach 98s. Source-derived warm p95: 0.141s
  serial / 0.617s with four callers. Receipts: reports/phase6/latency-concurrency.json
  and final-verification.json.
- 52 of 57 core responses in the complete final run make NO generation call.
  The full suite is essential for regression checks but insufficient for comparing
  LLMs: fast deterministic answers would conceal a slow replacement.
- Supported generated benchmark examples use roughly 3800–4700 prompt tokens
  on their first attempt. Gap requests often make two attempts with about
  10,000–12,000 aggregate prompt tokens across attempts, NOT one prompt.
- Read-only inspection today: Ollama 0.34.2, NVIDIA GB10; Command R fully
  GPU-resident at 32768 context. Separate Qwen 27B coding service also resident
  at 262144 context on the same GPU. Both services have engine parallelism 1.
  GPU utilization was 94% at inspection; this does NOT establish what caused it
  or prove that earlier Phase 6 measurements were contended.
- Measure model decoding, prompt processing, output length, repair retries,
  queueing and other GPU work separately. Smaller weights may help, but cannot
  be assumed to fix contention or retries.

## Shortlist and download tracking

### Fresh primary-source review — 2026-10-01, English-only scope

Historical research stage: testing/downloads were paused during this review.
The table below records proposed additions, not vendor-proven winners. All five
variants have since been downloaded/tested; measured results are linked above.
Prioritize document-grounded English answers, exact evidence/JSON, follow-up
context, unit reasoning and complete operational procedures. Model cards and
vendor benchmarks do not establish validated-answer latency on this GB10.

| Research priority | Proposed additional candidate | Task fit and constraints |
|---|---|---|
| 1 | Ministral 3 8B Instruct 2512; 14B Instruct as a quality step-up | Dedicated Instruct rather than Reasoning variants; system-prompt and JSON support; Apache-2.0. Ollama lists ministral-3:8b (~6.0GB) and :14b (~9.1GB). Verify exact checkpoint/template/quantization before pulling or testing. |
| 2 | Granite 4.2 8B, thinking disabled | Current dense IBM model; non-thinking mode documented, Apache-2.0, Ollama granite4.2:8b available. RAG/structured JSON are advertised capabilities, not proof of NOTBot citation reliability. Verify actual non-thinking API behavior; Granite 4.1 8B Instruct is a separate reserve if needed, not a silent substitute. |
| 3 | Qwen3-30B-A3B-Instruct-2507 | Explicit non-thinking-only MoE: 30.5B total / 3.3B active; Apache-2.0; Ollama qwen3:30b-a3b-instruct-2507-q4_K_M (~19GB). Active parameters are not total resident weight memory. Compare with the installed dense Qwen3.8 27B without replacing its pinned revision. |
| 4 | NVIDIA Nemotron 3.5 Lightning 30B-A3B, thinking disabled | August 2026 release, documented English/RAG applicability and DGX Spark deployment recipes; OpenMDW-1.1 licence review needed. Ollama available (~25GB default artifact). GB10 NVFP4/DSpark is a separate backend/quantization experiment, not assumed equivalent to Ollama or guaranteed faster. |

Primary sources checked:

- [Ministral 8B Instruct model card](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512), [Ollama family/tags](https://ollama.com/library/ministral-3).
- [Granite 4.2 8B model card and thinking controls](https://huggingface.co/ibm-granite/granite-4.2-8b), [Ollama family](https://ollama.com/library/granite4.2), [Granite 4.1 8B Instruct reserve](https://huggingface.co/ibm-granite/granite-4.1-8b).
- [Qwen non-thinking-only MoE model card](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507), [exact Ollama quantization tag](https://ollama.com/library/qwen3:30b-a3b-instruct-2507-q4_K_M).
- [Nemotron 3.5 Lightning model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16), [Ollama family](https://ollama.com/library/nemotron-3.5-lightning).

Retain Command R7B (documented RAG training, but the pinned artifact's actual
8K context and non-commercial licence remain gates), installed Qwen3.8 27B and
Qwen3 4B Instruct as existing comparators. The earlier Qwen3.5/Gemma4 receipts
remain valid historical observations, not a comprehensive family ranking.
Mistral Small 4 is 119B total despite ~6B active: defer this much larger footprint
for this latency-first round, rather than treating "Small" as a memory guarantee.
[Mistral Small 4 model card](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603).
Prefer these task-relevant variants over models selected for multilingual,
translation, coding-agent or extended-reasoning benchmarks alone.

The earlier pilot shortlist/preparation history follows unchanged. Expand the
English-only compatibility pilot before narrowing to two finalists; no new
downloads, inference runs or live changes were made during the fresh search.

Official published tags checked on 2026-10-01. Download sizes are approximate,
not RAM guarantees or measured speed. Pin local full manifest/weights digests
after pulling; registry aliases can change.

| Order | Candidate | Purpose | Preparation |
|---|---|---|---|
| Control | command-r-rag:35b | Exact current quality/latency reference | Already installed; preserve profile/weights |
| 1 | [command-r7b:7b-12-2024-q4_K_M](https://ollama.com/library/command-r7b:7b-12-2024-q4_K_M) | Smaller R-family model trained for RAG; first pilot priority | Downloaded 5.06GB, Q4_K_M; actual runtime clamps 32K request to 8K; budget/truncation gate required |
| 2 | [qwen3.5:9b](https://ollama.com/library/qwen3.5:9b) | Smaller general-purpose quality/speed candidate | Downloaded 6.59GB, Q4_K_M; verify thinking disabled |
| 3 | [qwen3.8:27b](https://ollama.com/library/qwen3.8:27b) | Larger quality comparator plus existing-resident deployment opportunity; test even if small models pass | Already installed 17.74GB, Q4_K_M; pin local revision and reuse weights |
| 4 | [qwen3:4b-instruct-2507-q4_K_M](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M) | Explicit small instruct variant; practical speed floor | Downloaded 2.50GB, Q4_K_M; verify reasoning behavior |
| 5 | [gemma4:12b](https://ollama.com/library/gemma4:12b) | Independent family and mid-sized quality comparator | Downloaded 8.02GB, Q4_K_M; verify new architecture |

Conditional only: [gemma3:12b](https://ollama.com/library/gemma3:12b) if Gemma4
does not work on the pinned engine. No automatic extra downloads or claim these
are faster. Do not select abliterated/uncensored models or transplant agent
personas into NOTBot. An existing coding-named profile can be a separately
labeled serving experiment after verifying its exact weights/template/options.

Command R7B was initially omitted, not excluded by a benchmark or incompatibility
finding. It belongs in the pilot because its documented RAG training fits this
application. Its weights carry CC-BY-NC-4.0 plus acceptable-use terms; record and
review deployment rights before any promotion. This is a separate model, not
the 35B model merely quantized more aggressively.

### Qwen3.8 27B: matched model test and existing-resident serving test

Read-only check on 2026-10-01 found the agents' profile
qwen3.8-27b-coding-stable-256k:latest resident entirely on GPU at context 262144.
It shares the SAME weight blob, template and license hashes as the installed
base qwen3.8:27b; profile manifests/parameters differ. No system preamble was
reported for either. Exact identities are in
[existing-qwen.json](reports/model-evaluation/existing-qwen.json).
The local base manifest differs from today's registry alias: do NOT pull or
silently update it; evaluate the already-installed pinned revision requested.

1. Matched comparison: reuse/copy only the pinned base model's required artifacts
   into the isolated store during M2, then use the same 32768 context, output cap,
   sampling and guards as other candidates. This may need its own runner/load;
   residency in another service does NOT guarantee zero load or shared KV cache.
2. Existing-resident opportunity: after an agreed low-impact window, test the
   exact resident profile/endpoint without changing its 262144 context or
   unloading/replacing it. Request output and sampling overrides must be recorded.
   Label these results a separate serving/context/queue experiment, not a fair
   model-only comparison. Record cold loading avoided, shared-agent contention,
   actual queueing, complete validated latency and resource use. This separate
   trial has not started; do not modify agent-service parallelism/keep-alive/settings.

Being resident removes a possible cold-load penalty, not prompt processing,
decoding, repair or queueing. Preserve the agents' service throughout preparation;
owner coordination is required before any action that changes its residency.

Separate store: Docker volume notbot_model_eval_20261001. Download-only container:
notbot-model-download-20261001, NO GPU, NO published port, daemon on container
localhost. Same engine image as live:
sha256:d772bbd3035a1cae8ffcd910ddbafce3b28846edfd4efbea4044009a3c71a932.
Downloads completed with SHA verification and successful exit codes. Exact
digests, sizes and license/template/parameter hashes are recorded in
[downloads.json](reports/model-evaluation/downloads.json) for the initial three,
and [command-r7b-download.json](reports/model-evaluation/command-r7b-download.json)
for the successful Command R7B pull. These are manifest
digests (pinning the complete model artifacts), not separately exported weight
blob hashes. License hashes establish identity, not a deployment-license review.
At the initial download-only stage, the three original downloads and existing Qwen comparator advertised thinking
capability but return no thinking-control metadata on this engine; inference
behavior was still untested, including the instruct tag. English-v2 has since
tested an explicit no-thinking request; full compatibility certification remains open.
The download-only container is now stopped; weights remain in the separate
volume for testing. Do not copy the entire production model store or load
candidates onto the live endpoint.

## Proposed latency gates — not approved or achieved SLOs

Clock: request accepted to fully validated answer available through the PHP
client, including queueing, repair and verification. No speed credit for
unsupported raw tokens or an abbreviated/incomplete required procedure.

| Workload | Proposed warm p95 | Additional condition |
|---|---:|---|
| Source-derived, 1 caller / 4 callers | ≤1s / ≤2s | No correctness regression |
| Generated supported answers/gaps, 1 caller | ≤10s | At least 3× faster than same-condition Command R p95 |
| Same generated workload, 2 callers / 4 callers | ≤15s / ≤20s | No growing backlog |
| Normal answer maximum | ≤30s | Count timeouts/errors/refusals, never discard them |

Report cold loading and process restarts separately. If model-cold answers
exceed 30s, require an approved warm-resident policy or another candidate.
Host-reboot testing needs a maintenance window, not an unannounced reboot.
Raw-token streaming alone cannot satisfy the gate: PHP currently waits for the
response and generated claims must be validated before being displayed.

## Work tracking

| ID | Work | Status | Evidence required |
|---|---|---|---|
| M0 | Freeze baseline/resource/config identities and establish comparable control | Fresh English capture/control complete; live fingerprints unchanged afterward | english-v2/frozen-capture.json + pilot/resources.json + service/resources.json + post-verification.json; controlled quiet-GPU rebaseline pending |
| M1 | Prepare expanded candidates and pin identities/licenses | Five new downloads complete; existing comparators pinned; deployment-license review pending | english-v2/models.json + download-status.json; weights retained in isolated volume |
| M2 | Implement isolated replay/service harness and freeze expectations | Replay/read-only final ChatService implemented;24 fixtures pass, including recovery integrity; HTTP/PHP pending | model_cases_en_v2.json (40); English capture; private outputs; real routing and actual-answer follow-up history; uniform explicit no-thinking adapter recorded; independent domain review pending |
| M3 | Ten-case English compatibility/quality/speed pilot for nine models | Complete:180/180, no request errors; no fully passing model | english-v2/pilot/summary.json and MODEL_COMPARISON.md; citation-free audit unchanged; R7B actual8K clamp qualified; native samplers/draft differ; full thinking-control certification pending |
| M4 | Full quality comparison of finalists + control | Qwen-only full English generator temperature bank complete360/360, zero request errors;44 final refusal-attempt replays and18 procedure diagnostics complete; seven real contradictory actions confirmed. New control/candidate comparison after proof/scope repairs and repeated service/broad/diagnostic gates pending | qwen27-quality-v1/RESULTS.md and recovery receipts;0 best99/120 but not quality-approved. Earlier final-service224 checks remain valid history, not full generator certification. No promotion |
| M5 | Warm/cold/concurrency and bounded sustained-load testing | Planned | Per-category counts, p50/p95/max, queue/tokens/resources |
| M6 | Tune finalists' context/output/parallelism independently | Initial60-screen and full360 temperature comparison complete; full optimization/revalidation pending | Full0 score99/120,0.1 97/120,0.3 91/120; supported57/75,56/75,53/75.0 is the next post-repair quality candidate, not approved.24 fixtures pass. No context/output/parallelism/draft retune; live code/settings/coding profiles unchanged |
| M7 | Human review, recommendation, PHP verification and approved promotion | Provisional recommendation recorded; human/PHP/release gates pending; promotion not authorized | english-v2/MODEL_COMPARISON.md; independent decision and rollback proof still required |

### M0/M1 — Freeze, download and coordinate

Record API image/app hash, corpus/index/version, settings, prompt/verifier pins,
Ollama version/image, template/weight/profile digests, quantization and GPU.
Never publish keys, raw settings, private prompts or endpoint credentials.
Downloads establish availability, not compatibility or inference performance.

Obtain an owner-agreed quiet-GPU window. Do not stop/unload/retune the separate
coding service without permission. If unavailable, label measurements shared-load,
not isolated performance. No model downloads during timing rounds.

When implementing the harness, copy only the control's required blobs/manifest
and pinned Qwen base artifacts into the test store, not entire shared stores or
unrelated agent profiles. Rebaseline control on the SAME engine/hardware/session
conditions as candidates. Six old generated samples are not a sufficient
statistical control. Check service idleness before changing residency.

### M2 — Two separate comparison paths

**A. Frozen-evidence generator replay.** Capture NEW public/synthetic test
questions, resolved subjects, bounded history and prepared evidence from v10.
Send the identical input to every candidate. Apply the same citation/NLI/value/
procedure guards and at most one repair. Force generation ONLY in this benchmark
path, including normally extracted procedures, to assess the model itself.
Label forced replay separately from production routing; never weaken validation.

Freeze 40 cases before seeing candidate answers: 25 supported questions covering
all operational instruments, multi-document summaries, historical/current scope,
unit reasoning, complete procedures and English conversation; 10 genuine
gaps/ambiguities; 5 citation-injection/prompt-injection/safety cases. Review
expected facets, forbidden actions, source requirements and full steps against
documentation. Old CSV expected answers are not automatically authoritative.

Static identical replay and dynamic conversation have separate scores. For
dynamic chains, each model's validated prior answer becomes its own next-turn
history; do not test only with prewritten correct assistant messages.

**B. End-to-end isolated API/PHP proxy.** Use the same app image and a private
catalogue/vector snapshot in an isolated database. Copied configuration points
only at test engine/database; no live-index ingestion or write access. Exercise
real routing/retrieval/history/validation/errors and frontend contract. Use a
new private test audit directory; historical audit files/keys are not needed.

Initial pilot keeps requested context32768, temperature0.3, maxTokens2048,
retrieval, verifier and repair rules fixed, with official model chat templates
and explicit thinking control for every model. Native sampler/draft defaults
were inherited and differ: see pilot-profile-options.json. This is a native
model/profile comparison, not a weights-only ablation. A normalized sampling
or disabled-draft comparison must be a separate profile/run for control too.
Never transplant a Command R template into Qwen/Gemma.

Pilot discovery: the pinned R7B artifact reports cohere2.context_length=8192.
The isolated engine explicitly clamps its requested/profile 32768 context to
8192; do not present it as a matched-32K trial. Preserve the initial results with
actual-window qualification and check every prompt/history/repair/output budget
and truncation log. If required inputs do not fit, this artifact fails that
compatibility gate. Changing artifact or context metadata is a NEW experiment,
not a silent fix. See command-r7b-context.json and sampledRuntimeContexts in the
pilot summary. Other candidates' actual runtime contexts must also be checked.

Compatibility gate: system/user/assistant roles, JSON object mode, exact quoted
evidence, numeric units, English follow-ups, context budgeting and verified thinking control.
Ollama documents model-dependent thinking controls and reasoning_effort:
query metadata AND test behavior on the installed engine. The installed Qwen
comparator currently lacks the newer thinking metadata. Do not assume "none"
works or that a /no_think instruction proves reasoning disabled.
If a test-only adapter is necessary, record its change and pass control through
the same adapter. No raw reasoning displayed to users or committed to Git.
[Thinking controls](https://docs.ollama.com/capabilities/thinking);
[Ollama compatibility](https://docs.ollama.com/api/openai-compatibility).

### M3/M4 — Eliminate unusable candidates, then prove quality

Pilot: 10 fixed prompt/evidence cases ×2/model. Include useful generated
definitions/summaries, long evidence/history, units, a complete procedure,
topic switch, genuine gap, fabricated citation and unsafe suggestion.
Reject malformed/truncated/unusable or plainly slow candidates; save failures.

Best TWO candidates + control: 56 English frozen core and 9 broad cases three COMPLETE
times; all 24 diagnostics at least once. Keep teloffset visibly failing until
sourced. A confident invented autoguiding sequence/load limit is worse, not an
improvement. Original diagnostic flags remain unscored.

Run 40 generator cases ×3/model. Measure first-pass JSON validity/support, repair
frequency, final usefulness/completeness, false refusal, unsupported claims,
semantic citation precision and context loss. Required selection gates:

- No currently supported core regression or critical supported false refusal.
- No conversation-context loss or fabricated/unsupplied citation.
- At least 95% independently reviewed semantic citation precision, denominator
  and sampling method published; automated entailment alone cannot certify it.
- 100% supported complete safety/procedure answers, with source prerequisites
  and correct instrument/version; no unsafe invented action.
- Review every new failure and source conflict, not only regex passes.

Score quality per supported/gap/ambiguous category. Do not use a weighted average
that lets unsafe or useless answers trade off against speed.

### M5 — Loading, caching, queueing, generation and sustained load

Distinguish model-cold, warm-uncached-prompt and warm-repeated-prompt conditions.
Model-cold means absent from TEST runner residency, not a rebooted host or cold
filesystem. Measure loading explicitly, warm the model, randomize case/block
order with a recorded seed, and interleave control blocks between candidates.
One model at a time on the shared GPU; record other residency/GPU activity.

Measure client workers 1, 2, 4 with engine parallelism 1 held fixed first.
Simultaneous engine execution is a later separate experiment, not the same
thing as client concurrency. For each cell, use 20 representative generation
questions ×5 trials =100 responses; separate supported/gap and cache groups.
Then run a 30-minute bounded load window on finalists. Report sample counts,
p50/p95/max, per-case tails, throughput, queue trends and failures/timeouts.
If a deadline expires, count it as a failure; don't silently rerun it until green.

Collect client total, embedding/retrieval, generation, validation, first attempt
and repair separately; prompt/output/reasoning counts where available; JSON
truncation and final answer length. Queue time is unknown unless actually measured.
Ollama native telemetry exposes load/prompt/cache/generation durations:
[official chat telemetry](https://docs.ollama.com/api/chat).
If compatibility responses lack them, use a labeled benchmark instrumentation
pass with identical messages/options. Never subtract different runs to claim an
exact queue time. First raw token is diagnostic, not verified-response latency.

### M6 — Tune independently only after model-only comparison

Small finalist/control matrix:

1. Output 2048 →1024 →512: incomplete JSON, missing qualifications or dropped
   required procedure steps count as failures, not successful faster answers.
2. Context 32768 →16384 only if EACH tokenizer's actual input/history/repair/
   output budget fits. Never silently drop history/evidence or reindex to win.
3. Optional temperature 0 for both control and candidates as a distinct trial.
   Candidate-specific sampling recommendations must be visible, not hidden.
4. Engine parallelism 1 →2 only in the dedicated runner after memory/queue
   checks. Keep quantization fixed initially; Q5 quality rescue is a separate
   profile/result, not a Q4 result relabeled.

Rerun quality and complete-answer latency for any chosen change. If no model
passes, report no winner and measured remaining costs. Do not automatically
relax targets, remove checks, add a slow fallback or change serving engines.

Keep model faults and generator/verifier contract faults separate. Early control
review found a correct four-science-fibre statement rejected with four evidence
items (validator permits at most three), including unsuitable/non-supplied
references; procedure details were omitted elsewhere. Some refusals are mechanical
checks, some semantic rejection, some deliberate empty claims. The prompt/schema
currently does not expose every enforced claim/text/evidence limit. Any explicit
contract/schema/prompt experiment must be a separately labeled profile applied
to the control too, with fresh identities and no weakened proof/safety checks.
Do not edit frozen expectations or live prompting to make initial pilots pass.

### M7 — Human review and reversible decision

Produce a ranked quality/latency matrix and exact identities, with sample/cache/
load qualifications. Recommend fastest fully passing model/profile, or no winner.
Instrument-owner review covers generated samples and EVERY safety case; no LLM
is the sole judge. Verify PHP7.4 proxy and actual target/browser when accessible.
Repeat final identity, persistence and rollback. Model replacement does not fix
the ARM package-consistency issue or remaining Phase6 documentation gaps.

Only after explicit promotion approval: save prior chat settings mode0600;
change model/endpoint pointer only; retain Command R and v10; smoke and canary
under agreed load. Roll back for critical refusal, wrong citation/value/procedure,
unsafe action, repeated timeout or budget breach. Verify original fingerprint.

## Artifacts and next step

- reports/model-evaluation/downloads.json: pull statuses, exact model identities,
  engine/store identity and proof of no candidate loaded for initial three.
- reports/model-evaluation/command-r7b-download.json: added R7B successful pull,
  pinned artifacts and post-download service checks.
- reports/model-evaluation/existing-qwen.json: already-installed base/profile
  identities, shared weight hash and resident context; no re-download/update.
- scripts/evaluation/compare_models.py and model_cases.json: implemented generator
  replay/capture with immutable input/app/harness/model hashes, support/facet
  scoring and atomic per-response checkpoints. The standalone replay does not
  use source-excerpt fallback to disguise a model refusal; full API routing will
  be measured separately. First call includes cold loading; following latency
  is only a mixed-cache pilot, NOT the formal M5 warm/cold matrix or PHP latency.
- scripts/evaluation/run_model_pilot.py: sequential six-model orchestration with
  shared GPU/residency samples; only the owned test engine is restarted after
  an error/timeout to avoid abandoned queued requests. No unrelated service stop.
- Initial harness import-path failure is retained unscored in
  initial-harness-attempt.json. Correct repository-depth mount verified in the
  same app image, then evidence recaptured and owned control unloaded before
  the scored run. This is not a silently discarded scored model failure.
- Private evidence/config snapshots mode0700 outside Git. Public IDs/hashes,
  timings and reviewed public answers only; no raw internal context, private
  generated text, credentials or reasoning in committed artifacts.
- Per-model pilot/quality/latency/compatibility receipts and MODEL_COMPARISON.md.
  Incomplete/filtered/identity-mismatched runs cannot be final reports.

Expanded English M3 is complete; M4 has an initial service comparison, not full
quality certification. The 51 no-generation passes per model must not hide
weaknesses in the five generated service responses or forced-generator screen.
Qwen27 is the primary conditional finalist; Ministral8B is blocked by its accepted
wrong ALFOSC FOV, Qwen4B by false refusal. No replacement is approved.

Next review shared generator-contract failures and source/version/value selection
without weakening proof checks. Any contract adapter requires a new labeled
control/candidate experiment. The Qwen40-case English bank ×3 ×3 temperatures
is complete with release-blocking findings; after scoped repairs rerun quality
with control and complete repeated English core/broad checks, diagnostics, domain review, formal
cache/load/concurrency testing and actual PHP path before a promotion proposal.
A quiet-GPU window needs owner coordination, not unilateral interruption of Qwen.
Explicit reasoning control remains a test-only change applied to control too.
