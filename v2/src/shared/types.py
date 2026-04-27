"""Shared Pydantic types used by providers and pipelines.

Pillar: Stable Core
Phase: 2

Keep this file focused on **value types** (request/response shapes,
domain objects) -- not behavior. Provider classes live under
`providers/`. Cross-cutting helpers live under `shared/tools/`.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]


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


__all__ = ["ChatChunk", "ChatMessage", "EmbeddingResult", "Role"]
