"""Tests for the conversation router."""

import ast
import inspect
import json
from types import SimpleNamespace
from typing import Any, AsyncIterator, Sequence

import httpx
import pytest

from backend.app import create_app
from backend.dependencies import (
    get_agents_provider,
    get_app_settings,
    get_content_safety_guard,
    get_credential,
    get_database_client,
    get_llm_provider,
    get_post_prompt_validator,
    get_search_provider,
)
from backend.core.agents.definitions import (
    CWYD_AGENT,
    CWYD_GUARDRAIL,
    resolve_cwyd_instructions,
)
from backend.core.pipelines import chat as chat_pipeline
from backend.core.providers.orchestrators import registry as orchestrators_registry
from backend.core.providers.orchestrators.base import OrchestratorBase
from backend.core.settings import Environment
from backend.core.types import (
    ChatMessage,
    Conversation,
    MessageRecord,
    OrchestratorEvent,
    RuntimeConfig,
)
from backend.routers import conversation as conv_module

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeOrchestrator(OrchestratorBase):
    """Yields a scripted sequence of events on each ``run()``."""

    scripted: list[OrchestratorEvent] = []
    last_kwargs: dict[str, Any] = {}

    def __init__(self, settings: Any, llm: Any, **extras: Any) -> None:  # noqa: D401
        super().__init__(settings, llm)
        type(self).last_kwargs = dict(extras)

    async def run(  # type: ignore[override]
        self,
        messages: Sequence[ChatMessage],
        *,
        settings_override: dict[str, Any] | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        for ev in type(self).scripted:
            yield ev


class _BoomOrchestrator(OrchestratorBase):
    """Raises mid-stream to exercise the SSE error channel."""

    def __init__(self, settings: Any, llm: Any, **_extras: Any) -> None:
        super().__init__(settings, llm)

    async def run(  # type: ignore[override]
        self,
        messages: Sequence[ChatMessage],
        *,
        settings_override: dict[str, Any] | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        yield OrchestratorEvent(channel="answer", content="partial ")
        raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _fake_settings(orchestrator_name: str = "fake") -> SimpleNamespace:
    """Complete-enough ``AppSettings`` stand-in for the conversation route.

    The route resolves the effective admin config
    (``resolve_effective_config``), which reads the orchestrator,
    OpenAI, search, observability, content-safety, and database
    sub-settings -- a stand-in exposing only ``orchestrator.name``
    would ``AttributeError`` inside the resolver. This mirrors the
    real nested shape with safe defaults (``AzureSearch`` keeps the
    cross-setting guard satisfied for every orchestrator); tests vary
    only ``orchestrator_name``.

    When a test sends no ``x-ms-client-principal-id`` header the route's
    ``user_id`` dependency (``get_user_id``) folds into the anonymous
    default id ``00000000-0000-0000-0000-000000000000``.
    """
    return SimpleNamespace(
        environment=Environment.LOCAL,
        orchestrator=SimpleNamespace(name=orchestrator_name, agent_id=""),
        openai=SimpleNamespace(temperature=0.0, max_tokens=1000),
        search=SimpleNamespace(use_semantic_search=True, top_k=5),
        observability=SimpleNamespace(log_level="INFO"),
        content_safety=SimpleNamespace(enabled=False),
        database=SimpleNamespace(index_store="AzureSearch"),
    )


class _FakeAgentsProvider:
    """Stand-in for `FoundryAgentsProvider` in router tests.

    `get_client()` returns a sentinel object so tests can assert the
    router forwards the *exact* provider instance into the
    ``orchestrators_registry.registry.get(...)(...)`` dispatch call.

    `get_or_create_agent()` records calls in `resolver_calls`. The
    router no longer bootstraps the agent itself -- create-if-missing
    moved into the provider's `build_agent`, invoked by the
    `agent_framework` orchestrator -- so the router tests assert
    `resolver_calls` stays empty (the router never calls it) and that
    the provider + DB client are forwarded into orchestrator
    construction instead.
    """

    def __init__(
        self,
        client: object | None = None,
        agent_id_to_return: str = "resolved-agent-id",
    ) -> None:
        self.client = client if client is not None else object()
        self.get_client_calls = 0
        self.agent_id_to_return = agent_id_to_return
        self.resolver_calls: list[dict[str, Any]] = []

    def get_client(self) -> object:
        self.get_client_calls += 1
        return self.client

    async def get_or_create_agent(self, definition: Any, db: Any) -> str:
        self.resolver_calls.append({"definition": definition, "db": db})
        return self.agent_id_to_return


class _FakeDatabaseClient:
    """Sentinel DB client. The router forwards this instance into the
    agents resolver; all assertions in this test module check
    *identity* (``is db_sentinel``), never behavior, because the
    resolver itself is faked at the agents-provider seam.
    """


class _RecordingDatabaseClient:
    """Recorder implementing the three methods ``persist_turn`` touches.

    Unlike the bare ``_FakeDatabaseClient`` sentinel (used only for
    identity assertions in the orchestrator-forwarding tests), this
    fake records the create / append calls so the persistence tests can
    assert a turn was titled with the question and written
    user-then-assistant, and echoes a fixed ``conv-new`` id back through
    the route. Mirrors the ``_FakeDB`` in ``test_services_conversation``.
    """

    def __init__(self, *, existing: Conversation | None = None) -> None:
        self._existing = existing
        self.created: list[tuple[str, str]] = []
        self.added: list[tuple[str, str, ChatMessage]] = []

    async def get_conversation(
        self, conversation_id: str, user_id: str
    ) -> Conversation | None:
        existing = self._existing
        if (
            existing is not None
            and existing.id == conversation_id
            and existing.user_id == user_id
        ):
            return existing
        return None

    async def create_conversation(self, user_id: str, title: str) -> Conversation:
        self.created.append((user_id, title))
        return Conversation(id="conv-new", user_id=user_id, title=title)

    async def add_message(
        self, conversation_id: str, user_id: str, message: ChatMessage
    ) -> MessageRecord:
        self.added.append((conversation_id, user_id, message))
        return MessageRecord(
            id=f"msg-{len(self.added)}",
            conversation_id=conversation_id,
            role=message.role,
            content=message.content,
        )


@pytest.fixture
def app_with_fakes(monkeypatch: pytest.MonkeyPatch):
    """Build the app, register fakes in the orchestrator registry, and DI-override settings + llm + agents."""
    monkeypatch.setitem(
        orchestrators_registry.registry._items, "fake", _FakeOrchestrator
    )
    monkeypatch.setitem(
        orchestrators_registry.registry._items, "boom", _BoomOrchestrator
    )

    app = create_app()
    app.dependency_overrides[get_app_settings] = lambda: _fake_settings()
    app.dependency_overrides[get_llm_provider] = lambda: object()
    # Always override the agents provider: ASGITransport doesn't run
    # lifespan, so `app.state.agents_provider` is never set. Without
    # this default the router's `agents.get_client()` would 500 even
    # for orchestrators that don't use it (langgraph swallows the
    # kwarg via `**_extras` -- Hard Rule #4: no name dispatch).
    app.dependency_overrides[get_agents_provider] = lambda: _FakeAgentsProvider()
    # Same reason: the chat route wires `db: DatabaseClientDep` into the
    # handler. Even orchestrators that never trigger the resolver
    # (anything other than `agent_framework`) need the DI to resolve
    # so FastAPI can satisfy the signature.
    app.dependency_overrides[get_database_client] = lambda: _FakeDatabaseClient()
    # The router forwards a `CredentialDep` into every orchestrator
    # constructor (the `agent_framework` orchestrator uses it to build
    # a per-request `FoundryAgent`; `langgraph` swallows the kwarg via
    # `**_extras`). ASGITransport doesn't run lifespan, so we override
    # with a per-test sentinel that individual tests can replace when
    # they want to assert the credential was forwarded.
    app.state.test_credential_sentinel = object()
    app.dependency_overrides[get_credential] = (
        lambda: app.state.test_credential_sentinel
    )
    return app


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def _spy_orchestrator_dispatch(
    monkeypatch: pytest.MonkeyPatch, recorded: list[str]
) -> None:
    """Record the registry key each orchestrator dispatch resolves.

    The bootstrap resolver call used to be the signal for which branch
    the router took; with create-if-missing moved into the provider's
    `build_agent`, the router no longer calls the resolver, so
    selection tests observe the single
    ``orchestrators_registry.registry.get(...)`` key directly.
    """
    real_get = orchestrators_registry.registry.get

    def _spy(key: str) -> Any:
        recorded.append(key)
        return real_get(key)

    monkeypatch.setattr(orchestrators_registry.registry, "get", _spy)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_json_mode_concatenates_answer_and_dedupes_citations(
    app_with_fakes,
) -> None:
    _FakeOrchestrator.scripted = [
        OrchestratorEvent(channel="reasoning", content="thinking"),
        OrchestratorEvent(channel="answer", content="Hello, "),
        OrchestratorEvent(channel="answer", content="world!"),
        OrchestratorEvent(
            channel="citation",
            metadata={"id": "doc1", "title": "Doc 1", "url": "https://x/1"},
        ),
        OrchestratorEvent(
            channel="citation",
            metadata={"id": "doc1", "title": "Doc 1 dup", "url": "https://x/1"},
        ),
        OrchestratorEvent(
            channel="citation",
            metadata={"id": "doc2", "title": "Doc 2", "url": "https://x/2"},
        ),
    ]

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "conversation_id": "c-1",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["content"] == "Hello, world!"
    assert body["conversation_id"] == "c-1"
    assert [c["id"] for c in body["citations"]] == ["doc1", "doc2"]


async def test_sse_mode_emits_one_frame_per_event(app_with_fakes) -> None:
    _FakeOrchestrator.scripted = [
        OrchestratorEvent(channel="reasoning", content="step 1"),
        OrchestratorEvent(channel="answer", content="ok"),
    ]

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hi"}]},
            headers={"Accept": "text/event-stream"},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    text = resp.text
    frames = [f for f in text.split("\n\n") if f]
    assert len(frames) == 2
    assert frames[0].startswith("event: reasoning\n")
    assert frames[1].startswith("event: answer\n")
    # Body of the second frame parses as JSON with the answer content.
    data_line = [ln for ln in frames[1].splitlines() if ln.startswith("data: ")][0]
    assert json.loads(data_line[len("data: ") :]) == {"content": "ok", "metadata": {}}


async def test_sse_mode_surfaces_orchestrator_exception_as_error_event(
    app_with_fakes,
) -> None:
    # Use the boom orchestrator instead of the scripted fake. The
    # effective-config resolver reads the full settings shape, so the
    # stand-in is built via `_fake_settings(...)`; only the
    # orchestrator name ("boom") matters for this path.
    app_with_fakes.dependency_overrides[get_app_settings] = lambda: _fake_settings(
        "boom"
    )

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hi"}]},
            headers={"Accept": "text/event-stream"},
        )

    assert resp.status_code == 200
    frames = [f for f in resp.text.split("\n\n") if f]
    assert frames[0].startswith("event: answer\n")
    assert frames[-1].startswith("event: error\n")
    data_line = [ln for ln in frames[-1].splitlines() if ln.startswith("data: ")][0]
    assert json.loads(data_line[len("data: ") :])["content"] == "boom"


async def test_empty_messages_returns_422(app_with_fakes) -> None:
    async with _client(app_with_fakes) as client:
        resp = await client.post("/api/conversation", json={"messages": []})
    assert resp.status_code == 422


async def test_router_forwards_search_provider_to_orchestrator(
    app_with_fakes,
) -> None:
    """The chat route must pass the DI'd search provider into
    orchestrator construction so production langgraph runs in retrieval mode."""
    sentinel_search = object()
    app_with_fakes.dependency_overrides[get_search_provider] = lambda: sentinel_search

    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]
    _FakeOrchestrator.last_kwargs = {}

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert _FakeOrchestrator.last_kwargs.get("search") is sentinel_search


