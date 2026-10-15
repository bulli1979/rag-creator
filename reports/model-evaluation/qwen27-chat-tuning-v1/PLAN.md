# Qwen27 chat-oriented parameter evaluation

Owner authorized focusing on Qwen27 on 2026-10-01. No live promotion authorized.
Use installed pinned qwen3.8:27b, not the updated registry alias or abliterated
weights. Coding profiles remain unchanged. No new weights need downloading.

## Configuration placement

Live NOTBot currently sends temperature and max_tokens on **both** first and
repair requests. Thus its 0.3/2048 values override profile defaults of 1/8192
(or 65536). Prompt/history/evidence come from NOTBot. Native template, context,
top_k and speculative draft options are inherited from the selected Ollama tag.
NOTBot currently sends no explicit reasoning_effort/top_p; prior evaluation
requests used reasoning_effort=none. Promotion must reconcile this difference.

Temperature/output and, with a tested code/config addition, top_p/thinking can
be request-level app settings. The current OpenAI-compatible interface does not
expose num_ctx as a standard request field. Prefer a small named NOTBot runner
profile for a verified context and draft/sampler defaults, rather than silently
altering global service defaults or importing the coding profile's 128K/256K
context and huge output allowance. Such a profile references the same local
weight blob, not a newly trained/quantized/downloaded model. Runtime loading
and KV memory can still differ; disk sharing does not guarantee shared GPU cache.

Moving all options into a native /api/chat adapter is possible, but would be a
separate transport/code change requiring error, usage, JSON, reasoning, repair,
audit and PHP tests; not needed simply to avoid a lightweight profile.

Sources checked 2026-10-01: [Ollama compatibility](https://docs.ollama.com/api/openai-compatibility),
[Modelfile parameters](https://docs.ollama.com/modelfile),
[native chat options](https://docs.ollama.com/api/chat).
Installed read-only metadata is in installed-profiles.json: parameter values and
weight/template/system hashes only, no system text or historical chats.

## Initial bounded experiment

1. Verify base/coding profile weight/template hashes and safe parameter values.
2. Same Qwen pin, frozen English evidence, native template, existing prompt and
   proof checks; 32K context, output2048, native top_k20/top_p0.95/repeat1,
   draft4 and explicit no-thinking for every test request.
3. Fresh temperature0.3 baseline, temperature0.1, temperature0: ten generator
   cases ×2 each, same recorded case order. These are experimental choices,
   not presumed optimal values. Repair/incompleteness/refusals count as failures.
4. Compare supported completeness, false refusal, schema/support rejection,
   repair rate and complete-answer timings. No cherry-picked reruns. Raw new
   outputs stay private; new receipts under this versioned directory, original
   English results remain untouched. The replay harness gains only explicit
   tuning options; its new hash is recorded uniformly across all variants.
5. Optional draft0 versus draft4 is a separate labeled comparison. Do not shrink
   context/output until per-tokenizer input/history/repair/output budgets and
   complete procedures are proved to fit. Fixed seed/deterministic decoding
   cannot replace repeated paraphrase/history testing or guarantee correctness.

## Advancement gates

Temperature tuning is not a substitute for the shared generator-contract/
support failures. Do not loosen validators or change frozen expectations.
After the initial parameter screen, run full40 English cases ×3 for candidate
settings and an unchanged-Qwen baseline, repeated operational/broad/diagnostic
checks, source/conflict and independent domain review. Retain Command R as the
quality/control reference; compare any prompt/contract change on it too.
Then formal warm/cold/cache/concurrency/agent-contention tests and actual PHP
path. No model/profile is quality-approved by this small screen. Live settings,
coding profiles, corpus and services remain unchanged; stop only the owned test
runner after each bounded batch and retain weights. No commit or push.
