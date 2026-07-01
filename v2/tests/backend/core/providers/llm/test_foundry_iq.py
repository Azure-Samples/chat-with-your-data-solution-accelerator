"""Tests for the LLM provider domain (Phase 2 task #12).

Pillar: Stable Core
Phase: 2
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import openai
import pytest
from azure.core.exceptions import AzureError, ServiceRequestError

from backend.core.providers.llm import registry as llm_registry
from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.providers.llm.foundry_iq import FoundryIQ
from backend.core.settings import AppSettings
from backend.core.types import ChatChunk, ChatMessage, EmbeddingResult


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
    "AZURE_AI_SERVICES_ENDPOINT": "https://foundry-cwyd001.cognitiveservices.azure.com/",
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
    # `AIProjectClient.get_openai_client()` is synchronous in
    # azure-ai-projects >=2.2.0 -- it returns an `AsyncOpenAI`
    # directly. Use plain `MagicMock(return_value=...)` so production
    # gets the client instead of an unawaited coroutine.
    project.get_openai_client = MagicMock(return_value=openai_client)
    return project


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------


def test_registry_contains_foundry_iq() -> None:
    assert "foundry_iq" in llm_registry.registry


def test_create_returns_foundry_iq(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    provider = llm_registry.registry.get("foundry_iq")(
        settings=settings, credential=fake_credential
    )
    assert isinstance(provider, FoundryIQ)
    assert isinstance(provider, BaseLLMProvider)


def test_unknown_key_raises(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    with pytest.raises(KeyError):
        llm_registry.registry.get("vllm")(
            settings=settings, credential=fake_credential
        )


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
    assert call.kwargs["model"] == "gpt-5.1"
    assert call.kwargs["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_chat_passes_temperature_and_max_completion_tokens(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    """`max_tokens` is sent on the wire as `max_completion_tokens` -- the
    forward-compatible parameter gpt-5 / o-series chat models require (the
    legacy `max_tokens` is rejected with a 400)."""
    openai = MagicMock()
    openai.chat.completions.create = AsyncMock(
        return_value=_build_openai_chat_response("ok")
    )
    provider = FoundryIQ(
        settings, fake_credential, project_client=_build_fake_project_client(openai)
    )
    await provider.chat(
        [ChatMessage(role="user", content="hi")],
        deployment="gpt-5.1-mini",
        temperature=0.2,
        max_tokens=128,
    )
    call = openai.chat.completions.create.await_args
    assert call.kwargs["model"] == "gpt-5.1-mini"
    assert call.kwargs["temperature"] == 0.2
    assert call.kwargs["max_completion_tokens"] == 128
    assert "max_tokens" not in call.kwargs


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


@pytest.mark.asyncio
async def test_chat_stream_passes_max_completion_tokens(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    """The streaming path uses the same `max_completion_tokens` wire name
    as `chat()` (gpt-5 / o-series reject `max_tokens`)."""
    openai = MagicMock()
    openai.chat.completions.create = AsyncMock(
        return_value=_build_openai_chat_stream(["ok"])
    )
    provider = FoundryIQ(
        settings, fake_credential, project_client=_build_fake_project_client(openai)
    )
    async for _ in provider.chat_stream(
        [ChatMessage(role="user", content="hi")], max_tokens=64
    ):
        pass
    call = openai.chat.completions.create.await_args
    assert call.kwargs["max_completion_tokens"] == 64
    assert "max_tokens" not in call.kwargs


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
    project = _build_fake_project_client(openai)
    provider = FoundryIQ(settings, fake_credential, project_client=project)
    result = await provider.embed(["foo", "bar"])
    assert isinstance(result, EmbeddingResult)
    assert result.model == "text-embedding-3-small"
    assert result.dimensions == 3
    assert result.vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    call = openai.embeddings.create.await_args
    assert call.kwargs["input"] == ["foo", "bar"]
    # Embeddings must request the index's vector width, not the model's
    # native default (3072 for text-embedding-3-large).
    assert call.kwargs["dimensions"] == settings.openai.embedding_dimensions
    # Embeddings are routed to the AI Services *account* endpoint via a
    # base_url override -- the Foundry project route doesn't serve them.
    embed_client_call = project.get_openai_client.call_args
    assert (
        embed_client_call.kwargs["base_url"]
        == "https://foundry-cwyd001.cognitiveservices.azure.com/openai/v1"
    )


# ---------------------------------------------------------------------------
# reason() -- Responses API streaming (task #25; refactored 2026-05-08)
# ---------------------------------------------------------------------------


def _build_reason_stream(
    chunks: list[tuple[str, str]],
):
    """Build an async-iterable mimicking a Responses-API streamed response.

    Each tuple is ``(reasoning_summary_delta, output_text_delta)``.
    Either side may be empty to assert the channel-routing logic.
    Events use the typed ``type`` discriminator the production code
    dispatches on:

    - ``"response.reasoning_summary_text.delta"`` -> REASONING channel
    - ``"response.output_text.delta"`` -> ANSWER channel

    A non-empty reasoning chunk + non-empty answer chunk in the same
    tuple yields TWO events (matching the real SDK, where reasoning
    summary deltas and output text deltas are interleaved as
    independent events).
    """
    events: list[Any] = []
    for reasoning, answer in chunks:
        if reasoning:
            events.append(
                SimpleNamespace(
                    type="response.reasoning_summary_text.delta",
                    delta=reasoning,
                )
            )
        if answer:
            events.append(
                SimpleNamespace(
                    type="response.output_text.delta",
                    delta=answer,
                )
            )
    return _async_iter(events)


def _wrap_responses_client(responses_create: AsyncMock) -> Any:
    """Build a fake openai client whose `responses.create` is the given
    AsyncMock and whose other namespaces are inert mocks.

    Required because production code's `_get_openai_client()` returns
    a client object, not just the responses namespace, and pyright +
    runtime both walk attribute access on `chat`/`embeddings` even
    when only `responses` is exercised in a given test.
    """
    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock())),
        embeddings=SimpleNamespace(create=AsyncMock()),
        responses=SimpleNamespace(create=responses_create),
    )


@pytest.mark.asyncio
async def test_reason_routes_to_chat_deployment_and_streams(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    responses_create = AsyncMock(
        return_value=_build_reason_stream(
            [
                ("thinking step 1 ", ""),
                ("step 2", ""),
                ("", "Final "),
                ("", "answer."),
            ]
        )
    )
    openai_client = _wrap_responses_client(responses_create)
    project = _build_fake_project_client(openai_client)
    provider = FoundryIQ(settings, fake_credential, project_client=project)

    events = [
        ev async for ev in provider.reason([ChatMessage(role="user", content="hi")])
    ]

    # Routes to the chat deployment via the Responses API.
    call = responses_create.await_args
    assert call.kwargs["model"] == settings.openai.gpt_deployment
    assert call.kwargs["stream"] is True
    # Responses API uses `input`, not `messages`, and each turn is an
    # explicit `message`-typed item -- the Responses endpoint rejects a
    # bare role/content dict with an empty-`type` error.
    assert call.kwargs["input"] == [
        {"type": "message", "role": "user", "content": "hi"}
    ]
    # Reasoning summary requested -- this is what makes gpt-5 emit
    # ResponseReasoningSummaryTextDeltaEvent on the stream.
    assert call.kwargs["reasoning"] == {"effort": "medium", "summary": "auto"}
    # No temperature / max_tokens for reasoning models.
    assert "temperature" not in call.kwargs
    assert "max_tokens" not in call.kwargs

    channels = [(e.channel, e.content) for e in events]
    assert channels == [
        ("reasoning", "thinking step 1 "),
        ("reasoning", "step 2"),
        ("answer", "Final "),
        ("answer", "answer."),
    ]


def test_to_responses_input_emits_explicitly_typed_message_items() -> None:
    """Each turn maps to an explicit `message`-typed Responses item with a
    plain-string role, so the Responses endpoint classifies it instead of
    rejecting a bare role/content dict with an empty-`type` error (the
    shape Chat Completions `messages` would accept but Responses `input`
    does not)."""
    items = FoundryIQ._to_responses_input(
        [
            ChatMessage(role="system", content="be helpful"),
            ChatMessage(role="user", content="hi"),
            ChatMessage(role="assistant", content="hello"),
        ]
    )

    # Each item is a typed model whose `model_dump()` is the explicit
    # `message` wire shape `reason()` sends to the Responses API.
    assert [item.model_dump() for item in items] == [
        {"type": "message", "role": "system", "content": "be helpful"},
        {"type": "message", "role": "user", "content": "hi"},
        {"type": "message", "role": "assistant", "content": "hello"},
    ]
    # Roles serialize as plain `str`, not `ChatRole` enum members, so the
    # openai SDK emits the bare wire value.
    assert all(type(item.role) is str for item in items)


@pytest.mark.asyncio
async def test_reason_uses_explicit_deployment_override(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    responses_create = AsyncMock(return_value=_build_reason_stream([]))
    openai_client = _wrap_responses_client(responses_create)
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(openai_client),
    )

    _ = [
        ev
        async for ev in provider.reason(
            [ChatMessage(role="user", content="hi")], deployment="o3-mini"
        )
    ]
    assert responses_create.await_args.kwargs["model"] == "o3-mini"


@pytest.mark.asyncio
async def test_reason_emits_error_event_on_stream_failure(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    async def _boom():
        yield SimpleNamespace(
            type="response.reasoning_summary_text.delta",
            delta="t1",
        )
        raise RuntimeError("upstream blew up")

    responses_create = AsyncMock(return_value=_boom())
    openai_client = _wrap_responses_client(responses_create)
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(openai_client),
    )

    events = [
        ev async for ev in provider.reason([ChatMessage(role="user", content="hi")])
    ]
    assert events[0].channel == "reasoning"
    assert events[-1].channel == "error"
    assert events[-1].metadata["code"] == "reason_stream_failed"
    assert "upstream blew up" in events[-1].content


@pytest.mark.asyncio
async def test_reason_raises_when_deployment_missing(
    monkeypatch: pytest.MonkeyPatch, fake_credential: MagicMock
) -> None:
    for key, value in COSMOS_ENV.items():
        if key != "AZURE_OPENAI_GPT_DEPLOYMENT":
            monkeypatch.setenv(key, value)
    monkeypatch.delenv("AZURE_OPENAI_GPT_DEPLOYMENT", raising=False)
    s = AppSettings()
    provider = FoundryIQ(s, fake_credential, project_client=MagicMock())
    iterator = provider.reason([ChatMessage(role="user", content="hi")])
    with pytest.raises(RuntimeError, match="chat deployment"):
        async for _ in iterator:
            pass


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


# ---------------------------------------------------------------------------
# complete() -- ABC-level auto-routing (CU-004a)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_routes_to_chat_for_default_deployment(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    """No explicit deployment + default gpt deployment != reasoning ->
    chat() path, single answer event."""
    openai = MagicMock()
    openai.chat.completions.create = AsyncMock(
        return_value=_build_openai_chat_response("hi back")
    )
    provider = FoundryIQ(
        settings, fake_credential, project_client=_build_fake_project_client(openai)
    )
    provider.supports_reasoning = AsyncMock(return_value=False)  # type: ignore[method-assign]

    events = [
        ev async for ev in provider.complete([ChatMessage(role="user", content="hi")])
    ]

    assert [(e.channel, e.content) for e in events] == [("answer", "hi back")]
    # Confirms chat() (non-streaming) was called, not reason() (streaming).
    assert openai.chat.completions.create.await_args.kwargs["model"] == "gpt-5.1"
    assert "stream" not in openai.chat.completions.create.await_args.kwargs


@pytest.mark.asyncio
async def test_complete_forwards_sampling_to_chat(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    """`complete()` forwards `temperature` / `max_tokens` to the chat()
    branch (sent on the wire as `max_completion_tokens`)."""
    openai = MagicMock()
    openai.chat.completions.create = AsyncMock(
        return_value=_build_openai_chat_response("ok")
    )
    provider = FoundryIQ(
        settings, fake_credential, project_client=_build_fake_project_client(openai)
    )
    provider.supports_reasoning = AsyncMock(return_value=False)  # type: ignore[method-assign]

    _ = [
        ev
        async for ev in provider.complete(
            [ChatMessage(role="user", content="hi")],
            temperature=0.3,
            max_tokens=77,
        )
    ]

    call = openai.chat.completions.create.await_args
    assert call.kwargs["temperature"] == 0.3
    assert call.kwargs["max_completion_tokens"] == 77
    assert "max_tokens" not in call.kwargs


@pytest.mark.asyncio
async def test_complete_streams_reasoning_for_explicit_deployment_when_supported(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    """Explicit deployment + a reasoning-capable model -> reason() path,
    propagates reasoning + answer events in order."""
    responses_create = AsyncMock(
        return_value=_build_reason_stream(
            [
                ("step a ", ""),
                ("step b", ""),
                ("", "Answer."),
            ]
        )
    )
    openai_client = _wrap_responses_client(responses_create)
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(openai_client),
    )
    provider.supports_reasoning = AsyncMock(return_value=True)  # type: ignore[method-assign]

    events = [
        ev
        async for ev in provider.complete(
            [ChatMessage(role="user", content="hi")], deployment="gpt-5.1"
        )
    ]

    assert [(e.channel, e.content) for e in events] == [
        ("reasoning", "step a "),
        ("reasoning", "step b"),
        ("answer", "Answer."),
    ]
    assert responses_create.await_args.kwargs["model"] == "gpt-5.1"
    assert responses_create.await_args.kwargs["stream"] is True


@pytest.mark.asyncio
async def test_complete_uses_chat_with_explicit_override_when_model_lacks_reasoning(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    """A non-reasoning model -> chat(), honoring the explicit deployment
    override."""
    openai = MagicMock()
    openai.chat.completions.create = AsyncMock(
        return_value=_build_openai_chat_response("plain")
    )
    provider = FoundryIQ(
        settings, fake_credential, project_client=_build_fake_project_client(openai)
    )
    provider.supports_reasoning = AsyncMock(return_value=False)  # type: ignore[method-assign]

    events = [
        ev
        async for ev in provider.complete(
            [ChatMessage(role="user", content="hi")], deployment="gpt-5.1"
        )
    ]

    assert [(e.channel, e.content) for e in events] == [("answer", "plain")]
    # chat() was called with the explicit override.
    assert openai.chat.completions.create.await_args.kwargs["model"] == "gpt-5.1"


@pytest.mark.asyncio
async def test_complete_emits_error_event_on_chat_failure(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    """chat() raising -> single error event with the documented code,
    no exception escapes the iterator."""
    openai = MagicMock()
    openai.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
    provider = FoundryIQ(
        settings, fake_credential, project_client=_build_fake_project_client(openai)
    )
    provider.supports_reasoning = AsyncMock(return_value=False)  # type: ignore[method-assign]

    events = [
        ev async for ev in provider.complete([ChatMessage(role="user", content="hi")])
    ]

    assert len(events) == 1
    assert events[0].channel == "error"
    assert events[0].metadata["code"] == "complete_chat_failed"
    assert "boom" in events[0].content


@pytest.mark.asyncio
async def test_complete_propagates_reason_error_events(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    """reason() emits its own error event mid-stream -> complete()
    propagates it unchanged (does NOT wrap with complete_chat_failed)."""
    async def _boom():
        yield SimpleNamespace(
            type="response.reasoning_summary_text.delta",
            delta="thinking",
        )
        raise RuntimeError("reason upstream blew up")

    responses_create = AsyncMock(return_value=_boom())
    openai_client = _wrap_responses_client(responses_create)
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(openai_client),
    )
    provider.supports_reasoning = AsyncMock(return_value=True)  # type: ignore[method-assign]

    events = [
        ev
        async for ev in provider.complete(
            [ChatMessage(role="user", content="hi")], deployment="o4-mini"
        )
    ]

    assert [e.channel for e in events] == ["reasoning", "error"]
    # error event came from reason(), not from complete()'s wrapper.
    assert events[-1].metadata["code"] == "reason_stream_failed"


@pytest.mark.asyncio
async def test_complete_streams_reasoning_when_model_supports_it(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    """A reasoning-capable answer model -> the *answer* (gpt) deployment
    streams through the Responses API with summary requested, emitting
    reasoning + answer events (the substantive thinking-panel content)."""
    responses_create = AsyncMock(
        return_value=_build_reason_stream(
            [
                ("weighing the options ", ""),
                ("", "Final answer."),
            ]
        )
    )
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(
            _wrap_responses_client(responses_create)
        ),
    )
    provider.supports_reasoning = AsyncMock(return_value=True)  # type: ignore[method-assign]

    events = [
        ev async for ev in provider.complete([ChatMessage(role="user", content="hi")])
    ]

    assert [(e.channel, e.content) for e in events] == [
        ("reasoning", "weighing the options "),
        ("answer", "Final answer."),
    ]
    # Capability detected against the ANSWER deployment (gpt-5.1); the
    # answer streams through the Responses API with the summary
    # requested -- this is what makes the answer model emit reasoning.
    provider.supports_reasoning.assert_awaited_once_with("gpt-5.1")
    call = responses_create.await_args
    assert call.kwargs["model"] == "gpt-5.1"
    assert call.kwargs["stream"] is True
    assert call.kwargs["reasoning"] == {"effort": "medium", "summary": "auto"}


@pytest.mark.asyncio
async def test_complete_uses_chat_when_model_lacks_reasoning(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    """A non-reasoning answer model -> base behavior: chat()
    non-streaming, single answer event, Responses API untouched."""
    openai = MagicMock()
    openai.chat.completions.create = AsyncMock(
        return_value=_build_openai_chat_response("plain answer")
    )
    openai.responses.create = AsyncMock()
    provider = FoundryIQ(
        settings, fake_credential, project_client=_build_fake_project_client(openai)
    )
    provider.supports_reasoning = AsyncMock(return_value=False)  # type: ignore[method-assign]

    events = [
        ev async for ev in provider.complete([ChatMessage(role="user", content="hi")])
    ]

    assert [(e.channel, e.content) for e in events] == [("answer", "plain answer")]
    provider.supports_reasoning.assert_awaited_once_with("gpt-5.1")
    openai.responses.create.assert_not_awaited()
    assert "stream" not in openai.chat.completions.create.await_args.kwargs


# ---------------------------------------------------------------------------
# Failure-path coverage (Phase C2d -- provider try/except sweep)
# ---------------------------------------------------------------------------
#
# Per v2/docs/exception_handling_policy.md (Provider entry-points + Lifespan
# rows), every OpenAI / AIProjectClient call at a provider boundary catches
# a narrow SDK exception, logs structured context via `logger.exception`
# (or `logger.warning` for shutdown), and re-raises (or yields an
# OrchestratorEvent for the streaming `reason()` carve-out).
#
# All tests drive an `AsyncMock(side_effect=<SDK error>(...))` at the SDK
# boundary and assert (a) the exception bubbles out unchanged (or is
# converted to an SSE ERROR event for `reason()`), (b) the structured
# log fires at the right level with the canonical `extra` schema
# {"operation": ..., "provider": "foundry_iq", "deployment": ...},
# (c) sibling SDK calls weren't made when one short-circuits the rest.


_FOUNDRY_LOGGER_NAME = "backend.core.providers.llm.foundry_iq"


def _api_error(message: str = "boom") -> openai.APIError:
    """Construct a generic openai.APIError. The base class requires an
    `httpx.Request` (the SDK populates it from the underlying HTTP call);
    a minimal in-memory request is fine for triggering the exception.
    """
    return openai.APIError(
        message,
        httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        body=None,
    )


def _find_record(
    caplog: pytest.LogCaptureFixture,
    operation: str,
    *,
    level: str = "ERROR",
) -> Any:
    matches = [
        r
        for r in caplog.records
        if r.levelname == level and getattr(r, "operation", None) == operation
    ]
    assert len(matches) == 1, (
        f"expected exactly 1 {level} record for operation={operation!r}, "
        f"got {len(matches)}: {[r.getMessage() for r in caplog.records]}"
    )
    return matches[0]


@pytest.mark.asyncio
async def test_get_openai_client_logs_and_reraises_on_azure_error(
    settings: AppSettings,
    fake_credential: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`AIProjectClient.get_openai_client()` lives in azure-core, so AAD /
    DNS / TLS failures surface as `AzureError` subclasses. The wrap must
    catch the umbrella + re-raise.
    """
    project = MagicMock(name="AIProjectClient")
    project.get_openai_client = MagicMock(
        side_effect=ServiceRequestError(message="DNS lookup failed")
    )
    provider = FoundryIQ(settings, fake_credential, project_client=project)

    with caplog.at_level("ERROR", logger=_FOUNDRY_LOGGER_NAME):
        with pytest.raises(AzureError):
            await provider.chat([ChatMessage(role="user", content="hi")])

    record = _find_record(caplog, "get_openai_client")
    assert record.provider == "foundry_iq"


