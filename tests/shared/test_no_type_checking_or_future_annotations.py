"""AST invariant: no `if TYPE_CHECKING:` and no `from __future__ import annotations` in v2/.

Per `.github/copilot-instructions.md` Hard Rule #11 (Python bullet, CU-013
amendment 2026-05-05): types in v2/ are always available at runtime. The
`if TYPE_CHECKING:` guard and `from __future__ import annotations` (PEP 563)
are banned everywhere under `v2/` (source, tests, scripts, functions).

This test walks every `*.py` under `v2/` (excluding `.venv/` and any
`__pycache__/`) and asserts:

1. No `from __future__ import annotations` statement.
2. No `if TYPE_CHECKING:` block (matches both `if TYPE_CHECKING:` and the
   fully-qualified `if typing.TYPE_CHECKING:`).
3. No bare `TYPE_CHECKING` symbol imported from `typing` (catches dead
   imports that linger after the guard block is deleted).

Rationale: lazy / quoted annotations created two recurring failure modes
during cleanup audit batch 2 -- (a) silent drift where the runtime symbol
disappeared but the string annotation kept type-checking green; (b)
Pydantic v2 + LangGraph wiring that introspects `__annotations__` at
runtime and crashed on unresolved forward refs.

If a genuine circular import surfaces, fix it by extracting the shared
type to a leaf module (e.g. `src/shared/types.py` or a new
`src/shared/contracts/` package) -- never reach for the guard.
Such an extraction is a structural change and triggers Hard Rule #10
(ask the user first).
"""

import ast
from pathlib import Path

import pytest

# Repo root resolves from this file: tests/shared/test_*.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Subtrees under v2/ that get scanned. Anything else (e.g. .venv, build
# artefacts) is implicitly excluded by not being listed here.
_SCAN_ROOTS = ("src", "tests", "scripts")

# Per-file exemption list. Empty by design -- the rule has no exceptions
# (Hard Rule #11 + user decision 2026-05-05). If you think you need to
# add an entry here, you don't: extract the shared type to a leaf module
# instead. Kept as a list so the test failure message can point at it
# unambiguously.
_EXEMPTIONS: frozenset[Path] = frozenset()


def _iter_v2_python_files() -> list[Path]:
    """Return every `*.py` under the scan roots, sorted for stable output."""
    files: list[Path] = []
    for root in _SCAN_ROOTS:
        root_dir = _REPO_ROOT / root
        if not root_dir.is_dir():
            continue
        for path in root_dir.rglob("*.py"):
            # Skip any cached / venv / build output that may have been
            # dropped under one of the scan roots.
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


def _has_future_annotations_import(tree: ast.Module) -> bool:
    """True if the module contains `from __future__ import annotations`."""
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            for alias in node.names:
                if alias.name == "annotations":
                    return True
    return False


def _has_type_checking_block(tree: ast.Module) -> bool:
    """True if the module body contains `if TYPE_CHECKING:` (any qualifier)."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        # Bare `if TYPE_CHECKING:`
        if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
            return True
        # Fully-qualified `if typing.TYPE_CHECKING:`
        if (
            isinstance(test, ast.Attribute)
            and test.attr == "TYPE_CHECKING"
            and isinstance(test.value, ast.Name)
            and test.value.id == "typing"
        ):
            return True
    return False


def _imports_type_checking_symbol(tree: ast.Module) -> bool:
    """True if the module imports `TYPE_CHECKING` from `typing`.

    Catches dead imports that linger after the guard block is deleted
    (the guard test alone would miss `from typing import TYPE_CHECKING`
    on a line by itself with no `if` block beneath).
    """
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            for alias in node.names:
                if alias.name == "TYPE_CHECKING":
                    return True
    return False


# Collect once; pytest will parametrise so each file shows as its own
# test case in failure output (instead of a single mega-failure).
_ALL_FILES = _iter_v2_python_files()


@pytest.mark.parametrize(
    "py_file",
    _ALL_FILES,
    ids=lambda p: str(p.relative_to(_REPO_ROOT)),
)
def test_no_future_annotations_or_type_checking(py_file: Path) -> None:
    if py_file in _EXEMPTIONS:
        pytest.skip(f"explicitly exempted: {py_file.relative_to(_REPO_ROOT)}")

    source = py_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(py_file))

    rel = py_file.relative_to(_REPO_ROOT)

    if _has_future_annotations_import(tree):
        pytest.fail(
            f"{rel}: `from __future__ import annotations` is banned in v2/ "
            f"(Hard Rule #11, CU-013). Annotations must resolve to real "
            f"runtime symbols at class-definition time. Remove the import "
            f"and fix any forward refs by importing the type for real or "
            f"using `typing.Self` for self-references."
        )

    if _has_type_checking_block(tree):
        pytest.fail(
            f"{rel}: `if TYPE_CHECKING:` is banned in v2/ (Hard Rule #11, "
            f"CU-013). Hoist the guarded imports into the regular import "
            f"block. If a circular import surfaces, extract the shared "
            f"type to a leaf module (e.g. `src/shared/types.py`) -- "
            f"that is a structural change and triggers Hard Rule #10 "
            f"(ask the user first)."
        )

    if _imports_type_checking_symbol(tree):
        pytest.fail(
            f"{rel}: `from typing import TYPE_CHECKING` is banned in v2/ "
            f"(Hard Rule #11, CU-013). Remove the import."
        )


def test_scan_actually_walked_files() -> None:
    """Sanity guard: the parametrise input must not be empty.

    If the path resolution above ever silently misses every file (e.g.
    because the test runs from an unexpected cwd in CI), the
    parametrised test would generate zero cases and quietly pass. This
    asserts at least the major source roots are visible.
    """
    assert _ALL_FILES, "no Python files discovered under {src,tests,scripts}"
    rel_parts = {p.relative_to(_REPO_ROOT).parts[0] for p in _ALL_FILES}
    assert (
        "src" in rel_parts
    ), "no files found under src/ -- path resolution likely broken"
    assert (
        "tests" in rel_parts
    ), "no files found under tests/ -- path resolution likely broken"
