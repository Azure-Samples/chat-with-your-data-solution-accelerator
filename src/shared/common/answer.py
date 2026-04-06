"""Common answer model used across orchestrators."""

from __future__ import annotations

from pydantic import BaseModel


class SourceDocument(BaseModel):
    id: str = ""
    content: str = ""
    title: str = ""
    source: str = ""
    chunk: int | None = None
    offset: int | None = None
    page_number: int | None = None


class Answer(BaseModel):
    question: str
    answer: str
    source_documents: list[SourceDocument] = []
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
