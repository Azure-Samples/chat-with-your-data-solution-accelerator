"""Tests for the LLM provider domain (Phase 2 task #12).

Pillar: Stable Core
Phase: 2
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from providers import llm
from providers.llm.base import BaseLLMProvider
from providers.llm.foundry_iq import FoundryIQ
from shared.settings import AppSettings
from shared.types import ChatChunk, ChatMessage, EmbeddingResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


COSMOS_ENV: dict[str, str] = {
    "AZURE_SOLUTION_SUFFIX": "cwyd001",
    "AZURE_RESOURCE_GROUP": "rg-cwyd-001",
    "AZURE_LOCATION": "eastus2",
    "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000001",
    "AZURE_DB_TYPE": "cosmosdb",
    "AZURE_INDEX_STORE": "AzureSearch",
    "AZURE_COSMOS_ENDPOINT": "https://cosmos-cwyd001.documents.azure.com:443/",
    "AZURE_AI_PROJECT_ENDPOINT": "https://foundry-cwyd001.services.ai.azure.com/api/projects/p1",
    "AZURE_OPENAI_GPT_DEPLOYMENT": "gpt-4o",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "text-embedding-3-small",
    "AZURE_OPENAI_REASONING_DEPLOYMENT": "o4-mini",
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


def _build_openai_chat_response(content: str) -> Any:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")
        ]
    )


async def _async_iter(items: list[Any]):
    for item in items:
        yield item


def _build_openai_chat_stream(deltas: list[str]):
    events = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content=delta),
                    finish_reason=None if i < len(deltas) - 1 else "stop",
                )
            ]
        )
        for i, delta in enumerate(deltas)
    ]
    return _async_iter(events)


def _build_openai_embedding_response(vectors: list[list[float]]) -> Any:
    return SimpleNamespace(
        data=[SimpleNamespace(embedding=v) for v in vectors]
    )


def _build_fake_project_client(openai_client: Any) -> MagicMock:
    project = MagicMock(name="AIProjectClient")
    project.get_openai_client = MagicMock(return_value=openai_client)
    return project


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------


def test_registry_contains_foundry_iq() -> None:
    assert "foundry_iq" in llm.registry


def test_create_returns_foundry_iq(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    provider = llm.create("foundry_iq", settings=settings, credential=fake_credential)
    assert isinstance(provider, FoundryIQ)
    assert isinstance(provider, BaseLLMProvider)


def test_unknown_key_raises(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    with pytest.raises(KeyError):
        llm.create("vllm", settings=settings, credential=fake_credential)


# ---------------------------------------------------------------------------
# chat()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_calls_openai_with_resolved_deployment(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    openai = MagicMock()
    openai.chat.completions.create = AsyncMock(
        return_value=_build_openai_chat_response("hello world")
    )
    provider = FoundryIQ(
        settings, fake_credential, project_client=_build_fake_project_client(openai)
    )
    reply = await provider.chat([ChatMessage(role="user", content="hi")])
    assert isinstance(reply, ChatMessage)
    assert reply.role == "assistant"
    assert reply.content == "hello world"
    call = openai.chat.completions.create.await_args
    assert call.kwargs["model"] == "gpt-4o"
    assert call.kwargs["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_chat_passes_temperature_and_max_tokens(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    openai = MagicMock()
    openai.chat.completions.create = AsyncMock(
        return_value=_build_openai_chat_response("ok")
    )
    provider = FoundryIQ(
        settings, fake_credential, project_client=_build_fake_project_client(openai)
    )
    await provider.chat(
        [ChatMessage(role="user", content="hi")],
        deployment="gpt-4o-mini",
        temperature=0.2,
        max_tokens=128,
    )
    call = openai.chat.completions.create.await_args
    assert call.kwargs["model"] == "gpt-4o-mini"
    assert call.kwargs["temperature"] == 0.2
    assert call.kwargs["max_tokens"] == 128


@pytest.mark.asyncio
async def test_chat_raises_when_no_deployment_configured(
    monkeypatch: pytest.MonkeyPatch, fake_credential: MagicMock
) -> None:
    for key, value in COSMOS_ENV.items():
        if key != "AZURE_OPENAI_GPT_DEPLOYMENT":
            monkeypatch.setenv(key, value)
    monkeypatch.delenv("AZURE_OPENAI_GPT_DEPLOYMENT", raising=False)
    s = AppSettings()
    openai = MagicMock()
    provider = FoundryIQ(
        s, fake_credential, project_client=_build_fake_project_client(openai)
    )
    with pytest.raises(RuntimeError, match="chat deployment"):
        await provider.chat([ChatMessage(role="user", content="hi")])


# ---------------------------------------------------------------------------
# chat_stream()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_stream_yields_chunks(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    openai = MagicMock()
    openai.chat.completions.create = AsyncMock(
        return_value=_build_openai_chat_stream(["hel", "lo"])
    )
    provider = FoundryIQ(
        settings, fake_credential, project_client=_build_fake_project_client(openai)
    )
    chunks: list[ChatChunk] = []
    async for chunk in provider.chat_stream([ChatMessage(role="user", content="hi")]):
        chunks.append(chunk)
    assert [c.content for c in chunks] == ["hel", "lo"]
    assert chunks[-1].finish_reason == "stop"
    assert openai.chat.completions.create.await_args.kwargs["stream"] is True


# ---------------------------------------------------------------------------
# embed()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_returns_vectors(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    openai = MagicMock()
    openai.embeddings.create = AsyncMock(
        return_value=_build_openai_embedding_response([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    )
    provider = FoundryIQ(
        settings, fake_credential, project_client=_build_fake_project_client(openai)
    )
    result = await provider.embed(["foo", "bar"])
    assert isinstance(result, EmbeddingResult)
    assert result.model == "text-embedding-3-small"
    assert result.dimensions == 3
    assert result.vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    call = openai.embeddings.create.await_args
    assert call.kwargs["input"] == ["foo", "bar"]


# ---------------------------------------------------------------------------
# reason() -- task #25 placeholder
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reason_is_not_yet_implemented(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    provider = FoundryIQ(settings, fake_credential, project_client=MagicMock())
    with pytest.raises(NotImplementedError, match="task #25"):
        await provider.reason([ChatMessage(role="user", content="hi")])


# ---------------------------------------------------------------------------
# Lazy AIProjectClient construction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_project_client_raises_when_endpoint_missing(
    monkeypatch: pytest.MonkeyPatch, fake_credential: MagicMock
) -> None:
    for key, value in COSMOS_ENV.items():
        if key != "AZURE_AI_PROJECT_ENDPOINT":
            monkeypatch.setenv(key, value)
    monkeypatch.delenv("AZURE_AI_PROJECT_ENDPOINT", raising=False)
    s = AppSettings()
    provider = FoundryIQ(s, fake_credential)
    with pytest.raises(RuntimeError, match="AZURE_AI_PROJECT_ENDPOINT"):
        await provider.chat([ChatMessage(role="user", content="hi")])


@pytest.mark.asyncio
async def test_aclose_does_not_close_injected_client(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    project = MagicMock()
    project.close = AsyncMock()
    provider = FoundryIQ(settings, fake_credential, project_client=project)
    await provider.aclose()
    project.close.assert_not_called()
