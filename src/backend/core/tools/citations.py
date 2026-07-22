"""Citation marker helper.

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

Caller pattern::

    sources = await search.search(query)
    block = format_sources_block(sources)              # → str for prompt
    citations = build_citations(sources)               # → list[Citation]
    # orchestrator injects `block` as system context, then for each
    # citation yields OrchestratorEvent(channel=OrchestratorChannel.CITATION,
    # metadata=c.model_dump()).
"""

import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Sequence, cast

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


def _clean_annotation_field(value: object) -> str:
    """Coerce an ``agent_framework`` annotation field to a clean string.

    The Knowledge Base SDK can surface a missing source attribute as a
    Python ``None`` -- or, once stringified upstream, the literal text
    ``"None"`` (notably on ``url`` when a grounded source has no
    renderable link). Treat both as absent so the placeholder never
    leaks into a citation ``id``, ``title``, ``url``, or ``snippet``.
    """
    if value is None:
        return ""
    text = str(value)
    return "" if text == "None" else text


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
        file_id = _clean_annotation_field(ann.get("file_id", ""))
        url = _clean_annotation_field(ann.get("url", ""))
        title = _clean_annotation_field(ann.get("title", ""))
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
            snippet=_clean_annotation_field(ann.get("snippet", "")),
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


# Native Foundry IQ Knowledge Base citation marker, e.g. 【6:1†source】:
# full-width brackets (U+3010 / U+3011) wrapping an N:M index and a
# †-prefixed source label. The agent_framework path emits these inline in
# the answer text; the langgraph path emits [docN] markers instead.
_KB_MARKER_RE = re.compile(r"【[\d:]+†[^】]+】")


def _region_bounds(region: object) -> tuple[int, int] | None:
    """Return a span's ``(start, end)`` if the region is a well-formed mapping.

    SDK ``TextSpanRegion`` values are mapping-shaped. Any region that is not a
    mapping or lacks a valid, non-inverted integer span yields ``None`` so a
    malformed annotation is skipped instead of corrupting the answer text.
    """
    if not isinstance(region, Mapping):
        return None
    # SDK boundary: agent_framework TextSpanRegion is a mapping of str -> object.
    span = cast(Mapping[str, object], region)
    start = span.get("start_index")
    end = span.get("end_index")
    if isinstance(start, int) and isinstance(end, int) and 0 <= start <= end:
        return start, end
    return None


def normalize_kb_citations(
    answer: str, citations: Sequence[Citation]
) -> tuple[str, list[Citation]]:
    """Rewrite native KB citation markers to the shared ``[docN]`` shape.

    The ``agent_framework`` path grounds through the server-side Foundry IQ
    Knowledge Base, whose model emits native ``【N:M†source】`` markers inline in
    the answer and citation annotations keyed by a raw
    ``mcp://searchindex/<key>`` id. This converts that output to the same
    inline ``[docN]`` markers and ``[docN]``-keyed :class:`Citation` list the
    ``langgraph`` path produces, so both orchestrators emit one citation shape
    (ADR 0007).

    Mapping is **offset-anchored**, not parsed from ``N:M`` (whose ``M`` is the
    KB's internal source index, not the citation order). Each citation is
    renumbered to its 1-based position (``[doc1]``, ``[doc2]`` ...); every
    native marker the SDK attributed to it via
    ``metadata["annotated_regions"]`` is rewritten to that ``[docN]``. Any
    residual native marker the SDK left unattributed is stripped so it never
    reaches the UI.

    Title and snippet recovery is a separate concern: the raw ``mcp://`` id is
    left on ``title`` / ``url`` / ``snippet`` here, so a caller that needs a
    friendly filename resolves it downstream.
    """
    marker_to_label: dict[str, str] = {}
    renumbered: list[Citation] = []

    for index, citation in enumerate(citations, start=1):
        label = doc_marker(index)
        raw_regions = citation.metadata.get("annotated_regions")
        regions: list[object] = []
        if isinstance(raw_regions, list):
            # SDK boundary: metadata is dict[str, Any]; the stored regions are
            # agent_framework TextSpanRegion mappings.
            regions = cast(list[object], raw_regions)
        for region in regions:
            bounds = _region_bounds(region)
            if bounds is None:
                continue
            start, end = bounds
            marker = answer[start:end]
            if _KB_MARKER_RE.fullmatch(marker):
                marker_to_label.setdefault(marker, label)
        renumbered.append(citation.model_copy(update={"id": label}))

    normalized = answer
    for marker, label in marker_to_label.items():
        normalized = normalized.replace(marker, label)
    normalized = _KB_MARKER_RE.sub("", normalized)
    return normalized, renumbered


