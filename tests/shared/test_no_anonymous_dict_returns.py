"""AST invariant: closed-set dict returns must be typed Pydantic models.

Per `.github/copilot-instructions.md` Hard Rule #15 (codified 2026-05-28): when
a function returns a dict (or ``list[dict]``) whose keys are a *fixed,
known-at-author-time* schema, the function must return a Pydantic v2
``BaseModel`` (frozen, ``extra="forbid"``) instead of ``dict[str, object]`` /
``dict[str, Any]``. Wire-shape conversion to ``Mapping[str, Any]`` happens at
the SDK boundary via ``model.model_dump(...)`` -- the model is the source of
truth for the schema, the dict is a transport detail.

This gate walks every ``*.py`` under ``src/`` (tests excluded -- capture
buffers like ``captured: dict[str, object] = {}`` are local accumulators, not
returns), inspects each ``FunctionDef`` / ``AsyncFunctionDef`` return
annotation, and fails if any function returns a closed-set dict shape that
isn't on the explicit boundary allow-list.

**What the gate flags** (the heuristic -- see Hard Rule #15 for the
spec):

* ``dict[str, *]`` (any value type) -- the canonical struct-like return.
* ``list[dict[str, *]]`` -- list of structs (e.g. ingestion handlers).
* ``dict[str, *] | None`` (and ``Optional[dict[str, *]]``) -- optional struct
  return.
* ``Mapping[str, *]`` and its optional / list wrappers -- same reasoning.

**Boundary allow-list** (each entry justified inline; growth requires a
``v2/docs/development_plan.md`` §0.1 debt-queue row):

* ``backend.exception_handlers._request_extras`` -- Hard Rule #15(c):
  builds the ``extra={...}`` payload for ``logger.exception``, which
  contractually requires ``Mapping[str, object]``. Every caller spreads via
  ``**`` to add ad-hoc per-call fields, so wrapping in a model just to
  immediately ``model_dump`` would add noise without value.
* ``backend.core.providers.databases.cosmosdb.CosmosDBClient._read_item`` --
  Hard Rule #15(a) + #11(a): returns a raw Azure Cosmos document. The Cosmos
  SDK contract is ``dict[str, Any]``; narrowing here would lie about the
  shape the SDK actually delivers.
* ``backend.core.providers.llm.foundry_iq.FoundryIQ._to_openai_messages`` --
  Hard Rule #15(a) + (b): converts already-typed ``ChatMessage`` Pydantic
  models into the ``openai.ChatCompletionMessageParam`` wire shape (a
  TypedDict union owned by the OpenAI SDK). This IS the model -> wire
  boundary the rule prescribes -- via ``m.model_dump(exclude_none=True)``
  per-message -- so the function exists *because of* Hard Rule #15, not in
  spite of it.
* ``functions.blob_event.event_parser._decode_event_payload`` -- Hard Rule
  #15(b): decodes the externally-defined Event Grid event envelope from a
  Storage Queue message body. The schema is owned by Azure Event Grid; the
  envelope carries arbitrary ``data`` whose shape varies per event type.
If a new boundary case surfaces, add it here with a one-line justification
and queue a §0.1 row noting the rule expansion.
"""

import ast
from pathlib import Path

import pytest

# Repo root resolves from this file: tests/shared/test_*.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"

# Allow-list of (module dotted path relative to src/, function qualname)
# tuples. Methods use ``ClassName.method_name``. Each entry is justified in
# the module docstring above.
_ALLOWED: frozenset[tuple[str, str]] = frozenset(
    {
        ("backend.exception_handlers", "_request_extras"),
        (
            "backend.core.providers.databases.cosmosdb",
            "CosmosDBClient._read_item",
        ),
        (
            "backend.core.providers.llm.foundry_iq",
            "FoundryIQ._to_openai_messages",
        ),
        (
            "functions.blob_event.event_parser",
            "_decode_event_payload",
        ),
    }
)


def _iter_v2_src_python_files() -> list[Path]:
    """Return every ``*.py`` under ``src/``, sorted for stable output.

    Skips ``__pycache__`` / ``.venv`` / ``build`` artefacts.
    """
    files: list[Path] = []
    if not _SRC_ROOT.is_dir():
        return files
    for path in _SRC_ROOT.rglob("*.py"):
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


