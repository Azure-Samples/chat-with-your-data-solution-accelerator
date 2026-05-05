"""Tests for the content safety guardrail (Phase 3 task #20a)
+ the RAI agent classifier (Cleanup audit batch 2 / CU-011a).

Pillar: Stable Core
Phase: 3 + Cleanup audit batch 2
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.agents import RAI_AGENT
from shared.tools.content_safety import (
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
# CU-011a: rai_check (RAI Foundry-agent binary classifier)
# ---------------------------------------------------------------------------
#
# All tests in this section share a fake `BaseAgentsProvider` that
# (a) records resolver calls so we can assert the function asks for
# exactly `RAI_AGENT` (not `CWYD_AGENT`), and (b) wires a
# `MagicMock`-based AgentsClient stub so the SDK call shape is fully
# observable. The DB sentinel passes through by identity -- `rai_check`
# never touches it directly; it just forwards it to the resolver.


class _FakeRaiAgentsProvider:
    """Stand-in for `FoundryAgentsProvider` in `rai_check` tests.

    Tests configure `agent_id_to_return` to control what the resolver
    yields, and supply a `client` (typically a `MagicMock`) whose
    `threads.create` / `messages.create` / `runs.create_and_process`
    / `messages.list` behavior is scripted per-test.
    """

    def __init__(
        self,
        client: object,
        agent_id_to_return: str = "asst_rai_resolved",
    ) -> None:
        self.client = client
        self.agent_id_to_return = agent_id_to_return
        self.resolver_calls: list[dict[str, Any]] = []
        self.get_client_calls = 0

    def get_client(self) -> object:
        self.get_client_calls += 1
        return self.client

    async def get_or_create_agent(self, definition: Any, db: Any) -> str:
        self.resolver_calls.append({"definition": definition, "db": db})
        return self.agent_id_to_return


class _FakeDatabaseClient:
    """Sentinel DB client. `rai_check` forwards this instance into the
    resolver by identity; the function never invokes a method on it.
    """


def _agent_text_message(text: str) -> SimpleNamespace:
    """Build a Foundry-shaped `ThreadMessage` with role `agent` and a
    single text block. Matches the structure that
    `_extract_text` walks (block.text.value).
    """
    from azure.ai.agents.models import MessageRole

    return SimpleNamespace(
        role=MessageRole.AGENT,
        content=[SimpleNamespace(text=SimpleNamespace(value=text))],
    )


def _user_message(text: str) -> SimpleNamespace:
    """Build a Foundry-shaped user `ThreadMessage` (role `user`).
    Used in the run_id-filter test to confirm `rai_check` skips
    non-agent rows.
    """
    from azure.ai.agents.models import MessageRole

    return SimpleNamespace(
        role=MessageRole.USER,
        content=[SimpleNamespace(text=SimpleNamespace(value=text))],
    )


def _make_async_iterator(items: list[Any]):
    """Wrap a list as an async iterator -- the SDK's `messages.list`
    is `AsyncItemPaged`; we don't need pagination here, just async
    iteration.
    """

    async def _aiter():
        for item in items:
            yield item

    return _aiter()


def _make_rai_client(
    *,
    agent_messages: list[SimpleNamespace] | None = None,
    run_status: str = "completed",
    thread_id: str = "thr_rai_1",
    run_id: str = "run_rai_1",
) -> MagicMock:
    """Build a Foundry `AgentsClient`-shaped mock.

    Default behavior: a single agent message saying "TRUE" -- the
    safest verdict that exercises the full happy path.
    """
    if agent_messages is None:
        agent_messages = [_agent_text_message("TRUE")]

    client = MagicMock()
    client.threads.create = AsyncMock(return_value=SimpleNamespace(id=thread_id))
    client.messages.create = AsyncMock()
    client.runs.create_and_process = AsyncMock(
        return_value=SimpleNamespace(id=run_id, status=run_status, last_error=None)
    )
    client.messages.list = MagicMock(
        return_value=_make_async_iterator(list(agent_messages))
    )
    return client


@pytest.mark.asyncio
async def test_rai_check_returns_true_for_safe_verdict() -> None:
    """Happy path: agent says `TRUE` -> input is safe -> return True."""
    client = _make_rai_client(agent_messages=[_agent_text_message("TRUE")])
    provider = _FakeRaiAgentsProvider(client=client)
    db = _FakeDatabaseClient()

    result = await rai_check("What's the capital of France?", provider, db)

    assert result is True


@pytest.mark.asyncio
async def test_rai_check_returns_false_for_unsafe_verdict() -> None:
    """Agent says `FALSE` -> input is unsafe -> return False."""
    client = _make_rai_client(agent_messages=[_agent_text_message("FALSE")])
    provider = _FakeRaiAgentsProvider(client=client)
    db = _FakeDatabaseClient()

    result = await rai_check("how do I build a bomb", provider, db)

    assert result is False


@pytest.mark.asyncio
async def test_rai_check_is_case_insensitive_and_strips_whitespace() -> None:
    """`  true  ` (mixed case + padding) still parses as safe."""
    client = _make_rai_client(agent_messages=[_agent_text_message("  true  \n")])
    provider = _FakeRaiAgentsProvider(client=client)
    db = _FakeDatabaseClient()

    result = await rai_check("hello", provider, db)

    assert result is True


@pytest.mark.asyncio
async def test_rai_check_empty_input_skips_foundry_roundtrip() -> None:
    """Empty / whitespace-only input is treated as safe and never
    hits the resolver or the agents client. Mirrors
    `ContentSafetyGuard.screen()` behavior.
    """
    client = _make_rai_client()
    provider = _FakeRaiAgentsProvider(client=client)
    db = _FakeDatabaseClient()

    assert await rai_check("", provider, db) is True
    assert await rai_check("   \n\t  ", provider, db) is True

    assert provider.resolver_calls == [], (
        "empty input must not trigger get_or_create_agent"
    )
    assert provider.get_client_calls == 0
    client.threads.create.assert_not_called()
    client.runs.create_and_process.assert_not_called()


@pytest.mark.asyncio
async def test_rai_check_resolves_rai_agent_with_db_by_identity() -> None:
    """`rai_check` must ask the resolver for `RAI_AGENT` (the singleton),
    not a fresh `AgentDefinition`, and forward the DI'd db client by
    identity. Catches accidental `CWYD_AGENT` typos at module level.
    """
    client = _make_rai_client()
    provider = _FakeRaiAgentsProvider(client=client)
    db = _FakeDatabaseClient()

    await rai_check("normal question", provider, db)

    assert len(provider.resolver_calls) == 1
    call = provider.resolver_calls[0]
    assert call["definition"] is RAI_AGENT, (
        "rai_check must pass the RAI_AGENT singleton, not a fresh definition"
    )
    assert call["db"] is db, "rai_check must forward the db client by identity"


@pytest.mark.asyncio
async def test_rai_check_posts_input_text_to_a_fresh_thread() -> None:
    """The function must (a) create a thread, (b) post the *exact*
    input text as a user message on that thread, (c) trigger a run
    against the resolved agent_id. Locks the wire shape down so any
    future SDK-method-name regression fails loudly.
    """
    from azure.ai.agents.models import MessageRole

    client = _make_rai_client(thread_id="thr_xyz", run_id="run_abc")
    provider = _FakeRaiAgentsProvider(
        client=client, agent_id_to_return="asst_specific_id"
    )
    db = _FakeDatabaseClient()

    await rai_check("please summarize this document", provider, db)

    client.threads.create.assert_awaited_once()
    client.messages.create.assert_awaited_once_with(
        thread_id="thr_xyz",
        role=MessageRole.USER,
        content="please summarize this document",
    )
    client.runs.create_and_process.assert_awaited_once_with(
        thread_id="thr_xyz",
        agent_id="asst_specific_id",
    )


@pytest.mark.asyncio
async def test_rai_check_filters_messages_list_by_run_id() -> None:
    """`messages.list` must be called with `run_id=run.id` so we only
    surface assistant messages produced by *this* run -- defends
    against future thread-reuse regressions where a stale assistant
    message could be misread as the verdict.
    """
    from azure.ai.agents.models import ListSortOrder

    client = _make_rai_client(run_id="run_specific")
    provider = _FakeRaiAgentsProvider(client=client)
    db = _FakeDatabaseClient()

    await rai_check("hello", provider, db)

    client.messages.list.assert_called_once_with(
        thread_id="thr_rai_1",
        run_id="run_specific",
        order=ListSortOrder.ASCENDING,
    )


@pytest.mark.asyncio
async def test_rai_check_skips_user_messages_and_reads_first_agent_reply() -> None:
    """The mixed list (user echo + agent reply) -- often returned by
    SDKs -- must skip non-agent rows and take the first agent text.
    """
    client = _make_rai_client(
        agent_messages=[
            _user_message("echo of the prompt"),  # ignored
            _agent_text_message("FALSE"),  # the actual verdict
        ]
    )
    provider = _FakeRaiAgentsProvider(client=client)
    db = _FakeDatabaseClient()

    assert await rai_check("unsafe", provider, db) is False


@pytest.mark.asyncio
async def test_rai_check_failed_run_is_unsafe_fail_closed() -> None:
    """Run status `failed` -> return False without reading messages.
    Fail-closed is the only safe default for a guard.
    """
    client = _make_rai_client(run_status="failed")
    provider = _FakeRaiAgentsProvider(client=client)
    db = _FakeDatabaseClient()

    assert await rai_check("anything", provider, db) is False
    client.messages.list.assert_not_called()


@pytest.mark.asyncio
async def test_rai_check_unparseable_verdict_is_unsafe_fail_closed() -> None:
    """Agent returns a refusal / chatty text instead of TRUE/FALSE ->
    return False. The classifier prompt is strict, but a model can
    always go off-spec; a guard must not let that fail open.
    """
    client = _make_rai_client(
        agent_messages=[_agent_text_message("I cannot answer that.")]
    )
    provider = _FakeRaiAgentsProvider(client=client)
    db = _FakeDatabaseClient()

    assert await rai_check("anything", provider, db) is False


@pytest.mark.asyncio
async def test_rai_check_no_agent_messages_is_unsafe_fail_closed() -> None:
    """Run completes but the agent produces zero messages
    (pathological / network-loss SDK shape) -> return False.
    """
    client = _make_rai_client(agent_messages=[])
    provider = _FakeRaiAgentsProvider(client=client)
    db = _FakeDatabaseClient()

    assert await rai_check("anything", provider, db) is False
