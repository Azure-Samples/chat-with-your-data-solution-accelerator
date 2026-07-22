"""AST + tokenize invariant: production code carries no process narrative.

Per ``.github/copilot-instructions.md`` Hard Rule #16 (codified 2026-05-28):
comments and docstrings under ``src/**`` describe **what the code is** --
never how it got there, what unit shipped it, what work lands next, what date
the line was written, or what dev_plan section it traces to. Process state
lives in ``v2/docs/development_plan.md``, commit history, and tracked debt
rows; production source files are not the work-tracker.

This gate walks every ``*.py`` under ``src/``, harvests:

* every module / class / function docstring (via ``ast.get_docstring``);
* every comment token (via ``tokenize.generate_tokens``);

and, separately, every ``*.ts`` / ``*.tsx`` under ``src/`` (the frontend
tree), harvesting ``//`` line comments and ``/* ... */`` block comments via a
minimal string-aware scanner. Either walk fails the parametrised case for that
file if any harvested text contains a banned pattern that is not covered by a
Hard Rule #16 carve-out.

**Banned patterns** (line-level regex set):

* ``\\bU\\d+[a-z]?\\b`` -- unit IDs (``U7g``, ``U10c``, ``U11``).
* ``\\btask\\s+#\\d+\\b`` -- dev_plan §4 task numbers (``task #41``).
* ``\\blands?\\s+next\\b`` -- forward-looking work pointers.
* ``\\bso\\s+far\\b`` -- phase roll-forward narrative.
* ``per\\s+\\[?v2/docs/development_plan\\.md`` -- dev_plan citations.
* ``\\b(future|upcoming)\\s+(smoke|e2e|integration|test)`` -- unrelated future
  work references.
* ``\\b20\\d{2}-\\d{2}-\\d{2}\\b(?!-)`` -- ISO process dates, with the
  trailing ``(?!-)`` lookahead carving out Azure API version literals such as
  ``2025-04-01-preview`` which keep the suffix.
* ``\\bCU-\\d+\\w*`` -- cleanup-unit IDs (``CU-009a``, ``CU-010b3``).
* ``#35[a-z]\\b`` -- GitHub issue references (``#35d``, ``#35g``); the trailing
  word boundary keeps multi-character hex colors such as ``#35abcd`` from
  matching.
* ``\\b[A-Z][A-Z0-9]*-MVP\\b`` -- MVP scenario codenames (``SPEECH-MVP``); the
  hyphenated ``-MVP`` suffix keeps Azure SKU tier names (``S1``, ``S2``, ``S3``)
  from matching, unlike a bare ``S\\d+`` pattern.

**Per-line carve-outs** (applied to the source line containing the comment /
docstring text -- a match inside any line below is ignored):

* ``# pyright: ignore`` -- type-checker debt directive; Hard Rule #11/#15
  contract requires the inline ignore to stay anchored to its call site.
* ``-DEBT`` -- debt-row name token (e.g. the ``-DEBT`` suffix in
  ``U8i-EMBEDDER-CTOR-DEBT``); pins the surrounding comment to a tracked
  dev_plan §0.1 row per Hard Rule #16 carve-out (b).
* ``Hard Rule`` -- standing-policy anchor citation per Hard Rule #16 carve-out
  (c).

**Block-scope carve-out** (applied to the entire docstring or comment text,
because the technical context phrase often wraps to a continuation line):

* ``api version`` (case-insensitive) anywhere in the harvested text block --
  Azure SDK technical context; carves out bare ISO-date matches that lack the
  ``-preview`` suffix but still belong to an API version list (Hard Rule #16
  carve-out (e)).

The gate has **no growable allow-list**. Fix the comment; do not exempt the
file. If a genuinely new carve-out class surfaces, raise it as a Hard Rule
#16 amendment request before adding it here.
"""

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

# Repo root resolves from this file: tests/shared/test_*.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"


# --- Banned-pattern regex set -------------------------------------------------

