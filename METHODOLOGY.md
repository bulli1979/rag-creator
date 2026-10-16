# Methodology

## End-to-End Ingestion and Retrieval Pipeline

The system implements a staged retrieval-augmented generation workflow in which document acquisition, corpus construction, vector indexing, evidence selection, answer generation and answer validation are separate processing phases. At startup, the FastAPI lifespan hook in [documentApi/app/main.py](documentApi/app/main.py) initializes the shared infrastructure (metadata database, managed file store, API-key service, encrypted chat audit and the active vector backend) and injects it into the ingestion and chat services. The vector backend is selected from the persisted configuration (or `VECTOR_BACKEND`) in [documentApi/app/vector_store/factory.py](documentApi/app/vector_store/factory.py) and resolves to PostgreSQL with pgvector, embedded SQLite or embedded Qdrant.

Document ingress begins at the folder-upload endpoint (`POST /api/documents/upload-folder-path` in [documentApi/app/routers/documents.py](documentApi/app/routers/documents.py)), which accepts a root path with `offset` and `batchSize` for incremental traversal. The helper [ingest_folder_batch.py](ingest_folder_batch.py) repeats the request to process large directory trees without one monolithic transfer. The scanner in [documentApi/app/services/folder_scan.py](documentApi/app/services/folder_scan.py) walks the tree recursively, preserves relative paths and restricts ingestion to supported corpus formats.

Each file receives two identities ([documentApi/app/source_identity.py](documentApi/app/source_identity.py)). The **source ID** is a SHA-256 over the environment and the canonical location (the `url` in the document front matter when present, otherwise source namespace plus file name). The **content hash** is a SHA-256 over the file content. The document version ID is `sha256(source_id + content_hash)`. Exact duplicates are skipped; changed content becomes a new version of the same source. A new version replaces the previous one only after indexing succeeds: the switch of `isActive` is transactional, and a failed indexing run leaves the previous active version untouched ([documentApi/app/ingest_service.py](documentApi/app/ingest_service.py), [documentApi/app/database.py](documentApi/app/database.py)). Versions carry `version`, `isActive`, `canonicalLocation` and `corpusVersion`, and an optional `force_rechunk` re-processes a document that is otherwise unchanged. Documents are keyed by `(docId, environmentId)` so the same document can be indexed into several environments (for example different embedding models or chunk sizes). The catalog is stateful: documents move through queued, processing, done and error states, and interrupted work is reconciled after an API restart. See [docs/source-lifecycle-migration.md](docs/source-lifecycle-migration.md) for migration and rollback.

Indexing runs asynchronously in the ingest service. It removes vectors previously stored for the same document version (idempotent re-indexing), then loads the corpus JSONL if available or re-parses the original file. Parsing in [documentApi/app/worker.py](documentApi/app/worker.py) tries layered extraction (structured partitioning, PDF fallback, plain text) and then calls `structured_chunks` in [documentApi/app/document_processing.py](documentApi/app/document_processing.py). That function removes boilerplate, redacts contact details while preserving technical values, and splits Markdown along its structure: tables, lists and procedures stay intact and each chunk carries heading metadata. `chunkSize` (default 900) is the target size in characters; `chunkOverlap` (a percentage, default 15) is retained in the settings for compatibility with the environment matrix but is **not used** by the structured chunker. The default embedding model in the settings is `paraphrase-multilingual-MiniLM-L12-v2`; it is configurable per environment, and embedding uses CUDA when available.

Each chunk is serialized into a corpus artifact with a deterministic chunk ID, content hash and source provenance, and the canonical source URL is taken from the document header when present so evidence can be linked to its origin. Embeddings are computed in worker threads with batching and sub-batch fallback, then written to the active vector store through a common interface ([documentApi/app/vector_store/](documentApi/app/vector_store/)). After a successful upsert the catalog records the chunk count and a terminal done status.

Query-time processing in [documentApi/app/chat_service.py](documentApi/app/chat_service.py) proceeds as follows.

1. **Bounding and context.** The question and recent history are length-bounded. [documentApi/app/conversation_context.py](documentApi/app/conversation_context.py) resolves follow-up questions (for example an instrument carried over from the previous turn) and detects explicit topic switches; history is context only, never evidence.
2. **Candidate retrieval.** The question is embedded with the environment's embedding model and a wider candidate pool than the final context budget is requested (between `topK` and 120 candidates).
3. **Evidence selection.** [documentApi/app/evidence_selection.py](documentApi/app/evidence_selection.py) and [documentApi/app/source_policy.py](documentApi/app/source_policy.py) rerank candidates by combining vector similarity with lexical and numeric overlap, optional per-source multipliers from `source_boosts.json`, instrument, authority and current-status preference. They deduplicate, apply `maxChunksPerSource` and `minEvidenceSimilarity`, and add bounded neighbouring chunks.
4. **Checked source-derived routes.** Where the evidence supports it, answers for reference lists, literal facts, tables, wavelength ranges, operational facts and source procedures are derived directly from the retrieved text ([documentApi/app/reference_answers.py](documentApi/app/reference_answers.py), [literal_answers.py](documentApi/app/literal_answers.py), [table_facts.py](documentApi/app/table_facts.py), [wavelength_reasoning.py](documentApi/app/wavelength_reasoning.py), [operational_answers.py](documentApi/app/operational_answers.py), [sourced_procedures.py](documentApi/app/sourced_procedures.py)) and no model generation is needed.
5. **Grounded generation.** Otherwise the language model, served through an OpenAI-compatible endpoint (a local Ollama server by default), is asked for a JSON answer that cites evidence items with quotations.
6. **Validation and repair.** [documentApi/app/grounding.py](documentApi/app/grounding.py) checks the answer mechanically (citations exist, quotations occur in the cited evidence, numbers and units are supported) and with a semantic entailment check ([documentApi/app/semantic_support.py](documentApi/app/semantic_support.py)). A failing answer gets at most one bounded repair attempt (two generation attempts in total); if it still fails, the system returns a verbatim source excerpt when one is available and otherwise abstains rather than answering unsupported.
7. **Audit and logging.** The prompt, evidence and answer are written to an encrypted audit trail ([documentApi/app/crypto_service.py](documentApi/app/crypto_service.py), key from `NOTBOT_AUDIT_KEY`). Separately, each request is stored in the metadata database (message and answer in plain text) so `GET /api/chat/requests` and the feedback endpoint can show and rate it.

