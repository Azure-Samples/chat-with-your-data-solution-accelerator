"""Production frontend ASGI app: serve the Vite-built SPA.

Pillar: Stable Core
Phase: 1

FastAPI serves the contents of ``dist/``. When ``VITE_BACKEND_URL`` is
set (container deployment), ``/api/*`` requests are proxied to the
backend. When unset (code deployment where the backend handles ``/api``
directly), those paths return 404.
"""

import base64
import json
import os
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

_DIST_DIR = Path(os.environ.get("DIST_DIR", "/usr/src/app/dist"))
_BACKEND_URL = os.environ.get("VITE_BACKEND_URL", "").rstrip("/")

app = FastAPI(title="cwyd-frontend")


# ---- Easy Auth user-info endpoint ------------------------------------
# Container Apps Easy Auth injects x-ms-client-principal on every request
# but may not serve /.auth/me as a token-store endpoint. This route reads
# the sidecar-injected header and returns the claims in the format the
# SPA expects (Container Apps clientPrincipal shape).
@app.get("/.auth/me", response_model=None)
async def auth_me(request: Request) -> Response:
    raw = request.headers.get("x-ms-client-principal", "")
    if not raw:
        return JSONResponse(content={"clientPrincipal": None})
    try:
        decoded = base64.b64decode(raw)
        principal = json.loads(decoded)
    except Exception:
        return JSONResponse(content={"clientPrincipal": None})
    return JSONResponse(content={"clientPrincipal": principal})


# ---- API proxy (container deployment only) ----------------------------
if _BACKEND_URL:
    import httpx  # noqa: E402

    _client = httpx.AsyncClient(base_url=_BACKEND_URL, timeout=120.0)

    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        response_model=None,
    )
    async def proxy_api(request: Request, path: str) -> Response:
        url = f"/api/{path}"
        if request.url.query:
            url = f"{url}?{request.url.query}"
        headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
        # Use streaming for SSE responses so events arrive incrementally.
        req = _client.build_request(
            method=request.method,
            url=url,
            headers=headers,
            content=await request.body(),
        )
        resp = await _client.send(req, stream=True)
        content_type = resp.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return StreamingResponse(
                content=resp.aiter_bytes(),
                status_code=resp.status_code,
                media_type=content_type,
            )
        # Non-streaming responses: read fully and return.
        body = await resp.aread()
        await resp.aclose()
        return Response(
            content=body,
            status_code=resp.status_code,
            media_type=content_type or None,
        )


# ---- SPA static file server ------------------------------------------
@app.get("/{full_path:path}", response_model=None)
def serve_spa(full_path: str) -> FileResponse | Response:
    """Serve a built file when it exists, else the SPA ``index.html``.

    Paths under ``api/`` are never served as ``index.html`` -- they must
    be handled by the proxy above or by a co-hosted backend.
    """
    dist_root = _DIST_DIR.resolve()
    candidate = (dist_root / full_path).resolve()
    if full_path and candidate.is_file() and candidate.is_relative_to(dist_root):
        return FileResponse(candidate)
    if full_path.startswith("api/"):
        return Response(status_code=404)
    return FileResponse(dist_root / "index.html")
