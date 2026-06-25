"""Production frontend ASGI app: serve the Vite-built SPA.

Pillar: Stable Core
Phase: 1

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
on the frontend site in `v2/infra/main.bicep`).
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

# `DIST_DIR` env var lets tests point at a fixture without rebuilding.
# Default resolves next to this module so it serves unchanged on App
# Service (server + `dist/` co-located under the app root) and in the
# Docker prod stage (both under `/usr/src/app`).
_DIST_DIR = Path(os.environ.get("DIST_DIR", str(Path(__file__).resolve().parent / "dist")))

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


@app.get("/{full_path:path}")
def serve_spa(full_path: str) -> FileResponse:
    """Serve a built file when it exists, else the SPA `index.html`.

    The on-disk file is returned only when the resolved candidate stays
    inside `dist/` (guards against `..` path traversal); every other
    request — unknown client routes, deep links, refreshes — resolves
    to `index.html` so the browser-side router can take over.
    """
    dist_root = _DIST_DIR.resolve()
    candidate = (dist_root / full_path).resolve()
    if full_path and candidate.is_file() and candidate.is_relative_to(dist_root):
        return FileResponse(candidate)
    return FileResponse(dist_root / "index.html")
