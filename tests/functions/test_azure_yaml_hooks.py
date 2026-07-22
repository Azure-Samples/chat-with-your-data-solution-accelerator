"""Guard: the function service deploys as a container image (Functions-on-ACA).

The function ships as a Docker image built + pushed to the shared ACR (like the
backend and frontend), so azure.yaml pins ``host: containerapp`` with a
``docker:`` block pointing at ``Dockerfile.functions``. The Dockerfile
reproduces the Functions deploy layout, so no packaging/staging hook is present
at either the service or project level.
"""

from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AZURE_YAML = _REPO_ROOT / "azure.yaml"


def _load_azure_yaml() -> dict[str, object]:
    return yaml.safe_load(_AZURE_YAML.read_text(encoding="utf-8"))


def test_no_project_level_prepackage_hook() -> None:
    cfg = _load_azure_yaml()
    project_hooks = cfg.get("hooks", {}) or {}
    assert "prepackage" not in project_hooks, (
        "The function image is built by azd from Dockerfile.functions; a "
        "project-level staging hook is not part of the container deploy."
    )