@pytest.mark.asyncio
async def test_chat_logs_and_reraises_on_openai_api_error(
    settings: AppSettings,
    fake_credential: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    chat_completions = MagicMock()
    chat_completions.create = AsyncMock(side_effect=_api_error("rate limited"))
    openai_client = SimpleNamespace(
        chat=SimpleNamespace(completions=chat_completions),
        embeddings=SimpleNamespace(create=AsyncMock()),
    )
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(openai_client),
    )

    with caplog.at_level("ERROR", logger=_FOUNDRY_LOGGER_NAME):
        with pytest.raises(openai.APIError):
            await provider.chat([ChatMessage(role="user", content="hi")])

    record = _find_record(caplog, "chat")
    assert record.provider == "foundry_iq"
    assert record.deployment == "gpt-5.1"
    chat_completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_stream_logs_and_reraises_on_create_api_error(
    settings: AppSettings,
    fake_credential: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Pre-stream failure (auth / throttle on the initial create call)
    must surface a distinct `chat_stream_create` log line and re-raise
    before any iteration is attempted.
    """
    chat_completions = MagicMock()
    chat_completions.create = AsyncMock(side_effect=_api_error("auth failed"))
    openai_client = SimpleNamespace(
        chat=SimpleNamespace(completions=chat_completions),
        embeddings=SimpleNamespace(create=AsyncMock()),
    )
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(openai_client),
    )

    with caplog.at_level("ERROR", logger=_FOUNDRY_LOGGER_NAME):
        with pytest.raises(openai.APIError):
            async for _ in provider.chat_stream(
                [ChatMessage(role="user", content="hi")]
            ):
                pass  # pragma: no cover -- never reached

    record = _find_record(caplog, "chat_stream_create")
    assert record.provider == "foundry_iq"
    assert record.deployment == "gpt-5.1"


@pytest.mark.asyncio
async def test_chat_stream_logs_and_reraises_on_iteration_api_error(
    settings: AppSettings,
    fake_credential: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mid-stream failure (server-side timeout, dropped connection)
    must surface a distinct `chat_stream_iter` log line and re-raise.
    Distinct operation tag from the create-failure case so an alert
    on rate-limit-during-iteration can fire separately from
    auth-failure-on-setup.
    """

    async def _failing_iter():
        # First chunk yields normally; second iteration step raises.
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="hel"),
                    finish_reason=None,
                )
            ]
        )
        raise _api_error("server disconnect mid-stream")

    chat_completions = MagicMock()
    chat_completions.create = AsyncMock(return_value=_failing_iter())
    openai_client = SimpleNamespace(
        chat=SimpleNamespace(completions=chat_completions),
        embeddings=SimpleNamespace(create=AsyncMock()),
    )
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(openai_client),
    )

    chunks: list[ChatChunk] = []
    with caplog.at_level("ERROR", logger=_FOUNDRY_LOGGER_NAME):
        with pytest.raises(openai.APIError):
            async for chunk in provider.chat_stream(
                [ChatMessage(role="user", content="hi")]
            ):
                chunks.append(chunk)

    # First chunk surfaced before the failure -- locks the partial-
    # delivery semantics so the FE can render in-flight tokens.
    assert [c.content for c in chunks] == ["hel"]
    record = _find_record(caplog, "chat_stream_iter")
    assert record.provider == "foundry_iq"
    assert record.deployment == "gpt-5.1"


