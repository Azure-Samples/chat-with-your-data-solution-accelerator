"""Chat-history router.

Pillar: Stable Core
Phase: 4 (task #31; hardened in #32b)

Thin REST surface over the registered ``BaseDatabaseClient``
(``cosmosdb`` or ``postgresql`` -- selected at startup, see
``backend/app.py::_lifespan``). All routes are tenant-scoped: the
``user_id`` is derived from the Easy Auth client-principal header
(``x-ms-client-principal-id``) so each request is naturally isolated
to its caller. When the header is missing we **only** fall back to a
single ``"local-dev"`` partition if ``AZURE_ENVIRONMENT=local``
(default for clean checkouts); production deployments raise ``401``
instead, so a misconfigured Easy Auth never silently merges every
caller into one tenant (see audit B1's sibling H1).

Routes
------

* ``GET    /api/history/status`` -- backend / db_type discovery
* ``GET    /api/history/conversations`` -- list (newest-first)
* ``POST   /api/history/conversations`` -- create
* ``GET    /api/history/conversations/{id}`` -- conversation + messages
* ``PATCH  /api/history/conversations/{id}`` -- rename
* ``DELETE /api/history/conversations/{id}`` -- delete (idempotent)
* ``POST   /api/history/conversations/{id}/messages`` -- append
* ``POST   /api/history/messages/{id}/feedback`` -- set feedback

KeyError raised by the database client surfaces as ``404`` -- the
router never inspects backend-specific exceptions (Cosmos /
asyncpg) directly, keeping the surface registry-only (Hard Rule #4).
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.dependencies import DatabaseClientDep, SettingsDep
from shared.types import ChatMessage, Conversation, MessageRecord

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/history", tags=["history"])


_LOCAL_DEV_USER = "local-dev"
_PRINCIPAL_ID_HEADER = "x-ms-client-principal-id"


def get_user_id(request: Request, settings: SettingsDep) -> str:
    """Return the caller's user id.

    Reads the Azure App Service Easy Auth header
    ``x-ms-client-principal-id`` (the user's Entra object id). When
    the header is absent we fall back to a single ``"local-dev"``
    partition **only** when ``settings.environment == "local"`` so
    the chat-history panel is exercisable end-to-end during
    development. In ``production`` a missing header raises
    ``401 Unauthorized`` -- a misconfigured Easy Auth must fail
    closed, never silently fold every anonymous caller into the
    ``local-dev`` partition.
    """
    value = request.headers.get(_PRINCIPAL_ID_HEADER, "").strip()
    if value:
        return value
    if settings.environment == "local":
        return _LOCAL_DEV_USER
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing client principal; Easy Auth header required.",
    )


UserIdDep = Annotated[str, Depends(get_user_id)]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateConversationRequest(BaseModel):
    title: str = Field(default="", max_length=512)


class RenameConversationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)


class AddMessageRequest(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1)


class SetFeedbackRequest(BaseModel):
    feedback: str = Field(min_length=1, max_length=64)


class HistoryStatus(BaseModel):
    enabled: bool
    db_type: str


class ConversationDetail(BaseModel):
    conversation: Conversation
    messages: list[MessageRecord]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/status", response_model=HistoryStatus)
async def history_status(settings: SettingsDep) -> HistoryStatus:
    return HistoryStatus(enabled=True, db_type=settings.database.db_type)


@router.get("/conversations", response_model=list[Conversation])
async def list_conversations(
    db: DatabaseClientDep, user_id: UserIdDep
) -> list[Conversation]:
    return list(await db.list_conversations(user_id))


@router.post(
    "/conversations",
    response_model=Conversation,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    body: CreateConversationRequest,
    db: DatabaseClientDep,
    user_id: UserIdDep,
) -> Conversation:
    return await db.create_conversation(user_id=user_id, title=body.title)


@router.get(
    "/conversations/{conversation_id}", response_model=ConversationDetail
)
async def get_conversation(
    conversation_id: str,
    db: DatabaseClientDep,
    user_id: UserIdDep,
) -> ConversationDetail:
    conv = await db.get_conversation(conversation_id, user_id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"conversation {conversation_id!r} not found",
        )
    messages = list(await db.list_messages(conversation_id, user_id))
    return ConversationDetail(conversation=conv, messages=messages)


@router.patch(
    "/conversations/{conversation_id}", response_model=Conversation
)
async def rename_conversation(
    conversation_id: str,
    body: RenameConversationRequest,
    db: DatabaseClientDep,
    user_id: UserIdDep,
) -> Conversation:
    try:
        return await db.rename_conversation(
            conversation_id, user_id, body.title
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"conversation {conversation_id!r} not found",
        ) from exc


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: str,
    db: DatabaseClientDep,
    user_id: UserIdDep,
) -> None:
    # Idempotent at the client layer (cosmos: silent on 404; postgres:
    # DELETE 0 returns silently). Always 204.
    await db.delete_conversation(conversation_id, user_id)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageRecord,
    status_code=status.HTTP_201_CREATED,
)
async def add_message(
    conversation_id: str,
    body: AddMessageRequest,
    db: DatabaseClientDep,
    user_id: UserIdDep,
) -> MessageRecord:
    try:
        return await db.add_message(
            conversation_id=conversation_id,
            user_id=user_id,
            message=ChatMessage(role=body.role, content=body.content),
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"conversation {conversation_id!r} not found",
        ) from exc


@router.post(
    "/messages/{message_id}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def set_feedback(
    message_id: str,
    body: SetFeedbackRequest,
    db: DatabaseClientDep,
    user_id: UserIdDep,
) -> None:
    try:
        await db.set_feedback(message_id, user_id, body.feedback)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"message {message_id!r} not found",
        ) from exc


__all__ = ["get_user_id", "router"]
