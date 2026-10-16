# Observatory Onboarding (Docker)

This guide is for teams who only need to run the backend stack in containers:
- documentApi (FastAPI)
- Postgres + pgvector
- Ollama

The Electron apps are not required for backend validation.

## 1) Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- At least 8 GB RAM recommended (Ollama models are memory-heavy)
- Network access to pull container images

Check installation:

```bash
docker --version
docker compose version
```

## 2) Prepare environment

From repository root:

```bash
cp .env.observatory.example .env
```

Optional: edit `.env` if your ports are in use.

## 3) Start services

```bash
docker compose up -d --build
```

Check status:

```bash
docker compose ps
```

Expected services:
- `*-postgres` (healthy)
- `*-ollama` (running)
- `*-document-api` (running)

## 4) Verify API is alive

```bash
curl http://localhost:8000/api/health
```

Expected: JSON response with healthy status.

## 5) Pull an Ollama model (first-time only)

```bash
docker compose exec ollama ollama pull llama3.2
```

Optional quick check:

```bash
docker compose exec ollama ollama list
```

## 6) Configure app-side clients

If a client (desktop app, script, or external system) talks to this stack:
- API base URL: `http://localhost:8000`
- Postgres host: `localhost`
- Postgres port: value from `.env` (`POSTGRES_PORT`, default `5432`)
- Ollama base URL: `http://localhost:11434/v1`

## 7) Logs and troubleshooting

Stream logs:

```bash
docker compose logs -f document-api
docker compose logs -f postgres
docker compose logs -f ollama
```

Common issues:
- Port already in use: change `API_PORT`, `POSTGRES_PORT`, or `OLLAMA_PORT` in `.env`, then restart.
- API cannot reach Postgres: check `postgres` service is healthy and `POSTGRES_*` values in `.env` are consistent.
- Slow first answer: model pull/warm-up can take time on first run.

## 8) Stop and cleanup

Stop:

```bash
docker compose down
```

Stop and delete all volumes/data:

```bash
docker compose down -v
```

## 9) Handoff checklist

Before sharing with another team:
- `.env` prepared with team-specific ports and credentials
- `docker compose up -d --build` tested once
- health endpoint validated
- at least one Ollama model pulled
- this document shared with the team
