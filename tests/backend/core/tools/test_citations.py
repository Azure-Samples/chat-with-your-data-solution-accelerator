"""Tests for backend/core/tools/citations.py."""

from collections.abc import Awaitable, Callable

import pytest

from backend.core.tools.citations import (
    build_citations,
    citations_from_annotations,
    doc_marker,
    enrich_kb_citations,
    filter_to_referenced,
    format_sources_block,
    normalize_kb_citations,
    referenced_markers,
    strip_kb_markers,
)
from backend.core.types import Citation, SearchResult


def _hit(
    id_: str, content: str = "body", title: str = "", url: str = ""
) -> SearchResult:
    return SearchResult(
        id=id_, content=content, title=title, url=url, metadata={"k": "v"}
    )


def test_doc_marker_is_one_indexed() -> None:
    assert doc_marker(1) == "[doc1]"
    assert doc_marker(7) == "[doc7]"


def test_doc_marker_rejects_zero_or_negative() -> None:
    with pytest.raises(ValueError):
        doc_marker(0)
    with pytest.raises(ValueError):
        doc_marker(-3)


def test_format_sources_block_empty_returns_empty_string() -> None:
    assert format_sources_block([]) == ""


def test_format_sources_block_renders_numbered_lines() -> None:
    block = format_sources_block([_hit("a", "alpha"), _hit("b", "beta")])
    assert block == "[doc1]: alpha\n[doc2]: beta"


def test_build_citations_uses_marker_id_and_preserves_source_id() -> None:
    citations = build_citations([_hit("src-1", title="T1", url="https://x/1")])
    assert len(citations) == 1
    c = citations[0]
    assert c.id == "[doc1]"
    assert c.title == "T1"
    assert c.url == "https://x/1"
    assert c.snippet == "body"
    assert c.metadata["source_id"] == "src-1"
    assert c.metadata["k"] == "v"


def test_build_citations_handles_empty() -> None:
    assert build_citations([]) == []


def test_referenced_markers_dedupes_and_preserves_first_occurrence_order() -> None:
    text = "See [doc2] and [doc1]; also [doc2] again, then [doc3]."
    assert referenced_markers(text) == ["[doc2]", "[doc1]", "[doc3]"]


def test_referenced_markers_returns_empty_on_no_matches() -> None:
    assert referenced_markers("plain answer with no markers") == []


def test_filter_to_referenced_drops_unreferenced_and_orders_by_appearance() -> None:
    citations = [
        Citation(id="[doc1]", title="A"),
        Citation(id="[doc2]", title="B"),
        Citation(id="[doc3]", title="C"),
    ]
    text = "First [doc3], then [doc1]; nothing about doc2."
    result = filter_to_referenced(text, citations)
    assert [c.id for c in result] == ["[doc3]", "[doc1]"]


def test_filter_to_referenced_returns_empty_when_text_has_no_markers() -> None:
    citations = [Citation(id="[doc1]")]
    assert filter_to_referenced("ungrounded answer", citations) == []


# ---------------------------------------------------------------------------
# citations_from_annotations -- agent_framework native-annotation adapter
# ---------------------------------------------------------------------------


def test_citations_from_annotations_maps_core_fields() -> None:
    citations = citations_from_annotations(
        [
            {
                "type": "citation",
                "title": "Benefits Guide",
                "url": "https://x/benefits",
                "file_id": "doc-1",
                "snippet": "PTO accrues monthly.",
            }
        ]
    )
    assert len(citations) == 1
    c = citations[0]
    assert c.id == "doc-1"
    assert c.title == "Benefits Guide"
    assert c.url == "https://x/benefits"
    assert c.snippet == "PTO accrues monthly."
    assert c.score is None
    assert c.metadata["source_id"] == "doc-1"
    assert c.metadata["file_id"] == "doc-1"


def test_citations_from_annotations_skips_non_citation_type() -> None:
    citations = citations_from_annotations(
        [
            {"type": "text_span", "file_id": "doc-1"},  # not a citation
            {"file_id": "doc-2"},  # no type at all
            {"type": "citation", "file_id": "doc-3"},
        ]
    )
    assert [c.id for c in citations] == ["doc-3"]


