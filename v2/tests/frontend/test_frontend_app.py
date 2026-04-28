"""Tests for the prod frontend ASGI app (debt #Q3).

Pillar: Stable Core
Phase: 1
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def _load_app(dist_dir: Path):
    """(Re)import the module with DIST_DIR pointed at a fixture."""
    import os

    os.environ["DIST_DIR"] = str(dist_dir)
    # Make v2/src/frontend importable as a top-level module.
    frontend_src = Path(__file__).resolve().parents[2] / "src" / "frontend"
    sys.path.insert(0, str(frontend_src))
    sys.modules.pop("frontend_app", None)
    try:
        return importlib.import_module("frontend_app")
    finally:
        sys.path.remove(str(frontend_src))


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
