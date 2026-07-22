"""AST invariant: no silent exception swallows in src/**.

Per [v2/docs/exception_handling_policy.md](../docs/exception_handling_policy.md)
cross-cutting rules: silent swallow (`except <anything>: pass`) and
`except BaseException` are banned everywhere under `src/**`.

This test walks every `*.py` under `src/**` (skip `__pycache__`,
`.venv`, `build`) and asserts:

1. **No `except BaseException`.** Catches `KeyboardInterrupt` /
   `SystemExit`, hangs Ctrl-C, breaks process management. Always wrong.
2. **No silent swallow.** An `except` handler whose body is exactly one
   of `pass`, `Ellipsis` (`...`), or a docstring-only statement is
   banned. If you genuinely want to ignore an exception, log it
   (`logger.debug("ignoring X: %s", exc)`) so the decision is visible.

The scope is `src/**` only (NOT tests / scripts):
- Tests legitimately use `pytest.raises(...)` blocks and may use
  `try/except: pass` patterns to test exception code paths.
- Scripts are one-off automation and not part of the production
  surface this policy protects.

Per-file exemption list (`_EXEMPTIONS`) is now **empty**. Phase C
closed every pre-policy site:

- C2 closure removed `cosmosdb.py` (idempotent-skip site now logs
  via `logger.debug` with message id + conversation id).
- C3 closure removed `backend/core/pipelines/chat.py` line 143 --
  malformed-citation `pass` replaced with
  `logger.debug("ignoring malformed citation metadata", extra={...})`
  carrying `operation="citation_parse"`, `pipeline="chat"`,
  `citation_id`, and `error` for App Insights triage.

Adding a new entry here is **not the right escape hatch**: fix the
construct (log via `logger.debug(...)` if the swallow is genuinely
intentional, otherwise narrow the catch and surface the failure).

Companion to [tests/shared/test_no_legacy_shared_imports.py] and
[tests/shared/test_no_type_checking_or_future_annotations.py],
which use the same AST-walker + parametrize-per-file pattern.
"""

import ast
from pathlib import Path

import pytest

# Repo root resolves from this file: tests/test_no_silent_excepts.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[1]

# Production-surface scan root only. Tests + scripts are intentionally
# excluded (see module docstring).
_SCAN_ROOT = _REPO_ROOT / "src"

# Per-file exemption list. Empty by design after Phase C3 closure --
# every pre-policy silent-swallow site has been migrated to
# `logger.debug(...)` per the exception_handling_policy. Adding a
# new entry here is not the right escape hatch; fix the construct.
_EXEMPTIONS: frozenset[Path] = frozenset()


def _iter_v2_src_python_files() -> list[Path]:
    """Return every `*.py` under `src/`, sorted for stable output."""
    files: list[Path] = []
    if not _SCAN_ROOT.is_dir():
        return files
    for path in _SCAN_ROOT.rglob("*.py"):
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


def _is_silent_swallow_body(body: list[ast.stmt]) -> bool:
    """True if an `except` handler body is exactly a silent swallow.

    A silent swallow body is any of:

    - Exactly one `pass` statement.
    - Exactly one bare `Ellipsis` expression (`...`).
    - Exactly one string-literal expression (a "docstring" placeholder).

    Multi-statement bodies, calls (incl. `logger.debug(...)`), `raise`,
    `yield`, `return`, etc. are *not* silent swallows.
    """
    if len(body) != 1:
        return False
    stmt = body[0]
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr):
        value = stmt.value
        # `...` parses as ast.Constant with value=Ellipsis on 3.8+
        if isinstance(value, ast.Constant) and (
            value.value is Ellipsis or isinstance(value.value, str)
        ):
            return True
    return False


def _exception_handler_violations(
    tree: ast.Module,
) -> list[tuple[int, str]]:
    """Return [(lineno, kind)] for every banned construct in the module.

    Kind is one of:
    - "except BaseException" -- a handler that catches BaseException
      (bare or fully-qualified).
    - "silent swallow" -- a handler whose body is empty per
      `_is_silent_swallow_body`.

    A single handler can produce both kinds; both are reported so the
    failure message is precise.
    """
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        # Catch-target check: `except BaseException` (bare Name) and
        # `except builtins.BaseException` (Attribute) both bad. Tuples
        # like `except (BaseException, X)` also bad.
        targets = _flatten_except_target(node.type)
        for t in targets:
            if t == "BaseException" or t.endswith(".BaseException"):
                out.append((node.lineno, "except BaseException"))
                break
        # Silent-swallow body check, regardless of catch target.
        if _is_silent_swallow_body(node.body):
            out.append((node.lineno, "silent swallow"))
    return out


