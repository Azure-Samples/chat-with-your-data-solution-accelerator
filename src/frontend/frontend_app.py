"""Production frontend ASGI app: serve the Vite-built SPA.

Single-runtime container: FastAPI serves the contents of `dist/`. A
catch-all route returns the requested file when it exists on disk and
falls back to `index.html` for every other path, so client-side
BrowserRouter deep links (for example `/admin/ingest`) and hard
refreshes resolve to the SPA entry point instead of a 404. No nginx,
no extra proxy. It also exposes `GET /config`, which returns the
backend base URL from the `BACKEND_API_URL` environment variable so the
SPA learns the backend at runtime instead of baking it into the bundle.
The dev profile keeps using Vite's HMR server unchanged; in production
the App Service runs this module via uvicorn (see the `appCommandLine`
on the frontend site in `infra/main.bicep`).
"""

import base64
import json
import os
from pathlib import Path

from fastapi import FastAPI, Header
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

# `DIST_DIR` env var lets tests point at a fixture without rebuilding.
# Default resolves next to this module so it serves unchanged on App
# Service (server + `dist/` co-located under the app root) and in the
# Docker prod stage (both under `/usr/src/app`).
_DIST_DIR = Path(
    os.environ.get("DIST_DIR", str(Path(__file__).resolve().parent / "dist"))
)

app = FastAPI(title="cwyd-frontend")


class FrontendConfig(BaseModel):
    """Runtime config the SPA fetches once at boot from `GET /config`.

    `backend_url` is the backend base URL (empty string when unset, as
    in local dev), serialized to the wire as `backendUrl`. Serving it
    from a runtime endpoint instead of a build-time constant means the
    same built bundle works against any backend.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    backend_url: str = Field(default="", serialization_alias="backendUrl")


@app.get("/config")
def get_config() -> FrontendConfig:
    """Return the backend base URL from the `BACKEND_API_URL` env var."""
    return FrontendConfig(backend_url=os.environ.get("BACKEND_API_URL", ""))


@app.get("/.auth/me")
def auth_me(
    principal: str = Header(default="", alias="x-ms-client-principal"),
    principal_id: str = Header(default="", alias="x-ms-client-principal-id"),
    principal_name: str = Header(default="", alias="x-ms-client-principal-name"),
) -> JSONResponse:
    """Serve the Easy Auth /.auth/me claims payload.

    Container Apps Easy Auth injects ``X-MS-CLIENT-PRINCIPAL`` (base64-
    encoded JSON with the full claim set), ``X-MS-CLIENT-PRINCIPAL-ID``
    (user object id or UPN), and ``X-MS-CLIENT-PRINCIPAL-NAME`` into every
    request from an authenticated user.  For unauthenticated requests Easy
    Auth blocks the call before it reaches this handler (``RedirectToLoginPage``
    mode).  We decode those headers and return the same array shape that App
    Service Easy Auth produces, so the SPA's ``getUserInfo()`` works without
    any browser-side changes.
    """
    if not principal:
        return JSONResponse(content=[])
    try:
        # base64 padding may be stripped -- add == to be safe.
        decoded = json.loads(
            base64.b64decode(principal + "==").decode("utf-8", errors="replace")
        )
        claims: list[dict[str, str]] = decoded.get("claims", [])
        provider_name: str = decoded.get("auth_typ", "aad")
    except Exception:
        return JSONResponse(content=[])
    return JSONResponse(
        content=[
            {
                "user_id": principal_id or principal_name,
                "user_claims": claims,
                "provider_name": provider_name,
            }
        ]
    )


@app.get("/{full_path:path}")
def serve_spa(full_path: str) -> FileResponse:
    """Serve a built file when it exists, else the SPA `index.html`.

    The on-disk file is returned only when the resolved candidate stays
    inside `dist/` (guards against `..` path traversal); every other
    request (unknown client routes, deep links, refreshes) resolves
    to `index.html` so the browser-side router can take over.

    Cache-control policy:
    - ``index.html``: ``no-store`` so the browser always re-fetches it,
      ensuring a new deployment is picked up immediately.
    - Hashed assets (``/assets/*``): ``max-age=31536000, immutable``
      so long-lived cache hits are safe (Vite embeds a content hash in
      every asset filename).
    """
    dist_root = _DIST_DIR.resolve()
    normalized_path = os.path.normpath(full_path).lstrip("/\\")
    if (
        normalized_path in ("", ".")
        or normalized_path.startswith("../")
        or normalized_path.startswith("..\\")
    ):
        return FileResponse(
            dist_root / "index.html",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )
    candidate = (dist_root / normalized_path).resolve()
    if candidate.is_file() and candidate.is_relative_to(dist_root):
        # Vite hashes asset filenames — safe to cache for a year.
        cache = (
            "public, max-age=31536000, immutable"
            if normalized_path.startswith("assets/")
            else "no-store, no-cache, must-revalidate"
        )
        return FileResponse(candidate, headers={"Cache-Control": cache})
    return FileResponse(
        dist_root / "index.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )
