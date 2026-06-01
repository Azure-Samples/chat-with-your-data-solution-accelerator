"""AST invariant: cleaned routers carry only routes + module setup.

Pillar: Stable Core
Phase: 7 (router cleanup -- locks the U-P7-ROUTER-CLEAN-N series in place)

Per `.github/copilot-instructions.md` Hard Rule #10 (Option 1 bucket
plan locked CLEAN-6, dev_plan §0.1 ROUTERS-NON-ROUTE-CONTENT-DEBT):
router modules under `v2/src/backend/routers/` are route-only files.
Helpers belong in `backend.services.<domain>`, dependency wrappers
in `backend.dependencies`, request / response models in
`backend.models.<domain>`, persisted types in `backend.core.types`.

This gate walks the AST body of each router file in
`v2/src/backend/routers/` and asserts every top-level node is one of:

1. **Module docstring** -- the `Pillar:` / `Phase:` header.
2. **Imports** -- `ast.Import` / `ast.ImportFrom` (Hard Rule #17 keeps
   them at the top; this gate only checks they are top-level, not
   their relative order).
3. **`logger = logging.getLogger(__name__)`** -- the module logger.
4. **`router = APIRouter(...)`** -- the router instance.
5. **`__all__ = [...]`** -- explicit re-export list when present.
6. **Route functions** -- `def` or `async def` carrying at least one
   `@router.<verb>(...)` decorator (`get` / `post` / `patch` / `put`
   / `delete` / `head` / `options` / `trace` / `route` / `api_route`
   / `websocket`).

Anything else -- a stray module-level constant, a helper `def`, a
class definition, a type alias, an `if` / `try` block -- fails with
the file path, line number, and AST node type. Fix the violation by
moving the displaced code to the canonical sibling per Hard Rule #10
(services / dependencies / models / core.types).

`_CLEANED_ROUTERS` is derived from a `*.py` scan of
`v2/src/backend/routers/` with `__init__.py` excluded as the package
marker (Hard Rule #13). New router modules dropped into that
directory are auto-enrolled.
"""

import ast
from pathlib import Path

import pytest

# v2/ root resolves from this file: v2/tests/shared/test_*.py -> v2/
_V2_ROOT = Path(__file__).resolve().parents[2]
_ROUTERS_DIR = _V2_ROOT / "src" / "backend" / "routers"

# All `*.py` files under `v2/src/backend/routers/` are router modules
# bound by the route-only invariant. `__init__.py` is excluded as the
# package marker (Hard Rule #13).
_CLEANED_ROUTERS: tuple[str, ...] = tuple(
    sorted(p.name for p in _ROUTERS_DIR.glob("*.py") if p.name != "__init__.py")
)

# Module-level assignment targets that are part of standard router
# setup. Anything else assigned at module scope is a violation.
_ALLOWED_ASSIGN_NAMES: frozenset[str] = frozenset({"logger", "router", "__all__"})

# FastAPI router decorator attributes that mark a function as a route.
_ROUTER_DECORATOR_VERBS: frozenset[str] = frozenset(
    {
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "head",
        "options",
        "trace",
        "route",
        "api_route",
        "websocket",
    }
)


def _is_docstring(node: ast.stmt) -> bool:
    """True if `node` is a module-level docstring expression."""
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _is_allowed_assign(node: ast.stmt) -> bool:
    """True for `logger = ...`, `router = ...`, or `__all__ = ...`."""
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return False
    target = node.targets[0]
    return isinstance(target, ast.Name) and target.id in _ALLOWED_ASSIGN_NAMES


def _has_router_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if any decorator on `node` is `@router.<verb>(...)`."""
    for dec in node.decorator_list:
        call = dec.func if isinstance(dec, ast.Call) else dec
        if (
            isinstance(call, ast.Attribute)
            and isinstance(call.value, ast.Name)
            and call.value.id == "router"
            and call.attr in _ROUTER_DECORATOR_VERBS
        ):
            return True
    return False


def _is_route_function(node: ast.stmt) -> bool:
    """True for a `def` / `async def` carrying a `@router.<verb>` decorator."""
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return False
    return _has_router_decorator(node)


@pytest.mark.parametrize(
    "router_filename",
    _CLEANED_ROUTERS,
    ids=lambda f: f,
)
def test_router_is_route_only(router_filename: str) -> None:
    router_path = _ROUTERS_DIR / router_filename
    source = router_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(router_path))
    rel = router_path.relative_to(_V2_ROOT)

    for node in tree.body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            continue
        if _is_docstring(node):
            continue
        if _is_allowed_assign(node):
            continue
        if _is_route_function(node):
            continue
        pytest.fail(
            f"{rel}:{node.lineno}: `{type(node).__name__}` is not allowed at "
            f"router top-level (Hard Rule #10, dev_plan §0.1 "
            f"ROUTERS-NON-ROUTE-CONTENT-DEBT). Allowed top-level content: "
            f"module docstring, imports, `logger = ...`, "
            f"`router = APIRouter(...)`, `__all__ = [...]`, and "
            f"`@router.<verb>` decorated route functions. Move helpers to "
            f"`backend.services.<domain>`, dependency wrappers to "
            f"`backend.dependencies`, request / response models to "
            f"`backend.models.<domain>`, persisted types to "
            f"`backend.core.types`."
        )


def test_router_directory_scan_is_non_empty() -> None:
    """Sanity guard: the directory scan must not be empty.

    If `_ROUTERS_DIR` ever resolves to the wrong path (e.g. tests run
    from an unexpected cwd), the parametrised test above would
    generate zero cases and quietly pass. Assert the directory is
    visible with a non-trivial router count so a silent drop trips
    the gate.
    """
    assert _ROUTERS_DIR.is_dir(), f"router directory missing: {_ROUTERS_DIR}"
    assert _CLEANED_ROUTERS, (
        "no `*.py` router files discovered under v2/src/backend/routers/"
    )
    # 5 router files at gate-landing. Treat any drop below 5 as a
    # sign the scan started silently dropping files.
    assert len(_CLEANED_ROUTERS) >= 5, (
        f"only {len(_CLEANED_ROUTERS)} router files discovered under "
        f"v2/src/backend/routers/ -- path resolution likely broken "
        f"(expected >=5)"
    )
