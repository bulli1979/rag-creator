# Alternative-model pilot — 2026-10-01

All six generator pilots completed: 120 scored responses, ten cases twice per
model. No candidate passed every check. **No replacement is approved.**
The live app/model, corpus and agents were not changed; the isolated test engine
has been stopped, with weights retained.

Scope update on 2026-10-01: the owner requires **English only**. Tables below
preserve the original pilot, which included one German case twice per model;
those results must not count towards model selection. A separately versioned
English-only bank and renewed control comparison are required. The fresh
primary-source shortlist in NOTBOT_MODEL_EVALUATION_PLAN.md also supersedes
the narrow two-finalist recommendation below pending expanded screening.

Expanded English screening and final-service regression checks are now complete:
[current English results](english-v2/MODEL_COMPARISON.md). Those results supersede
the historical selection recommendation below; no replacement is approved.

## Observed results

These are automated generator screening scores, not whole-chatbot accuracy.
Latency below covers all responses, including failed/refused ones, excluding
the first cold-load request. Each latency sample contains only 19 responses,
mixed prompt-cache conditions on a shared GPU; p95 here equals the observed
maximum. It is NOT PHP end-to-end latency or a formally isolated warm SLO.

| Profile | Checks passed /20 | Supported cases passed /14 | Median | Pilot p95 | Actual sampled context |
|---|---:|---:|---:|---:|---:|
| Command R control | 11 | 8 | 26.29s | 74.67s | 32768 |
| Command R7B | 10 | 8 | 8.35s | 62.97s | 8192 |
| Qwen3.5 9B | 9 | 7 | 7.24s | 42.36s | 32768 |
| Qwen3.8 27B, installed pinned revision | 14 | 11 | 6.37s | 43.06s | 32768 |
| Qwen3 4B Instruct | 10 | 8 | 2.26s | 18.72s | 32768 |
| Gemma4 12B | 10 | 8 | 4.96s | 28.07s | 32768 |

Detailed failures, identities and per-attempt metrics:
[pilot-summary.json](pilot-summary.json), pilot-*.json,
[resource samples](resource-samples-pilot.json).
Zero scored request errors occurred; all unsuccessful quality checks remain
included. The initial harness import failure is preserved separately as unscored.

## Recommendation for the next experiment, not deployment

Prioritize **Qwen3.8 27B** as the quality-oriented finalist and **Qwen3 4B Instruct**
as the speed-oriented finalist, keeping Command R as control. The 27B candidate
is worth pursuing despite its size: it passed FIES count and German cases on
both passes and had fewer repair responses (6/20 versus control 11/20).
The 4B candidate provides a useful speed comparison, not an acceptable replacement
yet: its count/procedure/safety screening failures remain unresolved.

Keep Gemma4 as a reserve if finalists fail. Its FIES definition lacked the required
spectrograph facet on both passes, and the dark-frame procedure was incomplete.
R7B did not improve this pilot's quality and has an additional context-budget
constraint. Qwen3.5 9B had the lowest score in this sample. These are small-bank
screening observations, not general rankings of the model families.

## Findings that matter before a model switch

1. **Quality is not just a knowledge test.** A reviewed Command R count output
   stated the correct four science fibres, but supplied four evidence items
   where the validator permits at most three, with unsuitable/non-supplied
   references. Quotation/schema/support failures can cause refusal even when
   the main fact is correct. Do not label every refusal as ignorance.
2. **Procedural completeness is a real problem.** Missing notcam.mdark, readout
   mode or first-frame handling occurred across profiles. Some outputs were
   supported but incomplete; a fast summary must not replace a complete recipe.
3. **Some shared failures involve the fixed grounding path.** Every model failed
   the forced-generation NOTCAM 500nm and fabricated-citation cases. Reviewed
   rejection receipts include value/unit and question-topic checks, as well as
   unsupported excerpts. Review these with source-aware fixtures before blaming
   only model size. Do not weaken proof or silently change the frozen cases.
4. **Live routing is different.** The pilot intentionally bypasses sourced
   extractors and excerpt fallback. It does not show that current live answers
   have regressed; end-to-end tests must retain all those routes. It also does
   not justify assuming that sourced routes cover every natural paraphrase.
5. **R7B actually ran at 8K.** Its GGUF advertises 8192 to this engine, which
   clamps the 32768 request. Bounded logs report no completed-call truncation;
   maximum reported total was 7951 tokens, close to the window. Maximum prompt
   plus full 2048 output allowance is 8648: the complete budget does not always
   fit. Full-bank/history/repair tests are required; do not silently modify GGUF
   metadata. See command-r7b-context.json.
6. **These are native-profile comparisons, not a weights-only ablation.**
   Temperature/context-request/output cap were fixed, but inherited samplers
   and draft settings differ. Qwen3.8 retains draft_num_predict=4 and Gemma4=3;
   Qwen3.5 has presence_penalty=1.5. Exact safe options are in
   pilot-profile-options.json. A separately normalized sampler/draft trial must
   be labeled as such. Do not attribute all speed differences to parameter size.
7. **No reasoning output observed is not full thinking-control certification.**
   Explicit reasoning_effort none was accepted and no reasoning field/tags were
   observed, but metadata is incomplete on this engine. Compatibility verification
   and every bounded output/context check still matter.

## Next stage

- Review failure attribution and add explicit generator-contract tests for the
  validator's existing claim/text/evidence limits. If testing a schema/prompt
  adapter, use a NEW labeled variant for finalists AND control, without changing
  live behavior or loosening citation/NLI/safety checks.
- Finish the isolated API/database/PHP path; run the complete core/broad suites,
  all 40 frozen generator cases, and dynamic candidate-own-history chains.
- Verify meaningful complete supported answers, genuine gaps and every safety
  procedure independently. Regex/entailment scores do not certify domain quality.
- Run the planned cold/warm/cache/1–2–4 caller and sustained-load matrix, with
  native timing telemetry and coordinated quiet-GPU conditions. Do not infer
  exact queue time from utilization or compare timing from different transports.
- Test the existing-resident 256K Qwen endpoint separately in an agreed window.
  This pilot reused its installed weights in an isolated 32K runner; it did not
  send inference to or unload the agents' endpoint.
- Retain all remaining Phase 6 source, dependency, domain and deployment gates.
  No automatic promotion, commit or push.
