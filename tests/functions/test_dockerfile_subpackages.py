"""Guard: the function image stages every functions package.

Dockerfile.functions copies an explicit list of blueprint subpackages into the
deploy layout (``COPY src/functions/<sub> ./functions/<sub>``) -- listed
explicitly rather than globbed so a stray dir never ships. The inverse failure
mode is a *new* blueprint package added under ``src/functions/`` that is
silently dropped from the image, leaving the deployed function missing its
handler while ``azd deploy`` still reports success. This guard asserts the
Dockerfile's COPY list equals the set of importable packages under
``src/functions/``, so adding a blueprint without wiring the image fails here
instead of in a silently handler-less cloud deploy.
"""

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FUNCTIONS_SRC = _REPO_ROOT / "src" / "functions"
_DOCKERFILE = _REPO_ROOT / "docker" / "Dockerfile.functions"

# Matches `COPY src/functions/<name> ./functions/<name>`; the backreference
# guarantees the source package and its deploy-layout destination agree.
_COPY_SUBPACKAGE = re.compile(
    r"^COPY\s+src/functions/(?P<name>\w+)\s+\./functions/(?P=name)\s*$",
    re.MULTILINE,
)


def _dockerfile_subpackages() -> set[str]:
    return set(_COPY_SUBPACKAGE.findall(_DOCKERFILE.read_text(encoding="utf-8")))


def _src_function_packages() -> set[str]:
    """Every importable package directory directly under `src/functions/`."""
    return {
        child.name
        for child in _FUNCTIONS_SRC.iterdir()
        if child.is_dir()
        and child.name != "__pycache__"
        and (child / "__init__.py").is_file()
    }


def test_dockerfile_stages_every_function_package() -> None:
    """Set equality catches both directions: a new blueprint package not copied
    into the image AND a stale COPY for a deleted package.
    """
    assert _src_function_packages() == _dockerfile_subpackages()