In methodological terms, this architecture provides deterministic content-version identity with latest-version replacement, explicit provenance retention, a retrieval policy that separates candidate generation from precision-oriented selection, and an answer policy in which every claim must be traceable to quoted evidence. The remaining limitations (for example the verifier accepting some contradictory procedural claims) are tracked in [NOTBOT_HANDOFF.md](NOTBOT_HANDOFF.md).

## Observatory Fit and Architectural Positioning

### 4.1 Observatory Operating Constraints

Professional astronomical observatories combine heterogeneous documentation sources, strict operational procedures, and time-critical decision windows. Unlike many enterprise deployments that assume centralized document management, observatory knowledge assets are often distributed across decentralized directory trees, mixed file formats, and team-specific storage conventions. In this context, RAG effectiveness is determined not only by retrieval quality but also by ingestion reliability, traceability, and deployment flexibility [CIT-1, CIT-2].

The present system addresses these constraints through asynchronous folder-native ingestion, explicit job-state management, and backend-portable vector infrastructure. This design aligns with operational requirements in which indexing jobs may span long durations, service restarts are possible, and answer provenance must remain inspectable for post hoc verification.

### 4.2 Architectural Suitability for Observatory Workflows

The architecture is particularly suitable for observatory workflows for six reasons.

1. It supports decentralized corpus acquisition from recursive directory scans with bounded batch submission ([documentApi/app/services/folder_scan.py](documentApi/app/services/folder_scan.py), [ingest_folder_batch.py](ingest_folder_batch.py)).
2. It uses a stable per-source identity plus content hashes, so a changed source replaces its older version atomically and unchanged sources are not re-indexed ([documentApi/app/source_identity.py](documentApi/app/source_identity.py)).
3. It provides operational resilience through explicit queue processing, restart recovery, and persisted document/job state ([documentApi/app/ingest_service.py](documentApi/app/ingest_service.py), [documentApi/app/database.py](documentApi/app/database.py)).
4. It preserves provenance and corpus artifacts (JSONL plus optional markdown), enabling auditing and reproducibility of retrieval evidence.
5. It improves precision on fact-heavy technical queries by combining semantic retrieval with lexical and numeric selection and by deriving tables, ranges and procedures directly from sources.
6. It validates generated answers against quoted evidence and keeps an encrypted audit trail, which supports review of safety-relevant answers.

Collectively, these properties are consistent with recommendations in scientific software engineering for transparency, recoverability, and controllable data flows [CIT-3, CIT-4].

### 4.3 Relation to Standard RAG Architecture

This system should be described as an observatory-adapted production RAG architecture rather than a purely standard baseline. Its core retrieval chain follows canonical RAG patterns (chunking, embedding, vector search, context construction, generation) [CIT-1, CIT-5]. However, its implementation extends baseline patterns with operational and domain-specific mechanisms that are not mandatory in minimal reference designs.

| Dimension | Baseline RAG (common reference pattern) | This implementation |
| --- | --- | --- |
| Corpus ingestion | One-shot or periodic batch preprocess | Continuous folder-native ingestion with offset pagination |
| Identity model | Often file-name or pipeline-local IDs | Stable source ID plus content-hash version ID, latest-only active version |
| Chunking | Fixed-size windows with overlap | Structure-aware Markdown chunks (tables, lists, procedures, heading metadata) |
| Processing control | Script-driven, limited state persistence | Asynchronous queued jobs with persisted status and restart recovery |
| Vector backend | Single backend assumed | Backend-portable (PostgreSQL/pgvector, embedded SQLite, embedded Qdrant) |
| Retrieval policy | Dense vector search only (common) | Dense candidate retrieval plus lexical, numeric, authority and instrument-aware selection |
| Answering | Free-form generation from context | Source-derived routes or grounded JSON generation with citation, quotation and entailment checks |
| Provenance artifacts | Variable, often implicit | Corpus JSONL/markdown, source-aware payloads and encrypted request audit |

Accordingly, the system is standard in algorithmic primitives but non-trivial in systems architecture. The contribution is therefore best framed as architectural adaptation for high-reliability scientific operations rather than as a novel retrieval algorithm.

### 4.4 Suggested Citation Mapping (Placeholders)

Use the following placeholder mapping in the manuscript and replace with your final BibTeX keys.

- CIT-1: Foundational RAG formulation (for example, Lewis et al., 2020).
- CIT-2: Domain-specific constraints of scientific observatory software operations.
- CIT-3: Reproducibility and provenance practices in computational science systems.
- CIT-4: Reliability engineering for long-running data processing pipelines.