@pytest.mark.asyncio
async def test_embed_logs_and_reraises_on_openai_api_error(
    settings: AppSettings,
    fake_credential: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    embeddings = SimpleNamespace(
        create=AsyncMock(side_effect=_api_error("quota exceeded"))
    )
    openai_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock())),
        embeddings=embeddings,
    )
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(openai_client),
    )

    with caplog.at_level("ERROR", logger=_FOUNDRY_LOGGER_NAME):
        with pytest.raises(openai.APIError):
            await provider.embed(["hello"])

    record = _find_record(caplog, "embed")
    assert record.provider == "foundry_iq"
    assert record.deployment == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_reason_yields_error_event_on_create_api_error(
    settings: AppSettings,
    fake_credential: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`reason()` is the streaming carve-out: pre-stream failures are
    logged AND surfaced as an SSE ERROR event (not re-raised) so the
    FE reasoning panel always gets an explicit error frame instead of
    a generator that just terminates silently.
    """
    responses_create = AsyncMock(side_effect=_api_error("auth failed"))
    openai_client = _wrap_responses_client(responses_create)
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(openai_client),
    )

    events = []
    with caplog.at_level("ERROR", logger=_FOUNDRY_LOGGER_NAME):
        async for ev in provider.reason(
            [ChatMessage(role="user", content="hi")], deployment="o4-mini"
        ):
            events.append(ev)

    # Exactly one ERROR event (no reasoning / answer events emitted
    # because the stream never started).
    assert len(events) == 1
    assert events[0].channel == "error"
    assert events[0].metadata["code"] == "reason_stream_failed"
    record = _find_record(caplog, "reason_create")
    assert record.provider == "foundry_iq"
    assert record.deployment == "o4-mini"


@pytest.mark.asyncio
async def test_reason_logs_iteration_failure_alongside_existing_error_event(
    settings: AppSettings,
    fake_credential: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The pre-existing `except Exception: yield ERROR event` (noqa
    BLE001 -- intentional per ADR 0007) is upgraded in C2d to also call
    `logger.exception` with the canonical extras so App Insights
    captures the failure even when the SSE consumer drops the error
    event. The error-event surface stays unchanged.
    """

    async def _failing_iter():
        yield SimpleNamespace(
            type="response.reasoning_summary_text.delta",
            delta="thi",
        )
        yield SimpleNamespace(
            type="response.output_text.delta",
            delta="answ",
        )
        raise RuntimeError("upstream blew up mid-stream")

    responses_create = AsyncMock(return_value=_failing_iter())
    openai_client = _wrap_responses_client(responses_create)
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(openai_client),
    )

    events = []
    with caplog.at_level("ERROR", logger=_FOUNDRY_LOGGER_NAME):
        async for ev in provider.reason(
            [ChatMessage(role="user", content="hi")], deployment="o4-mini"
        ):
            events.append(ev)

    # Pre-existing surface: reasoning + answer + error.
    assert [e.channel for e in events] == ["reasoning", "answer", "error"]
    # New (C2d): ERROR record emitted with `reason_iter` operation tag,
    # distinct from `reason_create` so iteration vs setup failures alert
    # separately.
    record = _find_record(caplog, "reason_iter")
    assert record.provider == "foundry_iq"
    assert record.deployment == "o4-mini"


