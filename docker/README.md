# RAG Stack — modulares Docker-Setup

Alles unter `docker/` ist optional kombinierbar: Du startest nur die **Profile**, die du brauchst.

## Schnellstart

```powershell
cd docker
Copy-Item .env.example .env
docker compose --profile backend --profile ollama up -d --build
```

- API: http://localhost:8000  
- Ollama: http://localhost:11434  
- Web-Chat: `docker compose --profile chat up -d --build` → http://localhost:8080
- Admin-Web: `docker compose --profile admin up -d --build` → http://localhost:8081

Der **Electron-ChatBot** (`npm run dev:chat`) laeuft weiterhin nativ und nutzt dieselbe API.

---

## Ordnerstruktur

```text
docker/
  compose.yml                 # Haupteinstieg (include aller Module)
  compose/
    backend.compose.yml       # documentApi (FastAPI)
    chat.compose.yml          # Web-Chat (qa_site + Nginx)
    admin.compose.yml         # Admin-Web (Document Handling UI + Nginx)
    postgres.compose.yml      # Postgres + pgvector
    qdrant.compose.yml        # Qdrant Server
    ollama.compose.yml        # gemeinsamer Ollama
    ollama-models.compose.yml # Modelle in gemeinsamen Ollama pullen
    network.compose.yml         # Netzwerk + Volumes
  backend/Dockerfile
  chat/Dockerfile
  admin/Dockerfile
  admin/nginx.conf
  postgres/init/              # pgvector Extension
  config/                     # Beispiel-settings fuer Docker
  ollama/models/<modell>/     # Eigenes Image + compose pro LLM
```

---

## Profile (modular)

| Profil | Dienst | Beschreibung |
|--------|--------|--------------|
| `backend` | `api` | FastAPI documentApi |
| `chat` | `chat-web` | Web-UI (qa_site) |
| `admin` | `admin-web` | Admin-UI (`adminWeb/`) |
| `postgres` | `postgres` | Postgres 16 + pgvector |
| `qdrant` | `qdrant` | Qdrant Vektor-Server |
| `ollama` | `ollama` | Gemeinsamer Ollama |
| `datastores` | postgres + qdrant | Beide Datenstores |
| `full` | alles oben | Komplett-Stack |
| `model-*` | Pull-Job | Modell in gemeinsamen Ollama laden |

### Beispiele

```powershell
# Minimal: API + Ollama (Vektoren: sqlite_embedded im API-Volume)
docker compose --profile backend --profile ollama up -d --build

# Mit Postgres pgvector
docker compose --profile backend --profile postgres --profile ollama up -d --build

# Modell in gemeinsamen Ollama laden
docker compose --profile ollama --profile model-qwen25 run --rm ollama-pull-qwen25

# Alles
docker compose --profile full up -d --build
```

---

## Konfiguration im Container

Daten liegen im Volume `rag_api_data` unter `/data`.

Beispiel-Dateien kopieren (nach erstem API-Start):

```powershell
docker cp config/settings.docker.example.json rag-api:/data/settings.json
docker cp config/chat_settings.docker.example.json rag-api:/data/chat_settings.json
docker restart rag-api
```

Wichtig bei **Postgres-Profil**: `dbHost` in `settings.json` muss `postgres` sein (siehe Beispiel).

Bei **gemeinsamem Ollama**: `llmBaseUrl` = `http://ollama:11434/v1` (intern im Docker-Netz).

---

## LLM-Empfehlungen zum Testen

| Modell | Ollama-Tag | Groesse ca. | Staerke | Eigenes Compose |
|--------|------------|-------------|---------|-----------------|
| **llama3.2** | `llama3.2` | ~2 GB | Schnell, Standard | `ollama/models/llama3.2/` Port 11434 |
| **llama3.1:8b** | `llama3.1:8b` | ~4.7 GB | Bessere Qualitaet | Port 11435 |
| **mistral:7b** | `mistral:7b` | ~4.1 GB | DE/EN, ausgewogen | Port 11436 |
| **qwen2.5:7b** | `qwen2.5:7b` | ~4.7 GB | Sehr gut DE/EN, **RAG-Empfehlung** | Port 11438 |
| **qwen2.5:32b** | `qwen2.5:32b` | ~20 GB | Starke Qualitaet DE/EN, viel RAM/GPU | Port 11443 |
| **gemma2:9b** | `gemma2:9b` | ~5.5 GB | Effizient, Fakten | Port 11437 |
| **gemma2:27b** | `gemma2:27b` | ~16 GB | Hohe Qualitaet, viel RAM/GPU | Port 11444 |
| **phi3:mini** | `phi3:mini` | ~2.3 GB | Sehr schnell, wenig RAM | Port 11439 |
| **command-r7b** | `command-r7b` | ~4.7 GB | Fuer Retrieval/RAG optimiert | Port 11442 |
| **deepseek-r1:7b** | `deepseek-r1:7b` | ~4.7 GB | Reasoning / laengere Antworten | Port 11441 |
| **mixtral:8x7b** | `mixtral:8x7b` | ~26 GB | Top-Qualitaet, GPU noetig | Port 11440 |

### Zwei Betriebsarten

1. **Gemeinsamer Ollama** (`--profile ollama`) — ein Container, Modelle per Profil `model-*` oder `docker exec rag-ollama ollama pull <tag>`  
2. **Dedizierter Container pro Modell** — eigenes Image startet Ollama und pulled genau ein Modell:

```powershell
docker compose -f ollama/models/qwen2.5-7b/compose.yml up -d --build
# API dann: LLM_BASE_URL=http://host.docker.internal:11438/v1  (Windows/Mac)
```

---

## GPU (optional)

In `compose/ollama.compose.yml` den `deploy.resources`-Block fuer NVIDIA aktivieren (nvidia-container-toolkit noetig).

---

## Ports (Standard)

| Dienst | Port |
|--------|------|
| API | 8000 |
| Web-Chat | 8080 |
| Admin-Web | 8081 |
| Postgres | 5432 |
| Qdrant | 6333 |
| Ollama (shared) | 11434 |
| Ollama-Modelle | 11434–11444 |

Alle Ports ueber `.env` aenderbar.

---

## Altes Setup

`documentApi/docker-compose.yml` bleibt als einfache Alternative; das neue modulare Setup liegt unter `docker/`.