def _flatten_except_target(node: ast.expr | None) -> list[str]:
    """Return the textual catch-target names from an ExceptHandler.type.

    `except X:`               -> ["X"]
    `except mod.X:`           -> ["mod.X"]
    `except (X, Y, mod.Z):`   -> ["X", "Y", "mod.Z"]
    `except:` (bare)          -> []
    """
    if node is None:
        return []
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        # Walk `a.b.c` -> "a.b.c"
        parts: list[str] = [node.attr]
        cur: ast.expr = node.value
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return [".".join(reversed(parts))]
    if isinstance(node, ast.Tuple):
        out: list[str] = []
        for elt in node.elts:
            out.extend(_flatten_except_target(elt))
        return out
    return []


# Collect once; pytest will parametrise so each file shows as its own
# test case in failure output (instead of a single mega-failure).
_ALL_FILES = _iter_v2_src_python_files()


@pytest.mark.parametrize(
    "py_file",
    _ALL_FILES,
    ids=lambda p: str(p.relative_to(_REPO_ROOT)),
)
def test_no_silent_excepts(py_file: Path) -> None:
    if py_file in _EXEMPTIONS:
        pytest.skip(f"explicitly exempted: {py_file.relative_to(_REPO_ROOT)}")

    source = py_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(py_file))

    violations = _exception_handler_violations(tree)
    if violations:
        rel = py_file.relative_to(_REPO_ROOT)
        formatted = "\n".join(f"  line {lineno}: {kind}" for lineno, kind in violations)
        pytest.fail(
            f"{rel}: banned exception-handler construct(s):\n{formatted}\n"
            f"See v2/docs/exception_handling_policy.md cross-cutting rules. "
            f"`except BaseException` catches KeyboardInterrupt/SystemExit "
            f"and is always wrong; silent swallow (`except X: pass`) hides "
            f"failures. If you must ignore an exception, log it "
            f"(`logger.debug(...)`) so the decision is visible."
        )


def test_silent_excepts_scan_walked_files() -> None:
    """Sanity guard: the parametrise input must not be empty.

    If the path resolution above ever silently misses every file (e.g.
    because the test runs from an unexpected cwd in CI), the
    parametrised test would generate zero cases and quietly pass.
    """
    assert _ALL_FILES, "no Python files discovered under src/"
    rel_parts = {p.relative_to(_REPO_ROOT).parts[0] for p in _ALL_FILES}
    assert rel_parts == {
        "src"
    }, f"unexpected scan roots: {rel_parts} (expected only 'src')"


def test_silent_swallow_detector_self_check() -> None:
    """Unit-test the helper directly so a regression in the detector
    itself (not in production code) shows up loudly.

    Drives every branch of `_is_silent_swallow_body` + the fixture
    sources through `_exception_handler_violations` to prove that:

    - `except Exception: pass` is flagged as silent swallow.
    - `except Exception: ...` is flagged as silent swallow.
    - `except Exception: \"docstring\"` is flagged as silent swallow.
    - `except BaseException: raise` is flagged as except BaseException
      (but NOT silent swallow, body is `raise`).
    - `except (BaseException, ValueError): pass` is flagged as both.
    - `except Exception: logger.debug(...)` is NOT flagged.
    - `except Exception as e: raise RuntimeError() from e` is NOT flagged.
    - `except Exception: pass\n  # comment` is flagged (comment doesn't
      change the AST body).
    """
    fixtures: list[tuple[str, set[str]]] = [
        # (source, expected kinds set)
        ("try:\n    x = 1\nexcept Exception:\n    pass\n", {"silent swallow"}),
        ("try:\n    x = 1\nexcept Exception:\n    ...\n", {"silent swallow"}),
        (
            'try:\n    x = 1\nexcept Exception:\n    "ignored"\n',
            {"silent swallow"},
        ),
        (
            "try:\n    x = 1\nexcept BaseException:\n    raise\n",
            {"except BaseException"},
        ),
        (
            "try:\n    x = 1\nexcept (BaseException, ValueError):\n    pass\n",
            {"except BaseException", "silent swallow"},
        ),
        (
            "try:\n    x = 1\nexcept Exception:\n    logger.debug('x')\n",
            set(),
        ),
        (
            "try:\n    x = 1\nexcept Exception as e:\n"
            "    raise RuntimeError() from e\n",
            set(),
        ),
        (
            "try:\n    x = 1\nexcept builtins.BaseException:\n    raise\n",
            {"except BaseException"},
        ),
    ]
    for source, expected in fixtures:
        tree = ast.parse(source)
        kinds = {kind for _lineno, kind in _exception_handler_violations(tree)}
        assert kinds == expected, (
            f"detector mismatch for source:\n{source}\n"
            f"expected {expected}, got {kinds}"
        )
