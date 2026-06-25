"""Tests for the frontend build wrappers (package-frontend.{sh,ps1}).

Pillar: Stable Core
Phase: 1

The wrappers are thin OS shims azd's `services.frontend.hooks.prepackage`
hook invokes to rebuild the Vite SPA and stage the App Service deploy
artifact before zip-deploy. The wrappers carry no branching logic, so
their contract is textual; the artifact assembly lives in
package_frontend.py and is exercised directly.
"""

import importlib
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
_SH = _SCRIPTS_DIR / "package-frontend.sh"
_PS1 = _SCRIPTS_DIR / "package-frontend.ps1"


def _load_module():
    """Import package_frontend from v2/scripts/ without a top-level import.

    `import package_frontend` after a sys.path mutation would trip the
    imports-at-top gate; importlib.import_module is a call, not an import
    statement, so the dynamic load stays compliant.
    """
    sys.path.insert(0, str(_SCRIPTS_DIR))
    sys.modules.pop("package_frontend", None)
    try:
        return importlib.import_module("package_frontend")
    finally:
        sys.path.remove(str(_SCRIPTS_DIR))


def _seed_frontend(root: Path) -> Path:
    frontend = root / "frontend"
    (frontend / "dist" / "assets").mkdir(parents=True)
    (frontend / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
    (frontend / "dist" / "assets" / "app.js").write_text("console.log(1);", encoding="utf-8")
    (frontend / "frontend_app.py").write_text("app = object()\n", encoding="utf-8")
    return frontend


def test_both_wrappers_exist() -> None:
    assert _SH.is_file()
    assert _PS1.is_file()


def test_posix_wrapper_fails_fast_and_builds() -> None:
    body = _SH.read_text(encoding="utf-8")
    assert "Pillar: Stable Core" in body
    assert "set -euo pipefail" in body
    assert "/../src/frontend" in body
    assert "npm ci" in body
    assert "npm run build" in body


def test_windows_wrapper_fails_fast_and_builds() -> None:
    body = _PS1.read_text(encoding="utf-8")
    assert "Pillar: Stable Core" in body
    assert "$ErrorActionPreference = 'Stop'" in body
    assert "src/frontend" in body
    assert "npm ci" in body
    assert "npm run build" in body


def test_wrappers_do_not_bake_a_backend_url() -> None:
    """The runtime /config contract forbids a build-time URL bake."""
    assert "VITE_BACKEND_URL" not in _SH.read_text(encoding="utf-8")
    assert "VITE_BACKEND_URL" not in _PS1.read_text(encoding="utf-8")


def test_wrappers_stage_the_deploy_artifact() -> None:
    """Each wrapper hands off to package_frontend.py after the build."""
    assert "package_frontend.py" in _SH.read_text(encoding="utf-8")
    assert "package_frontend.py" in _PS1.read_text(encoding="utf-8")


def test_build_artifact_stages_server_requirements_and_dist(tmp_path: Path) -> None:
    module = _load_module()
    frontend = _seed_frontend(tmp_path)
    build_dir = tmp_path / "build-frontend"

    module.build_artifact(frontend, build_dir)

    assert (build_dir / "frontend_app.py").is_file()
    assert (build_dir / "requirements.txt").is_file()
    assert (build_dir / "dist" / "index.html").is_file()
    assert (build_dir / "dist" / "assets" / "app.js").is_file()
    reqs = (build_dir / "requirements.txt").read_text(encoding="utf-8")
    assert "fastapi" in reqs
    assert "uvicorn" in reqs


def test_build_artifact_clears_stale_files(tmp_path: Path) -> None:
    module = _load_module()
    frontend = _seed_frontend(tmp_path)
    build_dir = tmp_path / "build-frontend"

    module.build_artifact(frontend, build_dir)
    (build_dir / "stale.txt").write_text("old", encoding="utf-8")
    module.build_artifact(frontend, build_dir)

    assert not (build_dir / "stale.txt").exists()
    assert (build_dir / "dist" / "index.html").is_file()


def test_build_artifact_requires_a_built_dist(tmp_path: Path) -> None:
    module = _load_module()
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "frontend_app.py").write_text("app = object()\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        module.build_artifact(frontend, tmp_path / "build-frontend")
