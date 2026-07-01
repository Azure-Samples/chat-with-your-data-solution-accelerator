"""Guard: the function service deploys as a container image (Functions-on-ACA).

Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

The function ships as a Docker image built + pushed to the shared ACR (like the
backend and frontend), so azure.yaml pins ``host: containerapp`` with a
``docker:`` block pointing at ``Dockerfile.functions``. The Dockerfile
reproduces the Functions deploy layout, so no packaging/staging hook is present
at either the service or project level.
"""

from pathlib import Path

import yaml

_V2_ROOT = Path(__file__).resolve().parents[2]
_AZURE_YAML = _V2_ROOT / "azure.yaml"


def _load_azure_yaml() -> dict[str, object]:
    return yaml.safe_load(_AZURE_YAML.read_text(encoding="utf-8"))


def test_function_service_is_container_app() -> None:
    cfg = _load_azure_yaml()
    function = cfg["services"]["function"]
    assert function["host"] == "containerapp", (
        "The function must deploy as a container image on Container Apps "
        f"(host: containerapp); got host={function.get('host')!r}."
    )
    docker = function.get("docker", {})
    assert str(docker.get("path", "")).endswith("docker/Dockerfile.functions"), (
        "services.function.docker.path must point at Dockerfile.functions; "
        f"got {docker.get('path')!r}."
    )
    assert docker.get("context") == "../..", (
        "services.function.docker.context must be the v2 root (../..) so the "
        f"Dockerfile can COPY src/functions + src/backend; got {docker.get('context')!r}."
    )


def test_function_service_has_no_packaging_hook() -> None:
    cfg = _load_azure_yaml()
    function_hooks = cfg["services"]["function"].get("hooks", {}) or {}
    assert "prepackage" not in function_hooks, (
        "The function image is self-contained (Dockerfile.functions reproduces "
        "the deploy layout), so no service-level staging hook is needed."
    )


def test_no_project_level_prepackage_hook() -> None:
    cfg = _load_azure_yaml()
    project_hooks = cfg.get("hooks", {}) or {}
    assert "prepackage" not in project_hooks, (
        "The function image is built by azd from Dockerfile.functions; a "
        "project-level staging hook is not part of the container deploy."
    )
