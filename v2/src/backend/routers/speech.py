"""Speech endpoint."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/speech")
async def get_speech_token():
    # TODO: Phase 2 — return Azure Speech token
    return {"token": "", "region": ""}
