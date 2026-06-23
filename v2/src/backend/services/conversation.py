"""Conversation-response shaping helpers shared across routers.

Pillar: Stable Core
Phase: 7 (router cleanup -- conversation buffered-response helpers)
"""

import json
import logging
from collections.abc import AsyncIterator

from fastapi import Request

from backend.core.agents.presets import (
    DEFAULT_POST_ANSWERING_FILTER_MESSAGE,
    DEFAULT_POST_ANSWERING_PROMPT,
)
from backend.core.providers.databases.base import BaseDatabaseClient
from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.tools.post_prompt import PostPromptValidator
from backend.core.types import (
    ChatMessage,
    ChatRole,
    Citation,
    OrchestratorChannel,
    OrchestratorEvent,
    RuntimeConfig,
)
from backend.models.conversation import ConversationResponse
from backend.services.sse import format_sse

__all__ = [
    "build_post_prompt_validator",
    "collect_response",
    "persist_turn",
    "persisting_sse_stream",
]

logger = logging.getLogger(__name__)

_CONVERSATION_EVENT = "conversation"
"""SSE event-type for the terminal control frame that carries the
resolved conversation id back to the client. A transport-level control
event, deliberately not an :class:`OrchestratorChannel` member -- the
reasoning channel set is locked (Hard Rule #6), so the id rides its own
event-type rather than a channel."""


def build_post_prompt_validator(
    llm: BaseLLMProvider,
    overrides: RuntimeConfig | None,
) -> PostPromptValidator | None:
    """Build a ``PostPromptValidator`` from runtime overrides, or ``None``.

    The post-answering knobs live only in ``RuntimeConfig`` -- there
    is no ``AppSettings`` env baseline -- so the cascade is: a validator
    is built only when the operator opts in
    (``post_answering_enabled is True``). The validation prompt and
    filter message come from the override, falling back to the populated
    JSON defaults (ADR 0030) when the override is empty -- so enabling
    the feature without re-typing the prompt uses the default the admin
    UI already shows, rather than silently doing nothing. Any
    not-enabled combination (overrides missing, toggle ``None`` /
    ``False``) returns ``None`` so the chat pipeline streams unbuffered.
    """
    if overrides is None:
        return None
    if overrides.post_answering_enabled is not True:
        return None
    prompt = overrides.post_answering_prompt
    if prompt is None or not prompt.strip():
        prompt = DEFAULT_POST_ANSWERING_PROMPT
    filter_message = overrides.post_answering_filter_message
    if filter_message is None or not filter_message.strip():
        filter_message = DEFAULT_POST_ANSWERING_FILTER_MESSAGE
    return PostPromptValidator(
        llm,
        validation_prompt=prompt,
        filter_message=filter_message,
    )


async def collect_response(
    events: AsyncIterator[OrchestratorEvent],
    *,
    conversation_id: str | None,
) -> ConversationResponse:
    """Drain an orchestrator stream into a buffered ``ConversationResponse``.

    Walks every event on the locked channel set, concatenates each
    ``ANSWER`` chunk into the final ``content`` string, materializes
    each unique ``CITATION`` (keyed by ``metadata["id"]``) into a
    :class:`Citation`, and converts the first ``ERROR`` event into a
    ``RuntimeError`` so the FastAPI default handler turns the failure
    into a 500. The buffered partner to ``services.sse.sse_stream`` --
    same event source, opposite output mode.
    """
    answer_chunks: list[str] = []
    citations: list[Citation] = []
    seen_citation_ids: set[str] = set()

    async for event in events:
        if event.channel == OrchestratorChannel.ANSWER:
            answer_chunks.append(event.content)
        elif event.channel == OrchestratorChannel.CITATION:
            cid = event.metadata.get("id")
            if isinstance(cid, str) and cid not in seen_citation_ids:
                citations.append(Citation(**event.metadata))
                seen_citation_ids.add(cid)
        elif event.channel == OrchestratorChannel.ERROR:
            raise RuntimeError(event.content)

    return ConversationResponse(
        content="".join(answer_chunks),
        citations=citations,
        conversation_id=conversation_id,
    )


