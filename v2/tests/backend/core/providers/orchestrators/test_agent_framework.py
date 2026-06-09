"""Tests for the Agent Framework orchestrator.

Pillar: Stable Core
Phase: 3
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core.exceptions import HttpResponseError

from backend.core.providers.orchestrators import registry as orchestrators_registry
from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.providers.orchestrators.agent_framework import AgentFrameworkOrchestrator
from backend.core.settings import (
    AppSettings,
    FoundrySettings,
    OpenAISettings,
    SearchSettings,
)
from backend.core.types import ChatMessage


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _settings(endpoint: str = "https://example.services.ai.azure.com/api/projects/p1") -> AppSettings:
    settings = MagicMock(spec=AppSettings)
    settings.foundry = MagicMock(spec=FoundrySettings)
    settings.foundry.project_endpoint = endpoint
    settings.search = MagicMock(spec=SearchSettings)
    settings.search.endpoint = "https://srch.example"
    settings.search.knowledge_base_name = "cwyd-kb"
    settings.search.knowledge_source_name = "cwyd-index-ks"
    settings.search.knowledge_base_api_version = "2025-11-01-preview"
    settings.openai = MagicMock(spec=OpenAISettings)
    settings.openai.temperature = 0.0
    settings.openai.max_tokens = 1000
    return settings


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _reasoning_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text_reasoning", text=text)


def _function_call_block(
    *, call_id: str, name: str, arguments: Any
) -> SimpleNamespace:
    return SimpleNamespace(
        type="function_call",
        call_id=call_id,
        name=name,
        arguments=arguments,
    )


def _update(*contents: Any) -> SimpleNamespace:
    return SimpleNamespace(contents=list(contents))


class _FakeAsyncIter:
    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)

    def __aiter__(self) -> "_FakeAsyncIter":
        return self

    async def __anext__(self) -> Any:
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


class _FakeFoundryAgent:
    """Captures construction kwargs + run inputs, returns canned updates."""

    def __init__(
        self,
        *,
        project_endpoint: str,
        agent_name: str,
        credential: Any,
        updates: list[Any] | None = None,
        run_error: Exception | None = None,
        ctor_error: Exception | None = None,
    ) -> None:
        if ctor_error is not None:
            raise ctor_error
        self.project_endpoint = project_endpoint
        self.agent_name = agent_name
        self.credential = credential
        self._updates = updates or []
        self._run_error = run_error
        self.run_calls: list[Any] = []
        self.close = AsyncMock(return_value=None)

    def run(
        self,
        messages: Any,
        *,
        stream: bool = False,
        tools: Any = None,
        options: Any = None,
    ) -> Any:
        self.run_calls.append(
            {
                "messages": messages,
                "stream": stream,
                "tools": tools,
                "options": options,
            }
        )
        if self._run_error is not None:
            raise self._run_error
        return _FakeAsyncIter(self._updates)


def _make_factory(
    *,
    updates: list[Any] | None = None,
    run_error: Exception | None = None,
    ctor_error: Exception | None = None,
) -> tuple[Any, list[_FakeFoundryAgent]]:
    """Return (factory, created_agents_list) so tests can assert on the
    factory call args + on the constructed agent's recorded calls."""
    created: list[_FakeFoundryAgent] = []

    def factory(
        *, project_endpoint: str, agent_name: str, credential: Any
    ) -> _FakeFoundryAgent:
        agent = _FakeFoundryAgent(
            project_endpoint=project_endpoint,
            agent_name=agent_name,
            credential=credential,
            updates=updates,
            run_error=run_error,
            ctor_error=ctor_error,
        )
        created.append(agent)
        return agent

    return factory, created


def _async_credential(*, token: str = "fake-token") -> Any:
    """An AsyncTokenCredential whose get_token returns a fake AccessToken.

    run() awaits credential.get_token(SEARCH_DATA_PLANE_SCOPE) to mint the
    KB bearer, so the default credential must be awaitable and yield an
    object exposing `.token`.
    """
    cred = AsyncMock()
    cred.get_token.return_value = SimpleNamespace(token=token)
    return cred


