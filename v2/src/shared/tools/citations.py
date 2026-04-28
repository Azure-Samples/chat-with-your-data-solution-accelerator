"""Citation marker helper.

Pillar: Stable Core
Phase: 3 (task #23)

Turns a list of :class:`SearchResult` hits into:

* a numbered ``[doc1] / [doc2] / ...`` source block the orchestrator
  injects into the LLM prompt (so the model can cite by id), and
* a parallel list of :class:`Citation` objects keyed by the same
  numbered ids, ready to emit on the SSE ``citation`` channel
  (ADR 0007).

Lives under ``shared/tools/`` because it is a cross-cutting helper
imported directly by orchestrators / pipelines (per
[development_plan.md] §4 task #20: tools are NOT a registry domain).

Caller pattern (Phase 3 wiring)::

    sources = await search.search(query)
    block = format_sources_block(sources)              # → str for prompt
    citations = build_citations(sources)               # → list[Citation]
    # orchestrator injects `block` as system context, then for each
    # citation yields OrchestratorEvent(channel="citation",
    # metadata=c.model_dump()).
"""
from __future__ import annotations

import re
from typing import Sequence

from shared.types import Citation, SearchResult


_DOC_MARKER_RE = re.compile(r"\[doc(\d+)\]")


def doc_marker(index: int) -> str:
    """Return the canonical marker for a 1-based citation index."""
    if index < 1:
        raise ValueError("doc_marker index must be >= 1")
    return f"[doc{index}]"


def build_citations(sources: Sequence[SearchResult]) -> list[Citation]:
    """Materialize numbered :class:`Citation` objects from search hits.

    The returned ``Citation.id`` is the marker string (``[doc1]``,
    ``[doc2]`` ...) so the frontend can match an inline marker in the
    answer text against the citation list without a separate index
    map. The original search-result id is preserved in
    ``metadata["source_id"]``.
    """
    citations: list[Citation] = []
    for i, src in enumerate(sources, start=1):
        marker = doc_marker(i)
        metadata = dict(src.metadata)
        metadata["source_id"] = src.id
        citations.append(
            Citation(
                id=marker,
                title=src.title,
                url=src.url,
                snippet=src.content,
                score=src.score,
                metadata=metadata,
            )
        )
    return citations


def format_sources_block(sources: Sequence[SearchResult]) -> str:
    """Render hits as ``[docN]: <content>`` lines for prompt injection.

    Empty input returns an empty string so callers can `if block:`
    cheaply. Matches the v1 prompt contract (`PostPromptValidator`
    uses the same shape) so prompt overrides drop in unchanged.
    """
    if not sources:
        return ""
    return "\n".join(
        f"{doc_marker(i)}: {src.content}" for i, src in enumerate(sources, start=1)
    )


def referenced_markers(text: str) -> list[str]:
    """Return citation markers (`[docN]`) referenced in ``text``, in order, deduped."""
    seen: set[str] = set()
    found: list[str] = []
    for match in _DOC_MARKER_RE.finditer(text):
        marker = f"[doc{match.group(1)}]"
        if marker not in seen:
            seen.add(marker)
            found.append(marker)
    return found


def filter_to_referenced(
    text: str, citations: Sequence[Citation]
) -> list[Citation]:
    """Keep only citations whose marker actually appears in ``text``."""
    referenced = set(referenced_markers(text))
    if not referenced:
        return []
    by_id = {c.id: c for c in citations}
    # Preserve the order they appear in the answer.
    return [by_id[m] for m in referenced_markers(text) if m in by_id]


__all__ = [
    "build_citations",
    "doc_marker",
    "filter_to_referenced",
    "format_sources_block",
    "referenced_markers",
]
