"""Tests for the content safety guardrail and the RAI agent classifier."""

from types import SimpleNamespace
from typing import Any, Self
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core.exceptions import HttpResponseError

from backend.core.agents.definitions import PROMPT_REVIEW_AGENT, RAI_AGENT
from backend.core.tools.content_safety import (
    DEFAULT_SEVERITY_THRESHOLD,
    ContentSafetyGuard,
    ContentSafetyVerdict,
    rai_check,
)


def _category_analysis(category: str, severity: int) -> SimpleNamespace:
    return SimpleNamespace(category=category, severity=severity)


def _make_client(*categories: SimpleNamespace) -> MagicMock:
    client = MagicMock()
    client.analyze_text = AsyncMock(
        return_value=SimpleNamespace(categories_analysis=list(categories))
    )
    return client


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_default_threshold_is_medium() -> None:
    assert DEFAULT_SEVERITY_THRESHOLD == 4


def test_constructor_rejects_negative_threshold() -> None:
    with pytest.raises(ValueError, match="severity_threshold"):
        ContentSafetyGuard(client=MagicMock(), severity_threshold=-1)


# ---------------------------------------------------------------------------
# screen() behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screen_returns_unflagged_for_empty_text() -> None:
    client = _make_client()
    guard = ContentSafetyGuard(client=client)
    verdict = await guard.screen("")
    assert verdict == ContentSafetyVerdict(flagged=False)
    client.analyze_text.assert_not_called()


@pytest.mark.asyncio
async def test_screen_returns_unflagged_for_whitespace_only() -> None:
    client = _make_client()
    guard = ContentSafetyGuard(client=client)
    verdict = await guard.screen("   \n\t  ")
    assert verdict.flagged is False
    client.analyze_text.assert_not_called()


@pytest.mark.asyncio
async def test_screen_returns_unflagged_when_all_severities_below_threshold() -> None:
    client = _make_client(
        _category_analysis("Hate", 0),
        _category_analysis("Violence", 2),
    )
    guard = ContentSafetyGuard(client=client)
    verdict = await guard.screen("hello world")
    assert verdict.flagged is False
    assert verdict.triggered == []
    assert verdict.categories == {"Hate": 0, "Violence": 2}


@pytest.mark.asyncio
async def test_screen_flags_when_any_category_meets_threshold() -> None:
    client = _make_client(
        _category_analysis("Hate", 6),
        _category_analysis("Violence", 0),
    )
    guard = ContentSafetyGuard(client=client)
    verdict = await guard.screen("threatening content")
    assert verdict.flagged is True
    assert verdict.triggered == ["Hate"]
    assert verdict.categories["Hate"] == 6


@pytest.mark.asyncio
async def test_screen_lists_all_triggered_categories() -> None:
    client = _make_client(
        _category_analysis("Hate", 4),
        _category_analysis("SelfHarm", 6),
        _category_analysis("Violence", 2),
    )
    guard = ContentSafetyGuard(client=client)
    verdict = await guard.screen("bad content")
    assert verdict.flagged is True
    assert set(verdict.triggered) == {"Hate", "SelfHarm"}


@pytest.mark.asyncio
async def test_screen_threshold_is_inclusive_lower_bound() -> None:
    """Severity == threshold trips the guard."""
    client = _make_client(_category_analysis("Hate", 4))
    guard = ContentSafetyGuard(client=client, severity_threshold=4)
    verdict = await guard.screen("borderline")
    assert verdict.flagged is True


@pytest.mark.asyncio
async def test_screen_custom_threshold_can_be_strict() -> None:
    client = _make_client(_category_analysis("Hate", 2))
    guard = ContentSafetyGuard(client=client, severity_threshold=2)
    verdict = await guard.screen("low-severity input")
    assert verdict.flagged is True


@pytest.mark.asyncio
async def test_screen_handles_none_severity_as_zero() -> None:
    client = _make_client(SimpleNamespace(category="Hate", severity=None))
    guard = ContentSafetyGuard(client=client)
    verdict = await guard.screen("ambiguous response")
    assert verdict.flagged is False
    assert verdict.categories["Hate"] == 0