@pytest.mark.asyncio
async def test_aclose_swallows_and_warns_on_close_failure(
    settings: AppSettings,
    fake_credential: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shutdown is best-effort: `AIProjectClient.close()` failure must
    NOT raise (the container is going away anyway), but a WARNING log
    must fire so the failure is visible in App Insights.
    """
    project = MagicMock(name="AIProjectClient")
    project.close = AsyncMock(side_effect=ServiceRequestError(message="socket already closed"))
    provider = FoundryIQ(settings, fake_credential)
    # Force production-ownership so aclose() actually calls close().
    provider._project_client = project  # type: ignore[attr-defined]
    provider._project_client_override = None  # type: ignore[attr-defined]

    with caplog.at_level("WARNING", logger=_FOUNDRY_LOGGER_NAME):
        await provider.aclose()  # MUST NOT raise

    record = _find_record(caplog, "aclose", level="WARNING")
    assert record.provider == "foundry_iq"
    project.close.assert_awaited_once()
    # Cached handles cleared even though close() failed (idempotent
    # lifecycle reset for the next aclose() / reuse cycle).
    assert provider._project_client is None  # type: ignore[attr-defined]
    assert provider._openai_client is None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# supports_reasoning() -- per-deployment capability probe + cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_supports_reasoning_probes_once_and_caches_true(
    settings: AppSettings, fake_credential: MagicMock
) -> None:
    """A 200 from the Responses-API probe -> capability True, cached so a
    second call does not re-probe. The probe targets the resolved answer
    deployment with a reasoning summary requested and a capped output."""
    responses_create = AsyncMock(return_value=SimpleNamespace())
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(
            _wrap_responses_client(responses_create)
        ),
    )

    first = await provider.supports_reasoning()
    second = await provider.supports_reasoning()

    assert first is True
    assert second is True
    responses_create.assert_awaited_once()
    call = responses_create.await_args
    assert call.kwargs["model"] == "gpt-5.1"
    assert call.kwargs["reasoning"] == {"effort": "low", "summary": "auto"}
    assert call.kwargs["stream"] is False
    assert call.kwargs["max_output_tokens"] == 256


@pytest.mark.asyncio
async def test_supports_reasoning_caches_false_on_reasoning_rejection(
    settings: AppSettings,
    fake_credential: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An explicit `reasoning`-parameter 400 -> capability False, cached
    (the model definitively cannot reason), and surfaced at INFO."""
    responses_create = AsyncMock(
        side_effect=_api_error(
            "Unsupported parameter: 'reasoning' is not supported with this model."
        )
    )
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(
            _wrap_responses_client(responses_create)
        ),
    )

    with caplog.at_level("INFO", logger=_FOUNDRY_LOGGER_NAME):
        first = await provider.supports_reasoning()
        second = await provider.supports_reasoning()

    assert first is False
    assert second is False
    responses_create.assert_awaited_once()
    record = _find_record(caplog, "supports_reasoning", level="INFO")
    assert record.deployment == "gpt-5.1"


