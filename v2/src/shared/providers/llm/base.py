"""LLM provider ABC.

Pillar: Stable Core
Phase: 2

Every concrete provider (`foundry_iq`, future swap-ins) inherits from
`BaseLLMProvider` and self-registers via `@registry.register("<key>")`.
Constructors take `AppSettings` + an `AsyncTokenCredential`; provider
classes never read env vars directly (settings is the boundary).

Lifecycle: providers may hold an SDK client (e.g. `AIProjectClient`)
that owns an HTTP transport. Callers are expected to invoke
`await provider.aclose()` during shutdown -- the FastAPI lifespan in
`backend/app.py` does this for the cached singleton.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, AsyncIterator, Sequence

if TYPE_CHECKING:
    from azure.core.credentials_async import AsyncTokenCredential

    from shared.settings import AppSettings
    from shared.types import (
        ChatChunk,
        ChatMessage,
        EmbeddingResult,
        OrchestratorEvent,
    )


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
        """Streamed chat completion. Yields deltas as `ChatChunk`s.

        Implementations are typically `async def` with `yield` -- the
        ABC declares the return type as `AsyncIterator[ChatChunk]` to
        match PEP 525 async generators.
        """

    @abstractmethod
    async def embed(
        self,
        inputs: "Sequence[str]",
        *,
        deployment: str | None = None,
    ) -> "EmbeddingResult":
        """Embed one or more inputs into a dense vector."""

    @abstractmethod
    def reason(
        self,
        messages: "Sequence[ChatMessage]",
        *,
        deployment: str | None = None,
    ) -> "AsyncIterator[OrchestratorEvent]":
        """Reasoning-model (o-series) completion.

        Yields `OrchestratorEvent`s on two channels:

        - `channel="reasoning"` -- chain-of-thought tokens (rendered in
          the frontend's collapsible reasoning panel).
        - `channel="answer"` -- the final answer tokens.

        Implementations route to the configured reasoning deployment.
        Wired end-to-end by task #25 in v2/docs/development_plan.md
        (Phase 7).
        """

    async def aclose(self) -> None:
        """Release any owned SDK clients. Default implementation is a no-op."""