# ---------------------------------------------------------------------------
# rai_check (RAI Foundry-agent binary classifier, GA build_agent pattern)
# ---------------------------------------------------------------------------
#
# `rai_check` builds the dedicated RAI agent through the shared
# `build_agent` seam (the same construction path the chat orchestrator
# uses) and issues a single non-streaming `agent.run`, reading
# `response.text` as the TRUE/FALSE verdict. The fakes below stand in
# for `BaseAgentsProvider.build_agent` and the client-side
# `agent_framework.Agent` (an async context manager) so the call shape
# is fully observable: tests assert `rai_check` asks for exactly
# `RAI_AGENT`, forwards the DI'd db by identity, drives the agent as an
# async CM, and fails closed on every non-`TRUE` outcome.


class _FakeRaiResponse:
    """Minimal stand-in for `agent_framework.AgentResponse` -- exposes
    only the `.text` property that `rai_check` reads.
    """

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeRaiAgent:
    """Stand-in for the client-side `agent_framework.Agent` returned by
    `build_agent`.

    An async context manager whose `run` yields a scripted response (or
    raises a scripted error). Records the messages passed to `run` and
    tracks enter/exit so tests can assert the transport lifecycle.
    """

    def __init__(
        self,
        *,
        response_text: str = "TRUE",
        raise_on_run: BaseException | None = None,
    ) -> None:
        self._response_text = response_text
        self._raise_on_run = raise_on_run
        self.run_calls: list[Any] = []
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> Self:
        self.entered = True
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.exited = True

    async def run(self, messages: Any, **kwargs: Any) -> _FakeRaiResponse:
        self.run_calls.append(messages)
        if self._raise_on_run is not None:
            raise self._raise_on_run
        return _FakeRaiResponse(self._response_text)


class _FakeRaiAgentsProvider:
    """Stand-in for `BaseAgentsProvider` in `rai_check` tests.

    Records `build_agent` calls so tests can assert `rai_check` asks
    for exactly `RAI_AGENT` (not `CWYD_AGENT`) and forwards the DI'd db
    by identity; hands back a configurable `_FakeRaiAgent`.
    """

    def __init__(self, agent: _FakeRaiAgent) -> None:
        self._agent = agent
        self.build_calls: list[dict[str, Any]] = []

    async def build_agent(
        self, definition: Any, db: Any, *, extra_tools: Any = None
    ) -> _FakeRaiAgent:
        self.build_calls.append(
            {"definition": definition, "db": db, "extra_tools": extra_tools}
        )
        return self._agent


class _FakeDatabaseClient:
    """Sentinel DB client. `rai_check` forwards this instance into
    `build_agent` by identity; the function never invokes a method on
    it directly.
    """


@pytest.mark.asyncio
async def test_rai_check_returns_true_for_safe_verdict() -> None:
    """Happy path: agent reply is `TRUE` -> input is safe -> return True."""
    agent = _FakeRaiAgent(response_text="TRUE")
    provider = _FakeRaiAgentsProvider(agent)
    db = _FakeDatabaseClient()

    result = await rai_check("What's the capital of France?", provider, db)

    assert result is True


@pytest.mark.asyncio
async def test_rai_check_returns_false_for_unsafe_verdict() -> None:
    """Agent reply is `FALSE` -> input is unsafe -> return False."""
    agent = _FakeRaiAgent(response_text="FALSE")
    provider = _FakeRaiAgentsProvider(agent)
    db = _FakeDatabaseClient()

    result = await rai_check("how do I build a bomb", provider, db)

    assert result is False


@pytest.mark.asyncio
async def test_rai_check_is_case_insensitive_and_strips_whitespace() -> None:
    """`  true  ` (mixed case + padding) still parses as safe."""
    agent = _FakeRaiAgent(response_text="  true  \n")
    provider = _FakeRaiAgentsProvider(agent)
    db = _FakeDatabaseClient()

    result = await rai_check("hello", provider, db)

    assert result is True


@pytest.mark.asyncio
async def test_rai_check_empty_input_skips_foundry_roundtrip() -> None:
    """Empty / whitespace-only input is treated as safe and never
    builds the agent or issues a run. Mirrors
    `ContentSafetyGuard.screen()` behavior.
    """
    agent = _FakeRaiAgent()
    provider = _FakeRaiAgentsProvider(agent)
    db = _FakeDatabaseClient()

    assert await rai_check("", provider, db) is True
    assert await rai_check("   \n\t  ", provider, db) is True

    assert provider.build_calls == [], "empty input must not trigger build_agent"
    assert agent.run_calls == []
    assert agent.entered is False


