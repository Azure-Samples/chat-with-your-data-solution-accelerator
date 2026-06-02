"""Pillar: Stable Core / Phase: 3 (task #22a) — tests for the conversation router."""

import ast
import inspect
import json
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
    get_search_provider,
)
from backend.core.agents.definitions import CWYD_AGENT
from backend.core.pipelines import chat as chat_pipeline
from backend.core.providers.orchestrators import registry as orchestrators_registry
from backend.core.providers.orchestrators.base import OrchestratorBase
from backend.core.types import ChatMessage, OrchestratorEvent
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


class _FakeSettings:
    class _O:
        name = "fake"
        agent_id = ""

    orchestrator = _O()


class _FakeAgentsProvider:
    """Stand-in for `FoundryAgentsProvider` in router tests.

    `get_client()` returns a sentinel object so we can assert the
    router forwards the *exact* client instance into the
    ``orchestrators_registry.registry.get(...)(...)`` dispatch call
    (CU-001d).

    `get_or_create_agent()` is the CU-010c lazy resolver seam --
    CU-010d wires the router to call it on the `agent_framework`
    branch only. Tests configure `agent_id_to_return` to control the
    resolved id and inspect `resolver_calls` to assert the resolver
    was invoked with `(CWYD_AGENT, db_sentinel)`.
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


@pytest.fixture
def app_with_fakes(monkeypatch: pytest.MonkeyPatch):
    """Build the app, register fakes in the orchestrator registry, and DI-override settings + llm + agents."""
    monkeypatch.setitem(orchestrators_registry.registry._items, "fake", _FakeOrchestrator)
    monkeypatch.setitem(orchestrators_registry.registry._items, "boom", _BoomOrchestrator)

    app = create_app()
    app.dependency_overrides[get_app_settings] = lambda: _FakeSettings()
    app.dependency_overrides[get_llm_provider] = lambda: object()
    # Always override the agents provider: ASGITransport doesn't run
    # lifespan, so `app.state.agents_provider` is never set. Without
    # this default the router's `agents.get_client()` would 500 even
    # for orchestrators that don't use it (langgraph swallows the
    # kwarg via `**_extras` -- Hard Rule #4: no name dispatch).
    app.dependency_overrides[get_agents_provider] = lambda: _FakeAgentsProvider()
    # Same reason: CU-010d wires `db: DatabaseClientDep` into the
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
    app.dependency_overrides[get_credential] = lambda: app.state.test_credential_sentinel
    return app


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_json_mode_concatenates_answer_and_dedupes_citations(app_with_fakes) -> None:
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


async def test_sse_mode_surfaces_orchestrator_exception_as_error_event(app_with_fakes) -> None:
    # Use the boom orchestrator instead of the scripted fake. The ad-hoc
    # settings type only needs `orchestrator.name` -- after CU-009b the
    # router forwards `agent_id=""` literally (CU-010d will replace
    # with a lazy DB-backed resolver), so the fake settings no longer
    # need to expose an `agent_id` attribute.
    app_with_fakes.dependency_overrides[get_app_settings] = lambda: type(
        "S",
        (),
        {"orchestrator": type("O", (), {"name": "boom"})()},
    )()

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
    """Phase 3.5 Q6c: chat route must pass the DI'd search provider into
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


