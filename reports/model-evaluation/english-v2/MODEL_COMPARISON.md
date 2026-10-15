# English-only alternative-model evaluation — 2026-10-01

**No deployable winner. Qwen3.8 27B is the primary conditional finalist.**
All five newly researched artifacts were downloaded and pinned in the isolated
store: Ministral 3 Instruct 8B/14B, Granite 4.2 8B, Qwen3 30B-A3B Instruct,
and Nemotron 3.5 Lightning 30B-A3B. Command R, the installed Qwen3.8 27B,
Qwen3 4B Instruct and Command R7B were renewed comparators. No live model,
application, corpus or configuration was changed. Nothing was committed/pushed.

## Completed measurements

- Nine models, ten English generator cases twice each: **180/180 responses**,
  zero request errors. Fixed evidence, exact production repair instruction and
  pinned verifier; source-derived answering routes deliberately bypassed.
- Four models, 56 English operational cases each: **224/224 responses** through
  the final in-process ChatService, real read-only retrieval, unchanged routing,
  and follow-up history constructed from each model's actual validated answers.
- Thirteen offline harness/summary fixtures pass. An additional citation-free
  numeric-facet audit preserved all generator scores. No independent semantic
  precision certification is claimed.
- Original mixed-language receipts/bank remain unchanged and are not pooled
  into English selection scores. Fresh 40-case English evidence was captured;
  its full three-repeat generator evaluation is **not yet run**.

### Forced-generator screening

Scores are automated usefulness/support/facet checks, not whole-chatbot accuracy.
Times include failed/refused responses and repairs; only the first model-load
request is excluded. Each latency sample has **19 responses**, mixed prompt-cache
conditions; p95 equals the maximum in this small sample. They are not formal
warm SLOs or PHP/browser timings.

| Model | Passed /20 | Supported passed /14 | Median | p95/max |
|---|---:|---:|---:|---:|
| Command R control | 11 | 7 | 20.40s | 124.44s |
| Ministral 3 8B | 13 | 9 | 8.87s | 30.90s |
| Ministral 3 14B | 13 | 10 | 13.55s | 69.69s |
| Granite 4.2 8B | 10 | 7 | 7.46s | 38.98s |
| Qwen3 30B-A3B Instruct | 10 | 8 | 3.14s | 6.76s |
| Nemotron 3.5 Lightning | 9 | 5 | 3.24s | 11.87s |
| Qwen3.8 27B, installed revision | 12 | 8 | 8.46s | 51.70s |
| Qwen3 4B Instruct | 10 | 8 | 2.32s | 8.29s |
| Command R7B | 11 | 8 | 12.84s | 56.13s |

Receipts: [pilot summary](pilot/summary.json), [resource samples](pilot/resources.json),
[citation-free audit](pilot/text-only-facet-audit.json).

### Final chatbot service regression check

Each model made generation calls for **only five of the 56 questions**. The other
51 used source-derived/no-generation paths and all passed, for every model.
Thus a ~0.2s overall median does **not** mean the LLM answers in ~0.2s, and
55/56 does **not** establish general LLM accuracy. Generated latency includes
the entire service call, failures, gaps, repairs and possible first-use loading;
five observations cannot establish reliable percentile performance.

| Model | All passed /56 | Generated passed /5 | Generated median | Generated p95/max |
|---|---:|---:|---:|---:|
| Command R control | 55 | 4 | 23.44s | 67.80s |
| Ministral 3 8B | 54 | 3 | 4.83s | 34.92s |
| Qwen3.8 27B | 55 | 4 | 7.22s | 15.44s |
| Qwen3 4B Instruct | 54 | 3 | 1.55s | 7.98s |

Receipts: [service summary](service/summary.json), [resources](service/resources.json).
Scope: final **in-process** service, not HTTP/PHP/target deployment certification.
All models, including control, used the same explicitly recorded test transport
adapter: reasoning_effort=none, SDK automatic retries disabled, timeout 180s.
This is not proof that default live requests have identical thinking behavior.

## Failures and selection

1. **Primary finalist: Qwen3.8 27B.** It matched the control's service outcome
   (55/56; same teloffset procedure failure), with materially shorter measured
   generation latency. This is promising, not statistically decisive or a
   promotion approval. Its forced-generator score was only 12/20; FIES count
   refusals and other failures remain. Reusing the agents' resident 256K profile
   is a separate, untested serving/queue experiment—not this matched 32K run.
