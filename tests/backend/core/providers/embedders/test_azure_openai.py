"""Tests for AzureOpenAIEmbedder."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core.exceptions import ServiceRequestError

from backend.core.providers.embedders import registry as embedders_registry
from backend.core.providers.embedders.azure_openai import AzureOpenAIEmbedder
from backend.core.settings import AppSettings
from backend.core.types import Chunk, EmbeddingResult

COSMOS_ENV: dict[str, str] = {
    "AZURE_SOLUTION_SUFFIX": "cwyd001",
    "AZURE_RESOURCE_GROUP": "rg-cwyd-001",
    "AZURE_LOCATION": "eastus2",
    "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000001",
    "AZURE_DB_TYPE": "cosmosdb",
    "AZURE_INDEX_STORE": "AzureSearch",
    "AZURE_COSMOS_ENDPOINT": "https://cosmos-cwyd001.documents.azure.com:443/",
    "AZURE_AI_PROJECT_ENDPOINT": "https://foundry-cwyd001.services.ai.azure.com/api/projects/p1",
    "AZURE_OPENAI_GPT_DEPLOYMENT": "gpt-5.1",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "text-embedding-3-small",
}


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> AppSettings:
    for key, value in COSMOS_ENV.items():
        monkeypatch.setenv(key, value)
    return AppSettings()


@pytest.fixture
def fake_credential() -> MagicMock:
    cred = MagicMock(name="AsyncTokenCredential")
    cred.close = AsyncMock()
    return cred


def test_registry_contains_azure_openai() -> None:
    assert "azure_openai" in embedders_registry.registry


def test_create_returns_azure_openai_embedder(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    embedder = embedders_registry.registry.get("azure_openai")(
        settings=settings,
        credential=fake_credential,
    )

    assert isinstance(embedder, AzureOpenAIEmbedder)


@pytest.mark.asyncio
async def test_embed_forwards_chunk_content_to_llm_provider(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    llm_provider = MagicMock()
    llm_provider.embed = AsyncMock(
        return_value=EmbeddingResult(
            vectors=[[0.1, 0.2], [0.3, 0.4]],
            model="text-embedding-3-small",
        )
    )

    embedder = AzureOpenAIEmbedder(
        settings=settings,
        credential=fake_credential,
        llm_provider=llm_provider,
    )
    chunks = [
        Chunk(id="a__0", content="hello", source="a", index=0),
        Chunk(id="a__1", content="world", source="a", index=1),
    ]

    results = await embedder.embed(chunks)

    llm_provider.embed.assert_awaited_once_with(
        ["hello", "world"],
        deployment="text-embedding-3-small",
    )
    assert results == [
        EmbeddingResult(
            vectors=[[0.1, 0.2], [0.3, 0.4]],
            model="text-embedding-3-small",
        )
    ]


@pytest.mark.asyncio
async def test_embed_batches_inputs_over_the_array_cap(
    settings: AppSettings,
    fake_credential: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A document whose chunk count exceeds the Azure OpenAI input-array cap
    # must be embedded in bounded batches (each request <= the cap) and its
    # vectors concatenated, not sent as one over-long request.
    monkeypatch.setattr(
        "backend.core.providers.embedders.azure_openai._MAX_EMBED_INPUTS", 2
    )

    async def fake_embed(
        inputs: list[str], *, deployment: str | None
    ) -> EmbeddingResult:
        return EmbeddingResult(
            vectors=[[float(len(text))] for text in inputs],
            model="text-embedding-3-small",
        )

    llm_provider = MagicMock()
    llm_provider.embed = AsyncMock(side_effect=fake_embed)

    embedder = AzureOpenAIEmbedder(
        settings=settings,
        credential=fake_credential,
        llm_provider=llm_provider,
    )
    chunks = [
        Chunk(id=f"a__{i}", content=f"chunk-{i}", source="a", index=i) for i in range(5)
    ]

    results = await embedder.embed(chunks)

    # 5 chunks, cap 2 -> batches of [2, 2, 1] = 3 provider calls.
    assert llm_provider.embed.await_count == 3
    batched_inputs = [call.args[0] for call in llm_provider.embed.await_args_list]
    assert batched_inputs == [
        ["chunk-0", "chunk-1"],
        ["chunk-2", "chunk-3"],
        ["chunk-4"],
    ]
    total_vectors = sum(len(result.vectors) for result in results)
    assert total_vectors == 5


@pytest.mark.asyncio
async def test_embed_empty_chunks_returns_empty_list(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    llm_provider = MagicMock()
    llm_provider.embed = AsyncMock()

    embedder = AzureOpenAIEmbedder(
        settings=settings,
        credential=fake_credential,
        llm_provider=llm_provider,
    )

    results = await embedder.embed([])

    assert results == []
    llm_provider.embed.assert_not_called()


@pytest.mark.asyncio
async def test_embed_raises_on_vector_count_mismatch(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    llm_provider = MagicMock()
    llm_provider.embed = AsyncMock(
        return_value=EmbeddingResult(
            vectors=[[0.1, 0.2]],
            model="text-embedding-3-small",
        )
    )

    embedder = AzureOpenAIEmbedder(
        settings=settings,
        credential=fake_credential,
        llm_provider=llm_provider,
    )

    with pytest.raises(RuntimeError, match="Embedding vector count mismatch"):
        await embedder.embed(
            [
                Chunk(id="a__0", content="hello", source="a", index=0),
                Chunk(id="a__1", content="world", source="a", index=1),
            ]
        )


@pytest.mark.asyncio
async def test_embed_reraises_azure_errors(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    llm_provider = MagicMock()
    llm_provider.embed = AsyncMock(side_effect=ServiceRequestError("network boom"))

    embedder = AzureOpenAIEmbedder(
        settings=settings,
        credential=fake_credential,
        llm_provider=llm_provider,
    )

    with pytest.raises(ServiceRequestError, match="network boom"):
        await embedder.embed([Chunk(id="a__0", content="x", source="a", index=0)])


@pytest.mark.asyncio
async def test_aclose_closes_owned_llm_provider(
    settings: AppSettings,
    fake_credential: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owned_provider = SimpleNamespace(
        embed=AsyncMock(
            return_value=EmbeddingResult(
                vectors=[[0.1, 0.2]], model="text-embedding-3-small"
            )
        ),
        aclose=AsyncMock(),
    )

    monkeypatch.setattr(
        "backend.core.providers.embedders.azure_openai.llm_registry.registry.get",
        lambda _: lambda **__: owned_provider,
    )

    embedder = AzureOpenAIEmbedder(settings=settings, credential=fake_credential)
    await embedder.embed([Chunk(id="a__0", content="x", source="a", index=0)])
    await embedder.aclose()

    owned_provider.aclose.assert_awaited_once()
