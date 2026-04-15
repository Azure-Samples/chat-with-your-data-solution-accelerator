"""Frontend server: serves the built React SPA and proxies /api calls to the backend.

In production, this is the entry point for the frontend App Service.
Locally, use the Vite dev server instead (npm run dev).
"""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "dist", "static")

app = FastAPI(title="CWYD Frontend Server")

_http_client: httpx.AsyncClient | None = None


async def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=BACKEND_URL,
            timeout=httpx.Timeout(60.0),
        )
    return _http_client


@app.on_event("shutdown")
async def _shutdown() -> None:
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_api(request: Request, path: str) -> StreamingResponse:
    """Forward all /api/* requests to the backend."""
    client = await _get_http_client()

    url = f"/api/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    body = await request.body()
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding")
    }

    response = await client.request(
        method=request.method,
        url=url,
        headers=headers,
        content=body,
    )

    return StreamingResponse(
        content=iter([response.content]),
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.headers.get("content-type"),
    )


# Serve static files if the build output exists
if os.path.isdir(STATIC_DIR):
    # Catch-all: serve index.html for SPA client-side routing
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static-assets")
