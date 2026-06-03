"""AST invariant: every `__init__.py` under `v2/` is a package marker only.

Pillar: Stable Core
Phase: 4 (cleanup audit follow-on, IA-C1)

Per `.github/copilot-instructions.md` Hard Rule #13 (codified 2026-05-20,
finalised 2026-05-26 after IA-B1..IA-B8): an `__init__.py` is a package
marker. The *only* permitted content is the module docstring (which
typically carries the `Pillar:` / `Phase:` header).

This test walks every `*__init__.py*` under `v2/src/` and `v2/tests/`
(excluding `.venv/`, `__pycache__/`, and build artefacts) and asserts
the AST body is one of:

1. **Empty** — zero top-level nodes.
2. **Docstring-only** — exactly one top-level node, of shape
   `ast.Expr(value=ast.Constant(value=str))`.

Anything else — a stray `pass`, an `import`, an assignment, a class /
function definition, a `Registry(...)` instantiation, an `__all__`
list — fails the test with the file path, offending node line, and
the AST node type for diagnostic clarity.

Displaced code goes to a sibling module: see dev_plan §2.4.4 ("Where
displaced code goes"). The canonical sibling for provider domains is
`registry.py`; non-provider packages use whatever name describes the
content (`definitions.py`, `contracts.py`, etc.).

This gate locks the IA-Bx migration series in place. Any future PR
that re-introduces code into an `__init__.py` will fail here long
before it merges.
"""

import ast
from pathlib import Path

import pytest

# v2/ root resolves from this file: v2/tests/shared/test_*.py -> v2/
_V2_ROOT = Path(__file__).resolve().parents[2]

# Subtrees under v2/ that get scanned. v2/scripts/ has no Python
# packages today (dev scripts are plain modules); if that ever changes,
# add "scripts" here and the gate will pick the new packages up.
_SCAN_ROOTS = ("src", "tests")

# Per-file exemption list. Empty by design -- the rule has no
# exceptions (Hard Rule #13 strict, locked 2026-05-26 by user). If you
# think you need to add an entry here, you don't: move the displaced
# code to a sibling module per dev_plan §2.4.4. Kept as a frozenset so
# the test failure message can point at it unambiguously.
_EXEMPTIONS: frozenset[Path] = frozenset()


def _iter_v2_init_files() -> list[Path]:
    """Return every `__init__.py` under the scan roots, sorted for stable output."""
    files: list[Path] = []
    for root in _SCAN_ROOTS:
        root_dir = _V2_ROOT / root
        if not root_dir.is_dir():
            continue
        for path in root_dir.rglob("__init__.py"):
            # Skip any cached / venv / build output that may have been
            # dropped under one of the scan roots.
            parts = set(path.parts)
            if "__pycache__" in parts or ".venv" in parts or "build" in parts or "node_modules" in parts:
                continue
            files.append(path)
    return sorted(files)


def _is_docstring_node(node: ast.stmt) -> bool:
    """True if `node` is a module-level docstring expression."""
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


# Collect once; pytest parametrises so each file shows as its own test
# case in failure output (instead of a single mega-failure).
_ALL_FILES = _iter_v2_init_files()


@pytest.mark.parametrize(
    "init_file",
    _ALL_FILES,
    ids=lambda p: str(p.relative_to(_V2_ROOT)),
)
def test_init_file_is_marker_only(init_file: Path) -> None:
    if init_file in _EXEMPTIONS:
        pytest.skip(f"explicitly exempted: {init_file.relative_to(_V2_ROOT)}")

    source = init_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(init_file))
    rel = init_file.relative_to(_V2_ROOT)

    # Allowed shape 1: empty body.
    if not tree.body:
        return

    # Allowed shape 2: exactly one top-level node, a docstring.
    if len(tree.body) == 1 and _is_docstring_node(tree.body[0]):
        return

    # Anything else is a violation. Surface the first offending node so
    # the developer doesn't have to guess.
    for node in tree.body:
        if _is_docstring_node(node):
            continue
        pytest.fail(
            f"{rel}:{node.lineno}: `{type(node).__name__}` is not allowed in "
            f"an `__init__.py` (Hard Rule #13). An `__init__.py` is a "
            f"package marker only -- the sole legal content is the module "
            f"docstring. Move this code to a sibling module (see dev_plan "
            f"§2.4.4: `registry.py` for provider domains, "
            f"`definitions.py` / `contracts.py` / similar elsewhere)."
        )

    # If we got here, every node was a docstring but there were
    # multiple of them -- still a violation (only one docstring is
    # legal).
    pytest.fail(
        f"{rel}: multiple module-level docstrings detected (Hard Rule "
        f"#13). An `__init__.py` accepts at most one docstring."
    )


def test_scan_actually_walked_files() -> None:
    """Sanity guard: the parametrise input must not be empty.

    If the path resolution above ever silently misses every file (e.g.
    because the test runs from an unexpected cwd in CI), the
    parametrised test would generate zero cases and quietly pass. This
    asserts at least the major source roots are visible.
    """
    assert _ALL_FILES, "no `__init__.py` files discovered under v2/{src,tests}"
    rel_parts = {p.relative_to(_V2_ROOT).parts[0] for p in _ALL_FILES}
    assert "src" in rel_parts, (
        "no `__init__.py` files found under v2/src/ -- path resolution "
        "likely broken"
    )
    assert "tests" in rel_parts, (
        "no `__init__.py` files found under v2/tests/ -- path resolution "
        "likely broken"
    )
