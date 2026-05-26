"""Tests for the embedders provider domain (Phase 6 task #41, U8e).

Pillar: Stable Core
Phase: 6
"""

import pytest

from backend.core.providers.embedders import registry as embedders_registry
from backend.core.providers.embedders.base import BaseEmbedder
from backend.core.registry import Registry
from backend.core.types import Chunk, EmbeddingResult


class _FakeEmbedder(BaseEmbedder):
    """Minimal concrete BaseEmbedder used to exercise the registry."""

    async def embed(self, chunks: list[Chunk]) -> list[EmbeddingResult]:
        vector_count = len(chunks)
        vectors = [[0.1, 0.2] for _ in range(vector_count)]
        return [EmbeddingResult(vectors=vectors, model="fake")]


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> Registry[type[BaseEmbedder]]:
    """Swap the module-level `embedders_registry.registry` for an empty one.

    Tests register fake embedders without polluting the global registry
    that real provider concretes (added in U8f) will populate.
    """
    fresh: Registry[type[BaseEmbedder]] = Registry("embedders")
    monkeypatch.setattr(embedders_registry, "registry", fresh)
    return fresh


def test_registry_is_named_embedders() -> None:
    assert embedders_registry.registry.domain == "embedders"


def test_register_and_create_returns_instance(
    isolated_registry: Registry[type[BaseEmbedder]],
) -> None:
    isolated_registry.register("azure_openai")(_FakeEmbedder)

    embedder = embedders_registry.registry.get("azure_openai")()

    assert isinstance(embedder, _FakeEmbedder)
    assert isinstance(embedder, BaseEmbedder)


def test_create_is_case_insensitive(
    isolated_registry: Registry[type[BaseEmbedder]],
) -> None:
    isolated_registry.register("Azure_OpenAI")(_FakeEmbedder)

    assert isinstance(embedders_registry.registry.get("azure_openai")(), _FakeEmbedder)
    assert isinstance(embedders_registry.registry.get("AZURE_OPENAI")(), _FakeEmbedder)


def test_create_unknown_key_raises_keyerror_listing_available(
    isolated_registry: Registry[type[BaseEmbedder]],
) -> None:
    isolated_registry.register("azure_openai")(_FakeEmbedder)

    with pytest.raises(KeyError) as exc:
        embedders_registry.registry.get("missing")

    assert "azure_openai" in str(exc.value)


def test_duplicate_registration_same_value_is_idempotent(
    isolated_registry: Registry[type[BaseEmbedder]],
) -> None:
    isolated_registry.register("azure_openai")(_FakeEmbedder)
    isolated_registry.register("azure_openai")(_FakeEmbedder)

    assert isinstance(embedders_registry.registry.get("azure_openai")(), _FakeEmbedder)


def test_duplicate_registration_different_value_raises(
    isolated_registry: Registry[type[BaseEmbedder]],
) -> None:
    class _OtherEmbedder(BaseEmbedder):
        async def embed(self, chunks: list[Chunk]) -> list[EmbeddingResult]:
            return [EmbeddingResult(vectors=[], model="other")]

    isolated_registry.register("azure_openai")(_FakeEmbedder)

    with pytest.raises(ValueError):
        isolated_registry.register("azure_openai")(_OtherEmbedder)


def test_baseembedder_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        BaseEmbedder()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_concrete_embedder_returns_embedding_results() -> None:
    embedder = _FakeEmbedder()

    results = await embedder.embed(
        [
            Chunk(id="a__0", content="hello", source="a", index=0),
            Chunk(id="a__1", content="world", source="a", index=1),
        ]
    )

    assert results == [EmbeddingResult(vectors=[[0.1, 0.2], [0.1, 0.2]], model="fake")]
