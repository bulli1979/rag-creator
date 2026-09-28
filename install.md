# Installation & Start

**Sprache:** [Deutsch](install.md) | [English](install.en.md)

Anleitung zum Einrichten und Starten von **RAG Ingest Studio** (Document Handling) und **RAG Chat** im Entwicklungs- und Produktionsmodus.

> Alternativ: Vollstaendiger Stack per Docker — siehe [docker/README.md](docker/README.md).

## Voraussetzungen

- Node.js 20+
- Python 3.10+
- Docker (optional, nur fuer Postgres/pgvector oder das modulare Docker-Setup)

## 1) Postgres (pgvector) lokal starten

Nur noetig, wenn du das Vektor-Backend `postgres` nutzen willst:

```bash
docker run --name rag-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=rag -p 5432:5432 -d pgvector/pgvector:pg16
```

Danach ist Postgres auf `localhost:5432` erreichbar.

## 2) documentApi Python-Umgebung einrichten

Im Verzeichnis `documentApi`:

```bash
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Wichtig: Alle API-Abhaengigkeiten (z. B. `qdrant-client`) in genau dieser venv installieren:

```bash
documentApi\.venv\Scripts\python.exe -m pip install -r documentApi/requirements.txt
```

## 3) Node Dependencies installieren

Im Repository-Root:

```bash
npm install
```

## 4) Development starten

### Document Handling (Ingest Studio)

Im Repository-Root:

```bash
npm run dev
```

Das startet:

- **documentApi** (FastAPI/Uvicorn) auf `http://127.0.0.1:8000`
- Vite Renderer auf `http://localhost:5173`
- Electron Main Process (startet erst, wenn Renderer **und** Port 8000 bereit sind)

Nur die API in einem eigenen Terminal: `npm run dev:api`

### Chat (Electron)

API muss laufen (`npm run dev:api` oder `npm run dev`). Dann in einem zweiten Terminal:

```bash
npm run dev:chat
```

Chat-Renderer: `http://localhost:5174`

### Admin-Web (Browser, eigener Ordner `adminWeb/`)

API muss laufen (`npm run dev:api` oder `npm run dev`). Dann:

```bash
npm run dev:admin-web
```

Admin-UI: `http://localhost:5175`  
API-URL und **Admin-API-Key** im Connection-Gate eingeben.  
Verbindungen werden zusätzlich in eigenen Backend-Tabellen (`admin_web_*`) gespeichert.

### Hinweis zu `qdrant_embedded`

Der API-Runner startet standardmaessig **ohne** `uvicorn --reload`, da der Qdrant-Ordner exklusiv gelockt wird.  
Reload nur explizit aktivieren:

```bash
# PowerShell
$env:DOCUMENT_API_RELOAD="1"
npm run dev:api
```

## 5) API-Keys (erster Start)

Alle API-Endpunkte (ausser `/` und `/api/auth/status`) erfordern den Header **`X-API-Key`**.

Beim **ersten Start** ohne bestehende Keys erzeugt die API automatisch:

- einen **Client-Key** (`default`) — fuer Electron-Apps und qa_site
- einen **Admin-Key** (`admin`) — fuer Key-Verwaltung in Document Handling

Beide Keys stehen **einmalig in den Server-Logs**, z. B.:

```text
Default API key (client): rag_...
Admin API key: rag_...
```

### Keys fest setzen (optional)

Per Umgebungsvariable vor dem API-Start:

```bash
# PowerShell
$env:RAG_DEFAULT_API_KEY="rag_mein_client_key"
$env:RAG_ADMIN_API_KEY="rag_mein_admin_key"
npm run dev:api
```

In Docker: `RAG_DEFAULT_API_KEY` und `RAG_ADMIN_API_KEY` in `docker/.env` — siehe [docker/.env.example](docker/.env.example).

### Electron-Apps verbinden

Beim ersten Start von **Document Handling** und **Chat** erscheint ein Dialog fuer **API-URL** und **API-Key**. Die Daten werden lokal gespeichert (`userData/connection.json`).

- Standard-URL: `http://localhost:8000`
- Client-Key aus den Logs eintragen
- Verbindung spaeter aendern: Document Handling → Einstellungen, Chat → Sidebar „API-Verbindung“
- Weitere Keys anlegen: Document Handling → Einstellungen (nur mit **Admin-Key**)

## 6) Production Build

```bash
npm run build
```

Chat separat:

```bash
npm run build:chat
```

## 7) Produktionsstart

Document Handling:

```bash
npm run start
```

Das Skript baut zuerst Renderer + Main und startet danach Electron im Production-Modus.

Chat:

```bash
npm run start:chat
```

## Datenablage

Alle Artefakte liegen lokal unter `~/RAGIngestStudio/` (Windows: `C:\Users\<user>\RAGIngestStudio\`):

- `files/<docId>/` — Originaldateien
- `corpus/<docId>.jsonl` — editierbare Source of Truth
- `index.sqlite` — Dokumente, Jobs, Chat-Logs, API-Keys
- `settings.json` — lokale Einstellungen
- `vector_sqlite/` / `vector_qdrant/` — eingebettete Vektor-Stores
