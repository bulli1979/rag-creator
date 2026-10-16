# Qwen testing profile

> **danka branch:** Written for the review branch's deployment. Referenced `reports/` files are not included in `danka`. Every API call now needs an `X-API-Key` header (see [install.en.md](../install.en.md)), and `docker-compose.qwen-testing.yml` is an overlay on the root `docker-compose.yml`, which no longer mounts `source_boosts.json`.

Activated on 2026-10-06 at the owner's request on
`review/production-improvements-clean` (base commit `adbb715`; local changes).
The existing **testing API** now uses Qwen instead of Command R. This is an
experimental model switch, not quality approval, a production release, or a
merge into `main`. Nothing was committed or pushed by this task.

## Active configuration

| Setting | Value |
|---|---|
| Ollama model | `notbot-qwen27:testing-32k` |
| Base | Installed standard `qwen3.8:27b`, Q4_K_M; not an abliterated variant |
| Context | 32,768 tokens, verified in `/api/ps` |
| Output limit | 2,048 tokens |
| Temperature | 0 |
| Thinking request | `reasoning_effort: none` |
| Request timeout | 180 seconds per generation attempt |
| SDK automatic retries | 0; the existing one grounding-repair attempt remains |
| Ollama draft parameter | `draft_num_predict: 4` |
| Endpoint | Existing local Ollama service on port 11434; no cloud inference |

The profile shares the installed base weights and template and has no stored
system preamble. No weight download, training, or coding-profile changes were
needed. The temperature/output/transport controls are persisted NOTBot chat
settings. Optional fields added to `ChatSettings` apply to both initial and
repair requests; omitted fields preserve previous SDK defaults.

