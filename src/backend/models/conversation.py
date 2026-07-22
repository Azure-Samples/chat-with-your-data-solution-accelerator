"""Conversation request/response models."""

from pydantic import BaseModel, Field

from backend.core.types import ChatMessage, Citation


class ConversationRequest(BaseModel):
    """POST /api/conversation request body."""

    messages: list[ChatMessage] = Field(
        min_length=1,
        description=(
            "Ordered chat turns for this exchange; the final entry is the "
            "current user prompt. Must contain at least one message."
        ),
    )
    conversation_id: str | None = Field(
        default=None,
        description=(
            "Existing conversation id to append this exchange to. Omit or "
            "send null to start a new conversation."
        ),
    )


class ConversationResponse(BaseModel):
    """Non-streaming response (when `Accept` is not `text/event-stream`).

    The streaming variant emits the same content over the SSE channel
    set defined in ADR 0007 (`reasoning` / `tool` / `answer` /
    `citation` / `error`).
    """

    content: str = Field(description="The assistant's answer text.")
    citations: list[Citation] = Field(
        default_factory=list[Citation],
        description=(
            "Source citations that ground the answer; empty when no sources "
            "were used."
        ),
    )
    conversation_id: str | None = Field(
        default=None,
        description=(
            "Id of the conversation this exchange belongs to, when chat "
            "history is enabled."
        ),
    )


__all__ = ["ConversationRequest", "ConversationResponse"]
