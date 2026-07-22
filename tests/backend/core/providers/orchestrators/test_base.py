"""Tests for the orchestrator domain skeleton."""

from typing import Any, AsyncIterator, Sequence
from unittest.mock import MagicMock

import pytest

from backend.core.providers.orchestrators import registry as orchestrators_registry
from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.providers.orchestrators.base import OrchestratorBase
from backend.core.settings import AppSettings
from backend.core.types import ChatMessage, OrchestratorEvent

# ---------------------------------------------------------------------------
# Minimal concrete subclass for shape tests. NOT registered (so the public
# registry stays empty until a real provider is registered).
# ---------------------------------------------------------------------------


class _StubOrchestrator(OrchestratorBase):
    async def run(
        self,
        messages: Sequence[ChatMessage],
        *,
        settings_override: dict[str, Any] | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        yield OrchestratorEvent(channel="answer", content="x")


# ---------------------------------------------------------------------------
# Registry shape
# ---------------------------------------------------------------------------


def test_registry_domain_and_known_providers() -> None:
    """`langgraph` and `agent_framework` are the registered orchestrators."""
    assert orchestrators_registry.registry.domain == "orchestrators"
    assert "langgraph" in orchestrators_registry.registry.keys()


def test_create_raises_keyerror_for_unknown_provider() -> None:
    with pytest.raises(KeyError) as excinfo:
        orchestrators_registry.registry.get("does_not_exist")
    msg = str(excinfo.value)
    assert "orchestrators" in msg
    assert "does_not_exist" in msg
    # Registered providers are listed in the error message.
    assert "langgraph" in msg


# ---------------------------------------------------------------------------
# ABC contract
# ---------------------------------------------------------------------------


def test_orchestrator_base_cannot_be_instantiated_directly() -> None:
    settings = MagicMock(spec=AppSettings)
    llm = MagicMock(spec=BaseLLMProvider)
    with pytest.raises(TypeError):
        OrchestratorBase(settings=settings, llm=llm)  # type: ignore[abstract]


def test_constructor_stores_settings_and_llm() -> None:
    settings = MagicMock(spec=AppSettings)
    llm = MagicMock(spec=BaseLLMProvider)
    orch = _StubOrchestrator(settings=settings, llm=llm)
    assert orch._settings is settings
    assert orch._llm is llm


@pytest.mark.asyncio
async def test_aclose_default_is_noop() -> None:
    settings = MagicMock(spec=AppSettings)
    llm = MagicMock(spec=BaseLLMProvider)
    orch = _StubOrchestrator(settings=settings, llm=llm)
    # Must be awaitable and return None without raising.
    result = await orch.aclose()
    assert result is None


@pytest.mark.asyncio
async def test_run_is_an_async_generator_yielding_orchestrator_events() -> None:
    settings = MagicMock(spec=AppSettings)
    llm = MagicMock(spec=BaseLLMProvider)
    orch = _StubOrchestrator(settings=settings, llm=llm)
    events = [
        event async for event in orch.run([ChatMessage(role="user", content="hi")])
    ]
    assert len(events) == 1
    assert events[0].channel == "answer"
    assert events[0].content == "x"