@pytest.mark.asyncio
async def test_supports_reasoning_does_not_cache_transient_failure(
    settings: AppSettings,
    fake_credential: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A transient / unrelated error (throttle, auth, 5xx) is NOT a
    capability verdict: report False WITHOUT caching and re-probe on the
    next call (which here succeeds -> True)."""
    responses_create = AsyncMock(
        side_effect=[_api_error("Rate limit reached. Please retry."), SimpleNamespace()]
    )
    provider = FoundryIQ(
        settings,
        fake_credential,
        project_client=_build_fake_project_client(
            _wrap_responses_client(responses_create)
        ),
    )

    with caplog.at_level("WARNING", logger=_FOUNDRY_LOGGER_NAME):
        first = await provider.supports_reasoning()
    second = await provider.supports_reasoning()

    assert first is False
    assert second is True
    assert responses_create.await_count == 2
    record = _find_record(caplog, "supports_reasoning", level="WARNING")
    assert record.deployment == "gpt-5.1"


def test_is_reasoning_unsupported_classifies_param_and_message() -> None:
    """The classifier returns True ONLY for an explicit reasoning-param
    rejection (via `.param` or a message naming it as unsupported), never
    for transient / unrelated errors."""
    param_err = openai.APIError(
        "bad request",
        httpx.Request("POST", "https://api.openai.com/v1/responses"),
        body={"param": "reasoning"},
    )
    message_err = _api_error(
        "Unsupported parameter: 'reasoning' is not supported with this model."
    )
    throttle_err = _api_error("Rate limit reached. Please retry.")
    missing_err = _api_error("The model 'gpt-foo' does not exist.")

    assert FoundryIQ._is_reasoning_unsupported(param_err) is True
    assert FoundryIQ._is_reasoning_unsupported(message_err) is True
    assert FoundryIQ._is_reasoning_unsupported(throttle_err) is False
    assert FoundryIQ._is_reasoning_unsupported(missing_err) is False
