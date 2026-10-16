"""NOTBot Admin — FastAPI proxy + static UI for chatBot administration.

Runs on port 8090 on loki. Proxies all /api/* requests to the
backend at port 8000 (or NOTBOT_API_URL env var). Serves the
admin SPA from static/.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("notbot-admin")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
API_BASE = os.getenv("NOTBOT_API_URL", "http://localhost:8000")

app = FastAPI(title="NOTBot Admin", version="1.0.0")


async def _proxy(request: Request, backend_path: str) -> Response:
    """Forward any HTTP request to the backend, preserving method/body/headers."""
    url = f"{API_BASE}{backend_path}"
    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(
                method=request.method,
                url=url,
                content=body,
                headers=headers,
            )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/json"),
        )
    except httpx.ConnectError:
        return Response(
            content=f'{{"detail":"Cannot reach backend at {API_BASE}"}}',
            status_code=502,
            media_type="application/json",
        )
    except httpx.TimeoutException:
        return Response(
            content='{"detail":"Backend timed out"}',
            status_code=504,
            media_type="application/json",
        )


@app.api_route("/api/health", methods=["GET"])
async def proxy_health(request: Request):
    return await _proxy(request, "/api/health")

@app.api_route("/api/settings", methods=["GET", "PUT"])
async def proxy_settings(request: Request):
    return await _proxy(request, "/api/settings")

@app.api_route("/api/chat/settings", methods=["GET", "PUT"])
async def proxy_chat_settings(request: Request):
    return await _proxy(request, "/api/chat/settings")

@app.api_route("/api/chat", methods=["POST"])
async def proxy_chat(request: Request):
    return await _proxy(request, "/api/chat")

@app.api_route("/api/llm/models", methods=["GET"])
async def proxy_models(request: Request):
    return await _proxy(request, "/api/llm/models")


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def spa():
    html = STATIC_DIR / "index.html"
    if html.exists():
        return html.read_text("utf-8")
    return HTMLResponse(
        "<html><body style='background:#1a1a2e;color:#e94560;font-family:sans-serif;padding:40px'>"
        "<h1>NOTBot Admin</h1><p>Static files not found.</p></body></html>"
    )
