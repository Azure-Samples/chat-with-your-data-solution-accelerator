"""Chat-history request/response models."""

from pydantic import BaseModel, Field, field_validator

from backend.core.types import Conversation, MessageRecord


class AddMessageRequest(BaseModel):
    """POST /api/history/conversations/{id}/messages request body."""

    role: str = Field(
        min_length=1,
        max_length=32,
        description="Author role of the message (e.g. user or assistant).",
    )
    content: str = Field(
        min_length=1, description="Message text to append to the conversation."
    )


class ConversationDetail(BaseModel):
    """GET /api/history/conversations/{id} response body."""

    conversation: Conversation = Field(
        description="Conversation metadata (id, title, timestamps)."
    )
    messages: list[MessageRecord] = Field(
        description="All stored messages in the conversation, in chronological order."
    )


class CreateConversationRequest(BaseModel):
    """POST /api/history/conversations request body."""

    title: str = Field(
        default="",
        max_length=512,
        description=(
            "Optional initial conversation title; defaults to empty and may be "
            "set later via rename."
        ),
    )


class HistoryStatus(BaseModel):
    """GET /api/history/status response body."""

    enabled: bool = Field(
        description="Whether chat-history persistence is enabled for this deployment."
    )
    db_type: str = Field(
        description="Configured history backend identifier (e.g. cosmosdb or postgres)."
    )


class RenameConversationRequest(BaseModel):
    """PATCH /api/history/conversations/{id} request body."""

    title: str = Field(
        min_length=1,
        max_length=512,
        description=(
            "New conversation title; leading/trailing whitespace is stripped "
            "and a blank title is rejected."
        ),
    )

    @field_validator("title")
    @classmethod
    def _strip_and_require_nonblank(cls, value: str) -> str:
        # A whitespace-only title (e.g. "   ") clears the displayed
        # name in the history list, so it is rejected. The accepted
        # value is normalized to its stripped form so a renamed
        # conversation never persists surrounding whitespace.
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be blank")
        return stripped


class SetFeedbackRequest(BaseModel):
    """POST /api/history/messages/{id}/feedback request body."""

    feedback: str = Field(
        min_length=1,
        max_length=64,
        description="Feedback marker for the message (e.g. positive or negative).",
    )


__all__ = [
    "AddMessageRequest",
    "ConversationDetail",
    "CreateConversationRequest",
    "HistoryStatus",
    "RenameConversationRequest",
    "SetFeedbackRequest",
]