async def persist_turn(
    db: BaseDatabaseClient,
    *,
    user_id: str,
    conversation_id: str | None,
    question: str,
    answer: str,
    citations: list[Citation],
) -> str:
    """Persist one completed chat turn and return its conversation id.

    A turn is the latest user ``question`` paired with the assistant's
    ``answer`` and the ``citations`` that grounded it. When
    ``conversation_id`` is ``None`` -- or names a conversation that does
    not exist or is not owned by ``user_id`` -- a fresh conversation is
    created with its title set to ``question``, the first thing the user
    asked. Otherwise the named conversation is reused and its title left
    unchanged. The user message is appended before the assistant message
    so ``list_messages`` (oldest-first) replays the turn in spoken
    order, and the conversation's ``updated_at`` bump floats it to the
    top of the newest-first list.

    The grounding citations ride the assistant message's ``metadata``
    under a ``"citations"`` key (each serialized via
    ``Citation.model_dump``) so a reloaded conversation rehydrates its
    reference block without re-running retrieval. A turn with no
    citations leaves the metadata an empty dict, identical to the user
    message.

    Only the latest turn is written -- not the full thread the frontend
    sends -- so a follow-up appends two rows. The caller invokes this
    only after a successful, non-blocked answer and owns any storage
    failure: a persistence error must not retract an answer already
    delivered to the user.
    """
    conversation = None
    if conversation_id is not None:
        conversation = await db.get_conversation(conversation_id, user_id)
    if conversation is None:
        conversation = await db.create_conversation(user_id, title=question)
    resolved_id = conversation.id
    await db.add_message(
        resolved_id,
        user_id,
        ChatMessage(role=ChatRole.USER, content=question),
    )
    assistant_metadata = (
        {"citations": [citation.model_dump(mode="json") for citation in citations]}
        if citations
        else {}
    )
    await db.add_message(
        resolved_id,
        user_id,
        ChatMessage(
            role=ChatRole.ASSISTANT,
            content=answer,
            metadata=assistant_metadata,
        ),
    )
    return resolved_id


async def persisting_sse_stream(
    events: AsyncIterator[OrchestratorEvent],
    request: Request,
    *,
    db: BaseDatabaseClient,
    user_id: str,
    conversation_id: str | None,
    question: str,
) -> AsyncIterator[bytes]:
    """Stream orchestrator events as SSE frames, then persist the turn.

    The streaming counterpart to :func:`collect_response`: it pumps
    every event to the client as an SSE frame (delegating wire framing
    to :func:`backend.services.sse.format_sse`) while observing the
    stream to accumulate the assistant answer and its grounding
    citations and notice a terminal ``error`` event. When the stream
    completes with a non-empty answer and no error, the turn is handed
    to :func:`persist_turn` and a final
    ``conversation`` control frame carries the resolved conversation id
    back to the client so the frontend can track the thread.

    The ``conversation`` frame is a transport-level control event, not
    one of the locked orchestrator channels (Hard Rule #6): the
    conversation id exists only once the answer is fully streamed and
    persisted, so it can ride neither a response header (already
    flushed) nor an orchestrator channel. EventSource clients add a
    listener for the ``conversation`` event-type to capture the id.

    Nothing is persisted when the client disconnects mid-stream (the
    answer is partial), when any ``error`` event is seen (a blocked or
    failed turn), or when the accumulated answer is empty. A persistence
    failure is logged and swallowed -- the answer has already been
    delivered, so a storage outage must not retract it by tearing the
    stream.
    """
    answer_chunks: list[str] = []
    citations: list[Citation] = []
    seen_citation_ids: set[str] = set()
    error_seen = False

    try:
        async for event in events:
            if await request.is_disconnected():
                logger.info("Client disconnected; aborting SSE stream.")
                return
            if event.channel == OrchestratorChannel.ANSWER:
                answer_chunks.append(event.content)
            elif event.channel == OrchestratorChannel.CITATION:
                cid = event.metadata.get("id")
                if isinstance(cid, str) and cid not in seen_citation_ids:
                    citations.append(Citation(**event.metadata))
                    seen_citation_ids.add(cid)
            elif event.channel == OrchestratorChannel.ERROR:
                error_seen = True
            yield format_sse(event)
    except Exception as exc:  # noqa: BLE001 -- surfaced to the client channel
        logger.exception("Orchestrator failed during SSE stream.")
        yield format_sse(
            OrchestratorEvent(channel=OrchestratorChannel.ERROR, content=str(exc))
        )
        return

    answer = "".join(answer_chunks)
    if error_seen or not answer:
        return

    try:
        resolved_id = await persist_turn(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            question=question,
            answer=answer,
            citations=citations,
        )
    except Exception:  # noqa: BLE001 -- answer already delivered; never tear the stream
        logger.exception(
            "Failed to persist conversation turn.",
            extra={
                "operation": "persist_turn",
                "user_id": user_id,
                "conversation_id": conversation_id,
            },
        )
        return

    payload = json.dumps({"conversation_id": resolved_id}, ensure_ascii=False)
    yield f"event: {_CONVERSATION_EVENT}\ndata: {payload}\n\n".encode("utf-8")
