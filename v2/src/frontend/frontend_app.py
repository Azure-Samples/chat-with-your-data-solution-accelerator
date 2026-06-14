"""Production frontend ASGI app: serve the Vite-built SPA.

Pillar: Stable Core
Phase: 1

Single-runtime container: FastAPI serves the contents of `dist/`. A
catch-all route returns the requested file when it exists on disk and
falls back to `index.html` for every other path, so client-side
BrowserRouter deep links (for example `/admin/ingest`) and hard
refreshes resolve to the SPA entry point instead of a 404. No nginx,
no extra proxy. The dev profile keeps using Vite's HMR server
unchanged; this module is only loaded by the `prod` stage of
`docker/Dockerfile.frontend`.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

# `DIST_DIR` env var lets tests point at a fixture without rebuilding.
# Default matches the path baked into Dockerfile.frontend prod stage.
_DIST_DIR = Path(os.environ.get("DIST_DIR", "/usr/src/app/dist"))

app = FastAPI(title="cwyd-frontend")


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
