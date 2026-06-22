"""Tests for `HtmlParser` (URL / `*.html` ingestion).

Pillar: Stable Core
Phase: 6
"""

import pytest

from backend.core.providers.parsers.base import BaseParser
from backend.core.types import Chunk
from functions.core.parsers import registry as ingestion_parsers_registry
from functions.core.parsers.html_parser import HtmlParser


def test_htmlparser_is_registered_under_html() -> None:
    assert ingestion_parsers_registry.registry.get("html") is HtmlParser


def test_htmlparser_is_a_baseparser_subclass() -> None:
    assert issubclass(HtmlParser, BaseParser)


@pytest.mark.asyncio
async def test_extracts_visible_text_and_drops_script_and_style() -> None:
    html = (
        b"<html><head><style>.x{color:red}</style></head>"
        b"<body><h1>Title</h1>"
        b"<script>console.log('noise')</script>"
        b"<p>Hello world</p></body></html>"
    )
    parser = HtmlParser()
    chunks = await parser.parse(html, source="page.html")
    joined = " ".join(chunk.content for chunk in chunks)
    assert "Title" in joined
    assert "Hello world" in joined
    # Markup, scripts, and styles must not leak into the index.
    assert "console.log" not in joined
    assert "color:red" not in joined
    assert "<p>" not in joined


@pytest.mark.asyncio
async def test_chunks_carry_deterministic_ids_and_source() -> None:
    parser = HtmlParser()
    chunks = await parser.parse(b"<p>only paragraph</p>", source="x.html")
    assert chunks == [
        Chunk(
            id=BaseParser.make_chunk_id("x.html", 0),
            content="only paragraph",
            source="x.html",
            index=0,
        ),
    ]


@pytest.mark.asyncio
async def test_empty_or_markup_only_input_yields_no_chunks() -> None:
    parser = HtmlParser()
    assert await parser.parse(b"", source="empty.html") == []
    assert (
        await parser.parse(b"<html><body></body></html>", source="blank.html") == []
    )