def _make_orchestrator(
    *,
    agent_name: str = "cwyd",
    settings: AppSettings | None = None,
    credential: Any = None,
    factory: Any = None,
) -> AgentFrameworkOrchestrator:
    return AgentFrameworkOrchestrator(
        settings=settings if settings is not None else _settings(),
        llm=MagicMock(spec=BaseLLMProvider),
        agent_name=agent_name,
        credential=credential if credential is not None else _async_credential(),
        agent_factory=factory,
    )


# ---------------------------------------------------------------------------
# Registration + constructor
# ---------------------------------------------------------------------------


def test_agent_framework_is_registered() -> None:
    assert "agent_framework" in orchestrators_registry.registry.keys()
    assert (
        orchestrators_registry.registry.get("agent_framework")
        is AgentFrameworkOrchestrator
    )


def test_create_returns_agent_framework_instance() -> None:
    factory, _ = _make_factory()
    orch = orchestrators_registry.registry.get("agent_framework")(
        settings=_settings(),
        llm=MagicMock(spec=BaseLLMProvider),
        agent_name="cwyd",
        credential=MagicMock(),
        agent_factory=factory,
    )
    assert isinstance(orch, AgentFrameworkOrchestrator)


def test_constructor_rejects_empty_agent_name() -> None:
    factory, _ = _make_factory()
    with pytest.raises(ValueError, match="agent_name"):
        AgentFrameworkOrchestrator(
            settings=_settings(),
            llm=MagicMock(spec=BaseLLMProvider),
            agent_name="",
            credential=MagicMock(),
            agent_factory=factory,
        )


def test_constructor_rejects_empty_project_endpoint() -> None:
    factory, _ = _make_factory()
    with pytest.raises(ValueError, match="project_endpoint"):
        AgentFrameworkOrchestrator(
            settings=_settings(endpoint=""),
            llm=MagicMock(spec=BaseLLMProvider),
            agent_name="cwyd",
            credential=MagicMock(),
            agent_factory=factory,
        )


def test_constructor_swallows_uniform_extras() -> None:
    """Router forwards `search=` (langgraph-only) to every orchestrator;
    `**_extras` must absorb it without raising."""
    factory, _ = _make_factory()
    orch = AgentFrameworkOrchestrator(
        settings=_settings(),
        llm=MagicMock(spec=BaseLLMProvider),
        agent_name="cwyd",
        credential=MagicMock(),
        agent_factory=factory,
        search=MagicMock(),  # uniform kwarg from router
    )
    assert isinstance(orch, AgentFrameworkOrchestrator)


# ---------------------------------------------------------------------------
# run() behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_constructs_agent_with_endpoint_credential_and_name() -> None:
    cred = _async_credential()
    factory, created = _make_factory(
        updates=[_update(_text_block("hello"))]
    )
    orch = _make_orchestrator(
        settings=_settings(endpoint="https://ep/api/projects/x"),
        credential=cred,
        factory=factory,
        agent_name="cwyd",
    )

    _ = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    assert len(created) == 1
    agent = created[0]
    assert agent.project_endpoint == "https://ep/api/projects/x"
    assert agent.agent_name == "cwyd"
    assert agent.credential is cred


