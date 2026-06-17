"""Pillar: Stable Core / Phase: 6 — tests for v2/src/functions/batch_push/handler.py."""

from typing import cast
from unittest.mock import AsyncMock

import pytest
from azure.storage.blob.aio import ContainerClient

from backend.core.providers.embedders.base import BaseEmbedder
from backend.core.providers.parsers.base import BaseParser
from backend.core.providers.search.base import BaseSearch
from backend.core.types import Chunk, EmbeddingResult, SearchDocument
from functions.batch_push.handler import batch_push_handler
from functions.core.contracts import BatchPushQueueMessage


class _FakeDownloader:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def readall(self) -> bytes:
        return self._payload


class _FakeContainerClient:
    def __init__(self, *, container_name: str = "documents", payload: bytes = b"") -> None:
        self.container_name = container_name
        self._payload = payload
        self.calls: list[str] = []

    async def download_blob(self, blob: str) -> _FakeDownloader:
        self.calls.append(blob)
        return _FakeDownloader(self._payload)


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


def _as_container(fake: _FakeContainerClient) -> ContainerClient:
    return cast(ContainerClient, fake)


def _message(filename: str = "doc.txt") -> BatchPushQueueMessage:
    return BatchPushQueueMessage(
        container_name="documents",
        filename=filename,
        ingestion_job_id="job-1",
        force_reindex=False,
    )


@pytest.mark.asyncio
async def test_pipeline_pushes_documents_with_vectors_and_returns_them() -> None:
    chunks = [
        Chunk(id="doc.txt__0", content="hello", source="doc.txt", index=0),
        Chunk(id="doc.txt__1", content="world", source="doc.txt", index=1),
    ]
    parser = _StubParser(chunks)
    embedder = _StubEmbedder(
        [EmbeddingResult(vectors=[[0.1, 0.2], [0.3, 0.4]], model="fake")]
    )
    container = _FakeContainerClient(payload=b"hello\n\nworld")
    search_provider = cast(BaseSearch, AsyncMock(spec=["merge_or_upload_documents"]))
    search_provider.merge_or_upload_documents = AsyncMock(return_value=[])  # type: ignore[method-assign]

    docs = await batch_push_handler(
        _message(),
        _as_container(container),
        parser,
        embedder,
        search_provider,
    )

    assert container.calls == ["doc.txt"]
    assert parser.calls == [(b"hello\n\nworld", "doc.txt")]
    assert embedder.calls == [chunks]
    assert docs == [
        SearchDocument(
            id="doc.txt__0",
            content="hello",
            title="doc.txt",
            content_vector=[0.1, 0.2],
        ),
        SearchDocument(
            id="doc.txt__1",
            content="world",
            title="doc.txt",
            content_vector=[0.3, 0.4],
        ),
    ]
    search_provider.merge_or_upload_documents.assert_awaited_once_with(
        documents=docs
    )


@pytest.mark.asyncio
async def test_zero_chunks_short_circuits_embed_and_search(
    caplog: pytest.LogCaptureFixture,
) -> None:
    parser = _StubParser([])
    embedder = _StubEmbedder([])
    container = _FakeContainerClient(payload=b"   ")
    search_provider = cast(BaseSearch, AsyncMock(spec=["merge_or_upload_documents"]))
    search_provider.merge_or_upload_documents = AsyncMock()  # type: ignore[method-assign]

    caplog.set_level("WARNING", logger="functions.batch_push.handler")
    docs = await batch_push_handler(
        _message(),
        _as_container(container),
        parser,
        embedder,
        search_provider,
    )

    assert docs == []
    assert embedder.calls == []
    search_provider.merge_or_upload_documents.assert_not_called()
    records = [r for r in caplog.records if r.name == "functions.batch_push.handler"]
    assert len(records) == 1
    assert records[0].levelname == "WARNING"
    assert records[0].operation == "batch_push_handler"  # type: ignore[attr-defined]
    assert records[0].blob_filename == "doc.txt"  # type: ignore[attr-defined]
    assert records[0].ingestion_job_id == "job-1"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_vector_count_mismatch_raises_runtimeerror() -> None:
    chunks = [
        Chunk(id="doc.txt__0", content="hello", source="doc.txt", index=0),
        Chunk(id="doc.txt__1", content="world", source="doc.txt", index=1),
    ]
    parser = _StubParser(chunks)
    embedder = _StubEmbedder(
        [EmbeddingResult(vectors=[[0.1, 0.2]], model="fake")]  # only 1 vector for 2 chunks
    )
    container = _FakeContainerClient(payload=b"hello\n\nworld")
    search_provider = cast(BaseSearch, AsyncMock(spec=["merge_or_upload_documents"]))
    search_provider.merge_or_upload_documents = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="vector count mismatch"):
        await batch_push_handler(
            _message(),
            _as_container(container),
            parser,
            embedder,
            search_provider,
        )
    search_provider.merge_or_upload_documents.assert_not_called()
