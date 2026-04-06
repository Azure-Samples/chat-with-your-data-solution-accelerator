"""Auth endpoints."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/checkauth")
async def check_auth():
    # TODO: Phase 2 — implement auth check (MS Entra ID headers)
    return {"authenticated": True}


@router.get("/assistanttype")
async def get_assistant_type():
    # TODO: Phase 2 — return conversation flow type from settings
    return {"assistant_type": "custom"}
