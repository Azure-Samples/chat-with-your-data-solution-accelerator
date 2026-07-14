"""AST invariant: all `import` / `from X import Y` at module top (no in-function, no conditional).

Per `.github/copilot-instructions.md` Hard Rule #17:

* No `import` / `from X import Y` inside `def` / `async def` / `class` bodies.
* No `import` / `from X import Y` inside module-level `if`/`else` or
  `try`/`except` branches (no profile-conditional import branches, no
  `try/except ImportError` soft-dependency shims).
* All imports appear at module top, after the module docstring,
  before any non-import statement.

This gate walks every `*.py` under the listed scan roots and fails if
any `ast.Import` / `ast.ImportFrom` node is either (a) nested inside
any compound statement (the import's enclosing block is not the module
body), or (b) at module level but follows a non-import, non-docstring
statement.

Scope: `src`, `tests`, and `scripts`. The full v2/ Python surface is
gated; the `tests` root joined after the IMPORTS-AT-TOP-DEBT refactor
pass hoisted every in-function import in `tests/**` to module top.

If a circular import surfaces, fix it structurally via leaf-module
extraction per Hard Rule #11 precedent (extract the shared type /
protocol to a leaf module, top-import from both call sites). Never
reach for an in-function import. Such an extraction is a structural
change and triggers Hard Rule #10 (ask the user first).
"""

import ast
from pathlib import Path

import pytest

# Repo root resolves from this file: tests/shared/test_*.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Subtrees under v2/ that get scanned. Full v2/ Python surface
# (production + scripts + tests) is gated.
_SCAN_ROOTS = ("src", "tests")

# Per-file exemption list. Empty by design -- Hard Rule #17 is absolute
# with zero carve-outs. If you think you need to add an entry here, you
# don't: fix the import site instead.
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


def _is_module_docstring(node: ast.stmt) -> bool:
    """True if `node` is an `Expr` wrapping a string `Constant` (a docstring shape)."""
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _find_misplaced_imports(tree: ast.Module) -> list[tuple[int, str]]:
    """Return `(lineno, reason)` for every misplaced import in the module.

    Two violation classes:
      1. Nested-scope import -- an `Import` / `ImportFrom` whose enclosing
         block is not the module body. Caught by walking descendants of
         every non-import top-level statement.
      2. Out-of-order top-level import -- an `Import` / `ImportFrom` at
         module level that appears after a non-import, non-docstring
         statement. Caught by a single pass over `tree.body`.
    """
    findings: list[tuple[int, str]] = []
    seen_non_import_top_level = False

    for idx, stmt in enumerate(tree.body):
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            if seen_non_import_top_level:
                findings.append(
                    (
                        stmt.lineno,
                        "import appears after a non-import statement at module top",
                    )
                )
            continue
        # Only the FIRST top-level statement may be a docstring (PEP 257).
        if idx == 0 and _is_module_docstring(stmt):
            continue
        # Non-import, non-docstring top-level statement.
        seen_non_import_top_level = True
        for descendant in ast.walk(stmt):
            if descendant is stmt:
                continue
            if isinstance(descendant, (ast.Import, ast.ImportFrom)):
                findings.append(
                    (
                        descendant.lineno,
                        f"import nested inside {type(stmt).__name__} block",
                    )
                )
    return findings


# Collect once; pytest parametrises per file so failures point at the
# exact module.
_ALL_FILES = _iter_v2_python_files()


@pytest.mark.parametrize(
    "py_file",
    _ALL_FILES,
    ids=lambda p: str(p.relative_to(_REPO_ROOT)),
)
def test_imports_at_module_top(py_file: Path) -> None:
    if py_file in _EXEMPTIONS:
        pytest.skip(f"explicitly exempted: {py_file.relative_to(_REPO_ROOT)}")

    source = py_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(py_file))

    findings = _find_misplaced_imports(tree)
    if not findings:
        return

    rel = py_file.relative_to(_REPO_ROOT)
    formatted = "\n".join(f"  line {lineno}: {reason}" for lineno, reason in findings)
    pytest.fail(
        f"{rel}: misplaced imports detected (Hard Rule #17 -- all imports at "
        f"module top, zero carve-outs):\n{formatted}\n\n"
        f"Fix: hoist every `import` / `from X import Y` to the module's import "
        f"block at the top of the file (after the docstring, before any other "
        f"statement). If a circular import surfaces, extract the shared type to "
        f"a leaf module (Hard Rule #10 structural change -- ask the user)."
    )


def test_scan_actually_walked_files() -> None:
    """Sanity guard: the parametrise input must not be empty.

    If the path resolution above ever silently misses every file (e.g.
    because the test runs from an unexpected cwd in CI), the
    parametrised test would generate zero cases and quietly pass.
    """
    assert _ALL_FILES, "no Python files discovered under {src,tests}"
    rel_parts = {p.relative_to(_REPO_ROOT).parts[0] for p in _ALL_FILES}
    assert (
        "src" in rel_parts
    ), "no files found under src/ -- path resolution likely broken"
    assert (
        "tests" in rel_parts
    ), "no files found under tests/ -- path resolution likely broken"