def _module_dotted_path(path: Path) -> str:
    """Convert ``src/backend/app.py`` -> ``backend.app``.

    Drops the trailing ``__init__`` segment so package ``__init__.py`` files
    map to their package's dotted path (consistent with how callers import
    them).
    """
    rel = path.relative_to(_SRC_ROOT).with_suffix("")
    parts = rel.parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _annotation_is_closed_set_dict(node: ast.expr | None) -> bool:
    """True if ``node`` looks like a closed-set ``dict``/``Mapping`` return.

    Recurses into ``list[...]``, ``Optional[...]``, and PEP 604 ``X | None``
    unions so wrappers around the struct shape are still caught.
    """
    if node is None:
        return False

    # Bare ``dict`` / ``Mapping`` without subscript -- also a closed-set
    # smell (no value type narrowing) but Python only allows this in older
    # syntax. Catch defensively.
    if isinstance(node, ast.Name) and node.id in {"dict", "Dict", "Mapping"}:
        return True

    # Subscripted: ``dict[str, X]`` / ``Mapping[str, X]`` / ``list[...]`` /
    # ``Optional[...]``.
    if isinstance(node, ast.Subscript):
        value = node.value
        slice_node = node.slice
        if isinstance(value, ast.Name):
            name = value.id
            if name in {"dict", "Dict"}:
                # ``dict[str, X]`` is parsed as Subscript(slice=Tuple(...)).
                if isinstance(slice_node, ast.Tuple) and len(slice_node.elts) == 2:
                    key_ann = slice_node.elts[0]
                    if isinstance(key_ann, ast.Name) and key_ann.id == "str":
                        return True
                return False
            if name == "Mapping":
                # ``Mapping[str, X]`` -- same shape as dict[str, X].
                if isinstance(slice_node, ast.Tuple) and len(slice_node.elts) == 2:
                    key_ann = slice_node.elts[0]
                    if isinstance(key_ann, ast.Name) and key_ann.id == "str":
                        return True
                return False
            if name in {"list", "List", "Sequence", "Iterable"}:
                # Recurse into the element type.
                return _annotation_is_closed_set_dict(slice_node)
            if name == "Optional":
                # ``Optional[X]`` -- recurse into the inner type.
                return _annotation_is_closed_set_dict(slice_node)
        # Fall through to recursive scan for any other shape.
        return False

    # PEP 604 union: ``dict[str, Any] | None`` -- recurse into each arm.
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _annotation_is_closed_set_dict(
            node.left
        ) or _annotation_is_closed_set_dict(node.right)

    return False


_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def _iter_functions_with_qualnames(
    tree: ast.Module,
) -> list[tuple[str, _FunctionNode]]:
    """Yield ``(qualname, node)`` for every function defined in ``tree``.

    Methods get ``Class.method_name`` qualnames. Nested classes get
    ``Outer.Inner.method``. Nested functions (closures) get
    ``outer.inner`` so the allow-list can disambiguate.
    """
    results: list[tuple[str, _FunctionNode]] = []

    def _walk(body: list[ast.stmt], prefix: str) -> None:
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = f"{prefix}{stmt.name}" if prefix else stmt.name
                results.append((qualname, stmt))
                _walk(stmt.body, f"{qualname}.")
            elif isinstance(stmt, ast.ClassDef):
                inner_prefix = f"{prefix}{stmt.name}." if prefix else f"{stmt.name}."
                _walk(stmt.body, inner_prefix)

    _walk(tree.body, "")
    return results


def _collect_violations() -> list[tuple[Path, str, _FunctionNode]]:
    """Return ``(file_path, qualname, node)`` for every gate violation."""
    violations: list[tuple[Path, str, _FunctionNode]] = []
    for path in _iter_v2_src_python_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        module = _module_dotted_path(path)
        for qualname, func in _iter_functions_with_qualnames(tree):
            if not _annotation_is_closed_set_dict(func.returns):
                continue
            if (module, qualname) in _ALLOWED:
                continue
            violations.append((path, qualname, func))
    return violations


_VIOLATIONS = _collect_violations()


@pytest.mark.parametrize(
    "violation",
    _VIOLATIONS,
    ids=lambda v: f"{v[0].relative_to(_REPO_ROOT)}::{v[1]}",
)
def test_no_anonymous_dict_returns(
    violation: tuple[Path, str, _FunctionNode],
) -> None:
    path, qualname, node = violation
    rel = path.relative_to(_REPO_ROOT)
    pytest.fail(
        f"{rel}:{node.lineno}: `{qualname}` returns a closed-set dict shape "
        f"(Hard Rule #15). Define a Pydantic `BaseModel` (frozen, "
        f'`extra="forbid"`) and return that; convert to the SDK wire shape '
        f"via `model.model_dump(...)` at the boundary. If this site is a "
        f"legitimate boundary case (third-party SDK row, externally-defined "
        f"protocol payload, stdlib `Mapping[str, object]` consumer with "
        f"`**`-spread call sites, or a test capture buffer), add an entry "
        f"to `_ALLOWED` in this file with a one-line justification AND a "
        f"§0.1 debt-queue row noting the allow-list growth."
    )


def test_allow_list_entries_resolve_to_real_functions() -> None:
    """Sanity guard: every allow-list entry must point at a real function.

    Without this, an allow-list entry whose target was renamed or removed
    would silently linger and weaken the rule.
    """
    seen: set[tuple[str, str]] = set()
    for path in _iter_v2_src_python_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        module = _module_dotted_path(path)
        for qualname, _func in _iter_functions_with_qualnames(tree):
            seen.add((module, qualname))
    missing = _ALLOWED - seen
    assert not missing, (
        f"allow-list entries do not resolve to any function under "
        f"src/: {sorted(missing)}. Either restore the function, "
        f"update the entry, or remove it from `_ALLOWED`."
    )


def test_scan_actually_walked_files() -> None:
    """Sanity guard: the source-tree walk must not be empty.

    Mirrors the equivalent guard in
    `test_init_files_are_marker_only.py` -- if the path resolution
    silently misses every file (e.g. CI cwd misconfiguration), every
    parametrised case would skip and the gate would falsely pass.
    """
    files = _iter_v2_src_python_files()
    assert files, "no `*.py` files discovered under src/"
    rel_parts = {p.relative_to(_SRC_ROOT).parts[0] for p in files}
    assert "backend" in rel_parts, (
        "no `*.py` files found under src/backend/ -- path resolution " "likely broken"
    )
    assert "functions" in rel_parts, (
        "no `*.py` files found under src/functions/ -- path resolution " "likely broken"
    )
