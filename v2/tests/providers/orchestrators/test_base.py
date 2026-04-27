"""Tests for the orchestrator domain skeleton (Phase 3 task #17).

Pillar: Stable Core
Phase: 3
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Sequence
from unittest.mock import MagicMock

import pytest

from providers import orchestrators
from providers.llm.base import BaseLLMProvider
from providers.orchestrators.base import OrchestratorBase
from shared.settings import AppSettings
from shared.types import ChatMessage, OrchestratorEvent


# ---------------------------------------------------------------------------
# Minimal concrete subclass for shape tests. NOT registered (so the public
# registry stays empty until task #18 lands a real provider).
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
# Registry shape (task #17 deliverable)
# ---------------------------------------------------------------------------


def test_registry_exists_and_is_empty_until_task_18() -> None:
    """No concrete provider registers in this unit -- only the ABC + registry land."""
    assert orchestrators.registry.domain == "orchestrators"
    assert orchestrators.registry.keys() == []


def test_create_raises_keyerror_with_helpful_message_when_empty() -> None:
    with pytest.raises(KeyError) as excinfo:
        orchestrators.create("langgraph")
    msg = str(excinfo.value)
    assert "orchestrators" in msg
    assert "langgraph" in msg
    assert "<none>" in msg  # registry's empty-availability marker


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
    events = [event async for event in orch.run([ChatMessage(role="user", content="hi")])]
    assert len(events) == 1
    assert events[0].channel == "answer"
    assert events[0].content == "x"
