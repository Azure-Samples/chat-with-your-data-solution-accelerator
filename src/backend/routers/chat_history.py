"""Chat history endpoints."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/history/list")
async def list_conversations():
    # TODO: Phase 2
    return []


@router.post("/history/read")
async def read_conversation():
    # TODO: Phase 2
    return {"messages": []}


@router.post("/history/update")
async def update_conversation():
    # TODO: Phase 2
    return {"success": True}


@router.post("/history/rename")
async def rename_conversation():
    # TODO: Phase 2
    return {"success": True}


@router.post("/history/delete")
async def delete_conversation():
    # TODO: Phase 2
    return {"success": True}


@router.delete("/history/delete_all")
async def delete_all_conversations():
    # TODO: Phase 2
    return {"success": True}


@router.get("/history/frontend_settings")
async def frontend_settings():
    # TODO: Phase 2 — return chat history feature flag + feedback flag
    return {"CHAT_HISTORY_ENABLED": False, "FEEDBACK_ENABLED": False}
