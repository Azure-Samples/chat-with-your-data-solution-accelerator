"""Guard: the function service's prepackage hook is service-scoped (BUG-0058).

A project-level ``hooks.prepackage`` runs only on the ``package`` command, so a
targeted ``azd deploy function`` shipped a **stale** ``build-functions/``
artifact (the hook never fired, the old tree was zipped and deployed). The hook
must live under ``services.function.hooks.prepackage`` so it fires whenever the
function deployment package is created -- including ``azd deploy function`` --
per the azd schema (service-level ``prepackage`` "Runs before the service is
deployment package is created").
"""

from pathlib import Path

import yaml

_V2_ROOT = Path(__file__).resolve().parents[2]
_AZURE_YAML = _V2_ROOT / "azure.yaml"


def _load_azure_yaml() -> dict[str, object]:
    return yaml.safe_load(_AZURE_YAML.read_text(encoding="utf-8"))


def test_function_service_has_scoped_prepackage_hook() -> None:
    cfg = _load_azure_yaml()
    services = cfg["services"]
    function_hooks = services["function"].get("hooks", {})
    assert "prepackage" in function_hooks, (
        "services.function.hooks.prepackage must exist so `azd deploy function` "
        "regenerates build-functions/ (BUG-0058). A project-level prepackage "
        "hook does not run on a targeted per-service deploy."
    )
    prepackage = function_hooks["prepackage"]
    for platform in ("posix", "windows"):
        assert platform in prepackage, f"{platform} wrapper missing from prepackage hook"
        # The run path is relative to the service path (build-functions/), so
        # it climbs one level to v2/scripts/.
        run = prepackage[platform]["run"]
        assert "prepackage-function" in run, (
            f"{platform} prepackage hook must invoke the prepackage-function wrapper; got {run!r}"
        )
        assert run.startswith("../scripts/"), (
            f"{platform} prepackage run path must be service-relative (../scripts/...); got {run!r}"
        )


def test_no_project_level_prepackage_hook() -> None:
    cfg = _load_azure_yaml()
    project_hooks = cfg.get("hooks", {}) or {}
    assert "prepackage" not in project_hooks, (
        "The prepackage hook was moved to the function service (BUG-0058); a "
        "project-level hooks.prepackage does not fire on `azd deploy function` "
        "and re-introducing it risks shipping a stale build-functions/ artifact."
    )
