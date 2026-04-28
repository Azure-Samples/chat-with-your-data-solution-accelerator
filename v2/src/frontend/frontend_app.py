"""Production frontend ASGI app: serve Vite-built static assets.

Pillar: Stable Core
Phase: 1 (debt #Q3 — restores prod path referenced by Dockerfile.frontend)

Single-runtime container: FastAPI + StaticFiles (`html=True`) serves
`dist/` so SPA routes fall through to `index.html`. No nginx, no extra
proxy. The dev profile keeps using Vite's HMR server unchanged; this
module is only loaded by the `prod` stage of `docker/Dockerfile.frontend`.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# `DIST_DIR` env var lets tests point at a fixture without rebuilding.
# Default matches the path baked into Dockerfile.frontend prod stage.
_DIST_DIR = Path(os.environ.get("DIST_DIR", "/usr/src/app/dist"))

app = FastAPI(title="cwyd-frontend")
app.mount("/", StaticFiles(directory=_DIST_DIR, html=True), name="static")
