"""Tests for ``DocumentIntelligenceParser``."""

import logging
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core.exceptions import AzureError

from backend.core.providers.parsers.base import BaseParser
from backend.core.settings import AppSettings
from backend.core.types import Chunk
from functions.core.parsers import document_intelligence_parser as di_parser_module
from functions.core.parsers import registry as ingestion_parsers_registry
from functions.core.parsers.document_intelligence_parser import (
    DocumentIntelligenceParser,
)


def _make_settings(
    *,
    endpoint: str = "https://contoso.cognitiveservices.azure.com",
    model_id: str = "prebuilt-layout",
    api_version: str = "2024-11-30",
) -> AppSettings:
    return cast(
        AppSettings,
        SimpleNamespace(
            foundry=SimpleNamespace(services_endpoint=endpoint),
            document_intelligence=SimpleNamespace(
                model_id=model_id, api_version=api_version
            ),
        ),
    )


def _make_credential() -> Any:
    return MagicMock()


def _make_fake_page(*lines: str) -> SimpleNamespace:
    return SimpleNamespace(lines=[SimpleNamespace(content=ln) for ln in lines])


def _make_fake_paragraph(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(content=content)


def _make_fake_client_with_result(result: Any) -> MagicMock:
    poller = MagicMock()
    poller.result = AsyncMock(return_value=result)
    client = MagicMock()
    client.begin_analyze_document = AsyncMock(return_value=poller)
    client.close = AsyncMock()
    return client


@pytest.mark.parametrize("key", ["pdf", "docx", "jpeg", "jpg", "png"])
def test_document_intelligence_parser_is_registered_under_key(key: str) -> None:
    assert ingestion_parsers_registry.registry.get(key) is DocumentIntelligenceParser


def test_document_intelligence_parser_is_a_baseparser_subclass() -> None:
    assert issubclass(DocumentIntelligenceParser, BaseParser)


def test_construction_stores_settings_credential_and_client_seam() -> None:
    settings = _make_settings()
    credential = _make_credential()
    client = MagicMock()
    parser = DocumentIntelligenceParser(
        settings=settings, credential=credential, client=client
    )
    assert parser._settings is settings
    assert parser._credential is credential
    assert parser._client is client
    assert parser._client_override is client


def test_construction_without_client_leaves_seam_none() -> None:
    parser = DocumentIntelligenceParser(
        settings=_make_settings(), credential=_make_credential()
    )
    assert parser._client is None
    assert parser._client_override is None


def test_get_client_returns_injected_seam_without_constructing_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_ctor = MagicMock(name="DocumentIntelligenceClient_should_not_be_called")
    monkeypatch.setattr(di_parser_module, "DocumentIntelligenceClient", sdk_ctor)
    injected = MagicMock()
    parser = DocumentIntelligenceParser(
        settings=_make_settings(),
        credential=_make_credential(),
        client=injected,
    )
    assert parser._get_client() is injected
    sdk_ctor.assert_not_called()


def test_get_client_constructs_sdk_with_endpoint_from_foundry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed = MagicMock()
    sdk_ctor = MagicMock(return_value=constructed)
    monkeypatch.setattr(di_parser_module, "DocumentIntelligenceClient", sdk_ctor)
    settings = _make_settings(
        endpoint="https://contoso.cognitiveservices.azure.com/",
        api_version="2024-11-30",
    )
    credential = _make_credential()
    parser = DocumentIntelligenceParser(settings=settings, credential=credential)
    got = parser._get_client()
    assert got is constructed
    sdk_ctor.assert_called_once_with(
        endpoint="https://contoso.cognitiveservices.azure.com/",
        credential=credential,
        api_version="2024-11-30",
    )


def test_get_client_normalises_endpoint_to_one_trailing_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_ctor = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(di_parser_module, "DocumentIntelligenceClient", sdk_ctor)
    parser = DocumentIntelligenceParser(
        settings=_make_settings(endpoint="https://contoso.cognitiveservices.azure.com"),
        credential=_make_credential(),
    )
    parser._get_client()
    assert (
        sdk_ctor.call_args.kwargs["endpoint"]
        == "https://contoso.cognitiveservices.azure.com/"
    )


def test_get_client_caches_constructed_sdk_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_ctor = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(di_parser_module, "DocumentIntelligenceClient", sdk_ctor)
    parser = DocumentIntelligenceParser(
        settings=_make_settings(), credential=_make_credential()
    )
    first = parser._get_client()
    second = parser._get_client()
    assert first is second
    sdk_ctor.assert_called_once()


def test_get_client_raises_actionable_error_when_endpoint_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_ctor = MagicMock(name="DocumentIntelligenceClient_should_not_be_called")
    monkeypatch.setattr(di_parser_module, "DocumentIntelligenceClient", sdk_ctor)
    parser = DocumentIntelligenceParser(
        settings=_make_settings(endpoint=""),
        credential=_make_credential(),
    )
    with pytest.raises(ValueError) as excinfo:
        parser._get_client()
    message = str(excinfo.value)
    assert "AZURE_AI_SERVICES_ENDPOINT" in message
    assert "https" in message
    sdk_ctor.assert_not_called()


@pytest.mark.parametrize(
    "bad_endpoint",
    [
        "http://contoso.cognitiveservices.azure.com",
        "/",
        "contoso.cognitiveservices.azure.com",
    ],
)
def test_get_client_raises_actionable_error_when_endpoint_is_not_https(
    monkeypatch: pytest.MonkeyPatch, bad_endpoint: str
) -> None:
    sdk_ctor = MagicMock(name="DocumentIntelligenceClient_should_not_be_called")
    monkeypatch.setattr(di_parser_module, "DocumentIntelligenceClient", sdk_ctor)
    parser = DocumentIntelligenceParser(
        settings=_make_settings(endpoint=bad_endpoint),
        credential=_make_credential(),
    )
    with pytest.raises(ValueError) as excinfo:
        parser._get_client()
    assert "AZURE_AI_SERVICES_ENDPOINT" in str(excinfo.value)
    sdk_ctor.assert_not_called()


def test_get_client_injected_seam_bypasses_endpoint_validation() -> None:
    injected = MagicMock()
    parser = DocumentIntelligenceParser(
        settings=_make_settings(endpoint=""),
        credential=_make_credential(),
        client=injected,
    )
    assert parser._get_client() is injected


@pytest.mark.asyncio
async def test_parse_calls_begin_analyze_document_with_model_id_and_bytes_source() -> (
    None
):
    fake_result = SimpleNamespace(pages=[_make_fake_page("page 1 content")])
    fake_client = _make_fake_client_with_result(fake_result)
    parser = DocumentIntelligenceParser(
        settings=_make_settings(model_id="prebuilt-layout"),
        credential=_make_credential(),
        client=fake_client,
    )
    await parser.parse(b"pdf bytes", source="doc.pdf")
    fake_client.begin_analyze_document.assert_awaited_once()
    call = fake_client.begin_analyze_document.await_args
    assert call.args[0] == "prebuilt-layout"
    assert call.args[1].bytes_source == b"pdf bytes"


@pytest.mark.asyncio
async def test_parse_returns_one_chunk_per_page_with_deterministic_ids() -> None:
    fake_result = SimpleNamespace(
        pages=[
            _make_fake_page("first page line 1", "first page line 2"),
            _make_fake_page("second page only line"),
        ]
    )
    fake_client = _make_fake_client_with_result(fake_result)
    parser = DocumentIntelligenceParser(
        settings=_make_settings(),
        credential=_make_credential(),
        client=fake_client,
    )
    chunks = await parser.parse(b"...", source="report.pdf")
    assert chunks == [
        Chunk(
            id=BaseParser.make_chunk_id("report.pdf", 0),
            content="first page line 1\nfirst page line 2",
            source="report.pdf",
            index=0,
        ),
        Chunk(
            id=BaseParser.make_chunk_id("report.pdf", 1),
            content="second page only line",
            source="report.pdf",
            index=1,
        ),
    ]


@pytest.mark.asyncio
async def test_parse_skips_pages_with_no_lines_or_whitespace_content() -> None:
    fake_result = SimpleNamespace(
        pages=[
            _make_fake_page("real page"),
            SimpleNamespace(lines=None),
            SimpleNamespace(lines=[]),
            _make_fake_page("   ", ""),
            _make_fake_page("another real page"),
        ]
    )
    fake_client = _make_fake_client_with_result(fake_result)
    parser = DocumentIntelligenceParser(
        settings=_make_settings(),
        credential=_make_credential(),
        client=fake_client,
    )
    chunks = await parser.parse(b"...", source="sparse.pdf")
    assert [c.id for c in chunks] == [
        BaseParser.make_chunk_id("sparse.pdf", 0),
        BaseParser.make_chunk_id("sparse.pdf", 1),
    ]
    assert [c.content for c in chunks] == ["real page", "another real page"]


@pytest.mark.asyncio
async def test_parse_returns_empty_list_when_result_has_no_pages_or_paragraphs() -> (
    None
):
    fake_client = _make_fake_client_with_result(
        SimpleNamespace(pages=None, paragraphs=None)
    )
    parser = DocumentIntelligenceParser(
        settings=_make_settings(),
        credential=_make_credential(),
        client=fake_client,
    )
    assert await parser.parse(b"...", source="empty.pdf") == []


@pytest.mark.asyncio
async def test_parse_falls_back_to_paragraphs_when_pages_have_no_lines() -> None:
    # Office / HTML shape: Document Intelligence returns a single pageless
    # page with empty lines and puts the extracted text in `paragraphs`.
    # Short paragraphs are grouped into one chunk (joined with a blank line)
    # rather than emitted one per paragraph.
    fake_result = SimpleNamespace(
        pages=[SimpleNamespace(lines=[])],
        paragraphs=[
            _make_fake_paragraph("First paragraph."),
            _make_fake_paragraph("Second paragraph."),
        ],
    )
    fake_client = _make_fake_client_with_result(fake_result)
    parser = DocumentIntelligenceParser(
        settings=_make_settings(),
        credential=_make_credential(),
        client=fake_client,
    )
    chunks = await parser.parse(b"...", source="press.docx")
    assert chunks == [
        Chunk(
            id=BaseParser.make_chunk_id("press.docx", 0),
            content="First paragraph.\n\nSecond paragraph.",
            source="press.docx",
            index=0,
        ),
    ]


@pytest.mark.asyncio
async def test_parse_groups_paragraphs_to_target_char_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # With a small target budget, consecutive paragraphs pack into
    # size-bounded chunks (fewer chunks than paragraphs, dense index) instead
    # of one chunk per Document Intelligence paragraph.
    monkeypatch.setattr(di_parser_module, "_FALLBACK_CHUNK_TARGET_CHARS", 15)
    fake_result = SimpleNamespace(
        pages=[SimpleNamespace(lines=[])],
        paragraphs=[_make_fake_paragraph(f"para-{n}") for n in range(1, 6)],
    )
    parser = DocumentIntelligenceParser(
        settings=_make_settings(),
        credential=_make_credential(),
        client=_make_fake_client_with_result(fake_result),
    )
    chunks = await parser.parse(b"...", source="big.docx")
    # 5 paragraphs (6 chars each), target 15 -> groups of [2, 2, 1] = 3 chunks.
    assert [chunk.content for chunk in chunks] == [
        "para-1\n\npara-2",
        "para-3\n\npara-4",
        "para-5",
    ]
    assert [chunk.index for chunk in chunks] == [0, 1, 2]


@pytest.mark.asyncio
async def test_parse_keeps_over_long_paragraph_as_whole_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A single paragraph longer than the target is never split; it becomes
    # its own chunk, and neighbours group around it.
    monkeypatch.setattr(di_parser_module, "_FALLBACK_CHUNK_TARGET_CHARS", 15)
    long_paragraph = "x" * 40
    fake_result = SimpleNamespace(
        pages=[SimpleNamespace(lines=[])],
        paragraphs=[
            _make_fake_paragraph("head"),
            _make_fake_paragraph(long_paragraph),
            _make_fake_paragraph("tail"),
        ],
    )
    parser = DocumentIntelligenceParser(
        settings=_make_settings(),
        credential=_make_credential(),
        client=_make_fake_client_with_result(fake_result),
    )
    chunks = await parser.parse(b"...", source="long.docx")
    assert [chunk.content for chunk in chunks] == ["head", long_paragraph, "tail"]
    assert [chunk.index for chunk in chunks] == [0, 1, 2]


@pytest.mark.asyncio
async def test_parse_prefers_pages_and_skips_paragraph_fallback_when_pages_have_text() -> (
    None
):
    # PDF shape: both `pages[].lines` and `paragraphs` are populated. Chunks
    # must come from the page pass only; the paragraph fallback must not
    # fire, so page content is never duplicated by paragraph content.
    fake_result = SimpleNamespace(
        pages=[_make_fake_page("page line")],
        paragraphs=[_make_fake_paragraph("paragraph that must be ignored")],
    )
    fake_client = _make_fake_client_with_result(fake_result)
    parser = DocumentIntelligenceParser(
        settings=_make_settings(),
        credential=_make_credential(),
        client=fake_client,
    )
    chunks = await parser.parse(b"...", source="report.pdf")
    assert [c.content for c in chunks] == ["page line"]


@pytest.mark.asyncio
async def test_parse_paragraph_fallback_skips_empty_and_keeps_indices_dense() -> None:
    fake_result = SimpleNamespace(
        pages=[],
        paragraphs=[
            _make_fake_paragraph("real one"),
            _make_fake_paragraph("   "),
            _make_fake_paragraph(""),
            _make_fake_paragraph(None),
            _make_fake_paragraph("real two"),
        ],
    )
    fake_client = _make_fake_client_with_result(fake_result)
    parser = DocumentIntelligenceParser(
        settings=_make_settings(),
        credential=_make_credential(),
        client=fake_client,
    )
    chunks = await parser.parse(b"...", source="sparse.docx")
    # Empty / whitespace / None paragraphs are skipped; the two real
    # paragraphs group into a single size-bounded chunk.
    assert [c.id for c in chunks] == [
        BaseParser.make_chunk_id("sparse.docx", 0),
    ]
    assert [c.content for c in chunks] == ["real one\n\nreal two"]


@pytest.mark.asyncio
async def test_parse_wraps_azureerror_with_structured_logger_and_reraises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_client = MagicMock()
    fake_client.begin_analyze_document = AsyncMock(side_effect=AzureError("boom"))
    parser = DocumentIntelligenceParser(
        settings=_make_settings(model_id="prebuilt-layout"),
        credential=_make_credential(),
        client=fake_client,
    )
    with caplog.at_level(
        logging.ERROR, logger="functions.core.parsers.document_intelligence_parser"
    ):
        with pytest.raises(AzureError):
            await parser.parse(b"...", source="bad.pdf")
    record = next(
        r
        for r in caplog.records
        if r.name == "functions.core.parsers.document_intelligence_parser"
    )
    assert record.exc_info is not None
    assert record.__dict__["operation"] == "parse"
    assert record.__dict__["provider"] == "document_intelligence"
    assert record.__dict__["source"] == "bad.pdf"
    assert record.__dict__["model_id"] == "prebuilt-layout"


@pytest.mark.asyncio
async def test_aclose_closes_owned_sdk_client_and_clears_reference() -> None:
    owned = MagicMock()
    owned.close = AsyncMock()
    parser = DocumentIntelligenceParser(
        settings=_make_settings(), credential=_make_credential()
    )
    parser._client = owned
    assert parser._client_override is None
    await parser.aclose()
    owned.close.assert_awaited_once()
    assert parser._client is None


@pytest.mark.asyncio
async def test_aclose_does_not_close_injected_client() -> None:
    injected = MagicMock()
    injected.close = AsyncMock()
    parser = DocumentIntelligenceParser(
        settings=_make_settings(),
        credential=_make_credential(),
        client=injected,
    )
    await parser.aclose()
    injected.close.assert_not_awaited()
    assert parser._client is injected


@pytest.mark.asyncio
async def test_aclose_is_a_noop_when_no_client_has_been_constructed() -> None:
    parser = DocumentIntelligenceParser(
        settings=_make_settings(), credential=_make_credential()
    )
    assert parser._client is None
    await parser.aclose()
    assert parser._client is None