async def test_router_uses_registry_dispatch_no_hardcoded_provider_names() -> None:
    """Greppable gate: orchestrator construction goes through the
    registry exactly once -- no parallel `if/elif` chain that
    *constructs* different orchestrator instances per name.

    CU-010d nuance: the router *does* contain a single
    ``if settings.orchestrator.name == "agent_framework"`` check, but
    that's *kwarg preparation* for the lazy agent-id resolver, not
    dispatch (the resolved id is then passed into the same single
    ``orchestrators_registry.registry.get(...)(...)`` call). The Hard
    Rule #4 invariant is that orchestrator *construction* is
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

    class _SettingsForFakeOrchestrator:
        class _O:
            name = "fake"

        orchestrator = _O()

    app_with_fakes.dependency_overrides[get_app_settings] = (
        lambda: _SettingsForFakeOrchestrator()
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

        class _S:
            class _O:
                pass

            orchestrator = _O()

        _S.orchestrator.name = name  # type: ignore[attr-defined]
        app_with_fakes.dependency_overrides[get_app_settings] = lambda s=_S: s()

        _FakeOrchestrator.scripted = [
            OrchestratorEvent(channel="answer", content=name)
        ]
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
# CU-010d: lazy DB-backed agent-id resolution on the agent_framework branch
# ---------------------------------------------------------------------------


async def test_agent_framework_branch_resolves_agent_id_via_provider(
    app_with_fakes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the configured orchestrator is `agent_framework`, the
    router must call `agents.get_or_create_agent(CWYD_AGENT, db)`
    exactly once (bootstrap path: create-if-missing). The orchestrator
    itself looks the agent up by name through the OSS
    `agent_framework_foundry.FoundryAgent` client, so the resolver's
    return value is intentionally discarded.
    """
    monkeypatch.setitem(
        orchestrators_registry.registry._items, "agent_framework", _FakeOrchestrator
    )

    fake_provider = _FakeAgentsProvider(agent_id_to_return="asst_resolved_123")
    app_with_fakes.dependency_overrides[get_agents_provider] = lambda: fake_provider

    class _S:
        class _O:
            name = "agent_framework"

        orchestrator = _O()

    app_with_fakes.dependency_overrides[get_app_settings] = lambda: _S()

    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]
    _FakeOrchestrator.last_kwargs = {}

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

    assert resp.status_code == 200
    assert len(fake_provider.resolver_calls) == 1, (
        "agent_framework branch must call get_or_create_agent exactly once"
    )
    # The router does not pass the resolved id to the orchestrator
    # (the OSS FoundryAgent looks the agent up by name). It does pass
    # the agent name + credential uniformly.
    assert _FakeOrchestrator.last_kwargs.get("agent_name") == CWYD_AGENT.name


async def test_non_agent_framework_branch_does_not_call_resolver(
    app_with_fakes,
) -> None:
    """When the orchestrator is anything other than `agent_framework`,
    the router must skip the resolver entirely (zero DB / Foundry
    round-trips).

    `_FakeSettings.orchestrator.name == "fake"` (set in the fixture).
    """
    fake_provider = _FakeAgentsProvider()
    app_with_fakes.dependency_overrides[get_agents_provider] = lambda: fake_provider

    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]
    _FakeOrchestrator.last_kwargs = {}

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

    assert resp.status_code == 200
    assert fake_provider.resolver_calls == [], (
        "non-agent_framework orchestrators must not trigger the resolver"
    )


async def test_resolver_receives_cwyd_definition_and_database_client(
    app_with_fakes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The resolver must be called with (a) the `CWYD_AGENT` built-in
    definition (not `RAI_AGENT`, not a fresh instance), and (b) the
    DI'd database client *instance* (identity check).
    """
    monkeypatch.setitem(
        orchestrators_registry.registry._items, "agent_framework", _FakeOrchestrator
    )

    fake_provider = _FakeAgentsProvider()
    db_sentinel = _FakeDatabaseClient()
    app_with_fakes.dependency_overrides[get_agents_provider] = lambda: fake_provider
    app_with_fakes.dependency_overrides[get_database_client] = lambda: db_sentinel

    class _S:
        class _O:
            name = "agent_framework"

        orchestrator = _O()

    app_with_fakes.dependency_overrides[get_app_settings] = lambda: _S()

    _FakeOrchestrator.scripted = [OrchestratorEvent(channel="answer", content="ok")]

    async with _client(app_with_fakes) as client:
        resp = await client.post(
            "/api/conversation",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

    assert resp.status_code == 200
    assert len(fake_provider.resolver_calls) == 1
    call = fake_provider.resolver_calls[0]
    assert call["definition"] is CWYD_AGENT, (
        "router must pass the CWYD_AGENT singleton, not a fresh definition"
    )
    assert call["db"] is db_sentinel, (
        "router must forward the DI'd database client by identity"
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
    assert "content_safety" in calls[0]["kwargs"], (
        "router must pass `content_safety` kwarg explicitly to run_chat"
    )
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
