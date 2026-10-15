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

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
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

    The `auth_*` fields carry the browser-side MSAL (PKCE) parameters:
    the app registration client id, the tenant authority URL, and the
    backend API scope the SPA requests an access token for. All are
    env-specific, so they are served at runtime rather than baked into
    the bundle, and all default to empty on a local dev stack with no
    identity provider.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    backend_url: str = Field(default="", serialization_alias="backendUrl")
    auth_client_id: str = Field(default="", serialization_alias="authClientId")
    auth_authority: str = Field(default="", serialization_alias="authAuthority")
    auth_api_scope: str = Field(default="", serialization_alias="authApiScope")


@app.get("/config")
def get_config() -> FrontendConfig:
    """Return the backend URL and browser-side MSAL parameters from env."""
    tenant_id = os.environ.get("AZURE_TENANT_ID", "")
    authority = f"https://login.microsoftonline.com/{tenant_id}" if tenant_id else ""
    return FrontendConfig(
        backend_url=os.environ.get("BACKEND_API_URL", ""),
        auth_client_id=os.environ.get("AZURE_AUTH_CLIENT_ID", ""),
        auth_authority=authority,
        auth_api_scope=os.environ.get("AZURE_AUTH_API_SCOPE", ""),
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
