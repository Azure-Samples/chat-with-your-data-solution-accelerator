"""File serving endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/files/{filename:path}")
async def get_file(filename: str):
    # TODO: Phase 2 — serve files from blob storage
    raise HTTPException(status_code=404, detail="File not found")