_UNIT_ID_RE = re.compile(r"\bU\d+[a-z]?\b")
_TASK_NUM_RE = re.compile(r"\btask\s+#\d+\b", re.IGNORECASE)
_LANDS_NEXT_RE = re.compile(r"\blands?\s+next\b", re.IGNORECASE)
_SO_FAR_RE = re.compile(r"\bso\s+far\b", re.IGNORECASE)
_DEVPLAN_RE = re.compile(r"per\s+\[?v2/docs/development_plan\.md")
_FUTURE_TESTS_RE = re.compile(
    r"\b(?:future|upcoming)\s+(?:smoke|e2e|integration|test)",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b(?!-)")
_CU_ID_RE = re.compile(r"\bCU-\d+\w*")
_ISSUE_35_RE = re.compile(r"#35[a-z]\b")
_SCENARIO_MVP_RE = re.compile(r"\b[A-Z][A-Z0-9]*-MVP\b")

# (regex, human-readable label) pairs. Order is presentation-only.
_CHECKS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_UNIT_ID_RE, "unit ID"),
    (_TASK_NUM_RE, "task #N"),
    (_LANDS_NEXT_RE, "lands next"),
    (_SO_FAR_RE, "so far"),
    (_DEVPLAN_RE, "dev_plan citation"),
    (_FUTURE_TESTS_RE, "future tests"),
    (_ISO_DATE_RE, "ISO date"),
    (_CU_ID_RE, "CU-### unit ID"),
    (_ISSUE_35_RE, "#35x issue ref"),
    (_SCENARIO_MVP_RE, "MVP scenario codename"),
)


def _line_is_carved_out(line: str) -> bool:
    """True if the line carries a Hard Rule #16 carve-out marker."""
    return "pyright: ignore" in line or "-DEBT" in line or "Hard Rule" in line


# --- Source walkers -----------------------------------------------------------


def _iter_v2_src_python_files() -> list[Path]:
    """Return every ``*.py`` under ``src/``, sorted for stable output."""
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


_TS_SUFFIXES = ("*.ts", "*.tsx")


def _iter_v2_src_ts_files() -> list[Path]:
    """Return every ``*.ts`` / ``*.tsx`` under ``src/``, sorted."""
    files: list[Path] = []
    if not _SRC_ROOT.is_dir():
        return files
    for pattern in _TS_SUFFIXES:
        for path in _SRC_ROOT.rglob(pattern):
            parts = set(path.parts)
            if (
                "__pycache__" in parts
                or ".venv" in parts
                or "build" in parts
                or "dist" in parts
                or "node_modules" in parts
            ):
                continue
            files.append(path)
    return sorted(files)


def _iter_ts_comments(source: str) -> list[tuple[int, str]]:
    """Return ``(line_no, comment_text)`` for every TS/TSX comment.

    A minimal string-aware scanner: it tracks single-quote, double-quote, and
    backtick string context so that ``//`` and ``/*`` sequences inside string
    literals are not mistaken for comments. Both ``//`` line comments and
    ``/* ... */`` block comments are harvested; the reported line number is the
    line the comment opens on.
    """
    results: list[tuple[int, str]] = []
    i = 0
    n = len(source)
    line = 1
    while i < n:
        ch = source[i]
        two = source[i : i + 2]
        if ch == "\n":
            line += 1
            i += 1
        elif ch in "'\"`":
            quote = ch
            i += 1
            while i < n:
                c = source[i]
                if c == "\\":
                    if i + 1 < n and source[i + 1] == "\n":
                        line += 1
                    i += 2
                    continue
                if c == "\n":
                    line += 1
                    i += 1
                    if quote != "`":
                        break
                    continue
                if c == quote:
                    i += 1
                    break
                i += 1
        elif two == "//":
            start = i
            while i < n and source[i] != "\n":
                i += 1
            results.append((line, source[start:i]))
        elif two == "/*":
            start = i
            start_line = line
            i += 2
            while i < n and source[i : i + 2] != "*/":
                if source[i] == "\n":
                    line += 1
                i += 1
            i = min(i + 2, n)
            results.append((start_line, source[start:i]))
        else:
            i += 1
    return results


def _iter_docstrings(tree: ast.Module) -> list[tuple[int, str]]:
    """Return ``(line_no, text)`` for every module/class/function docstring."""
    results: list[tuple[int, str]] = []
    mod_doc = ast.get_docstring(tree, clean=False)
    if mod_doc is not None and tree.body and isinstance(tree.body[0], ast.Expr):
        results.append((tree.body[0].lineno, mod_doc))
    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            ds = ast.get_docstring(node, clean=False)
            if ds is not None and node.body and isinstance(node.body[0], ast.Expr):
                results.append((node.body[0].lineno, ds))
    return results


def _iter_comments(source: str) -> list[tuple[int, str]]:
    """Return ``(line_no, comment_text)`` for every comment token."""
    results: list[tuple[int, str]] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                results.append((tok.start[0], tok.string))
    except tokenize.TokenError:
        # Truncated source -- best-effort.
        pass
    return results


