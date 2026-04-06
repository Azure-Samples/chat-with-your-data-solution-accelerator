"""Admin request/response models."""

from __future__ import annotations

from pydantic import BaseModel


class DocumentListResponse(BaseModel):
    documents: list[dict] = []


class UploadSasResponse(BaseModel):
    sas_url: str


class AdminSettingsResponse(BaseModel):
    function_url: str
    function_key: str
