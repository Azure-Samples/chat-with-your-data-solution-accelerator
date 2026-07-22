"""AST invariant: no `from shared.` or `import shared` imports in v2/.

Per `v2/docs/development_plan.md` §0.1 REFACTOR-B + `/memories/session/plan.md`
Phase B: the legacy `shared/` package has been moved to `src/backend/core/`.
Backend is now standalone; functions opt-in extension layer for ingestion.
The legacy import surface (`from shared.` / `import shared`) is therefore
banned everywhere under `v2/`.

This test walks every `*.py` under `{src,tests,scripts}` and asserts:

1. No `from shared.X import Y` statement.
2. No `from shared import Y` statement.
3. No `import shared` (or `import shared.X` / `import shared as S`).

Phase 5.5 lifecycle:

- B1: land the test marked `@pytest.mark.xfail(strict=False)` so the
  existing ~155 violation surface stays *visible* (xfailed, not green) but
  does not break the suite during the sweep.
- B2: `git mv src/shared src/backend/core` + `git mv tests/shared
  tests/backend/core` + create empty `src/functions/core/__init__.py`.
- B3: mechanical import sweep across all `*.py` (`from shared.` ->
  `from backend.core.`, etc.).
- B4: config + docs sweep (pyproject pyright/hatch, docker-compose mounts,
  Dockerfile.functions, .env.sample, agents.md, env-vars.md, ADR 0008,
  copilot-instructions, instruction file rename, memory).
- B5 (this revision): `xfail` decorator removed -- future re-introduction
  of `from shared.` anywhere in `{src,tests,scripts}` goes red
  immediately.

If a future PR introduces `from shared.` somewhere, the failure points at
the offending file with a clear remediation message (use `backend.core`
instead).
"""

import ast
from pathlib import Path

import pytest

# Repo root resolves from this file: tests/shared/test_*.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Subtrees under v2/ that get scanned. Anything else (e.g. .venv, build
# artefacts) is implicitly excluded by not being listed here.
_SCAN_ROOTS = ("src", "tests", "scripts")

# Per-file exemption list. Empty by design -- the rule has no exceptions.
# This test file itself contains the literal string "from shared." in its
# docstring + error messages, but the AST walker only inspects import
# nodes, so no exemption is needed.
_EXEMPTIONS: frozenset[Path] = frozenset()


def _iter_v2_python_files() -> list[Path]:
    """Return every `*.py` under the scan roots, sorted for stable output."""
    files: list[Path] = []
    for root in _SCAN_ROOTS:
        root_dir = _REPO_ROOT / root
        if not root_dir.is_dir():
            continue
        for path in root_dir.rglob("*.py"):
            parts = set(path.parts)
            if (
                "__pycache__" in parts
                or ".venv" in parts
                or "build" in parts
                or "node_modules" in parts
            ):
                continue
            files.append(path)
    return sorted(files)


def _has_legacy_shared_import(tree: ast.Module) -> tuple[bool, str | None]:
    """Return (has_violation, offending_form) for legacy `shared.` imports.

    Catches three forms:

    - `from shared import X`         -> ImportFrom, module == "shared"
    - `from shared.sub import X`     -> ImportFrom, module starts with "shared."
    - `import shared` / `import shared.sub` / `import shared as s`
                                     -> Import, alias.name == "shared" or
                                        starts with "shared."
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "shared" or mod.startswith("shared."):
                return True, f"from {mod} import ..."
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "shared" or alias.name.startswith("shared."):
                    return True, f"import {alias.name}"
    return False, None


# Collect once; pytest will parametrise so each file shows as its own
# test case in failure output (instead of a single mega-failure).
_ALL_FILES = _iter_v2_python_files()


@pytest.mark.parametrize(
    "py_file",
    _ALL_FILES,
    ids=lambda p: str(p.relative_to(_REPO_ROOT)),
)
def test_no_legacy_shared_imports(py_file: Path) -> None:
    if py_file in _EXEMPTIONS:
        pytest.skip(f"explicitly exempted: {py_file.relative_to(_REPO_ROOT)}")

    source = py_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(py_file))

    has_violation, form = _has_legacy_shared_import(tree)
    if has_violation:
        rel = py_file.relative_to(_REPO_ROOT)
        pytest.fail(
            f"{rel}: legacy `{form}` is banned in v2/ (REFACTOR-B, "
            f"Phase 5.5). The `shared/` package was moved to "
            f"`src/backend/core/`. Replace `from shared.X import Y` "
            f"with `from backend.core.X import Y`. If this file is in "
            f"`src/functions/core/`, it must extend a `backend.core` "
            f"library (subclass / extension module), never re-define it."
        )


def test_legacy_shared_scan_walked_files() -> None:
    """Sanity guard: the parametrise input must not be empty.

    If the path resolution above ever silently misses every file (e.g.
    because the test runs from an unexpected cwd in CI), the
    parametrised test would generate zero cases and quietly pass.
    """
    assert _ALL_FILES, "no Python files discovered under {src,tests,scripts}"
    rel_parts = {p.relative_to(_REPO_ROOT).parts[0] for p in _ALL_FILES}
    assert (
        "src" in rel_parts
    ), "no files found under src/ -- path resolution likely broken"
    assert (
        "tests" in rel_parts
    ), "no files found under tests/ -- path resolution likely broken"
