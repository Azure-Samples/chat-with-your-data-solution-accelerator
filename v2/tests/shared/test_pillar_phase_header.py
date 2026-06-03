"""AST invariant: every `*.py` under `v2/src/` carries a `Pillar:` / `Phase:` docstring header.

Pillar: Stable Core
Phase: 7

Per `.github/copilot-instructions.md` Hard Rule #3:

* Every new module/class in `v2/src/**` opens with a docstring header
  carrying `Pillar: <Stable Core | Scenario Pack | Configuration Layer
  | Customization Layer>` and `Phase: <N>` (or `<N.M>`), each on its
  own line, in canonical form.

The Phase line may carry an optional parenthetical tail with the
phase's standing descriptive name (e.g. `Phase: 6 (Functions
blueprints / modular RAG indexing pipeline)`), per Hard Rule #16
carve-out (a). Forbidden tail content (`+ Cleanup audit batch N`, `+
task #N`, `, U#`, etc.) is policed separately by Hard Rule #16's
process-narrative gate; this gate enforces only the canonical *shape*
of the two header lines.

This gate walks every `*.py` under `v2/src/` and asserts the module
docstring matches both regexes. Files without a module docstring fail
loudly. The gate has no growable allow-list -- fix the header, do not
exempt the file.
"""

import ast
import re
from pathlib import Path

import pytest

# v2/ root resolves from this file: v2/tests/shared/test_*.py -> v2/
_V2_ROOT = Path(__file__).resolve().parents[2]

# Production-code surface only. Tests + scripts are intentionally
# excluded -- Hard Rule #3 scopes to `v2/src/**`.
_SCAN_ROOTS = ("src",)

# Per-file exemption list. Empty by design -- Hard Rule #3 is
# unconditional. If you think you need to add an entry here, you
# don't: add the header to the file.
_EXEMPTIONS: frozenset[Path] = frozenset()

# Exactly one of the four canonical pillar names, on its own line.
_PILLAR_RE = re.compile(
    r"^Pillar: (Stable Core|Scenario Pack|Configuration Layer|Customization Layer)$",
    re.MULTILINE,
)

# Numeric phase (`N` or `N.M`) with optional Hard Rule #16(a)
# descriptive parenthetical tail. The parenthetical body cannot
# contain a `)` (no nested groups, no narrative chains).
_PHASE_RE = re.compile(
    r"^Phase: \d+(\.\d+)?( \([^)]+\))?$",
    re.MULTILINE,
)


def _iter_v2_python_files() -> list[Path]:
    """Return every `*.py` under the scan roots, sorted for stable output."""
    files: list[Path] = []
    for root in _SCAN_ROOTS:
        root_dir = _V2_ROOT / root
        if not root_dir.is_dir():
            continue
        for path in root_dir.rglob("*.py"):
            parts = set(path.parts)
            if "__pycache__" in parts or ".venv" in parts or "build" in parts or "node_modules" in parts:
                continue
            files.append(path)
    return sorted(files)


_ALL_FILES = _iter_v2_python_files()


@pytest.mark.parametrize(
    "py_file",
    _ALL_FILES,
    ids=lambda p: str(p.relative_to(_V2_ROOT)),
)
def test_pillar_phase_header(py_file: Path) -> None:
    if py_file in _EXEMPTIONS:
        pytest.skip(f"explicitly exempted: {py_file.relative_to(_V2_ROOT)}")

    source = py_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(py_file))
    rel = py_file.relative_to(_V2_ROOT)

    docstring = ast.get_docstring(tree)
    if docstring is None:
        pytest.fail(
            f"{rel}: module has no docstring (Hard Rule #3). Every "
            f"module under `v2/src/**` must open with a docstring "
            f"carrying `Pillar: <...>` and `Phase: <N>` on their own "
            f"lines."
        )

    pillar_match = _PILLAR_RE.search(docstring)
    phase_match = _PHASE_RE.search(docstring)

    if pillar_match is None:
        pytest.fail(
            f"{rel}: docstring missing canonical `Pillar:` line (Hard "
            f"Rule #3). Expected exactly one of `Pillar: Stable Core` "
            f"/ `Pillar: Scenario Pack` / `Pillar: Configuration "
            f"Layer` / `Pillar: Customization Layer` on its own line."
        )

    if phase_match is None:
        pytest.fail(
            f"{rel}: docstring missing canonical `Phase:` line (Hard "
            f"Rule #3). Expected `Phase: <N>` or `Phase: <N.M>` on its "
            f"own line, optionally followed by a single parenthetical "
            f"descriptive tail (e.g. `Phase: 6 (Functions blueprints / "
            f"modular RAG indexing pipeline)`). Process narrative "
            f"chains like `+ Cleanup audit batch N` or `+ task #N` are "
            f"forbidden by Hard Rule #16."
        )


def test_scan_actually_walked_files() -> None:
    """Sanity guard: the parametrise input must not be empty.

    If path resolution silently misses every file (e.g. tests run from
    an unexpected cwd), the parametrised test would generate zero
    cases and quietly pass. This asserts at least the production
    source root is visible with a non-trivial file count.
    """
    assert _ALL_FILES, "no `*.py` files discovered under v2/src/"
    rel_parts = {p.relative_to(_V2_ROOT).parts[0] for p in _ALL_FILES}
    assert rel_parts == {"src"}, (
        f"scan root mismatch -- expected only `src`, got {sorted(rel_parts)}"
    )
    # 101 modules at gate-landing. Treat any drop below 90 as a sign
    # path resolution started silently dropping files.
    assert len(_ALL_FILES) >= 90, (
        f"only {len(_ALL_FILES)} files discovered under v2/src/ -- "
        f"path resolution likely broken (expected >=90)"
    )