2. **Conditional quality challenger: Ministral 8B, blocked by regression.**
   Highest combined screening score (tied with 14B), but the service returned
   an accepted, cited **7.3 arcminutes square** ALFOSC imaging field instead of
   the required **6.4×6.4 arcminutes**. Trace: one generation attempt, one accepted
   claim, zero rejected claims. This is a real current-answer regression and
   demonstrates that validation acceptance alone does not prove the appropriate
   operational value. It must not be promoted on its screening score/speed.
   Qwen27 returned the expected 6.4×6.4 value. Source/version/conflict attribution
   for the Ministral claim remains to be investigated; do not call it a proven
   unsupported hallucination without that review.
3. **Qwen3 4B remains the speed-oriented reserve**, not an acceptable replacement:
   the ALFOSC field-of-view question falsely refused, plus generator count,
   procedure and safety-usefulness failures. Fast refusals are not speed wins.
4. Ministral14B offers no clear overall gain over 8B and has much slower tails.
   Granite, MoE Qwen and Nemotron did not show a quality advantage in this bank.
   MoE speed is encouraging but insufficient for selection. These are local
   artifact/profile observations, not general family rankings.
5. Command R7B did not win either speed or quality; actual runtime context was
   **8192**, despite the 32768 request. It is not a matched-32K comparator and
   requires tokenizer/budget/truncation verification and deployment-licence
   review (noncommercial terms). Do not repair context metadata silently.
6. **Shared generator-contract/grounding problems persist.** Every model failed
   both forced-generation NOTCAM 500nm and fabricated-citation challenge cases;
   no model produced a fully acceptable NOTCAM dark procedure. Failure of the
   fabricated-citation challenge often means refusal of a legitimate answer,
   not acceptance of the attack's fake citation. Do not equate these scores.
   Existing live NOTCAM source-derived answers passed the service checks.
   Schema/proof rejection, missing procedure details and actual model mistakes
   must be separated before expecting a weight swap to cure them.
7. The **teloffset autoguiding sequence remains failed for all four service
   models**. Control produced an incomplete answer; candidates refused. It is
   retained in the denominator, not excluded as inconvenient. Authoritative
   source/owner review and sequence completeness remain unresolved. The
   Cassegrain-current-load-limit gap correctly abstained for all four models.

## Identity, isolation and qualifications

- Final app Python hash:
  `626df80f3e89d72be7d49db3abf54c94f46b9b9cb8466155effc5f216d958a7e`.
- Corpus `phase6-2026-10-01-v10`: 483 sources / 5479 active chunks;
  `recovery-mxbai:postgres:public.rag_recovery_mxbai_20260930`, unchanged.
- Ollama 0.34.2, task-owned single-slot engine, 32K requested context, temperature
  0.3, output cap 2048, pinned native templates/quantizations/samplers. Native
  draft/sampling options differ: **not a weights-only ablation**.
- Sampled test models were fully GPU-offloaded; R7B's sampled context was 8K,
  others 32K. Known production/secondary residency was empty in sampled generator
  rounds. This is not proof of host-exclusive GPU access or a controlled idle
  window. No unrelated service was stopped/unloaded/retuned.
- No reasoning output was observed under the explicit test request. This alone
  does not certify every model's thinking controls under other requests.
- Model manifest/parameter/template/licence hashes and sizes:
  [models.json](models.json). Pull outcomes: [download-status.json](download-status.json).
  Five new artifacts total approximately 64.45GB; weights remain available in
  `notbot_model_eval_20261001`. Nemotron's OpenMDW-1.1 rights need review before
  deployment; no licence hash is itself a legal approval.
- Raw newly generated test evidence/responses remain in a 0700 private directory
  outside Git. No historical chat audits were read/decrypted. Public receipts
  contain identities, timings, scoped trace and hashes, not private prompts.
- Both task-owned inference/download containers are stopped. Live API/agents
  remain running; live settings/chat-settings fingerprints match the baseline.
  [Post-run verification](post-verification.json).

## Next required work, not completed gates

Keep Qwen27 as the primary finalist and retain Ministral8B only as a conditional
challenger pending its current-value regression review. Use Command R as control.
First review the shared generator/verifier contract and ALFOSC source selection;
any prompt/schema adapter must be a **new labeled experiment for control too**,
with existing citation/safety checks preserved. Do not change frozen expectations
to hide failures or expand deterministic routes solely to pass the bank.

Then run the complete 40-case English generator bank ×3, repeated English
core/broad suites and diagnostics, independent domain/citation/procedure review,
and formal warm/cold/cache/concurrency/sustained-load measurements. Verify the
actual PHP frontend path and proposed transport changes. An approved warm
resident policy, shared-agent contention/queue tests and agreed latency budgets
are still required. No automatic live switch, fallback, commit or push.
