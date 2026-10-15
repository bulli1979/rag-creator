# Alternative-model evaluation receipts

Current handoff: [NOTBOT_HANDOFF.md](../../NOTBOT_HANDOFF.md). The unchanged-runtime
statements below describe the October 1 experiments. The owner subsequently
authorized a Qwen testing switch on October 6; the profile and remaining release
blockers are documented in [the testing runbook](../../docs/qwen-testing-profile.md).

Evaluation commenced on 2026-10-01 against the Phase 6 final app image and v10
corpus. These files are experiment receipts, not production-release approval.
Live application code/settings, corpus/index and agent service remain unchanged.

## Completed initial pilot

All six models completed twenty responses each (120 total), with zero scored
request errors. No model passed every quality check. The test engine is stopped,
weights retained, and no live model switch was made. See MODEL_COMPARISON.md
and pilot-summary.json for the qualified comparison and next-stage candidates.

The initial generator pilot uses the current Command R control plus Command
R7B, Qwen3.5 9B, the already-installed Qwen3.8 27B, Qwen3 4B Instruct and Gemma4
12B. Each receives the same frozen ten cases in two recorded seeded orders,
requested 32768 context, output cap 2048, temperature 0.3 and the same citation/CPU NLI
validation with at most one production-equivalent repair prompt. Explicit
reasoning_effort none is requested for control and alternatives alike. A model
request error/timeout stops that model and restarts only the test engine, preventing
abandoned requests from queuing behind later models. Partial failures stay visible.
Native sampler/draft defaults differ and are pinned in pilot-profile-options.json;
this was not a sampling-normalized, weights-only ablation.

The 40-case bank contains 25 supported, 10 genuine gap, and 5 injection/safety
cases. Evidence is newly captured from v10, with read-only PostgreSQL sessions
and read-only live configuration/cache mounts. Capture uses CPU embeddings;
no historical chat audit or its encryption key is accessed. Raw evidence, messages
and new model outputs are under an ephemeral private mode-0700 directory outside
Git; public receipts contain hashes, scores, metadata and timings only.

## Interpretation

- Pilot checks are automated screening, not independent citation/domain review.
  Regex facets and entailment cannot alone prove complete, safe procedures.
- Replay forces generation for questions that live NOTBot answers with sourced
  extraction. A refusal here does not by itself establish a live-app regression.
  Source-excerpt fallback is not used to conceal generator failures in replay.
- First scored request includes model cold loading. Later requests have mixed
  prompt-cache state. Pilot p95 is a small-sample descriptor, not a formal SLO.
- R7B's pinned GGUF/engine clamps the 32K request to an actual 8K runtime window.
  Its latency is not a matched-32K comparison; command-r7b-context.json records
  the discovery. Check every actual prompt/history/repair/output budget and
  truncation before selection. Summary contexts come from matching-profile
  residency samples; they do not imply every request was exhaustively verified.
- Shared GPU residency/utilization is sampled. Agent/live services are not stopped
  or retuned; their residency may naturally expire. No exact queue attribution
  or isolated-performance claim is made from GPU utilization alone.
- Installed Qwen3.8 base weights are pinned, not updated to today's registry alias.
  They match the agent profile's weights, but this pilot uses the isolated 32K
  profile, not the existing 256K agent endpoint. That serving trial is separate.
- A faster failed/refused/truncated response is not a successful speed gain.
  Public summaries show failures and all-response latency; passing-only latency
  is explicitly not an all-requests SLO. No model is automatically promoted.
- The isolated API/database/PHP path, full regressions/dynamic conversations,
  native generation telemetry, formal cache/concurrency/load matrix, verified
  thinking controls and owner review remain required after this pilot.

## Files

- Download preparation: downloads.json, command-r7b-download.json,
  existing-qwen.json and copied-installed.json.
- Immutable test evidence/app identities: frozen-capture.json.
- Per-response checkpoints: pilot-*.json, including unsuccessful attempts.
- Shared-resource snapshots: resource-samples-pilot.json.
- Overall process state: pilot-run-status.json; complete means all models were
  attempted, while allPilotsComplete separately requires all twenty scored rows.
- Cross-model score/identity summary: pilot-summary.json, refreshed using
  scripts/evaluation/summarize_model_pilot.py. It may lag active checkpoints.
- Unscored initial harness import-path failure: initial-harness-attempt.json.

To inspect progress, read the per-model receipts/process state. Do not open raw
private outputs by default. The harness rejects identity-mismatched resumptions;
do not edit the frozen questions, evidence or running harness to erase a failure.
Next work is tracked in NOTBOT_MODEL_EVALUATION_PLAN.md.
