"""Conversation request/response models.

Pillar: Stable Core
Phase: 3 (task #22a)
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from shared.types import ChatMessage, Citation


class ConversationRequest(BaseModel):
    """POST /api/conversation request body."""

    messages: list[ChatMessage] = Field(min_length=1)
    conversation_id: str | None = None


class ConversationResponse(BaseModel):
    """Non-streaming response (when `Accept` is not `text/event-stream`).

    The streaming variant emits the same content over the SSE channel
    set defined in ADR 0007 (`reasoning` / `tool` / `answer` /
    `citation` / `error`).
    """

    content: str
    citations: list[Citation] = Field(default_factory=list)
    conversation_id: str | None = None


__all__ = ["ConversationRequest", "ConversationResponse"]
