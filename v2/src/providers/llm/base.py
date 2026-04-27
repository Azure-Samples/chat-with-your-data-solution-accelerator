"""LLM provider ABC.

Pillar: Stable Core
Phase: 2

Every concrete provider (`foundry_iq`, future swap-ins) inherits from
`BaseLLMProvider` and self-registers via `@registry.register("<key>")`.
Constructors take `AppSettings` + an `AsyncTokenCredential`; provider
classes never read env vars directly (settings is the boundary).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, AsyncIterator, Sequence

if TYPE_CHECKING:
    from azure.core.credentials_async import AsyncTokenCredential

    from shared.settings import AppSettings
    from shared.types import ChatChunk, ChatMessage, EmbeddingResult


class BaseLLMProvider(ABC):
    def __init__(
        self, settings: "AppSettings", credential: "AsyncTokenCredential"
    ) -> None:
        self._settings = settings
        self._credential = credential

    @abstractmethod
    async def chat(
        self,
        messages: "Sequence[ChatMessage]",
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> "ChatMessage":
        """Single-shot chat completion. Returns the assistant message."""

    @abstractmethod
    def chat_stream(
        self,
        messages: "Sequence[ChatMessage]",
        *,
        deployment: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> "AsyncIterator[ChatChunk]":
        """Streamed chat completion. Yields deltas as `ChatChunk`s."""

    @abstractmethod
    async def embed(
        self,
        inputs: "Sequence[str]",
        *,
        deployment: str | None = None,
    ) -> "EmbeddingResult":
        """Embed one or more inputs into a dense vector."""

    @abstractmethod
    async def reason(
        self,
        messages: "Sequence[ChatMessage]",
        *,
        deployment: str | None = None,
    ) -> "ChatMessage":
        """Reasoning-model (o-series) completion.

        Implementations must route to the configured reasoning
        deployment and surface chain-of-thought separately from the
        final answer when the orchestrator integration lands (task #25
        in v2/docs/development_plan.md).
        """
