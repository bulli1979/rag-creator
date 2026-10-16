# Methodology

## End-to-End Ingestion and Retrieval Pipeline

The system implements a staged retrieval-augmented generation workflow in which document acquisition, corpus construction, vector indexing, and query-time reranking are separated into explicit processing phases. At application startup, the FastAPI lifespan hook initializes the shared infrastructure, including the metadata database, managed file store, and the active vector backend, and then injects those dependencies into the ingestion and chat services [documentApi/app/main.py](documentApi/app/main.py#L28). The active vector backend is selected from the persisted configuration and may resolve to PostgreSQL with pgvector or to an embedded local backend, depending on the environment profile [documentApi/app/vector_store/factory.py](documentApi/app/vector_store/factory.py#L35).

Document ingress begins at the directory-upload endpoint, which accepts a root path and paging parameters for incremental traversal [documentApi/app/routers/documents.py](documentApi/app/routers/documents.py#L51). The batch helper script submits the same request repeatedly in order to process large decentralized directory trees without requiring a single monolithic transfer [ingest_folder_batch.py](ingest_folder_batch.py#L11). The folder scanner enumerates the source tree recursively, preserves relative paths, and restricts ingestion to the supported corpus formats, thereby treating the input directory as a structured evidence repository rather than a flat upload buffer [documentApi/app/services/folder_scan.py](documentApi/app/services/folder_scan.py#L20).

For each discovered file, the ingest service computes a SHA-256 digest over the file content and uses that digest as the document version identifier. This suppresses exact-content duplicates, but it does not provide a stable logical source identity: changed content receives a new identifier, so older vectors for the same source can remain until source lifecycle handling is implemented and the index is rebuilt [documentApi/app/file_store.py](documentApi/app/file_store.py#L30). The file is copied into managed storage, and a document record is inserted into the SQLite catalog with environment metadata, source attributes, storage paths, and size information [documentApi/app/database.py](documentApi/app/database.py#L113). This catalog layer is stateful: documents transition through queued, processing, and done states, and interrupted processing can be reconciled after an API restart by resetting stale statuses and re-enqueuing pending work [documentApi/app/database.py](documentApi/app/database.py#L243).

The indexing job is executed asynchronously in the ingest service [documentApi/app/ingest_service.py](documentApi/app/ingest_service.py#L591). The implementation first removes any previously stored vectors for the same document to guarantee idempotent reindexing, then loads the document corpus from JSONL if available or reparses the original file when necessary [documentApi/app/ingest_service.py](documentApi/app/ingest_service.py#L741). Parsing is delegated to a worker-thread function that applies layered extraction logic: structured partitioning is attempted first, followed by PDF-specific fallback, and finally plain-text reading if no structured text can be recovered [documentApi/app/worker.py](documentApi/app/worker.py#L126). The resulting text is segmented into overlapping fixed-size chunks, with the default parameters defined in the application settings as chunk size 900, overlap 150, embedding model all-MiniLM-L6-v2, and optional markdown persistence [documentApi/app/worker.py](documentApi/app/worker.py#L111) [documentApi/app/models.py](documentApi/app/models.py#L94).

Each chunk is serialized into a corpus artifact together with chunk-level metadata, including a deterministic chunk identifier and source provenance. The service also attempts to extract a canonical source URL from the document header when present, so that retrieved evidence can be linked back to its original location with greater fidelity [documentApi/app/worker.py](documentApi/app/worker.py#L60). The corpus is then embedded in worker threads using a SentenceTransformer model, with batching and fallback logic to contain failures at subbatch granularity [documentApi/app/worker.py](documentApi/app/worker.py#L242). The embeddings and associated payloads are written to the active vector store through a common interface, which supports either PostgreSQL/pgvector or embedded SQLite as backend implementations [documentApi/app/vector_store/postgres_store.py](documentApi/app/vector_store/postgres_store.py#L136) [documentApi/app/vector_store/sqlite_embedded.py](documentApi/app/vector_store/sqlite_embedded.py#L83). After successful vector upsert, the document catalog is finalized with the observed chunk count and a terminal done status [documentApi/app/database.py](documentApi/app/database.py#L167).

Query-time retrieval uses the same embedding model to project the user question into the shared vector space [documentApi/app/chat_service.py](documentApi/app/chat_service.py#L87). The system then performs semantic nearest-neighbour retrieval from the active vector store and intentionally requests a wider candidate pool than the final context budget [documentApi/app/chat_service.py](documentApi/app/chat_service.py#L108). A second-stage reranking procedure subsequently reorders the candidates by combining vector similarity with lexical token overlap and numeric overlap, which operationalizes a hybrid retrieval strategy at the application layer rather than through a fused inverted-index data structure [documentApi/app/chat_service.py](documentApi/app/chat_service.py#L34). The final prompt context is constructed from the reranked chunks, and the language model is instructed to answer exclusively from that retrieved evidence set.

In methodological terms, this architecture provides deterministic content-version identity, explicit provenance retention through corpus and source metadata, and a two-stage retrieval policy that separates candidate generation from precision-oriented reranking. Stable logical source identity and latest-version replacement remain required before the production index can be considered duplicate-safe.

## Observatory Fit and Architectural Positioning

### 4.1 Observatory Operating Constraints

Professional astronomical observatories combine heterogeneous documentation sources, strict operational procedures, and time-critical decision windows. Unlike many enterprise deployments that assume centralized document management, observatory knowledge assets are often distributed across decentralized directory trees, mixed file formats, and team-specific storage conventions. In this context, RAG effectiveness is determined not only by retrieval quality but also by ingestion reliability, traceability, and deployment flexibility [CIT-1, CIT-2].

The present system addresses these constraints through asynchronous folder-native ingestion, explicit job-state management, and backend-portable vector infrastructure. This design aligns with operational requirements in which indexing jobs may span long durations, service restarts are possible, and answer provenance must remain inspectable for post hoc verification.

### 4.2 Architectural Suitability for Observatory Workflows

The architecture is particularly suitable for observatory workflows for five reasons.

1. It supports decentralized corpus acquisition from recursive directory scans with bounded batch submission [documentApi/app/services/folder_scan.py](documentApi/app/services/folder_scan.py#L20), [ingest_folder_batch.py](ingest_folder_batch.py#L11).
2. It uses deterministic content hashes for exact-version identity; stable per-source identity and replacement of older versions remain planned correctness work [documentApi/app/file_store.py](documentApi/app/file_store.py#L30).
3. It provides operational resilience through explicit queue processing, restart recovery, and persisted document/job state [documentApi/app/ingest_service.py](documentApi/app/ingest_service.py#L591), [documentApi/app/database.py](documentApi/app/database.py#L243).
4. It preserves provenance and corpus artifacts (JSONL plus optional markdown), enabling auditing and reproducibility of retrieval evidence [documentApi/app/ingest_service.py](documentApi/app/ingest_service.py#L652).
5. It improves precision on fact-heavy technical queries by combining semantic retrieval with lexical and numeric reranking [documentApi/app/chat_service.py](documentApi/app/chat_service.py#L34), which is valuable for parameter-sensitive operational questions.

Collectively, these properties are consistent with recommendations in scientific software engineering for transparency, recoverability, and controllable data flows [CIT-3, CIT-4].

### 4.3 Relation to Standard RAG Architecture

This system should be described as an observatory-adapted production RAG architecture rather than a purely standard baseline. Its core retrieval chain follows canonical RAG patterns (chunking, embedding, vector search, context construction, generation) [CIT-1, CIT-5]. However, its implementation extends baseline patterns with operational and domain-specific mechanisms that are not mandatory in minimal reference designs.

| Dimension | Baseline RAG (common reference pattern) | This implementation |
| --- | --- | --- |
| Corpus ingestion | One-shot or periodic batch preprocess | Continuous folder-native ingestion with offset pagination |
| Identity model | Often file-name or pipeline-local IDs | Content-hash version IDs; stable source lifecycle is still required |
| Processing control | Script-driven, limited state persistence | Asynchronous queued jobs with persisted status and restart recovery |
| Vector backend | Single backend assumed | Backend-portable (PostgreSQL/pgvector, embedded SQLite, embedded Qdrant) |
| Retrieval policy | Dense vector search only (common) | Dense candidate retrieval plus lexical and numeric reranking |
| Provenance artifacts | Variable, often implicit | Explicit corpus JSONL/markdown and source-aware payloads |

Accordingly, the system is standard in algorithmic primitives but non-trivial in systems architecture. The contribution is therefore best framed as architectural adaptation for high-reliability scientific operations rather than as a novel retrieval algorithm.

### 4.4 Suggested Citation Mapping (Placeholders)

Use the following placeholder mapping in the manuscript and replace with your final BibTeX keys.

- CIT-1: Foundational RAG formulation (for example, Lewis et al., 2020).
- CIT-2: Domain-specific constraints of scientific observatory software operations.
- CIT-3: Reproducibility and provenance practices in computational science systems.
- CIT-4: Reliability engineering for long-running data processing pipelines.
- CIT-5: Modern retrieval stack surveys (dense retrieval, hybrid retrieval, reranking).