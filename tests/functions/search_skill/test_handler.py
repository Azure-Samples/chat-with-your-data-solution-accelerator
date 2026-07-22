"""Tests for src/functions/search_skill/handler.py."""

import pytest

from backend.core.providers.embedders.base import BaseEmbedder
from backend.core.types import Chunk, EmbeddingResult
from functions.search_skill.handler import search_skill_handler
from functions.search_skill.models import (
    SearchSkillInputData,
    SearchSkillInputRecord,
    SearchSkillOutputData,
    SearchSkillOutputRecord,
    SearchSkillRequest,
    SearchSkillResponse,
)


class _StubEmbedder(BaseEmbedder):
    """Embedder stub that records the chunks it received and returns canned results."""

    def __init__(self, results: list[EmbeddingResult]) -> None:
        self._results = results
        self.calls: list[list[Chunk]] = []

    async def embed(self, chunks: list[Chunk]) -> list[EmbeddingResult]:
        self.calls.append(chunks)
        return list(self._results)


class _RaisingEmbedder(BaseEmbedder):
    """Embedder stub that always raises the configured exception."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc
        self.calls: list[list[Chunk]] = []

    async def embed(self, chunks: list[Chunk]) -> list[EmbeddingResult]:
        self.calls.append(chunks)
        raise self._exc


def _request(*records: tuple[str, str]) -> SearchSkillRequest:
    """Build a request from ``(record_id, text)`` pairs."""
    return SearchSkillRequest(
        values=[
            SearchSkillInputRecord(record_id=rid, data=SearchSkillInputData(text=text))
            for rid, text in records
        ]
    )


@pytest.mark.asyncio
async def test_embeds_and_returns_response_with_vectors_per_record() -> None:
    request = _request(("1", "hello"), ("2", "world"))
    embedder = _StubEmbedder(
        [EmbeddingResult(vectors=[[0.1, 0.2], [0.3, 0.4]], model="fake")]
    )

    response = await search_skill_handler(request, embedder)

    assert response == SearchSkillResponse(
        values=[
            SearchSkillOutputRecord(
                record_id="1",
                data=SearchSkillOutputData(embedding=[0.1, 0.2]),
            ),
            SearchSkillOutputRecord(
                record_id="2",
                data=SearchSkillOutputData(embedding=[0.3, 0.4]),
            ),
        ]
    )


@pytest.mark.asyncio
async def test_embedder_called_with_synthetic_chunks_built_from_records() -> None:
    request = _request(("a", "alpha"), ("b", "bravo"))
    embedder = _StubEmbedder([EmbeddingResult(vectors=[[0.0], [0.0]], model="fake")])

    await search_skill_handler(request, embedder)

    assert embedder.calls == [
        [
            Chunk(id="a", content="alpha", source="a", index=0),
            Chunk(id="b", content="bravo", source="b", index=1),
        ]
    ]


@pytest.mark.asyncio
async def test_single_record_request_returns_single_record_response() -> None:
    request = _request(("only", "just one"))
    embedder = _StubEmbedder([EmbeddingResult(vectors=[[1.0, 2.0, 3.0]], model="fake")])

    response = await search_skill_handler(request, embedder)

    assert len(response.values) == 1
    assert response.values[0].record_id == "only"
    assert response.values[0].data.embedding == [1.0, 2.0, 3.0]
    assert response.values[0].errors is None
    assert response.values[0].warnings is None


@pytest.mark.asyncio
async def test_response_preserves_request_record_order() -> None:
    request = _request(("z", "z-text"), ("a", "a-text"), ("m", "m-text"))
    embedder = _StubEmbedder(
        [EmbeddingResult(vectors=[[0.1], [0.2], [0.3]], model="fake")]
    )

    response = await search_skill_handler(request, embedder)

    assert [r.record_id for r in response.values] == ["z", "a", "m"]
    assert [r.data.embedding for r in response.values] == [[0.1], [0.2], [0.3]]


@pytest.mark.asyncio
async def test_response_is_search_skill_response_pydantic_model() -> None:
    """Hard Rule #15 receipt: handler returns a typed model, not a dict."""
    request = _request(("1", "hello"))
    embedder = _StubEmbedder([EmbeddingResult(vectors=[[0.1]], model="fake")])

    response = await search_skill_handler(request, embedder)

    assert isinstance(response, SearchSkillResponse)


@pytest.mark.asyncio
async def test_vector_count_mismatch_raises_runtimeerror() -> None:
    request = _request(("1", "hello"), ("2", "world"))
    embedder = _StubEmbedder(
        [EmbeddingResult(vectors=[[0.1, 0.2]], model="fake")]  # 1 vector for 2 records
    )

    with pytest.raises(RuntimeError, match="vector count mismatch"):
        await search_skill_handler(request, embedder)


@pytest.mark.asyncio
async def test_embedder_exception_propagates_to_caller() -> None:
    """Embedder SDK errors already wrapped at the provider boundary (Hard Rule #14)."""
    request = _request(("1", "hello"))
    boom = RuntimeError("openai down")
    embedder = _RaisingEmbedder(boom)

    with pytest.raises(RuntimeError, match="openai down"):
        await search_skill_handler(request, embedder)
    assert embedder.calls == [[Chunk(id="1", content="hello", source="1", index=0)]]


@pytest.mark.asyncio
async def test_handler_flattens_multiple_embedding_result_batches() -> None:
    """Embedders MAY return multiple :class:`EmbeddingResult` batches (e.g., chunked SDK calls)."""
    request = _request(("1", "a"), ("2", "b"), ("3", "c"))
    embedder = _StubEmbedder(
        [
            EmbeddingResult(vectors=[[0.1], [0.2]], model="fake"),
            EmbeddingResult(vectors=[[0.3]], model="fake"),
        ]
    )

    response = await search_skill_handler(request, embedder)

    assert [r.data.embedding for r in response.values] == [[0.1], [0.2], [0.3]]