def test_citations_from_annotations_id_falls_back_url_then_title() -> None:
    citations = citations_from_annotations(
        [
            {"type": "citation", "url": "https://x/a"},  # no file_id -> url
            {"type": "citation", "title": "Only Title"},  # no file_id/url -> title
        ]
    )
    assert [c.id for c in citations] == ["https://x/a", "Only Title"]


def test_citations_from_annotations_skips_when_no_identity() -> None:
    citations = citations_from_annotations(
        [{"type": "citation", "snippet": "floating text, no source"}]
    )
    assert citations == []


def test_citations_from_annotations_dedupes_by_id_and_merges_regions() -> None:
    citations = citations_from_annotations(
        [
            {
                "type": "citation",
                "file_id": "doc-1",
                "title": "First",
                "annotated_regions": [
                    {"type": "text_span", "start_index": 0, "end_index": 5}
                ],
            },
            {
                "type": "citation",
                "file_id": "doc-1",
                "title": "ignored second title",
                "annotated_regions": [
                    {"type": "text_span", "start_index": 9, "end_index": 14}
                ],
            },
        ]
    )
    assert len(citations) == 1
    c = citations[0]
    assert c.id == "doc-1"
    assert c.title == "First"  # first occurrence wins
    regions = c.metadata["annotated_regions"]
    assert [(r["start_index"], r["end_index"]) for r in regions] == [(0, 5), (9, 14)]


def test_citations_from_annotations_preserves_tool_name() -> None:
    citations = citations_from_annotations(
        [
            {
                "type": "citation",
                "file_id": "doc-1",
                "tool_name": "knowledge_base_retrieve",
            }
        ]
    )
    assert citations[0].metadata["tool_name"] == "knowledge_base_retrieve"


def test_citations_from_annotations_omits_regions_key_when_absent() -> None:
    citations = citations_from_annotations([{"type": "citation", "file_id": "doc-1"}])
    assert "annotated_regions" not in citations[0].metadata


def test_citations_from_annotations_empty_input() -> None:
    assert citations_from_annotations([]) == []


def test_citations_from_annotations_coerces_none_string_url_to_empty() -> None:
    # The KB SDK stringifies a missing url into the literal "None".
    citations = citations_from_annotations(
        [
            {
                "type": "citation",
                "file_id": "doc-1",
                "title": "Benefit_Options.pdf",
                "url": "None",
            }
        ]
    )
    assert len(citations) == 1
    assert citations[0].url == ""


def test_citations_from_annotations_coerces_python_none_fields_to_empty() -> None:
    citations = citations_from_annotations(
        [{"type": "citation", "file_id": "doc-1", "title": "T", "url": None}]
    )
    assert citations[0].url == ""


def test_citations_from_annotations_treats_none_string_file_id_as_absent() -> None:
    # A "None" file_id must not become the id; identity falls back to url.
    citations = citations_from_annotations(
        [{"type": "citation", "file_id": "None", "url": "https://x/a"}]
    )
    assert len(citations) == 1
    assert citations[0].id == "https://x/a"
    assert "file_id" not in citations[0].metadata


def test_citations_from_annotations_skips_when_all_identity_fields_are_none() -> None:
    citations = citations_from_annotations(
        [{"type": "citation", "file_id": "None", "url": "None", "title": "None"}]
    )
    assert citations == []


# ---------------------------------------------------------------------------
# normalize_kb_citations -- native 【N:M†source】 -> [docN] rewriter
# ---------------------------------------------------------------------------


_MARKER_A = "【6:1†source】"
_MARKER_B = "【6:0†source】"


def _span(answer: str, marker: str) -> dict[str, object]:
    start = answer.index(marker)
    return {"type": "text_span", "start_index": start, "end_index": start + len(marker)}


def _kb_citation(id_: str, regions: list[dict[str, object]]) -> Citation:
    return Citation(id=id_, metadata={"source_id": id_, "annotated_regions": regions})


