# Installation & Getting Started

**Language:** [English](install.en.md) | [German](install.md)

Guide for setting up and running **RAG Ingest Studio** (Document Handling) and **RAG Chat** in development and production.

> Alternatively: full stack via Docker — see [docker/README.md](docker/README.md).

## Requirements

- Node.js 20+
- Python 3.10+
- Docker (optional, for Postgres/pgvector or the modular Docker setup)

## 1) Start Postgres (pgvector) locally

Only needed if you use the `postgres` vector backend:

```bash
docker run --name rag-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=rag -p 5432:5432 -d pgvector/pgvector:pg16
```

Postgres is then reachable at `localhost:5432`.

## 2) Set up documentApi Python environment

In the `documentApi` directory:

```bash
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Install all API dependencies (e.g. `qdrant-client`) in this venv:

```bash
documentApi\.venv\Scripts\python.exe -m pip install -r documentApi/requirements.txt
```

## 3) Install Node dependencies

At repository root:

```bash
npm install
```

## 4) Start development

### Document Handling (Ingest Studio)

At repository root:

```bash
npm run dev
```

This starts:

- **documentApi** (FastAPI/Uvicorn) at `http://127.0.0.1:8000`
- Vite renderer at `http://localhost:5173`
- Electron main (starts only when renderer **and** port 8000 are ready)

API only in a separate terminal: `npm run dev:api`

### Chat (Electron)

The API must be running (`npm run dev:api` or `npm run dev`). Then in a second terminal:

```bash
npm run dev:chat
```

Chat renderer: `http://localhost:5174`

### Admin web (browser, folder `adminWeb/`)

The API must be running (`npm run dev:api` or `npm run dev`). Then:

```bash
npm run dev:admin-web
```

Admin UI: `http://localhost:5175`  
Enter API URL and **admin API key** in the connection gate.  
Connections are also stored in dedicated backend tables (`admin_web_*`).

### Note on `qdrant_embedded`

The API runner starts **without** `uvicorn --reload` by default because the Qdrant folder is exclusively locked.  
Enable reload only explicitly:

```bash
# PowerShell
$env:DOCUMENT_API_RELOAD="1"
npm run dev:api
```

## 5) API keys (first start)

All API endpoints (except `/` and `/api/auth/status`) require the **`X-API-Key`** header.

On **first start** with no existing keys, the API automatically creates:

- a **client key** (`default`) — for Electron apps and qa_site
- an **admin key** (`admin`) — for key management in Document Handling

Both keys appear **once in the server logs**, e.g.:

```text
Default API key (client): rag_...
Admin API key: rag_...
```

### Fixed keys (optional)

Set environment variables before starting the API:

```bash
# PowerShell
$env:RAG_DEFAULT_API_KEY="rag_my_client_key"
$env:RAG_ADMIN_API_KEY="rag_my_admin_key"
npm run dev:api
```

In Docker: set `RAG_DEFAULT_API_KEY` and `RAG_ADMIN_API_KEY` in `docker/.env` — see [docker/.env.example](docker/.env.example).

### Connect Electron apps

On first launch of **Document Handling** and **Chat**, a dialog asks for **API URL** and **API key**. Credentials are stored locally (`userData/connection.json`).

- Default URL: `http://localhost:8000`
- Enter the client key from the logs
- Change connection later: Document Handling → Settings, Chat → sidebar “API connection”
- Create more keys: Document Handling → Settings (requires **admin key**)

## 6) Production build

```bash
npm run build
```

Chat separately:

```bash
npm run build:chat
```

## 7) Production start

Document Handling:

```bash
npm run start
```

The script builds renderer + main first, then starts Electron in production mode.

Chat:

```bash
npm run start:chat
```

## Data layout

All artifacts are stored locally under `~/RAGIngestStudio/` (Windows: `C:\Users\<user>\RAGIngestStudio\`):

- `files/<docId>/` — original files
- `corpus/<docId>.jsonl` — editable source of truth
- `index.sqlite` — documents, jobs, chat logs, API keys
- `settings.json` — local settings
- `vector_sqlite/` / `vector_qdrant/` — embedded vector stores