async def test_sse_emits_leading_retrieval_narration_when_search_wired(
    app_with_fakes,
) -> None:
    """When a search backend is wired the stream opens with the
    orchestrator-agnostic retrieval narration so the thinking panel
    shows activity for the whole wait, not a flash at the end."""
    app_with_fakes.dependency_overrides[get_search_provider] = lambda: object()
    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hi"}]},
            headers={"Accept": "text/event-stream"},
        )

    assert resp.status_code == 200
    frames = [f for f in resp.text.split("\n\n") if f]
    assert frames[0].startswith("event: reasoning\n")
    data_line = [ln for ln in frames[0].splitlines() if ln.startswith("data: ")][0]
    # The narration reasoning event is marked `placeholder` so the
    # frontend can replace it once retrieval completes (run_chat sets
    # `metadata={"placeholder": True}` on the leading hint event).
    assert json.loads(data_line[len("data: ") :]) == {
        "content": chat_pipeline.KB_SEARCH_NARRATION,
        "metadata": {"placeholder": True},
    }
    assert frames[1].startswith("event: answer\n")


async def test_sse_omits_retrieval_narration_when_search_disabled(
    app_with_fakes,
) -> None:
    """Pass-through mode (no search provider) must not claim to search:
    the stream carries only the orchestrator's own events."""
    # `app_with_fakes` leaves `get_search_provider` at its default --
    # ASGITransport skips lifespan, so `app.state.search_provider` is
    # unset and the dependency returns None.
    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hi"}]},
            headers={"Accept": "text/event-stream"},
        )

    assert resp.status_code == 200
    frames = [f for f in resp.text.split("\n\n") if f]
    assert len(frames) == 1
    assert frames[0].startswith("event: answer\n")


