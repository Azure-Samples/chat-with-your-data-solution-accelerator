"""Conversation endpoint: POST /api/conversation."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..models.conversation import ConversationRequest

router = APIRouter()


@router.post("/conversation")
async def conversation(request: ConversationRequest, req: Request):
    # TODO: Phase 2 — implement BYOD + Custom conversation flows with streaming
    return JSONResponse(
        content={
            "id": "",
            "choices": [
                {
                    "messages": [
                        {
                            "role": "assistant",
                            "content": "Conversation endpoint not yet implemented.",
                        }
                    ]
                }
            ],
        }
    )
