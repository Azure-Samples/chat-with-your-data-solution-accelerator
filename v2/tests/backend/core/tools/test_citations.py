"""Pillar: Stable Core / Phase: 3 (#23) — tests for backend/core/tools/citations.py."""

import pytest

from backend.core.tools.citations import (
    build_citations,
    citations_from_annotations,
    doc_marker,
    filter_to_referenced,
    format_sources_block,
    referenced_markers,
)
from backend.core.types import Citation, SearchResult


def _hit(id_: str, content: str = "body", title: str = "", url: str = "") -> SearchResult:
    return SearchResult(id=id_, content=content, title=title, url=url, metadata={"k": "v"})


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
        [{"type": "citation", "file_id": "doc-1", "tool_name": "knowledge_base_retrieve"}]
    )
    assert citations[0].metadata["tool_name"] == "knowledge_base_retrieve"


def test_citations_from_annotations_omits_regions_key_when_absent() -> None:
    citations = citations_from_annotations([{"type": "citation", "file_id": "doc-1"}])
    assert "annotated_regions" not in citations[0].metadata


def test_citations_from_annotations_empty_input() -> None:
    assert citations_from_annotations([]) == []