async def test_router_uses_registry_dispatch_no_hardcoded_provider_names() -> None:
    """Greppable gate: orchestrator construction goes through the
    registry exactly once -- no parallel `if/elif` chain that
    *constructs* different orchestrator instances per name.

    The Hard Rule #4 invariant is that orchestrator *construction* is
    registry-keyed -- so the test asserts there is exactly one
    ``orchestrators_registry.registry.get(...)`` *call site*
    (AST-counted, ignoring docstrings + comments).
    """
    src = inspect.getsource(conv_module)
    tree = ast.parse(src)

    get_calls = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match `orchestrators_registry.registry.get(...)` -- an
        # `Attribute(value=Attribute(value=Name("orchestrators_registry"),
        # attr="registry"), attr="get")`.
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "registry"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "orchestrators_registry"
        ):
            get_calls += 1

    assert get_calls == 1, (
        "router must dispatch through `orchestrators_registry.registry.get(...)` "
        f"exactly once -- found {get_calls} call sites; a parallel `if/elif` "
        "chain constructing orchestrators by name is forbidden (Hard Rule #4)"
    )


async def test_router_routes_through_chat_pipeline(
    app_with_fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase-3 audit step 6c: router must call ``pipelines.chat.run_chat``,
    not ``orchestrator.run`` directly. This gives content-safety and
    post-prompt a wiring point once they reach DI."""
    _FakeOrchestrator.scripted = [
        OrchestratorEvent(channel="answer", content="ok"),
    ]

    calls: list[dict[str, Any]] = []

    real_run_chat = chat_pipeline.run_chat

    def _spy_run_chat(messages, **kwargs):
        calls.append({"messages": list(messages), "kwargs": kwargs})
        return real_run_chat(messages, **kwargs)

    monkeypatch.setattr(conv_module, "run_chat", _spy_run_chat)

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert resp.json()["content"] == "ok"
    assert len(calls) == 1, "router did not delegate to pipelines.chat.run_chat"
    # The orchestrator is passed as a keyword arg, never positionally.
    assert "orchestrator" in calls[0]["kwargs"]
    assert isinstance(calls[0]["kwargs"]["orchestrator"], _FakeOrchestrator)


# ---------------------------------------------------------------------------
# Credential + agent_name forwarded uniformly to every orchestrator
# ---------------------------------------------------------------------------


async def test_router_forwards_credential_and_agent_name_to_orchestrator(
    app_with_fakes,
) -> None:
    """Router must forward (a) the `CredentialDep` it receives via
    DI as `credential=`, and (b) the `CWYD_AGENT.name` literal as
    `agent_name=`, uniformly into
    ``orchestrators_registry.registry.get(name)(...)`` so dispatch
    stays name-free (Hard Rule #4).

    The `agent_framework` orchestrator uses these to build a
    per-request `FoundryAgent`; orchestrators that don't need them
    (e.g. `langgraph`) swallow the kwargs via `**_extras`.
    """
    fake_provider = _FakeAgentsProvider()
    app_with_fakes.dependency_overrides[get_agents_provider] = lambda: fake_provider

    app_with_fakes.dependency_overrides[get_app_settings] = lambda: _fake_settings(
        "fake"
    )

    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]
    _FakeOrchestrator.last_kwargs = {}

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert (
        _FakeOrchestrator.last_kwargs.get("credential")
        is app_with_fakes.state.test_credential_sentinel
    )
    assert _FakeOrchestrator.last_kwargs.get("agent_name") == CWYD_AGENT.name


async def test_router_forwards_effective_system_prompt_to_orchestrator(
    app_with_fakes,
) -> None:
    """Router threads the effective `cwyd_agent_instructions` into
    orchestrator construction as `system_prompt=`. With no saved
    override it resolves to the `CWYD_AGENT.instructions` default."""
    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]
    _FakeOrchestrator.last_kwargs = {}

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert _FakeOrchestrator.last_kwargs.get("system_prompt") == CWYD_AGENT.instructions


@pytest.mark.asyncio
async def test_router_forwards_effective_sampling_to_orchestrator(
    app_with_fakes,
) -> None:
    """Router threads the effective `openai_temperature` / `openai_max_tokens`
    sampling knobs into orchestrator construction so the model honors the
    admin settings. With no override they resolve to the env defaults."""
    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]
    _FakeOrchestrator.last_kwargs = {}

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert _FakeOrchestrator.last_kwargs.get("openai_temperature") == 0.0
    assert _FakeOrchestrator.last_kwargs.get("openai_max_tokens") == 1000


async def test_router_saved_system_prompt_override_wins(
    app_with_fakes,
) -> None:
    """A persisted `cwyd_agent_instructions` override is forwarded as
    `system_prompt=`, guardrail-wrapped through the shared composition
    seam: the operator body leads and the fixed `CWYD_GUARDRAIL` is
    appended exactly once, last. The orchestrator never receives a raw,
    un-wrapped override, so the non-negotiable safety / out-of-domain /
    citation rules bookend an operator-authored persona."""
    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]
    _FakeOrchestrator.last_kwargs = {}
    app_with_fakes.state.runtime_overrides = RuntimeConfig(
        cwyd_agent_instructions="CUSTOM SYSTEM PROMPT"
    )

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    system_prompt = _FakeOrchestrator.last_kwargs.get("system_prompt")
    assert system_prompt == resolve_cwyd_instructions("CUSTOM SYSTEM PROMPT")
    assert system_prompt.startswith("CUSTOM SYSTEM PROMPT")
    assert system_prompt.endswith(CWYD_GUARDRAIL)
    assert system_prompt.count(CWYD_GUARDRAIL) == 1


async def test_router_forwards_effective_search_knobs_to_orchestrator(
    app_with_fakes,
) -> None:
    """Router threads the effective `search_top_k` /
    `search_use_semantic_search` into orchestrator construction. With no
    saved overrides they resolve to the `settings.search` defaults
    (`top_k=5`, `use_semantic_search=True`)."""
    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]
    _FakeOrchestrator.last_kwargs = {}

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert _FakeOrchestrator.last_kwargs.get("search_top_k") == 5
    assert _FakeOrchestrator.last_kwargs.get("search_use_semantic_search") is True


async def test_router_saved_search_knob_overrides_win(
    app_with_fakes,
) -> None:
    """Persisted `search_top_k` / `search_use_semantic_search` overrides
    are forwarded as the orchestrator ctor kwargs, beating the defaults."""
    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]
    _FakeOrchestrator.last_kwargs = {}
    app_with_fakes.state.runtime_overrides = RuntimeConfig(
        search_top_k=11,
        search_use_semantic_search=False,
    )

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert _FakeOrchestrator.last_kwargs.get("search_top_k") == 11
    assert _FakeOrchestrator.last_kwargs.get("search_use_semantic_search") is False


async def test_router_dispatches_both_orchestrator_kinds_with_same_kwargs(
    app_with_fakes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parametrize across `langgraph`/`agent_framework` to prove the
    router treats orchestrator selection as a registry key, not a
    branch. Both registrations resolve to `_FakeOrchestrator` here so
    we can read back `last_kwargs` for each name.
    """
    monkeypatched_keys = ["langgraph", "agent_framework"]
    for name in monkeypatched_keys:
        monkeypatch.setitem(
            orchestrators_registry.registry._items, name, _FakeOrchestrator
        )

    fake_provider = _FakeAgentsProvider()
    app_with_fakes.dependency_overrides[get_agents_provider] = lambda: fake_provider

    for name in monkeypatched_keys:
        app_with_fakes.dependency_overrides[get_app_settings] = (
            lambda n=name: _fake_settings(n)
        )

        _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content=name)]
        _FakeOrchestrator.last_kwargs = {}

        async with _client(app_with_fakes) as client:
            resp = await client.post(
                "/api/conversation",
                json={"messages": [{"role": "user", "content": "hi"}]},
            )

        assert resp.status_code == 200, f"{name} failed: {resp.text}"
        assert resp.json()["content"] == name
        # Same kwargs forwarded regardless of orchestrator key.
        assert (
            _FakeOrchestrator.last_kwargs.get("credential")
            is app_with_fakes.state.test_credential_sentinel
        )
        assert _FakeOrchestrator.last_kwargs.get("agent_name") == CWYD_AGENT.name
        assert "search" in _FakeOrchestrator.last_kwargs


