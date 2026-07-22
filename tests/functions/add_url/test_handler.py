"""Tests for src/functions/add_url/handler.py."""

from typing import cast
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from backend.core.providers.embedders.base import BaseEmbedder
from backend.core.providers.parsers.base import BaseParser
from backend.core.providers.search.base import BaseSearch
from backend.core.types import Chunk, EmbeddingResult, SearchDocument
from functions.add_url import handler as handler_module
from functions.add_url.handler import AddUrlRequest, add_url_handler


class _StubParser(BaseParser):
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        self.calls: list[tuple[bytes, str]] = []

    async def parse(self, content: bytes, *, source: str) -> list[Chunk]:
        self.calls.append((content, source))
        return list(self._chunks)


class _StubEmbedder(BaseEmbedder):
    def __init__(self, results: list[EmbeddingResult]) -> None:
        self._results = results
        self.calls: list[list[Chunk]] = []

    async def embed(self, chunks: list[Chunk]) -> list[EmbeddingResult]:
        self.calls.append(chunks)
        return list(self._results)


def _make_search_provider() -> BaseSearch:
    provider = AsyncMock(spec=["merge_or_upload_documents"])
    provider.merge_or_upload_documents = AsyncMock(return_value=[])
    return cast(BaseSearch, provider)


def _patch_fetch(
    monkeypatch: pytest.MonkeyPatch, payload: bytes
) -> list[tuple[str, object]]:
    """Replace ``fetch_url`` in the handler module with a recorder.

    Returns the call log (``(url, client)`` tuples) so tests can
    assert on the URL and the injected client identity. The patch
    targets the bound symbol in ``handler_module`` rather than the
    original module to mimic the standard ``from x import y``
    isolation pattern.
    """
    calls: list[tuple[str, object]] = []

    async def _fake_fetch_url(
        url: str, *, client: object | None = None, timeout_seconds: float = 30.0
    ) -> bytes:
        calls.append((url, client))
        return payload

    monkeypatch.setattr(handler_module, "fetch_url", _fake_fetch_url)
    return calls


def _request(url: str = "https://example.invalid/page") -> AddUrlRequest:
    return AddUrlRequest(url=url, ingestion_job_id="job-1")


@pytest.mark.asyncio
async def test_pipeline_pushes_documents_with_vectors_and_returns_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"<html>hello world</html>"
    fetch_calls = _patch_fetch(monkeypatch, payload)

    chunks = [
        Chunk(
            id="https://example.invalid/page__0",
            content="hello",
            source="https://example.invalid/page",
            index=0,
        ),
        Chunk(
            id="https://example.invalid/page__1",
            content="world",
            source="https://example.invalid/page",
            index=1,
        ),
    ]
    parser = _StubParser(chunks)
    embedder = _StubEmbedder(
        [EmbeddingResult(vectors=[[0.1, 0.2], [0.3, 0.4]], model="fake")]
    )
    search_provider = _make_search_provider()

    docs = await add_url_handler(_request(), parser, embedder, search_provider)

    assert fetch_calls == [("https://example.invalid/page", None)]
    assert parser.calls == [(payload, "https://example.invalid/page")]
    assert embedder.calls == [chunks]
    assert docs == [
        SearchDocument(
            id="https://example.invalid/page__0",
            content="hello",
            title="https://example.invalid/page",
            content_vector=[0.1, 0.2],
        ),
        SearchDocument(
            id="https://example.invalid/page__1",
            content="world",
            title="https://example.invalid/page",
            content_vector=[0.3, 0.4],
        ),
    ]
    search_provider.merge_or_upload_documents.assert_awaited_once_with(  # type: ignore[attr-defined]
        documents=docs
    )


@pytest.mark.asyncio
async def test_zero_chunks_short_circuits_embed_and_search(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _patch_fetch(monkeypatch, b"   ")
    parser = _StubParser([])
    embedder = _StubEmbedder([])
    search_provider = _make_search_provider()

    caplog.set_level("INFO", logger="functions.add_url.handler")
    docs = await add_url_handler(_request(), parser, embedder, search_provider)

    assert docs == []
    assert embedder.calls == []
    search_provider.merge_or_upload_documents.assert_not_called()  # type: ignore[attr-defined]
    records = [r for r in caplog.records if r.name == "functions.add_url.handler"]
    assert len(records) == 1
    record = records[0]
    assert record.message == "add_url produced zero chunks"
    assert record.operation == "add_url_handler"  # type: ignore[attr-defined]
    assert record.url == "https://example.invalid/page"  # type: ignore[attr-defined]
    assert record.ingestion_job_id == "job-1"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_vector_count_mismatch_raises_runtimeerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_fetch(monkeypatch, b"hello world")
    chunks = [
        Chunk(
            id="u__0",
            content="hello",
            source="https://example.invalid/page",
            index=0,
        ),
        Chunk(
            id="u__1",
            content="world",
            source="https://example.invalid/page",
            index=1,
        ),
    ]
    parser = _StubParser(chunks)
    # Only 1 vector for 2 chunks -- triggers the mismatch guard.
    embedder = _StubEmbedder([EmbeddingResult(vectors=[[0.1, 0.2]], model="fake")])
    search_provider = _make_search_provider()

    with pytest.raises(RuntimeError, match="vector count mismatch"):
        await add_url_handler(_request(), parser, embedder, search_provider)
    search_provider.merge_or_upload_documents.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_injected_client_is_passed_through_to_fetch_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_calls = _patch_fetch(monkeypatch, b"hello")
    parser = _StubParser(
        [
            Chunk(
                id="u__0",
                content="hello",
                source="https://example.invalid/page",
                index=0,
            )
        ]
    )
    embedder = _StubEmbedder([EmbeddingResult(vectors=[[0.5, 0.6]], model="fake")])
    search_provider = _make_search_provider()
    sentinel_client = object()

    await add_url_handler(
        _request(),
        parser,
        embedder,
        search_provider,
        client=cast("None", sentinel_client),
    )

    assert fetch_calls == [("https://example.invalid/page", sentinel_client)]


def test_add_url_request_rejects_empty_url() -> None:
    with pytest.raises(ValidationError):
        AddUrlRequest(url="")


def test_add_url_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AddUrlRequest(url="https://example.invalid/", junk="x")  # type: ignore[call-arg]


def test_add_url_request_strips_whitespace_on_url() -> None:
    request = AddUrlRequest(url="   https://example.invalid/page   ")
    assert request.url == "https://example.invalid/page"


def test_add_url_request_assigns_default_ingestion_job_id() -> None:
    request_one = AddUrlRequest(url="https://example.invalid/a")
    request_two = AddUrlRequest(url="https://example.invalid/a")
    # Default factory produces a uuid4 string per instance.
    assert request_one.ingestion_job_id != request_two.ingestion_job_id
    assert len(request_one.ingestion_job_id) > 0
