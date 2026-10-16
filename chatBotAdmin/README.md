# NOTBot Admin — FastAPI web UI for chatBot administration

A standalone FastAPI application that provides an admin interface for managing:
- LLM settings (API key, base URL, model, temperature, etc.)
- Postgres vector database environments
- Chat configuration

## Quick Start

```bash
cd chatBotAdmin
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8090 --reload
```

## Access

Open `http://localhost:8090` in your browser.

The admin UI has no built-in authentication. Keep it bound to loopback, or place it behind an authenticated reverse proxy before allowing network access.

## Architecture

This mirrors the Electron chatBot admin capabilities as a web interface:

- **Electron IPC** → FastAPI endpoints
- **LocalStorage config** → JSON file (`data/admin_settings.json`)
- **Backend API (port 8000)** → proxied via httpx

## Integration with NOTBot Backend

The admin app proxies chat requests to the existing backend API at `localhost:8000`. Configure LLM settings and Postgres environments via the web UI, which are saved to `data/admin_settings.json` and forwarded to backend on each chat request.