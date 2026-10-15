# Qwen27 chat parameter screen — completed 2026-10-01

**Keep focusing on the installed Qwen27 weights. Temperature0 is the primary
next-stage quality candidate;0.1 remains a latency challenger. Neither is
production-optimal or quality-approved.** Live NOTBot and coding tags unchanged.

## Installed versions and configuration ownership

The five inspected standard Qwen27 tags on the coding endpoint share the SAME
weight blob and native template, and all have no stored SYSTEM prompt. They
are runtime profiles, not five independently coding-fine-tuned models. Safe
metadata: [installed-profiles.json](installed-profiles.json). Main-service model
listing has the same five tag IDs; no further standard Qwen27 tag appeared on
the development service. The separate abliterated artifact was not selected.

All five inspected defaults use temperature1/top_k20/top_p0.95/repeat_penalty1
and draft4. Coding profile contexts are128K or256K; output allowances8192 or65536.
NOTBot currently overrides **temperature0.3/output2048 on every first/repair
request**. Its prompt/history come from the application, not a coding SYSTEM.

Therefore no new weight download or fine-tune is needed. Keep temperature/output
in app settings rather than hard-coding them or creating a tag for each value.
For the current OpenAI-compatible transport, a lightweight named NOTBot runner
profile is the straightforward way to pin context/draft defaults independently
of agents. These profiles reference the same blob; they do not each consume
another17GB of model weights in that store. Actual GPU runner/cache reuse and
simultaneous memory occupancy still require testing.

The current app does not send top_p or explicit no-thinking. Tests did send
reasoning_effort=none. A future tested application configuration addition can
make those explicit; no live code change was made here. Native /api/chat supports
runtime options, but switching transport solely to avoid a tiny profile is not
necessary and would require separate integration/usage/error/repair testing.
See [Ollama compatibility and context](https://docs.ollama.com/api/openai-compatibility),
[Modelfile parameters](https://docs.ollama.com/modelfile),
[native chat options](https://docs.ollama.com/api/chat).

## Fresh parameter comparison

Same pinned base manifest22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643;
32K context, output2048, native template/samplers, explicit draft4/no-thinking,
same English evidence/app/verifier/prompt and repair instruction. Only temperature
changed. The replay harness gained explicit tuning knobs and variant-specific
private output paths; all three fresh receipts have the same new harness hash.
Original English-v2 scores/receipts were not rewritten or pooled into this run.

Ten generator cases ×2 each ×3 configurations =**60 complete responses**,
zero request errors or observed reasoning output. Three profiles' common
weight/template hashes and exact options were confirmed independently:
[tuning-profile-identities.json](tuning-profile-identities.json).
Additional citation-free text-facet audit preserved all scores:
[text-only-facet-audit.json](text-only-facet-audit.json).

| Temperature | Passed /20 | Supported passed /14 | False refusals* | Repairs /20 | Median | p95/max |
|---|---:|---:|---:|---:|---:|---:|
|0.3 baseline|12|9|7|8|8.05s|31.02s|
|0.1|13|9|6|8|6.12s|35.46s|
|0|14|10|6|10|6.49s|40.10s|

*Non-gap abstentions against this bank's expected useful response, including
safety/injection questions; not a count of unsafe invented answers.
Times include failures/repairs; exclude only each variant's first request.
**19 mixed-cache observations per variant**, sequential blocks0.3→0.1→0.
No interleaved/randomized variant blocks, formal idle-GPU window, independent
review or HTTP/PHP timing; p95 equals maximum. Inherited prompt caching can
benefit later blocks; do not attribute every speed difference to temperature.
Same-case greedy repeats are not independent statistical samples and do not
guarantee determinism or correctness across paraphrases/contexts.

## Meaningful findings and unresolved failures

- At temperature0 the NOTCAM dark procedure met required supported facets on
  both repeats; at0.1/0.3 only one repeat passed. This is encouraging but not
  owner-certified procedural completeness. Its repair took roughly40s at0,
  so lowering temperature did not improve the worst measured latency.
- All settings falsely refused both FIES-count cases and NOTCAM500nm cases,
  and the legitimate FIES answer under the fabricated-citation challenge.
  Temperature tuning did not cure these shared generator/verifier failures.
  The zero-temperature count was rejected as not_entailed_by_excerpt; its
  wavelength claim as unrelated_to_question, on both attempts. These are
  recorded proof-path failures, not proof that the model lacks the instrument
  knowledge. Attribution needs source-aware output/contract review, not weaker
  validation or changed expectations.
- Temperature0.1's extra overall pass versus0.3 was the safety-response check;
  supported-answer passes stayed9/14. Differences of one/two passes on this
  small bank cannot establish a statistically clear optimum.
- Native sampler/draft defaults were held fixed, not optimized. No context/output
  shrink, seed tuning, concurrency change, draft0 trial or serving through the
  agents' resident256K profile occurred. Temperature0.3 remains the baseline.

## Next stage

Carry **temperature0 and0.1** into the full40-case English generator bank ×3,
with a fresh unchanged-Qwen0.3 baseline. Retain Command R quality/control evidence;
any prompt/schema/contract experiment must include control too. Diagnose shared
count/wavelength/citation-challenge rejection with exact source-aware fixtures,
preserving citation/NLI/safety checks. Do not hide failures behind score changes.

Then repeat final-service operational/broad/diagnostic cases for candidate
settings, independent source/procedure/citation review, formal warm/cold/cache/
concurrency and agent-contention tests, and the actual PHP path. Only afterward
choose final request settings and runner profile. No promotion authorization.

Seventeen offline fixtures pass. Both task-owned engine/download containers are
stopped; weights/profile metadata retained. Live configuration fingerprints
unchanged; no application/frontend edits, commit/push or historical audit access.
[Post-run verification](post-verification.json).
