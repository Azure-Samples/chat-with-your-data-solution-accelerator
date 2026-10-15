"""Tests for the prod frontend ASGI app (debt #Q3)."""

import importlib
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def _load_app(dist_dir: Path):
    """(Re)import the module with DIST_DIR pointed at a fixture."""
    os.environ["DIST_DIR"] = str(dist_dir)
    # Make src/frontend importable as a top-level module.
    frontend_src = Path(__file__).resolve().parents[2] / "src" / "frontend"
    sys.path.insert(0, str(frontend_src))
    sys.modules.pop("frontend_app", None)
    try:
        return importlib.import_module("frontend_app")
    finally:
        sys.path.remove(str(frontend_src))


def test_default_dist_dir_is_module_relative(tmp_path: Path) -> None:
    """With DIST_DIR unset the default resolves next to the module file.

    App Service deploys the server + `dist/` together under the app root
    (`/home/site/wwwroot`); the Docker prod stage co-locates them under
    `/usr/src/app`. A module-relative default serves both unchanged.
    """
    os.environ.pop("DIST_DIR", None)
    frontend_src = Path(__file__).resolve().parents[2] / "src" / "frontend"
    sys.path.insert(0, str(frontend_src))
    sys.modules.pop("frontend_app", None)
    try:
        module = importlib.import_module("frontend_app")
    finally:
        sys.path.remove(str(frontend_src))

    expected = (Path(module.__file__).resolve().parent / "dist").resolve()
    assert module._DIST_DIR.resolve() == expected


def test_serves_index_html_at_root(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html><body>cwyd v2</body></html>")
    module = _load_app(tmp_path)
    client = TestClient(module.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "cwyd v2" in response.text


def test_serves_static_asset(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html></html>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('hi');")
    module = _load_app(tmp_path)
    client = TestClient(module.app)

    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert "console.log" in response.text


def test_serves_index_html_for_spa_deep_link(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html><body>cwyd v2 spa</body></html>")
    module = _load_app(tmp_path)
    client = TestClient(module.app)

    response = client.get("/admin/ingest")

    assert response.status_code == 200
    assert "cwyd v2 spa" in response.text


def test_unknown_nested_route_falls_back_to_index(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html><body>fallback</body></html>")
    (tmp_path / "assets").mkdir()
    module = _load_app(tmp_path)
    client = TestClient(module.app)

    response = client.get("/assets/does-not-exist.js")

    assert response.status_code == 200
    assert "fallback" in response.text


def test_config_returns_backend_url_from_env(tmp_path: Path) -> None:
    """GET /config echoes BACKEND_API_URL as the `backendUrl` wire key."""
    (tmp_path / "index.html").write_text("<html></html>")
    os.environ["BACKEND_API_URL"] = "https://backend.example.com"
    try:
        module = _load_app(tmp_path)
        client = TestClient(module.app)
        response = client.get("/config")
    finally:
        os.environ.pop("BACKEND_API_URL", None)

    assert response.status_code == 200
    assert response.json() == {
        "backendUrl": "https://backend.example.com",
        "authClientId": "",
        "authAuthority": "",
        "authApiScope": "",
    }


def test_config_defaults_to_empty_when_env_unset(tmp_path: Path) -> None:
    """With BACKEND_API_URL unset, /config returns an empty backendUrl."""
    (tmp_path / "index.html").write_text("<html></html>")
    os.environ.pop("BACKEND_API_URL", None)
    module = _load_app(tmp_path)
    client = TestClient(module.app)

    response = client.get("/config")

    assert response.status_code == 200
    assert response.json() == {
        "backendUrl": "",
        "authClientId": "",
        "authAuthority": "",
        "authApiScope": "",
    }


def test_config_route_takes_precedence_over_spa_catch_all(tmp_path: Path) -> None:
    """A `config` file in dist/ must not shadow the JSON /config route."""
    (tmp_path / "index.html").write_text("<html></html>")
    (tmp_path / "config").write_text("static file that must not win")
    os.environ.pop("BACKEND_API_URL", None)
    module = _load_app(tmp_path)
    client = TestClient(module.app)

    response = client.get("/config")

    assert response.status_code == 200
    assert response.json() == {
        "backendUrl": "",
        "authClientId": "",
        "authAuthority": "",
        "authApiScope": "",
    }


def test_config_returns_auth_fields_from_env(tmp_path: Path) -> None:
    """GET /config surfaces the MSAL client id, authority, and API scope.

    The SPA runs a browser-side PKCE flow, so it needs the app
    registration client id, the tenant authority, and the backend API
    scope at runtime -- all env-specific, hence served from /config
    rather than baked into the bundle.
    """
    (tmp_path / "index.html").write_text("<html></html>")
    os.environ["AZURE_AUTH_CLIENT_ID"] = "11111111-1111-1111-1111-111111111111"
    os.environ["AZURE_TENANT_ID"] = "22222222-2222-2222-2222-222222222222"
    os.environ["AZURE_AUTH_API_SCOPE"] = (
        "api://11111111-1111-1111-1111-111111111111/user_impersonation"
    )
    try:
        module = _load_app(tmp_path)
        client = TestClient(module.app)
        response = client.get("/config")
    finally:
        os.environ.pop("AZURE_AUTH_CLIENT_ID", None)
        os.environ.pop("AZURE_TENANT_ID", None)
        os.environ.pop("AZURE_AUTH_API_SCOPE", None)

    assert response.status_code == 200
    body = response.json()
    assert body["authClientId"] == "11111111-1111-1111-1111-111111111111"
    assert body["authAuthority"] == (
        "https://login.microsoftonline.com/" "22222222-2222-2222-2222-222222222222"
    )
    assert body["authApiScope"] == (
        "api://11111111-1111-1111-1111-111111111111/user_impersonation"
    )
