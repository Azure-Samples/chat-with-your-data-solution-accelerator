"""Citation marker helper.

Pillar: Stable Core
Phase: 3

Turns a list of :class:`SearchResult` hits into:

* a numbered ``[doc1] / [doc2] / ...`` source block the orchestrator
  injects into the LLM prompt (so the model can cite by id), and
* a parallel list of :class:`Citation` objects keyed by the same
  numbered ids, ready to emit on the SSE ``citation`` channel
  (ADR 0007).

The ``agent_framework`` orchestrator instead grounds answers through a
server-side Knowledge Base tool, so its sources arrive as native
``agent_framework`` citation annotations rather than ``[docN]``
markers. :func:`citations_from_annotations` maps those onto the same
:class:`Citation` model, so both orchestrators emit one citation shape.

Lives under ``shared/tools/`` because it is a cross-cutting helper
imported directly by orchestrators / pipelines (tools are NOT a
registry domain).

Caller pattern (Phase 3 wiring)::

    sources = await search.search(query)
    block = format_sources_block(sources)              # → str for prompt
    citations = build_citations(sources)               # → list[Citation]
    # orchestrator injects `block` as system context, then for each
    # citation yields OrchestratorEvent(channel=OrchestratorChannel.CITATION,
    # metadata=c.model_dump()).
"""

import re
from typing import Sequence

from agent_framework import Annotation, TextSpanRegion

from backend.core.types import Citation, SearchResult


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


def citations_from_annotations(
    annotations: Sequence[Annotation],
) -> list[Citation]:
    """Map ``agent_framework`` citation annotations to :class:`Citation`s.

    The ``agent_framework`` orchestrator grounds answers through a
    server-side Knowledge Base retrieval tool, so the SDK surfaces
    sources as native ``Content.annotations`` (``type == "citation"``)
    rather than the numbered ``[docN]`` markers the ``langgraph`` path
    injects. This adapter normalizes those annotations onto the same
    :class:`Citation` model both orchestrators emit on the SSE
    ``citation`` channel (ADR 0007), so the frontend renders one shape.

    A citation's ``id`` is its ``file_id`` (falling back to ``url``
    then ``title``); annotations without any of those carry no usable
    source identity and are dropped. A source cited in more than one
    place collapses to a single :class:`Citation` (the frontend dedupes
    by ``id``), keeping the first occurrence's fields and merging the
    text spans under ``metadata["annotated_regions"]``. ``file_id`` and
    ``tool_name`` are preserved in ``metadata`` when present.
    """
    by_id: dict[str, Citation] = {}
    regions_by_id: dict[str, list[TextSpanRegion]] = {}
    ordered: list[Citation] = []

    for ann in annotations:
        if ann.get("type") != "citation":
            continue
        file_id = ann.get("file_id", "")
        url = ann.get("url", "")
        title = ann.get("title", "")
        citation_id = file_id or url or title
        if not citation_id:
            continue

        regions = list(ann.get("annotated_regions") or ())

        if citation_id in by_id:
            regions_by_id[citation_id].extend(regions)
            continue

        metadata: dict[str, str] = {"source_id": citation_id}
        if file_id:
            metadata["file_id"] = file_id
        tool_name = ann.get("tool_name", "")
        if tool_name:
            metadata["tool_name"] = tool_name

        citation = Citation(
            id=citation_id,
            title=title,
            url=url,
            snippet=ann.get("snippet", ""),
            metadata=metadata,
        )
        by_id[citation_id] = citation
        regions_by_id[citation_id] = regions
        ordered.append(citation)

    for citation in ordered:
        collected = regions_by_id[citation.id]
        if collected:
            citation.metadata["annotated_regions"] = collected
    return ordered


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
    "citations_from_annotations",
    "doc_marker",
    "filter_to_referenced",
    "format_sources_block",
    "referenced_markers",
]