def strip_kb_markers(text: str) -> str:
    """Remove native Foundry IQ KB citation markers from free text.

    The answer channel rewrites ``【N:M†source】`` markers to the shared
    ``[docN]`` shape via :func:`normalize_kb_citations`; the reasoning
    channel has no ``[docN]`` rendering, so it simply drops the markers.
    Runs of spaces / tabs left behind by a removed marker are collapsed
    to a single space so the text reads cleanly, while newlines are
    preserved so a multi-line reasoning summary keeps its structure.
    """
    stripped = _KB_MARKER_RE.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", stripped)


# Native Foundry IQ Knowledge Base source scheme. The agent_framework KB
# annotation keys a citation by ``mcp://searchindex/<key>``, where ``<key>`` is
# the Azure AI Search document id. Stripping the scheme yields the bare key a
# by-id document lookup resolves.
_KB_SOURCE_SCHEME = "mcp://searchindex/"


def _kb_document_key(citation: Citation) -> str | None:
    """Return the bare Search document key behind a KB citation, or ``None``.

    The ``agent_framework`` Knowledge Base path keys citations by a raw
    ``mcp://searchindex/<key>`` id, carried on ``metadata["source_id"]`` and
    mirrored onto ``url`` / ``title`` until enrichment runs; ``<key>`` is the
    Search document id. A citation without that scheme (the ``langgraph``
    path, or an already-enriched citation) yields ``None`` so it passes
    through untouched.
    """
    candidates = (
        citation.metadata.get("source_id"),
        citation.url,
        citation.title,
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.startswith(_KB_SOURCE_SCHEME):
            return candidate[len(_KB_SOURCE_SCHEME) :]
    return None


async def enrich_kb_citations(
    citations: Sequence[Citation],
    fetch_document: Callable[[str], Awaitable[SearchResult | None]],
) -> list[Citation]:
    """Backfill friendly ``title`` / ``snippet`` / ``url`` on KB citations.

    The ``agent_framework`` Knowledge Base annotation carries only a raw
    ``mcp://searchindex/<key>`` id -- no filename, no snippet -- so a
    KB-grounded citation renders with an internal scheme where the
    ``langgraph`` path shows the document name. This resolves each KB-keyed
    citation's ``<key>`` (the Search document id) through the injected
    ``fetch_document`` lookup and replaces ``title`` / ``snippet`` / ``url``
    with the document's friendly fields.

    ``fetch_document`` is injected (key -> ``SearchResult`` | ``None``) so
    this stays a pure citation-shaping step with no Search-provider import --
    the single response-format point (ADR 0026 / Hard Rule #20 R2). The caller
    (the ``agent_framework`` orchestrator) owns the lookup's SDK boundary and
    resilience (Hard Rule #14).

    A citation with no ``mcp://searchindex/`` key (the ``langgraph`` path, or
    an already-enriched citation) passes through unchanged. A key that
    ``fetch_document`` resolves to ``None`` (document not in the index) also
    passes through unchanged, so a missing lookup degrades to the raw id
    rather than dropping the citation. ``id``, ``score``, and ``metadata``
    (including the original ``source_id``) are preserved.
    """
    enriched: list[Citation] = []
    for citation in citations:
        key = _kb_document_key(citation)
        if key is None:
            enriched.append(citation)
            continue
        document = await fetch_document(key)
        if document is None:
            enriched.append(citation)
            continue
        enriched.append(
            citation.model_copy(
                update={
                    "title": document.title,
                    "snippet": document.content,
                    "url": document.url,
                }
            )
        )
    return enriched


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


def filter_to_referenced(text: str, citations: Sequence[Citation]) -> list[Citation]:
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
    "enrich_kb_citations",
    "filter_to_referenced",
    "format_sources_block",
    "normalize_kb_citations",
    "referenced_markers",
    "strip_kb_markers",
]