The OpenAI Docs skill was used to check client timeout/retry controls against
the [official Python SDK reference](https://developers.openai.com/api/reference/python).
The thinking setting follows [Ollama's OpenAI compatibility documentation](https://docs.ollama.com/api/openai-compatibility);
runner parameters follow [Ollama's Modelfile documentation](https://docs.ollama.com/modelfile).
A synthetic JSON smoke returned no reasoning content. This is not a general
certification of the model's internal reasoning behavior.

## Verification and limits

- All 123 offline backend fixtures passed, including profile forwarding to
  initial/repair calls, alias validation, and unchanged legacy defaults.
- The complete existing HTTP operational bank passed **56/57**. The sole
  failure is the already-known missing approved autoguided `teloffset` sequence;
  its expected answer was not weakened. The bank retains one historical German
  case; the English subset is 55/56, not a new English-only quality study.
- FIES and NOTCAM conversational checks passed. These largely use checked
  source-derived routes, so they do not certify Qwen's general generation.
- Isolated PHP 7.4.33 proxy integration passed **13/13**, including follow-up
  history, citations, error propagation and synthetic temporary logging.
  JavaScript history/escaping fixtures passed. Neither the actual remote PHP
  target nor browser rendering was tested; local frontend ports 8092/8093 were
  not running before the separate fixture. The fixture was stopped afterward.
- Qwen settings survived a restart of only `observatory-document-api`.
- The deployed app hash matches local code. Health checks pass with the same
  pinned local NLI verifier. Corpus `phase6-2026-10-01-v10`, embedding model,
  index pointer and database settings are unchanged: 483 active documents,
  5,479 active chunks, 1,024-dimensional vectors, zero active CSC chunks and
  zero multiple-active-version sources. Database settings are byte-identical.
- This image layers the updated app onto the retained Phase 6 image. It does
  **not** resolve the separate clean-dependency-build/ARM wheel gate.

Earlier matched service-generation samples favored Qwen (median 7.22s vs
Command R 23.44s; five generated answers per model). This is not an agreed
latency SLO or proof of equal quality. This switch's ALFOSC field-of-view answer
still took 22.7s. Cold starts, contention and long generated answers remain
important limits; no unrelated model service was stopped or retuned.

**Release blockers remain:** P6.15 typed-count/range false refusals and P6.16
instrument-applicability checks. The full Qwen generator evaluation accepted
contradictory NOTCAM abort instructions at every tested temperature, including
0. Passing source-derived operational routes does not close that safety gap.
Do not rely on this testing switch for unreviewed operational procedures.
See [full generator results](../reports/model-evaluation/qwen27-quality-v1/RESULTS.md)
and [Phase 6 tracking](../NOTBOT_IMPLEMENTATION_PLAN.md).

## Reproduce on this host

Retain the existing environment, corpus mount and data volume. The standard base
tag must still have manifest digest
`22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643`
before creating the profile; inspect metadata without exporting model/system
content. From the repository root:

```sh
docker cp documentApi/Modelfile.qwen-testing ollama-prod:/tmp/notbot-qwen-testing.Modelfile
docker exec ollama-prod ollama create notbot-qwen27:testing-32k -f /tmp/notbot-qwen-testing.Modelfile
docker compose --env-file .env -f docker-compose.yml -f docker-compose.qwen-testing.yml build document-api
docker compose --env-file .env -f docker-compose.yml -f docker-compose.qwen-testing.yml up -d --no-deps --no-build document-api
```

This overlay selects the testing image; it does not replace chat settings, which
live in the persistent API data volume. Preserve all other settings when
applying the profile through the existing API:

```python
import json
from urllib.request import Request, urlopen

url = "http://127.0.0.1:8000/api/chat/settings"
with urlopen(url) as response:
    settings = json.load(response)
settings.update(llmModel="notbot-qwen27:testing-32k", temperature=0,
                maxTokens=2048, llmReasoningEffort="none",
                llmTimeoutSeconds=180, llmMaxRetries=0)
request = Request(url, data=json.dumps(settings).encode(), method="PUT",
                  headers={"Content-Type": "application/json"})
with urlopen(request) as response:
    assert response.status == 200
# Do not print or commit the complete settings object; it may contain secrets.
```

The app's grounding prompts, validation, source routing and frontend are not
changed by this profile. Future API rebuilds on this testing branch must include
`docker-compose.qwen-testing.yml`; use `--no-deps` when updating just the API.

## Private receipts and rollback

Full verification answers and the pre-switch chat settings are outside Git in
the mode-0700 directory:

`/home/llmrunner/.local/share/notbot-verification/qwen-switch-20261006.FH0tzQ`

Receipts: `http-operational.json`, `php74.json`, `runtime.json`.
`command-r-chat-settings.json` is a mode-0600 rollback backup and may contain
secrets. Do not print, paste, upload or commit it.

To restore the **exact previous chat settings**, load that private backup as
JSON and PUT it to `/api/chat/settings`, without printing either payload or
response. Restore the retained previous API image if full image rollback is
needed:

```sh
docker compose --env-file .env -f docker-compose.yml -f docker-compose.phase6.yml up -d --no-deps --no-build document-api
```

Then verify selected non-secret settings (`command-r-rag:35b`, temperature 0.3,
output 2,048), health and a fresh smoke. Neither rollback needs reindexing or
touching the database. The old image and Command R weights were retained.

Recorded identities:

- Qwen profile manifest: `54315d88f106c84beef29e98b122950660216c8be4bdb82c2a791c8bf1620a0c`.
- Shared weight blob: `f5f1dd8920d417aac2718b0bda3403da274301efdd6760b4f0f4b864ff2ad57d`.
- Image: `sha256:b9a5c6a3c865d560ecc454c05b6c02f0673d605f8a593bdeebb79298564296c2`.
- App Python hash: `2bf49adf38c857f8bd05a5a44c3e9ad9618fabab26d489e6cb1edfd8d79db70f`.
- Unchanged database settings hash: `229c656e20059a19019a11393db34717a28fe8fc4e5b93ffabcff87cf86dd129`.
