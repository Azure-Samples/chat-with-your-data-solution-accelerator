"""Chat history request/response models."""

from __future__ import annotations

from pydantic import BaseModel


class HistoryReadRequest(BaseModel):
    conversation_id: str


class HistoryRenameRequest(BaseModel):
    conversation_id: str
    title: str


class HistoryDeleteRequest(BaseModel):
    conversation_id: str


class HistoryMessage(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    feedback: str | None = None


class HistoryListResponse(BaseModel):
    conversations: list[dict] = []
