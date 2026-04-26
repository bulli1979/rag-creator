# RAG Ingest Studio + RAG Chat

**Sprache:** [Deutsch](README.md) | [English](README.en.md)

Desktop-Stack (Electron + React + TypeScript + FastAPI) fuer lokale Dokument-Ingestion und Chat ueber Vektor-Retrieval:

- Upload per File Picker, Drag & Drop und rekursiver Ordner-Ingest
- Parsing + Chunking + lokale Embeddings (Python Worker)
- Vektor-Backends pro Umgebung:
  - `postgres` (pgvector)
  - `sqlite_embedded` (ohne separaten Server)
  - `qdrant_embedded` (lokaler Qdrant-Speicherordner, ohne separaten Server)
- Lokale Index-DB in SQLite (`index.sqlite`) fuer Dokument-/Job-Metadaten
- Editierbarer Corpus als JSONL (optional Markdown)
- Reindex pro Dokument, Bulk und "Alle neu indexieren"
- Chat-UI mit Quellenlinks (extern) und Antwort-Metriken (Dauer, Tokens, Tokens/s)

## Monorepo Struktur

```text
documentHandling/    Dokumentverwaltung + Ingestion UI (Electron)
chatBot/             Chat UI (Electron)
documentApi/         FastAPI Backend + Worker + Vector Stores
scripts/             Startskripte (u. a. documentApi Runner)
batchTest/           Batch-Chat gegen die API + Excel-Export (Python)
```

## Systemdiagramm (Ingest + Reindex)

```mermaid
flowchart LR
  UI[Renderer UI\nUpload / Dashboard / Corpus Viewer] --> IPC[IPC Contracts\npackages/shared]
  IPC --> MAIN[Electron Main\napps/main]
  MAIN --> FS[(Lokale Dateien\nfiles/<docId>/)]
  MAIN --> CORPUS[(Corpus JSONL/MD\ncorpus/<docId>.*)]
  MAIN --> SQLITE[(SQLite\nindex.sqlite)]
  MAIN --> WORKER[Python Worker\napps/python_worker]
  WORKER --> PGVECTOR[(Postgres + pgvector\nrag_documents)]
  PGVECTOR --> MAIN
  MAIN --> UI
```

### Was das Diagramm genau zeigt

1. **UI startet den Prozess**  
   Im Renderer waehlt der User Dateien aus (Picker oder Drag & Drop), sieht Status im Dashboard und kann Reindex/Remove ausloesen.

2. **IPC entkoppelt Frontend und Backend**  
   Die UI spricht nie direkt mit Dateisystem, Python oder Postgres. Sie sendet nur typisierte IPC-Requests ueber `packages/shared`.

3. **Electron Main orchestriert alles**  
   Der Main Process ist die zentrale Steuerung: Er nimmt Jobs an, schreibt Metadaten in SQLite, verwaltet Dateipfade und koordiniert den Worker.

4. **Lokale Artefakte werden persistiert**  
   Originaldateien landen in `files/<docId>/`.  
   Der editierbare Corpus wird als `corpus/<docId>.jsonl` (optional `.md`) gespeichert und dient als Source of Truth fuer spaetere Reindex-Laeufe.

5. **Python Worker macht Parsing + Embeddings**  
   Der Worker liest den lokalen Input, fuehrt Parsing/Chunking aus und erzeugt Embeddings fuer die Chunks.

6. **Postgres (pgvector) speichert die Vektoren fuer Retrieval**  
   Die erzeugten Punkte werden in `rag_documents` geschrieben. Vor Reindex werden bestehende Punkte des Dokuments entfernt, damit der Zustand idempotent bleibt.

7. **Rueckmeldung an die UI**  
   Der Main Process aktualisiert Job-/Dokumentstatus in SQLite und liefert den Fortschritt zurueck an die UI, damit Dashboard und Corpus Viewer den aktuellen Stand anzeigen.

## Voraussetzungen

- Node.js 20+
- Python 3.10+
- Docker (optional, nur fuer Postgres/pgvector)

## 1) Postgres (pgvector) lokal starten

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

Im Repository-Root:

```bash
npm run dev
```

Das startet:

- **documentApi** (FastAPI/Uvicorn) auf `http://127.0.0.1:8000`
- Vite Renderer auf `http://localhost:5173`
- Electron Main Process (startet erst, wenn Renderer **und** Port 8000 bereit sind)

Nur die API in einem eigenen Terminal: `npm run dev:api`

Hinweis zu `qdrant_embedded`: Der API-Runner startet standardmaessig **ohne** `uvicorn --reload`, da der Qdrant-Ordner exklusiv gelockt wird.  
Reload nur explizit aktivieren:

```bash
# PowerShell
$env:DOCUMENT_API_RELOAD="1"
npm run dev:api
```

## 5) Production Build

```bash
npm run build
```

## 6) Produktionsstart

```bash
npm run start
```

Das Skript baut zuerst Renderer + Main und startet danach Electron im Production-Modus.