def test_normalize_kb_citations_maps_by_grouping_order_not_n_m() -> None:
    answer = f"Plans{_MARKER_A} and cost{_MARKER_B}."
    citations = [
        _kb_citation("mcp://searchindex/aaa", [_span(answer, _MARKER_A)]),
        _kb_citation("mcp://searchindex/bbb", [_span(answer, _MARKER_B)]),
    ]
    normalized, result = normalize_kb_citations(answer, citations)
    # Citation[0] -> [doc1] though its marker is 【6:1...】 (M=1); Citation[1] ->
    # [doc2] though its marker is 【6:0...】 (M=0). The mapping follows citation
    # order, not the misleading N:M index.
    assert normalized == "Plans[doc1] and cost[doc2]."
    assert [c.id for c in result] == ["[doc1]", "[doc2]"]


def test_normalize_kb_citations_rewrites_every_repeat_of_a_marker() -> None:
    answer = f"X{_MARKER_A} Y{_MARKER_A}"
    first = answer.index(_MARKER_A)
    second = answer.index(_MARKER_A, first + 1)
    regions = [
        {
            "type": "text_span",
            "start_index": first,
            "end_index": first + len(_MARKER_A),
        },
        {
            "type": "text_span",
            "start_index": second,
            "end_index": second + len(_MARKER_A),
        },
    ]
    citations = [_kb_citation("mcp://searchindex/aaa", regions)]
    normalized, result = normalize_kb_citations(answer, citations)
    assert normalized == "X[doc1] Y[doc1]"
    assert [c.id for c in result] == ["[doc1]"]


def test_normalize_kb_citations_strips_residual_unattributed_marker() -> None:
    orphan = "【9:9†source】"
    answer = f"Body{_MARKER_A} tail{orphan}"
    citations = [_kb_citation("mcp://searchindex/aaa", [_span(answer, _MARKER_A)])]
    normalized, _result = normalize_kb_citations(answer, citations)
    # The attributed marker becomes [doc1]; the orphan native marker is removed.
    assert normalized == "Body[doc1] tail"


def test_normalize_kb_citations_renumbers_ids_when_answer_has_no_markers() -> None:
    answer = "Already a clean answer."
    citations = [
        _kb_citation("mcp://searchindex/aaa", []),
        _kb_citation("mcp://searchindex/bbb", []),
    ]
    normalized, result = normalize_kb_citations(answer, citations)
    assert normalized == "Already a clean answer."
    assert [c.id for c in result] == ["[doc1]", "[doc2]"]


def test_normalize_kb_citations_empty_citations_strip_native_markers() -> None:
    answer = f"Floating{_MARKER_A}."
    normalized, result = normalize_kb_citations(answer, [])
    assert normalized == "Floating."
    assert result == []


def test_normalize_kb_citations_ignores_region_whose_slice_is_not_a_marker() -> None:
    answer = "Hello world."
    # Offset drift: the span points at "Hello", not a native marker.
    citations = [
        _kb_citation(
            "mcp://searchindex/aaa",
            [{"type": "text_span", "start_index": 0, "end_index": 5}],
        )
    ]
    normalized, result = normalize_kb_citations(answer, citations)
    assert normalized == "Hello world."  # untouched -- no corruption
    assert [c.id for c in result] == ["[doc1]"]


def test_normalize_kb_citations_preserves_title_url_snippet_and_score() -> None:
    answer = f"Body{_MARKER_A}."
    citation = Citation(
        id="mcp://searchindex/aaa",
        title="Benefit_Options.pdf",
        url="https://x/benefits",
        snippet="PTO accrues monthly.",
        score=0.87,
        metadata={
            "source_id": "mcp://searchindex/aaa",
            "annotated_regions": [_span(answer, _MARKER_A)],
        },
    )
    normalized, result = normalize_kb_citations(answer, [citation])
    assert normalized == "Body[doc1]."
    c = result[0]
    assert c.id == "[doc1]"  # only the id is renumbered
    assert c.title == "Benefit_Options.pdf"
    assert c.url == "https://x/benefits"
    assert c.snippet == "PTO accrues monthly."
    assert c.score == 0.87


# ---------------------------------------------------------------------------
# strip_kb_markers -- drop native 【N:M†source】 markers from free text
# (reasoning channel has no [docN] rendering)
# ---------------------------------------------------------------------------