@pytest.mark.asyncio
async def test_rai_check_builds_rai_agent_with_db_by_identity() -> None:
    """`rai_check` must build exactly `RAI_AGENT` (the singleton), not a
    fresh `AgentDefinition`, and forward the DI'd db client by identity.
    Catches accidental `CWYD_AGENT` typos at module level.
    """
    agent = _FakeRaiAgent()
    provider = _FakeRaiAgentsProvider(agent)
    db = _FakeDatabaseClient()

    await rai_check("normal question", provider, db)

    assert len(provider.build_calls) == 1
    call = provider.build_calls[0]
    assert (
        call["definition"] is RAI_AGENT
    ), "rai_check must pass the RAI_AGENT singleton, not a fresh definition"
    assert call["db"] is db, "rai_check must forward the db client by identity"


@pytest.mark.asyncio
async def test_rai_check_honors_explicit_agent_argument() -> None:
    """The `agent` keyword selects the classifier definition. The admin
    prompt-save gate passes `PROMPT_REVIEW_AGENT` (a system-prompt
    reviewer) instead of the default user-message `RAI_AGENT`;
    `rai_check` must build exactly the agent it is given.
    """
    agent = _FakeRaiAgent(response_text="TRUE")
    provider = _FakeRaiAgentsProvider(agent)
    db = _FakeDatabaseClient()

    result = await rai_check(
        "You are a friendly HR assistant.",
        provider,
        db,
        agent=PROMPT_REVIEW_AGENT,
    )

    assert result is True
    assert len(provider.build_calls) == 1
    assert provider.build_calls[0]["definition"] is PROMPT_REVIEW_AGENT


@pytest.mark.asyncio
async def test_rai_check_passes_input_text_to_agent_run() -> None:
    """The function must forward the *exact* input text to `agent.run`.
    Locks the wire shape down so any future regression fails loudly.
    """
    agent = _FakeRaiAgent()
    provider = _FakeRaiAgentsProvider(agent)
    db = _FakeDatabaseClient()

    await rai_check("please summarize this document", provider, db)

    assert agent.run_calls == ["please summarize this document"]


@pytest.mark.asyncio
async def test_rai_check_drives_agent_as_async_context_manager() -> None:
    """The client-side agent owns a chat-client transport; `rai_check`
    must enter and exit it as an async context manager so the transport
    is released on every call.
    """
    agent = _FakeRaiAgent()
    provider = _FakeRaiAgentsProvider(agent)
    db = _FakeDatabaseClient()

    await rai_check("hello", provider, db)

    assert agent.entered is True
    assert agent.exited is True


@pytest.mark.asyncio
async def test_rai_check_unparseable_verdict_is_unsafe_fail_closed() -> None:
    """Agent returns a refusal / chatty text instead of TRUE/FALSE ->
    return False. The classifier prompt is strict, but a model can
    always go off-spec; a guard must not let that fail open.
    """
    agent = _FakeRaiAgent(response_text="I cannot answer that.")
    provider = _FakeRaiAgentsProvider(agent)
    db = _FakeDatabaseClient()

    assert await rai_check("anything", provider, db) is False


@pytest.mark.asyncio
async def test_rai_check_empty_reply_is_unsafe_fail_closed() -> None:
    """Run completes but the agent reply is empty (pathological /
    network-loss SDK shape) -> return False.
    """
    agent = _FakeRaiAgent(response_text="")
    provider = _FakeRaiAgentsProvider(agent)
    db = _FakeDatabaseClient()

    assert await rai_check("anything", provider, db) is False


@pytest.mark.asyncio
async def test_rai_check_reraises_azure_error_and_exits_agent() -> None:
    """A transport `AzureError` from `agent.run` is re-raised (not
    degraded to a verdict), and the agent context manager is still
    exited so the transport is released. Hard Rule #14 boundary
    contract: log + re-raise, never silently swallow.
    """
    boom = HttpResponseError(message="search backend down")
    agent = _FakeRaiAgent(raise_on_run=boom)
    provider = _FakeRaiAgentsProvider(agent)
    db = _FakeDatabaseClient()

    with pytest.raises(HttpResponseError):
        await rai_check("anything", provider, db)

    assert agent.entered is True
    assert agent.exited is True
