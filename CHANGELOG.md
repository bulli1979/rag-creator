# Changes proposed for review

This branch builds on `main` at `b922b39`. It keeps the original project structure and documentation while adding the production changes below.

## RAG quality and safety

- Blend vector similarity with lexical and numeric overlap when reranking retrieved chunks.
- Support optional per-source score multipliers through `documentApi/source_boosts.json`.
- Keep boosted-source lookup consistent across PostgreSQL, SQLite, and Qdrant backends.
- Bound user queries and recent conversation history before sending them to the model.
- Limit forced source injection so configured boosts cannot dominate the context.

## Performance and deployment

- Use CUDA automatically for sentence-transformer embeddings when available, with CPU fallback.
- Allow the API container to reach a host-managed OpenAI-compatible model server.
- Add optional GPU access for the API container.
- Mount the document corpus read-only through the configurable `NOTBOT_DOCUMENTS_DIR` path.
- Mount source-boost configuration read-only so changes can be applied without rebuilding the API image.

## Interfaces

- Add `chatBotPHP`, the browser frontend and PHP proxy used for deployment. It includes bounded conversation history, health checks, source display, and optional answer feedback logging.
- Add `chatBotAdmin`, a lightweight FastAPI admin UI for chat and backend settings.
- Keep environment-specific PHP configuration, logs, credentials, and admin runtime state out of Git; safe example configuration is provided.

## Notes for reviewers

- Existing files from `main`, including `OBSERVATORY_ONBOARDING.md`, are retained.
- Model weights, document corpora, user feedback logs, local `.env` files, and deployment credentials are not included.
- Source boosts default to neutral values and do not affect ranking until explicitly configured.