## Datenablage / Offline Verhalten

Alle Artefakte liegen lokal in:

`~/RAGIngestStudio/`

Unterstruktur:

- `files/<docId>/` - Originaldateien
- `corpus/<docId>.jsonl` - editierbare Source of Truth
- `corpus/<docId>.md` - optionaler Markdown-Export
- `index.sqlite` - Dokumente + Jobs
- `settings.json` - lokale Einstellungen (inkl. Vektor-Backend pro Umgebung)
- `vector_sqlite/` - Speicher fuer `sqlite_embedded`
- `vector_qdrant/` - Speicher fuer `qdrant_embedded`

## Kern-Funktionen

- **Dashboard** mit Filter/Suche, Status, Chunk-Anzahl, Bulk-Aktionen
- **Upload** per Picker oder Drag & Drop
- **Corpus Viewer** (editierbar), Speichern + Reindex
- **Settings** pro Umgebung inkl. Backend-Auswahl (`postgres`, `sqlite_embedded`, `qdrant_embedded`)
- **Connection Test** backend-spezifisch (Postgres/SQLite/Qdrant)
- **CSV Export** der Dokumentliste
- **Chat** mit Quellenanzeige, "Website"-Button (externer Browser), Copy-Button und Antwort-Metriken

## batchTest (Batch-Chat + Excel)

Im Ordner `batchTest/` liegt ein kleines **Python**-Tool, das viele Chat-Fragen gegen die laufende **documentApi** schickt und eine **Excel-Arbeitsmappe** mit Antworten, Token-Metriken, Geschwindigkeit und den gezogenen Kontext-Chunks schreibt.

> English: [README.en.md](README.en.md) — same **batchTest** section.

### Voraussetzungen

- **documentApi** erreichbar (gleiche URL wie die App, Standard `http://localhost:8000`)
- Derselbe Index/Vektor-Backend wie im Chat, damit das Retrieval zu euren Dokumenten passt
- Abhaengigkeiten: `pip install -r batchTest/requirements.txt` (`httpx`, `openpyxl`)

### Kurzstart

```bash
cd batchTest
pip install -r requirements.txt
cp batch_config.example.json batch_config.json
# batch_config.json anpassen (Fragen, API-URL, optionale Chat-Settings)
python batch_chat.py --config batch_config.json
```

Unter Windows (PowerShell) geht `cp` nicht immer; dann z. B. `Copy-Item batch_config.example.json batch_config.json`.

### Konfiguration (`batch_config.json`)

| Bereich | Bedeutung |
|--------|-----------|
| `apiBaseUrl` | Basis-URL der documentApi (ohne abschliessenden Slash) |
| `requestTimeoutSeconds` | HTTP-Timeout pro Anfrage |
| `questions` | Liste von Fragen (Strings) |
| `questionsFile` | Optionaler Pfad zu einer Textdatei: eine Frage pro Zeile; Zeilen mit `#` sind Kommentare |
| `language` | `"de"` oder `"en"`, oder weglassen (wie in der API) |
| `history` | Optional Liste aus `{"role":"user"|"assistant","content":"..."}` (wie Chat-API) |
| `applyChatSettings` | Bei `true`: aktuelle Einstellungen per `GET /api/chat/settings` laden, mit `chatSettings` mergen, danach per `PUT` speichern |
| `chatSettings` | Gleiche Felder wie im App-Chat: `llmApiKey`, `llmBaseUrl`, `llmModel`, `temperature`, `maxTokens`, `topK`, `systemPrompt`, `encryptionKey` (CamelCase wie in der API) |
| `restoreChatSettingsAfterRun` | Bei `true`: nach dem Lauf die zuvor gesicherten Settings wiederherstellen |
| `outputExcel` | Pfad zur `.xlsx`-Ausgabe (relative Pfade beziehen sich auf das **aktuelle Arbeitsverzeichnis**) |

### Excel-Ausgabe

Die Arbeitsmappe enthaelt:

- **Meta** – Zeitstempel (UTC), API-URL, Konfigurationspfad, optional angewendete `chatSettings`
- **Ergebnisse** – eine Zeile pro Frage: Antwort, HTTP-Fehler (falls vorhanden), `elapsedMs`, Prompt-/Completion-/Total-Tokens, Tokens/s, Chunk-Anzahl, Kurzliste der Chunks, ausfuehrlicher Chunk-Text
- **Chunks** – eine Zeile pro abgerufenem Chunk: Frage-Nr., Position, Dateiname, `chunkIndex`, `documentId`, Aehnlichkeit, Quelle, Textauszug

Lange Texte werden bei Bedarf wegen Excel-Zelllimits gekuerzt.

## Hinweise zu Idempotenz

- Vor jedem Reindex werden bestehende Vektoren fuer `documentId` aus Postgres entfernt.
- Point IDs sind deterministisch via `sha256(documentId + ":" + chunkIndex)`.
- JSONL bleibt die editierbare Truth-Quelle fuer spaetere Reindex-Laeufe.