def test_strip_kb_markers_removes_marker_and_collapses_whitespace() -> None:
    text = f"The plan {_MARKER_A} covers dental."
    # The marker (flanked by spaces) is removed and the doubled space it
    # leaves behind collapses to one, so the text reads cleanly.
    assert strip_kb_markers(text) == "The plan covers dental."


def test_strip_kb_markers_removes_multiple_markers() -> None:
    text = f"A{_MARKER_A} B{_MARKER_B} C"
    assert strip_kb_markers(text) == "A B C"


def test_strip_kb_markers_preserves_newlines() -> None:
    text = f"First point {_MARKER_A} matters.\nSecond point."
    # Newlines survive so a multi-line reasoning summary keeps its structure;
    # only the horizontal whitespace around the removed marker collapses.
    assert strip_kb_markers(text) == "First point matters.\nSecond point."


def test_strip_kb_markers_noop_without_markers() -> None:
    text = "Clean reasoning with no markers."
    assert strip_kb_markers(text) == text


# ---------------------------------------------------------------------------
# enrich_kb_citations -- backfill friendly title/snippet/url on KB-keyed citations
# ---------------------------------------------------------------------------

_KB_SCHEME = "mcp://searchindex/"


def _kb_keyed_citation(key: str, *, doc_id: str = "[doc1]") -> Citation:
    """A normalized agent_framework KB citation before friendly-field recovery."""
    raw = f"{_KB_SCHEME}{key}"
    return Citation(
        id=doc_id, title=raw, url=raw, snippet="", metadata={"source_id": raw}
    )


def _doc_fetcher(
    documents: dict[str, SearchResult], *, calls: list[str] | None = None
) -> Callable[[str], Awaitable[SearchResult | None]]:
    async def fetch(key: str) -> SearchResult | None:
        if calls is not None:
            calls.append(key)
        return documents.get(key)

    return fetch


async def test_enrich_kb_citations_backfills_friendly_fields() -> None:
    citation = _kb_keyed_citation("KEY1")
    doc = SearchResult(
        id="KEY1",
        content="Welcome to Contoso Electronics.",
        title="Benefit_Options.pdf",
        url="https://blob/benefit_options.pdf",
    )
    (out,) = await enrich_kb_citations([citation], _doc_fetcher({"KEY1": doc}))
    assert out.id == "[doc1]"  # the [docN] id is preserved
    assert out.title == "Benefit_Options.pdf"
    assert out.snippet == "Welcome to Contoso Electronics."
    assert out.url == "https://blob/benefit_options.pdf"
    assert out.metadata["source_id"] == f"{_KB_SCHEME}KEY1"  # original key kept


async def test_enrich_kb_citations_strips_scheme_before_lookup() -> None:
    calls: list[str] = []
    await enrich_kb_citations(
        [_kb_keyed_citation("abc123")], _doc_fetcher({}, calls=calls)
    )
    assert calls == ["abc123"]  # the bare key, not the mcp:// id


async def test_enrich_kb_citations_passes_through_non_kb_citation() -> None:
    calls: list[str] = []
    citation = Citation(
        id="[doc1]",
        title="Plain",
        url="https://x/1",
        snippet="body",
        metadata={"source_id": "src-1"},
    )
    (out,) = await enrich_kb_citations([citation], _doc_fetcher({}, calls=calls))
    assert out == citation  # langgraph-shaped citation untouched
    assert calls == []  # and no lookup attempted


async def test_enrich_kb_citations_keeps_citation_when_document_not_found() -> None:
    citation = _kb_keyed_citation("missing")
    (out,) = await enrich_kb_citations([citation], _doc_fetcher({}))
    assert out == citation  # unresolved key degrades to the raw id, not dropped


async def test_enrich_kb_citations_detects_key_from_url_when_source_id_absent() -> None:
    raw = f"{_KB_SCHEME}url-key"
    citation = Citation(id="[doc1]", title="", url=raw, snippet="", metadata={})
    doc = SearchResult(id="url-key", content="snippet text", title="Doc.pdf")
    (out,) = await enrich_kb_citations([citation], _doc_fetcher({"url-key": doc}))
    assert out.title == "Doc.pdf"
    assert out.snippet == "snippet text"


async def test_enrich_kb_citations_empty_input_returns_empty() -> None:
    assert await enrich_kb_citations([], _doc_fetcher({})) == []