# --- Per-text scanner ---------------------------------------------------------


def _scan_text(text: str, start_line: int) -> list[str]:
    """Return human-readable violation messages for the given text block.

    ``start_line`` is the source line number of the first character of
    ``text`` (1-based). Multi-line docstrings have line offsets added so
    diagnostics point at the actual source line.

    The ``api version`` ISO-date carve-out is evaluated at **block** scope,
    not per-line, because Azure SDK version lists routinely wrap to a
    continuation line whose date tokens still belong to the preceding
    ``api versions`` context phrase.
    """
    out: list[str] = []
    lines = text.splitlines() or [text]
    block_has_api_version_context = "api version" in text.lower()
    for offset, line in enumerate(lines):
        if _line_is_carved_out(line):
            continue
        for regex, label in _CHECKS:
            for match in regex.finditer(line):
                if regex is _ISO_DATE_RE and block_has_api_version_context:
                    continue
                src_line = start_line + offset
                snippet = line.strip()
                if len(snippet) > 120:
                    snippet = snippet[:117] + "..."
                out.append(
                    f"  L{src_line}: {label} match {match.group(0)!r} in: "
                    f"{snippet!r}"
                )
    return out


def _scan_file(path: Path) -> list[str]:
    """Return every violation discovered in the given source file."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    for line_no, text in _iter_docstrings(tree):
        violations.extend(_scan_text(text, line_no))
    for line_no, text in _iter_comments(source):
        violations.extend(_scan_text(text, line_no))
    return violations


def _scan_ts_file(path: Path) -> list[str]:
    """Return every violation discovered in the given TS/TSX source file."""
    source = path.read_text(encoding="utf-8")
    violations: list[str] = []
    for line_no, text in _iter_ts_comments(source):
        violations.extend(_scan_text(text, line_no))
    return violations


# --- Parametrised test --------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    _iter_v2_src_python_files(),
    ids=lambda p: str(p.relative_to(_REPO_ROOT)),
)
def test_no_process_narrative_in_src(path: Path) -> None:
    """Per-file gate: each ``*.py`` under src/ must be narrative-free."""
    violations = _scan_file(path)
    if violations:
        rel = path.relative_to(_REPO_ROOT)
        pytest.fail(
            f"\n{rel}: Hard Rule #16 violations:\n"
            + "\n".join(violations)
            + "\n\nFix the comment/docstring. Process state belongs in "
            "v2/docs/development_plan.md and commit history, not production "
            "source. See .github/copilot-instructions.md Hard Rule #16 for "
            "the carve-out list (Pillar:/Phase: headers without unit-ID "
            "tails, # pyright: ignore lines, -DEBT: anchors, Hard Rule N "
            "citations, Azure SDK API version literals)."
        )


@pytest.mark.parametrize(
    "path",
    _iter_v2_src_ts_files(),
    ids=lambda p: str(p.relative_to(_REPO_ROOT)),
)
def test_no_process_narrative_in_frontend_ts(path: Path) -> None:
    """Per-file gate: each ``*.ts`` / ``*.tsx`` under src/ is narrative-free."""
    violations = _scan_ts_file(path)
    if violations:
        rel = path.relative_to(_REPO_ROOT)
        pytest.fail(
            f"\n{rel}: Hard Rule #16 violations:\n"
            + "\n".join(violations)
            + "\n\nFix the comment. Process state belongs in "
            "v2/docs/development_plan.md and commit history, not production "
            "source. See .github/copilot-instructions.md Hard Rule #16 for "
            "the carve-out list (bare Pillar:/Phase: headers, -DEBT anchors, "
            "Hard Rule N citations, Azure SDK API version literals)."
        )


def test_scan_actually_walked_files() -> None:
    """Sanity guard: the source-tree walk must not be empty.

    Mirrors the equivalent guard in
    ``test_init_files_are_marker_only.py`` and
    ``test_no_anonymous_dict_returns.py`` -- if path resolution silently
    misses every file (e.g. CI cwd misconfiguration), every parametrised
    case would skip and the gate would falsely pass.
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
    ts_files = _iter_v2_src_ts_files()
    assert ts_files, "no `*.ts` / `*.tsx` files discovered under src/"
    ts_rel_parts = {p.relative_to(_SRC_ROOT).parts[0] for p in ts_files}
    assert "frontend" in ts_rel_parts, (
        "no `*.ts` / `*.tsx` files found under src/frontend/ -- path "
        "resolution likely broken"
    )
