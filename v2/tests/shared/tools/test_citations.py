"""Pillar: Stable Core / Phase: 3 (#23) — tests for shared/tools/citations.py."""
from __future__ import annotations

import pytest

from shared.tools.citations import (
    build_citations,
    doc_marker,
    filter_to_referenced,
    format_sources_block,
    referenced_markers,
)
from shared.types import Citation, SearchResult


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
