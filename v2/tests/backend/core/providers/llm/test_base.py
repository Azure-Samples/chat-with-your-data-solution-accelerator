"""Tests for the LLM provider ABC default behavior.

Pillar: Stable Core
Phase: 2
"""

from typing import AsyncIterator, Sequence
from unittest.mock import MagicMock

import pytest

from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.settings import AppSettings
from backend.core.types import (
    ChatChunk,
    ChatMessage,
    EmbeddingResult,
    OrchestratorEvent,
)


class _StubProvider(BaseLLMProvider):
    """Minimal concrete provider that does NOT override
    ``supports_reasoning`` -- exercises the ABC default. The abstract
    methods are implemented as trivial stubs; the capability tests
    never call them."""

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatMessage:
        return ChatMessage(role="assistant", content="")

    async def chat_stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        yield ChatChunk(content="", finish_reason=None)

    async def embed(
        self,
        inputs: Sequence[str],
        *,
        deployment: str | None = None,
    ) -> EmbeddingResult:
        return EmbeddingResult(vectors=[], model="")

    async def reason(
        self,
        messages: Sequence[ChatMessage],
        *,
        deployment: str | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        yield OrchestratorEvent(channel="answer", content="")


def _stub() -> _StubProvider:
    return _StubProvider(MagicMock(spec=AppSettings), MagicMock())


@pytest.mark.asyncio
async def test_supports_reasoning_defaults_to_false() -> None:
    """A provider that does not override the capability query reports no
    reasoning support, so callers degrade to plain chat."""
    provider = _stub()

    assert await provider.supports_reasoning() is False


@pytest.mark.asyncio
async def test_supports_reasoning_defaults_to_false_for_explicit_deployment() -> None:
    """The default is unconditional -- an explicit deployment name does
    not change the ABC default."""
    provider = _stub()

    assert await provider.supports_reasoning("any-deployment") is False