# ---------------------------------------------------------------------------
# agents provider + db forwarded into orchestrator construction
# (the agent_framework orchestrator owns create-if-missing via build_agent;
#  the router performs no get_or_create_agent bootstrap)
# ---------------------------------------------------------------------------


async def test_agent_framework_branch_forwards_agents_and_db_to_orchestrator(
    app_with_fakes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On the `agent_framework` branch the router forwards the DI'd
    agents provider (`agents=`) and database client (`db=`) into
    orchestrator construction. Create-if-missing now lives in the
    provider's `build_agent` (invoked by the orchestrator), so the
    router performs no bootstrap round-trip itself -- it never calls
    `get_or_create_agent`.
    """
    monkeypatch.setitem(
        orchestrators_registry.registry._items, "agent_framework", _FakeOrchestrator
    )

    fake_provider = _FakeAgentsProvider()
    db_sentinel = _FakeDatabaseClient()
    app_with_fakes.dependency_overrides[get_agents_provider] = lambda: fake_provider
    app_with_fakes.dependency_overrides[get_database_client] = lambda: db_sentinel

    app_with_fakes.dependency_overrides[get_app_settings] = lambda: _fake_settings(
        "agent_framework"
    )

    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]
    _FakeOrchestrator.last_kwargs = {}

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

    assert resp.status_code == 200
    assert _FakeOrchestrator.last_kwargs.get("agents") is fake_provider
    assert _FakeOrchestrator.last_kwargs.get("db") is db_sentinel
    assert fake_provider.resolver_calls == [], (
        "router must not bootstrap the agent via get_or_create_agent; "
        "the orchestrator owns create-if-missing through build_agent"
    )


async def test_router_forwards_agents_and_db_uniformly_and_never_bootstraps(
    app_with_fakes,
) -> None:
    """Every orchestrator receives `agents=` + `db=` uniformly (Hard
    Rule #4: no name dispatch), and the router never calls
    `get_or_create_agent` -- create-if-missing lives in the provider's
    `build_agent`, invoked by the orchestrator, not the router.

    `_fake_settings()` default orchestrator name is "fake".
    """
    fake_provider = _FakeAgentsProvider()
    db_sentinel = _FakeDatabaseClient()
    app_with_fakes.dependency_overrides[get_agents_provider] = lambda: fake_provider
    app_with_fakes.dependency_overrides[get_database_client] = lambda: db_sentinel

    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]
    _FakeOrchestrator.last_kwargs = {}

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

    assert resp.status_code == 200
    assert _FakeOrchestrator.last_kwargs.get("agents") is fake_provider
    assert _FakeOrchestrator.last_kwargs.get("db") is db_sentinel
    assert (
        fake_provider.resolver_calls == []
    ), "router must never call get_or_create_agent (bootstrap removed)"


# ---------------------------------------------------------------------------
# Admin-saved orchestrator override drives dispatch over the env default
# ---------------------------------------------------------------------------


async def test_orchestrator_override_takes_precedence_over_env(
    app_with_fakes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persisted ``RuntimeConfig.orchestrator_name`` override must
    drive orchestrator selection over the ``CWYD_ORCHESTRATOR_NAME``
    env default. With env name "fake" but a saved override of
    "agent_framework", the registry must be keyed with
    "agent_framework" -- proving the saved override (not the env
    "fake") drove dispatch.
    """
    monkeypatch.setitem(
        orchestrators_registry.registry._items, "agent_framework", _FakeOrchestrator
    )

    dispatched: list[str] = []
    _spy_orchestrator_dispatch(monkeypatch, dispatched)

    # Fixture env default is "fake"; the saved override flips it.
    app_with_fakes.state.runtime_overrides = RuntimeConfig(
        orchestrator_name="agent_framework"
    )

    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

    assert resp.status_code == 200
    assert dispatched == ["agent_framework"], (
        "saved orchestrator override must drive registry dispatch to "
        "agent_framework even when the env default is 'fake'"
    )


async def test_none_orchestrator_override_falls_through_to_env(
    app_with_fakes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``RuntimeConfig`` whose ``orchestrator_name`` is ``None`` must
    fall through to the env default. With env name "fake" and an
    override that leaves ``orchestrator_name`` unset, the registry must
    be keyed with "fake".
    """
    dispatched: list[str] = []
    _spy_orchestrator_dispatch(monkeypatch, dispatched)

    # Override present but orchestrator_name unset -> env "fake" wins.
    app_with_fakes.state.runtime_overrides = RuntimeConfig(openai_temperature=0.7)

    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

    assert resp.status_code == 200
    assert dispatched == ["fake"], (
        "a None orchestrator_name override must fall through to the env "
        "default 'fake'"
    )


# ---------------------------------------------------------------------------
# U-CS-4: content-safety guard forwarded into pipelines.chat.run_chat
# ---------------------------------------------------------------------------


def _spy_run_chat_no_op(
    calls: list[dict[str, Any]],
):
    """Build a non-invoking spy: records kwargs, yields no events.

    Using a no-op generator (instead of the real ``run_chat``) keeps
    these tests focused on the *forwarding contract* -- we never
    exercise the guard's ``screen()`` method here, so the sentinel
    passed via DI can be a bare ``object()`` without needing a
    fully-shaped fake.
    """

    def _spy(messages: Any, **kwargs: Any) -> AsyncIterator[OrchestratorEvent]:
        calls.append({"kwargs": kwargs})

        async def _empty() -> AsyncIterator[OrchestratorEvent]:
            if False:
                yield  # pragma: no cover

        return _empty()

    return _spy


async def test_router_forwards_none_content_safety_when_dep_returns_none(
    app_with_fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default DI path: ASGITransport skips lifespan so
    ``app.state.content_safety_client`` is never set ->
    ``get_content_safety_guard`` returns None -> router must forward
    ``content_safety=None`` to ``run_chat``.
    """
    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]

    calls: list[dict[str, Any]] = []

    monkeypatch.setattr(conv_module, "run_chat", _spy_run_chat_no_op(calls))

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert len(calls) == 1
    assert (
        "content_safety" in calls[0]["kwargs"]
    ), "router must pass `content_safety` kwarg explicitly to run_chat"
    assert calls[0]["kwargs"]["content_safety"] is None


async def test_router_forwards_content_safety_guard_when_dep_returns_guard(
    app_with_fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``get_content_safety_guard`` returns a guard instance
    (DI-overridden here with a sentinel object), the router must
    forward that exact instance into ``run_chat(content_safety=...)``.
    """
    sentinel_guard = object()
    app_with_fakes.dependency_overrides[get_content_safety_guard] = (
        lambda: sentinel_guard
    )

    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(conv_module, "run_chat", _spy_run_chat_no_op(calls))

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert calls[0]["kwargs"]["content_safety"] is sentinel_guard


# ---------------------------------------------------------------------------
# post-prompt validator forwarded into pipelines.chat.run_chat
# ---------------------------------------------------------------------------


async def test_router_forwards_none_post_prompt_when_dep_returns_none(
    app_with_fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default DI path: ASGITransport skips lifespan so no
    ``app.state.runtime_overrides`` is set ->
    ``get_post_prompt_validator`` returns ``None`` -> router must
    forward ``post_prompt=None`` to ``run_chat``.
    """
    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(conv_module, "run_chat", _spy_run_chat_no_op(calls))

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert len(calls) == 1
    assert (
        "post_prompt" in calls[0]["kwargs"]
    ), "router must pass `post_prompt` kwarg explicitly to run_chat"
    assert calls[0]["kwargs"]["post_prompt"] is None


async def test_router_forwards_post_prompt_validator_when_dep_returns_validator(
    app_with_fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``get_post_prompt_validator`` returns a validator instance
    (DI-overridden here with a sentinel object), the router must
    forward that exact instance into ``run_chat(post_prompt=...)``.
    """
    sentinel_validator = object()
    app_with_fakes.dependency_overrides[get_post_prompt_validator] = (
        lambda: sentinel_validator
    )

    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(conv_module, "run_chat", _spy_run_chat_no_op(calls))

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "ping"}]},
        )

    assert resp.status_code == 200
    assert calls[0]["kwargs"]["post_prompt"] is sentinel_validator


# ---------------------------------------------------------------------------
# Conversation persistence: each completed turn is written keyed by user_id
# ---------------------------------------------------------------------------


async def test_json_mode_persists_turn_and_echoes_conversation_id(
    app_with_fakes,
) -> None:
    """Buffered mode writes the completed turn and echoes the resolved
    conversation id. With no ``conversation_id`` in the request the DB
    creates a fresh thread (``conv-new``) titled with the user's
    question, appending the user message before the assistant answer."""
    recorder = _RecordingDatabaseClient()
    app_with_fakes.dependency_overrides[get_database_client] = lambda: recorder
    _FakeOrchestrator.scripted = [
        OrchestratorEvent(channel="answer", content="Hello, world!"),
    ]

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "What is CWYD?"}]},
        )

    assert resp.status_code == 200
    assert resp.json()["conversation_id"] == "conv-new"
    # New thread titled with the question (no existing id supplied), keyed
    # by the anonymous default id (no principal header on this request).
    assert recorder.created == [
        ("00000000-0000-0000-0000-000000000000", "What is CWYD?")
    ]
    # User message persisted before the assistant answer.
    assert [(m.role, m.content) for (_cid, _uid, m) in recorder.added] == [
        ("user", "What is CWYD?"),
        ("assistant", "Hello, world!"),
    ]


async def test_json_mode_persists_citations_in_assistant_message_metadata(
    app_with_fakes,
) -> None:
    """Buffered mode threads the answer's deduplicated citations into the
    persisted assistant message metadata under the ``citations`` key, so a
    reloaded conversation rehydrates its reference block without re-running
    retrieval. The user message stays metadata-free."""
    recorder = _RecordingDatabaseClient()
    app_with_fakes.dependency_overrides[get_database_client] = lambda: recorder
    _FakeOrchestrator.scripted = [
        OrchestratorEvent(channel="answer", content="Grounded answer."),
        OrchestratorEvent(
            channel="citation",
            metadata={"id": "doc1", "title": "Doc 1", "url": "https://x/1"},
        ),
        OrchestratorEvent(
            channel="citation",
            metadata={"id": "doc1", "title": "Doc 1 dup", "url": "https://x/1"},
        ),
        OrchestratorEvent(
            channel="citation",
            metadata={"id": "doc2", "title": "Doc 2", "url": "https://x/2"},
        ),
    ]

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "What is covered?"}]},
        )

    assert resp.status_code == 200
    _user_cid, _user_uid, user_msg = recorder.added[0]
    _asst_cid, _asst_uid, assistant_msg = recorder.added[1]
    assert user_msg.metadata == {}
    assert [c["id"] for c in assistant_msg.metadata["citations"]] == ["doc1", "doc2"]


async def test_sse_mode_emits_terminal_conversation_frame_and_persists(
    app_with_fakes,
) -> None:
    """Streaming mode persists the turn after the answer is fully sent
    and closes with a terminal ``conversation`` control frame carrying
    the resolved id (a transport event, not a locked channel)."""
    recorder = _RecordingDatabaseClient()
    app_with_fakes.dependency_overrides[get_database_client] = lambda: recorder
    _FakeOrchestrator.scripted = [
        OrchestratorEvent(channel="answer", content="hi there"),
    ]

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hello"}]},
            headers={"Accept": "text/event-stream"},
        )

    assert resp.status_code == 200
    frames = [f for f in resp.text.split("\n\n") if f]
    assert frames[0].startswith("event: answer\n")
    assert frames[-1].startswith("event: conversation\n")
    data_line = [ln for ln in frames[-1].splitlines() if ln.startswith("data: ")][0]
    assert json.loads(data_line[len("data: ") :]) == {"conversation_id": "conv-new"}
    assert recorder.created == [("00000000-0000-0000-0000-000000000000", "hello")]


async def test_persisted_turn_is_keyed_by_easy_auth_principal_header(
    app_with_fakes,
) -> None:
    """The persisted turn is keyed by the ``x-ms-client-principal-id``
    Easy Auth header (the signed-in user), proving per-user history
    isolation rather than the anonymous default-id fallback."""
    recorder = _RecordingDatabaseClient()
    app_with_fakes.dependency_overrides[get_database_client] = lambda: recorder
    _FakeOrchestrator.scripted = [
        OrchestratorEvent(channel="answer", content="answer"),
    ]

    principal_id = "11111111-1111-1111-1111-111111111111"
    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "q"}]},
            headers={"x-ms-client-principal-id": principal_id},
        )

    assert resp.status_code == 200
    assert recorder.created == [(principal_id, "q")]
    assert all(uid == principal_id for (_cid, uid, _m) in recorder.added)
