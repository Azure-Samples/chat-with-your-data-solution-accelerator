"""Shared Pydantic types used by providers and pipelines.

Pillar: Stable Core
Phase: 2

Keep this file focused on **value types** (request/response shapes,
domain objects) -- not behavior. Provider classes live under
`providers/`. Cross-cutting helpers live under `shared/tools/`.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]

# Channels exposed by orchestrators on the SSE reasoning feed (see
# v2-workflow.instructions.md). Defined here -- not in
# providers/orchestrators/ -- so providers like FoundryIQ.reason()
# can yield events without reaching across packages. Phase 5 brings
# the orchestrator base class itself.
OrchestratorChannel = Literal[
    "reasoning", "tool", "answer", "citation", "error"
]


class ChatMessage(BaseModel):
    """One turn in a chat conversation."""

    role: Role
    content: str
    name: str | None = None


class ChatChunk(BaseModel):
    """One streamed delta from a chat completion."""

    content: str = ""
    finish_reason: str | None = None


class EmbeddingResult(BaseModel):
    """Result of an embedding call. One vector per input."""

    vectors: list[list[float]] = Field(default_factory=list)
    model: str = ""

    @property
    def dimensions(self) -> int:
        return len(self.vectors[0]) if self.vectors else 0


class OrchestratorEvent(BaseModel):
    """Single event on the SSE reasoning feed.

    Shape is locked here so any producer (LLM provider's `reason()`,
    every concrete orchestrator, tool runners) emits the same wire
    format. Frontend renders `reasoning` events in a collapsible panel
    and `answer` events as the final response (per
    v2-workflow.instructions.md).
    """

    channel: OrchestratorChannel
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "ChatChunk",
    "ChatMessage",
    "EmbeddingResult",
    "OrchestratorChannel",
    "OrchestratorEvent",
    "Role",
]
