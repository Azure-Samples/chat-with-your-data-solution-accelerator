"""Conversation request/response models."""

from __future__ import annotations

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class Citation(BaseModel):
    content: str = ""
    title: str = ""
    url: str = ""
    filepath: str = ""
    chunk_id: str = ""


class ConversationRequest(BaseModel):
    messages: list[ChatMessage]
    conversation_id: str | None = None


class ConversationChoice(BaseModel):
    messages: list[ChatMessage]


class ConversationResponse(BaseModel):
    id: str
    choices: list[ConversationChoice]