@pytest.mark.asyncio
async def test_run_skips_system_and_tool_messages_when_forwarding_to_agent() -> None:
    factory, created = _make_factory(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(factory=factory)

    _ = [
        ev
        async for ev in orch.run(
            [
                ChatMessage(role="system", content="you are helpful"),
                ChatMessage(role="user", content="hi"),
                ChatMessage(role="tool", content='{"result": 42}'),
                ChatMessage(role="assistant", content="prior reply"),
            ]
        )
    ]

    assert len(created) == 1
    forwarded = created[0].run_calls[0]["messages"]
    # Only user + assistant survive; system + tool are dropped.
    roles = [m.role for m in forwarded]
    assert roles == ["user", "assistant"]


@pytest.mark.asyncio
async def test_run_buffers_text_chunks_into_single_answer_event() -> None:
    factory, _ = _make_factory(
        updates=[
            _update(_text_block("Hello, ")),
            _update(_text_block("world!")),
        ]
    )
    orch = _make_orchestrator(factory=factory)

    events = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    answer_events = [e for e in events if e.channel == "answer"]
    assert len(answer_events) == 1
    assert answer_events[0].content == "Hello, world!"


@pytest.mark.asyncio
async def test_run_emits_reasoning_events_for_text_reasoning_blocks() -> None:
    factory, _ = _make_factory(
        updates=[
            _update(_reasoning_block("looking up docs")),
            _update(_text_block("Final answer.")),
        ]
    )
    orch = _make_orchestrator(factory=factory)

    events = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    pairs = [(e.channel, e.content) for e in events]
    assert pairs == [
        ("reasoning", "looking up docs"),
        ("answer", "Final answer."),
    ]


@pytest.mark.asyncio
async def test_run_emits_tool_events_for_function_call_blocks() -> None:
    factory, _ = _make_factory(
        updates=[
            _update(
                _function_call_block(
                    call_id="call_1",
                    name="search_documents",
                    arguments={"q": "foundry"},
                ),
            ),
            _update(_text_block("done")),
        ]
    )
    orch = _make_orchestrator(factory=factory)

    events = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    pairs = [(e.channel, e.content) for e in events]
    assert pairs == [
        ("tool", "search_documents"),
        ("answer", "done"),
    ]
    tool_event = events[0]
    assert tool_event.metadata == {
        "id": "call_1",
        "type": "function",
        "arguments": '{"q": "foundry"}',
    }


@pytest.mark.asyncio
async def test_run_serializes_string_arguments_as_is() -> None:
    factory, _ = _make_factory(
        updates=[
            _update(
                _function_call_block(
                    call_id="call_2",
                    name="fetch_url",
                    arguments='{"url":"https://x"}',
                ),
            ),
            _update(_text_block("done")),
        ]
    )
    orch = _make_orchestrator(factory=factory)

    events = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    assert events[0].metadata["arguments"] == '{"url":"https://x"}'


@pytest.mark.asyncio
async def test_run_emits_error_event_when_stream_raises_azure_error() -> None:
    factory, _ = _make_factory(
        run_error=HttpResponseError("quota exceeded"),
    )
    orch = _make_orchestrator(factory=factory)

    events = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    assert len(events) == 1
    assert events[0].channel == "error"
    assert "quota exceeded" in events[0].content


@pytest.mark.asyncio
async def test_run_emits_error_event_when_no_content_returned() -> None:
    factory, _ = _make_factory(updates=[])  # empty stream
    orch = _make_orchestrator(factory=factory)

    events = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    assert len(events) == 1
    assert events[0].channel == "error"
    assert "no assistant reply" in events[0].content.lower()


@pytest.mark.asyncio
async def test_run_closes_foundry_agent_in_finally() -> None:
    factory, created = _make_factory(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(factory=factory)

    _ = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    assert len(created) == 1
    created[0].close.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_closes_foundry_agent_even_when_stream_raises() -> None:
    factory, created = _make_factory(
        run_error=HttpResponseError("boom"),
    )
    orch = _make_orchestrator(factory=factory)

    _ = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    assert len(created) == 1
    created[0].close.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_propagates_construction_failure_via_logger() -> None:
    factory, _ = _make_factory(
        ctor_error=HttpResponseError("invalid endpoint"),
    )
    orch = _make_orchestrator(factory=factory)

    with pytest.raises(HttpResponseError):
        _ = [
            ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
        ]


@pytest.mark.asyncio
async def test_aclose_is_a_noop() -> None:
    factory, _ = _make_factory()
    orch = _make_orchestrator(factory=factory)
    # Must not raise -- credential lifecycle is owned by the wiring layer.
    await orch.aclose()


# ---------------------------------------------------------------------------
# _build_kb_tool() -- Foundry IQ Knowledge Base MCP tool construction
# ---------------------------------------------------------------------------


def _settings_with_search(
    *,
    endpoint: str = "https://srch.example",
    kb_name: str = "cwyd-kb",
    api_version: str = "2025-11-01-preview",
) -> AppSettings:
    settings = _settings()
    settings.search.endpoint = endpoint
    settings.search.knowledge_base_name = kb_name
    settings.search.knowledge_base_api_version = api_version
    return settings


def test_build_kb_tool_returns_none_when_search_endpoint_missing() -> None:
    orch = _make_orchestrator(settings=_settings_with_search(endpoint=""))
    assert orch._build_kb_tool(bearer_token="tok") is None


def test_build_kb_tool_returns_none_when_kb_name_missing() -> None:
    orch = _make_orchestrator(settings=_settings_with_search(kb_name=""))
    assert orch._build_kb_tool(bearer_token="tok") is None


def test_build_kb_tool_constructs_managed_mcp_url_with_api_version() -> None:
    orch = _make_orchestrator(
        settings=_settings_with_search(
            endpoint="https://srch.example/",  # trailing slash trimmed
            kb_name="cwyd-kb",
            api_version="2025-11-01-preview",
        )
    )
    tool = orch._build_kb_tool(bearer_token="tok")
    assert tool is not None
    assert tool.name == "cwyd-kb"
    assert tool.url == (
        "https://srch.example/knowledgebases/cwyd-kb/mcp"
        "?api-version=2025-11-01-preview"
    )


def test_build_kb_tool_sets_never_require_and_allowed_tools() -> None:
    orch = _make_orchestrator(settings=_settings_with_search())
    tool = orch._build_kb_tool(bearer_token="tok")
    assert tool is not None
    assert tool.approval_mode == "never_require"
    assert list(tool.allowed_tools or []) == ["knowledge_base_retrieve"]


def test_build_kb_tool_header_provider_injects_bearer() -> None:
    orch = _make_orchestrator(settings=_settings_with_search())
    tool = orch._build_kb_tool(bearer_token="tok123")
    assert tool is not None
    # `_header_provider` is the SDK's private storage for the header hook;
    # poking it directly is the only way to assert the bearer is injected.
    headers = tool._header_provider({"Content-Type": "application/json"})
    assert headers["Authorization"] == "Bearer tok123"
    # Existing headers are preserved (merge, not replace).
    assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# run() KB tool wiring -- token acquisition + tool forwarding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_acquires_search_data_plane_token() -> None:
    cred = _async_credential()
    factory, _ = _make_factory(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(credential=cred, factory=factory)

    _ = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    cred.get_token.assert_awaited_once_with("https://search.azure.com/.default")


@pytest.mark.asyncio
async def test_run_forwards_kb_tool_to_agent() -> None:
    factory, created = _make_factory(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(
        settings=_settings_with_search(
            endpoint="https://srch.example",
            kb_name="cwyd-kb",
            api_version="2025-11-01-preview",
        ),
        factory=factory,
    )

    _ = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    tools = created[0].run_calls[0]["tools"]
    assert tools is not None
    assert len(tools) == 1
    assert tools[0].url == (
        "https://srch.example/knowledgebases/cwyd-kb/mcp"
        "?api-version=2025-11-01-preview"
    )


@pytest.mark.asyncio
async def test_run_skips_token_and_tool_when_kb_unconfigured() -> None:
    cred = _async_credential()
    factory, created = _make_factory(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(
        settings=_settings_with_search(endpoint=""),  # KB not configured
        credential=cred,
        factory=factory,
    )

    _ = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    assert created[0].run_calls[0]["tools"] is None
    cred.get_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_raises_when_token_acquisition_fails() -> None:
    cred = AsyncMock()
    cred.get_token = AsyncMock(side_effect=HttpResponseError("no token"))
    factory, created = _make_factory(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(credential=cred, factory=factory)

    with pytest.raises(HttpResponseError):
        _ = [
            ev
            async for ev in orch.run([ChatMessage(role="user", content="hi")])
        ]
    # The token is acquired before the agent transport, so a failure must
    # surface without constructing (and leaking) an agent.
    assert created == []


# ---------------------------------------------------------------------------
# run() sampling knobs -- temperature / max_tokens via ChatOptions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_threads_temperature_and_max_tokens_via_options() -> None:
    settings = _settings()
    settings.openai.temperature = 0.5
    settings.openai.max_tokens = 256
    factory, created = _make_factory(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(settings=settings, factory=factory)

    _ = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    options = created[0].run_calls[0]["options"]
    assert options is not None
    assert options["temperature"] == 0.5
    assert options["max_tokens"] == 256


@pytest.mark.asyncio
async def test_run_passes_default_sampling_knobs_via_options() -> None:
    factory, created = _make_factory(updates=[_update(_text_block("ok"))])
    orch = _make_orchestrator(factory=factory)  # default _settings()

    _ = [
        ev async for ev in orch.run([ChatMessage(role="user", content="hi")])
    ]

    options = created[0].run_calls[0]["options"]
    assert options is not None
    assert options["temperature"] == 0.0
    assert options["max_tokens"] == 1000
