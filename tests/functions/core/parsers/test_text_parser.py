"""Tests for `TextParser`."""

from unittest.mock import Mock

import pytest

from backend.core.providers.parsers.base import BaseParser
from backend.core.settings import AppSettings
from backend.core.types import Chunk
from functions.core.parsers import registry as ingestion_parsers_registry
from functions.core.parsers.text_parser import TextParser


def test_textparser_is_registered_under_txt() -> None:
    assert ingestion_parsers_registry.registry.get("txt") is TextParser


def test_textparser_is_registered_under_md_and_json() -> None:
    """Markdown + JSON are UTF-8 text, so they route to the same
    TextParser (v1 supported all three)."""
    assert ingestion_parsers_registry.registry.get("md") is TextParser
    assert ingestion_parsers_registry.registry.get("json") is TextParser


def test_textparser_is_a_baseparser_subclass() -> None:
    assert issubclass(TextParser, BaseParser)


def test_registry_get_txt_constructs_textparser_instance() -> None:
    parser = ingestion_parsers_registry.registry.get("txt")()
    assert isinstance(parser, TextParser)


def test_textparser_zero_arg_construction_still_works() -> None:
    """Defaults to `None` on both `BaseParser.__init__` kwargs so
    pure-CPU parsers stay constructible without arguments and
    existing zero-arg call sites keep working."""
    parser = TextParser()
    assert isinstance(parser, TextParser)
    assert parser._settings is None
    assert parser._credential is None


def test_textparser_stores_uniform_construction_kwargs() -> None:
    """`BaseParser` accepts and stores `(settings, credential)` so
    every parser can be wired by blueprints with the same
    `cls(settings=settings, credential=credential)` line as
    `BaseEmbedder` subclasses (uniform construction contract)."""
    settings = Mock(spec=AppSettings)
    credential = Mock()
    parser = TextParser(settings=settings, credential=credential)
    assert parser._settings is settings
    assert parser._credential is credential


@pytest.mark.asyncio
async def test_single_paragraph_yields_single_chunk() -> None:
    parser = TextParser()
    chunks = await parser.parse(b"hello world", source="greeting.txt")
    assert chunks == [
        Chunk(
            id=BaseParser.make_chunk_id("greeting.txt", 0),
            content="hello world",
            source="greeting.txt",
            index=0,
        ),
    ]


@pytest.mark.asyncio
async def test_blank_line_splits_into_two_chunks_with_sequential_indices() -> None:
    parser = TextParser()
    chunks = await parser.parse(b"first para\n\nsecond para", source="doc.txt")
    assert chunks == [
        Chunk(
            id=BaseParser.make_chunk_id("doc.txt", 0),
            content="first para",
            source="doc.txt",
            index=0,
        ),
        Chunk(
            id=BaseParser.make_chunk_id("doc.txt", 1),
            content="second para",
            source="doc.txt",
            index=1,
        ),
    ]


@pytest.mark.asyncio
async def test_multiple_blank_lines_and_whitespace_collapse_to_one_split() -> None:
    parser = TextParser()
    payload = b"one\n\n\n  \n\ntwo\r\n\r\nthree"
    chunks = await parser.parse(payload, source="x.txt")
    assert chunks == [
        Chunk(
            id=BaseParser.make_chunk_id("x.txt", 0),
            content="one",
            source="x.txt",
            index=0,
        ),
        Chunk(
            id=BaseParser.make_chunk_id("x.txt", 1),
            content="two",
            source="x.txt",
            index=1,
        ),
        Chunk(
            id=BaseParser.make_chunk_id("x.txt", 2),
            content="three",
            source="x.txt",
            index=2,
        ),
    ]
