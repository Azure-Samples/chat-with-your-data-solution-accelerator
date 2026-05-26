"""Tests for `TextParser` (Phase 6 task #41, U8d).

Pillar: Stable Core
Phase: 6
"""

import pytest

from backend.core.providers.parsers.base import BaseParser
from functions.core.parsers import registry as ingestion_parsers_registry
from functions.core.parsers.text_parser import TextParser
from backend.core.types import Chunk

def test_textparser_is_registered_under_txt() -> None:
    assert ingestion_parsers_registry.registry.get("txt") is TextParser

def test_textparser_is_a_baseparser_subclass() -> None:
    assert issubclass(TextParser, BaseParser)

def test_registry_get_txt_constructs_textparser_instance() -> None:
    parser = ingestion_parsers_registry.registry.get("txt")()
    assert isinstance(parser, TextParser)

@pytest.mark.asyncio
async def test_single_paragraph_yields_single_chunk() -> None:
    parser = TextParser()
    chunks = await parser.parse(b"hello world", source="greeting.txt")
    assert chunks == [
        Chunk(id="greeting.txt__0", content="hello world", source="greeting.txt", index=0),
    ]

@pytest.mark.asyncio
async def test_blank_line_splits_into_two_chunks_with_sequential_indices() -> None:
    parser = TextParser()
    chunks = await parser.parse(b"first para\n\nsecond para", source="doc.txt")
    assert chunks == [
        Chunk(id="doc.txt__0", content="first para", source="doc.txt", index=0),
        Chunk(id="doc.txt__1", content="second para", source="doc.txt", index=1),
    ]

@pytest.mark.asyncio
async def test_multiple_blank_lines_and_whitespace_collapse_to_one_split() -> None:
    parser = TextParser()
    payload = b"one\n\n\n  \n\ntwo\r\n\r\nthree"
    chunks = await parser.parse(payload, source="x.txt")
    assert chunks == [
        Chunk(id="x.txt__0", content="one", source="x.txt", index=0),
        Chunk(id="x.txt__1", content="two", source="x.txt", index=1),
        Chunk(id="x.txt__2", content="three", source="x.txt", index=2),
    ]
