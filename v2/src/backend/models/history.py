"""Chat-history request/response models.

Pillar: Stable Core
Phase: 4
"""

from pydantic import BaseModel, Field, field_validator

from backend.core.types import Conversation, MessageRecord


class AddMessageRequest(BaseModel):
    """POST /api/history/conversations/{id}/messages request body."""

    role: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1)


class ConversationDetail(BaseModel):
    """GET /api/history/conversations/{id} response body."""

    conversation: Conversation
    messages: list[MessageRecord]


class CreateConversationRequest(BaseModel):
    """POST /api/history/conversations request body."""

    title: str = Field(default="", max_length=512)


class HistoryStatus(BaseModel):
    """GET /api/history/status response body."""

    enabled: bool
    db_type: str


class RenameConversationRequest(BaseModel):
    """PATCH /api/history/conversations/{id} request body."""

    title: str = Field(min_length=1, max_length=512)

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

    feedback: str = Field(min_length=1, max_length=64)


__all__ = ["AddMessageRequest", "ConversationDetail", "CreateConversationRequest", "HistoryStatus", "RenameConversationRequest", "SetFeedbackRequest"]
