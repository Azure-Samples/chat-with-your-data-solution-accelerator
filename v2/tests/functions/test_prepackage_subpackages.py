"""Guard: the prepackage deploy artifact must stage every functions package.

Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

`infra/scripts/prepackage/prepackage_function.py` stages an explicit allow-list of
subpackages (`_FUNCTION_SUBPACKAGES`) into the Flex Consumption deploy
artifact -- listed explicitly rather than globbed so a stray dir never
ships. The failure mode of an explicit list is the inverse: a *new*
blueprint package added under `src/functions/` is silently dropped from
the artifact, so the deployed Function App is missing its handler while
`azd deploy` still reports success. This guard asserts the allow-list
equals the set of importable packages under `src/functions/`, so adding
a blueprint without wiring the deploy list fails here instead of in a
silently handler-less cloud deploy.
"""

import importlib.util
from pathlib import Path

_V2_ROOT = Path(__file__).resolve().parents[2]
_FUNCTIONS_SRC = _V2_ROOT / "src" / "functions"
_PREPACKAGE_SCRIPT = (
    _V2_ROOT / "infra" / "scripts" / "prepackage" / "prepackage_function.py"
)


def _load_function_subpackages() -> tuple[str, ...]:
    """Load `_FUNCTION_SUBPACKAGES` from the prepackage script by file path.

    The script lives under `v2/infra/scripts/prepackage/` (not on the test import path),
    and importing it is side-effect-free -- `main()` only runs under the
    `__main__` guard -- so loading the module to read the constant is safe.
    """
    spec = importlib.util.spec_from_file_location(
        "prepackage_function", _PREPACKAGE_SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._FUNCTION_SUBPACKAGES


def _src_function_packages() -> set[str]:
    """Every importable package directory directly under `src/functions/`."""
    return {
        child.name
        for child in _FUNCTIONS_SRC.iterdir()
        if child.is_dir()
        and child.name != "__pycache__"
        and (child / "__init__.py").is_file()
    }


def test_prepackage_allowlist_matches_src_function_packages() -> None:
    """Set equality catches both directions: a new blueprint package not
    added to the allow-list (the `blob_event` miss that shipped a
    handler-less Function App) AND a stale entry for a deleted package.
    """
    assert _src_function_packages() == set(_load_function_subpackages())
