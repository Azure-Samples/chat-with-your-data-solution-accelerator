"""Orchestrator ABC.

Pillar: Stable Core
Phase: 3

Every concrete orchestrator (`langgraph` task #18, `agent_framework`
task #19, future swap-ins) inherits from `OrchestratorBase` and
self-registers via `@registry.register("<key>")`. Constructors take
`AppSettings` + an `BaseLLMProvider` (so the orchestrator can call into
Foundry IQ without re-resolving credentials -- see ADR 0005).

The single abstract method `run()` returns an `AsyncIterator` of typed
`OrchestratorEvent` objects on the locked SSE channel set
(`reasoning` / `tool` / `answer` / `citation` / `error` -- ADR 0007).
Reasoning text never leaks into the answer string; producers emit
events on the channel that matches their semantics.

Lifecycle: orchestrators that hold long-lived clients (e.g. a
`langgraph` `MemorySaver`, an Agent Framework session) override
`aclose()` to release them. The default is a no-op so simple
orchestrators don't need ceremony.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncIterator, Sequence

if TYPE_CHECKING:
    from shared.providers.llm.base import BaseLLMProvider
    from shared.settings import AppSettings
    from shared.types import ChatMessage, OrchestratorEvent


class OrchestratorBase(ABC):
    def __init__(
        self,
        settings: "AppSettings",
        llm: "BaseLLMProvider",
    ) -> None:
        self._settings = settings
        self._llm = llm

    @abstractmethod
    def run(
        self,
        messages: "Sequence[ChatMessage]",
        *,
        settings_override: dict[str, Any] | None = None,
    ) -> "AsyncIterator[OrchestratorEvent]":
        """Run the orchestrator and yield typed events.

        Implementations are typically `async def` with `yield` -- the
        ABC declares the return type as `AsyncIterator[OrchestratorEvent]`
        to match PEP 525 async generators.

        `settings_override` is a per-request escape hatch for
        runtime-tunable knobs (e.g. orchestrator selection, prompt
        overrides). Infrastructure-pinned settings (Bicep outputs)
        cannot be overridden -- those live on `self._settings`.
        """

    async def aclose(self) -> None:
        """Release any long-lived resources. Default no-op."""
        return None
