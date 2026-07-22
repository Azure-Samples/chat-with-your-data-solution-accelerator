"""Chat-history router.

Thin REST surface over the registered ``BaseDatabaseClient``
(``cosmosdb`` or ``postgresql`` -- selected at startup, see
``backend/app.py::_lifespan``). All routes are tenant-scoped: the
``user_id`` is derived from the ``x-ms-client-principal-id`` header
via ``UserIdDep`` so each request is naturally isolated to its
caller. A missing, blank, or non-GUID header folds into the anonymous
default id ``00000000-0000-0000-0000-000000000000`` (see
``backend.dependencies.get_user_id``), which scopes a shared tenant
partition rather than raising -- the id is a partition key, never a
trust boundary.

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

import logging
from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, Path, status

from backend.core.types import ChatMessage, ChatRole, Conversation, MessageRecord
from backend.dependencies import (
    ContentSafetyGuardDep,
    DatabaseClientDep,
    SettingsDep,
    UserIdDep,
)
from backend.models.errors import ErrorResponse
from backend.models.history import (
    AddMessageRequest,
    ConversationDetail,
    CreateConversationRequest,
    HistoryStatus,
    RenameConversationRequest,
    SetFeedbackRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/history", tags=["history"])


# Routes


@router.get(
    "/status",
    response_model=HistoryStatus,
    summary="Get chat-history status",
    description=(
        "Report whether chat history is enabled for this deployment and "
        "which chat-history store backs it (Cosmos DB or Postgres)."
    ),
)
async def history_status(settings: SettingsDep) -> HistoryStatus:
    return HistoryStatus(enabled=True, db_type=settings.database.db_type)


@router.get(
    "/conversations",
    response_model=list[Conversation],
    summary="List conversations",
    description=(
        "List every conversation belonging to the signed-in user, most " "recent first."
    ),
)
async def list_conversations(
    db: DatabaseClientDep, user_id: UserIdDep
) -> list[Conversation]:
    return list(await db.list_conversations(user_id))


@router.post(
    "/conversations",
    response_model=Conversation,
    status_code=status.HTTP_201_CREATED,
    summary="Create a conversation",
    description=(
        "Create a new, empty conversation for the signed-in user with an "
        "optional title and return the created record."
    ),
)
async def create_conversation(
    body: CreateConversationRequest,
    db: DatabaseClientDep,
    user_id: UserIdDep,
) -> Conversation:
    return await db.create_conversation(user_id=user_id, title=body.title)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
    summary="Get a conversation",
    description=(
        "Return a single conversation and its full ordered message list. "
        "Responds 404 when the conversation does not exist or does not "
        "belong to the signed-in user."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Conversation not found."},
    },
)
async def get_conversation(
    conversation_id: Annotated[
        str, Path(description="Identifier of the conversation to fetch.")
    ],
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
    "/conversations/{conversation_id}",
    response_model=Conversation,
    summary="Rename a conversation",
    description=(
        "Rename a conversation. The new title is screened by the "
        "content-safety guard when enabled (flagged titles are rejected "
        "with 400) and responds 404 when the conversation is not found."
    ),
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Title blocked by the content-safety guard.",
        },
        404: {"model": ErrorResponse, "description": "Conversation not found."},
    },
)
async def rename_conversation(
    conversation_id: Annotated[
        str, Path(description="Identifier of the conversation to rename.")
    ],
    body: RenameConversationRequest,
    db: DatabaseClientDep,
    user_id: UserIdDep,
    content_safety: ContentSafetyGuardDep,
) -> Conversation:
    # A renamed title is user-visible persisted text, so it is screened
    # by the content-safety guard (when enabled) before being stored: a
    # flagged title is rejected with 400 and never written. When the
    # guard is disabled (no client wired, or operator-off via runtime
    # overrides) screening is skipped. A guard transport failure
    # (AzureError) propagates to the app-level handler (503), not a
    # route-level try/except (Hard Rule #9).
    if content_safety is not None:
        verdict = await content_safety.screen(body.title)
        if verdict.flagged:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Title was blocked by the content safety guard.",
            )
    try:
        return await db.rename_conversation(conversation_id, user_id, body.title)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"conversation {conversation_id!r} not found",
        ) from exc


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
    description=(
        "Delete a conversation and its messages for the signed-in user. "
        "Idempotent: always responds 204 whether or not the conversation "
        "existed."
    ),
)
async def delete_conversation(
    conversation_id: Annotated[
        str, Path(description="Identifier of the conversation to delete.")
    ],
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
    summary="Append a message",
    description=(
        "Append a message to an existing conversation and return the "
        "stored record. Responds 404 when the conversation is not found."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Conversation not found."},
    },
)
async def add_message(
    conversation_id: Annotated[
        str, Path(description="Identifier of the conversation to append to.")
    ],
    body: AddMessageRequest,
    db: DatabaseClientDep,
    user_id: UserIdDep,
) -> MessageRecord:
    try:
        return await db.add_message(
            conversation_id=conversation_id,
            user_id=user_id,
            message=ChatMessage(role=cast(ChatRole, body.role), content=body.content),
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"conversation {conversation_id!r} not found",
        ) from exc


@router.post(
    "/messages/{message_id}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Set message feedback",
    description=(
        "Record thumbs-up / thumbs-down feedback on a message for the "
        "signed-in user. Responds 404 when the message is not found."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Message not found."},
    },
)
async def set_feedback(
    message_id: Annotated[
        str, Path(description="Identifier of the message to set feedback on.")
    ],
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


__all__ = ["router"]
