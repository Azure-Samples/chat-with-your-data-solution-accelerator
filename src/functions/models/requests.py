"""Pydantic models for function inputs/outputs."""

from __future__ import annotations

from pydantic import BaseModel


class AddUrlRequest(BaseModel):
    url: str
    metadata: dict = {}


class BatchStartRequest(BaseModel):
    process_all: bool = True


class SearchSkillInput(BaseModel):
    values: list[dict] = []


class SearchSkillOutput(BaseModel):
    values: list[dict] = []
