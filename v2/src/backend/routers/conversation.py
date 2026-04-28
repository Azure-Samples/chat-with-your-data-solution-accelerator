"""Conversation router.

Pillar: Stable Core
Phase: 3 (task #22a)

Single endpoint: ``POST /api/conversation``.

Two response modes, content-negotiated by the ``Accept`` header:

* ``text/event-stream`` → Server-Sent Events on the locked channel
  set in ADR 0007 (``reasoning`` / ``tool`` / ``answer`` /
  ``citation`` / ``error``). Each event is wire-formatted as
  ``event: <channel>\\ndata: <json>\\n\\n``.
* anything else (default) → buffered JSON
  (:class:`backend.models.conversation.ConversationResponse`) with the
  concatenated answer plus deduplicated citations.

Orchestrator dispatch goes through ``orchestrators.create(...)`` per
ADR 0001 / Hard Rule #4 — *no ``if/elif`` over orchestrator names in
this module*. The orchestrator stream is wrapped by
``pipelines.chat.run_chat`` (#22b), which gives us the seam to plug
content-safety / post-prompt guards once they are exposed via DI.
Today both guards default to ``None`` (pipeline streams through
unchanged), preserving the original router behavior.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from backend.dependencies import LLMProviderDep, SearchProviderDep, SettingsDep
from backend.models.conversation import ConversationRequest, ConversationResponse
from shared.pipelines.chat import run_chat
from shared.providers import orchestrators
from shared.types import Citation, OrchestratorEvent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["conversation"])

_SSE_MEDIA_TYPE = "text/event-stream"


def _wants_sse(accept: str | None) -> bool:
    """Return True when the client asked for the SSE feed."""
    if not accept:
        return False
    return _SSE_MEDIA_TYPE in accept.lower()


def _format_sse(event: OrchestratorEvent) -> bytes:
    """Encode one ``OrchestratorEvent`` as an SSE frame."""
    payload = json.dumps(
        {"content": event.content, "metadata": event.metadata},
        ensure_ascii=False,
    )
    return f"event: {event.channel}\ndata: {payload}\n\n".encode("utf-8")


async def _sse_stream(
    events: AsyncIterator[OrchestratorEvent],
    request: Request,
) -> AsyncIterator[bytes]:
    """Pump orchestrator events to the client; surface errors as ``error`` events."""
    try:
        async for event in events:
            if await request.is_disconnected():
                logger.info("Client disconnected; aborting SSE stream.")
                break
            yield _format_sse(event)
    except Exception as exc:  # noqa: BLE001 -- surfaced to the client channel
        logger.exception("Orchestrator failed during SSE stream.")
        yield _format_sse(
            OrchestratorEvent(channel="error", content=str(exc))
        )


async def _collect(
    events: AsyncIterator[OrchestratorEvent],
    *,
    conversation_id: str | None,
) -> ConversationResponse:
    """Buffer the event stream into a non-streaming JSON response."""
    answer_chunks: list[str] = []
    citations: list[Citation] = []
    seen_citation_ids: set[str] = set()

    async for event in events:
        if event.channel == "answer":
            answer_chunks.append(event.content)
        elif event.channel == "citation":
            cid = event.metadata.get("id")
            if isinstance(cid, str) and cid not in seen_citation_ids:
                citations.append(Citation(**event.metadata))
                seen_citation_ids.add(cid)
        elif event.channel == "error":
            # Bubble orchestrator failures to the caller verbatim; the
            # FastAPI default handler turns this into a 500.
            raise RuntimeError(event.content)

    return ConversationResponse(
        content="".join(answer_chunks),
        citations=citations,
        conversation_id=conversation_id,
    )


@router.post(
    "/conversation",
    response_model=None,  # response shape depends on Accept header
)
async def conversation(
    request: Request,
    body: ConversationRequest,
    settings: SettingsDep,
    llm: LLMProviderDep,
    search: SearchProviderDep,
    accept: str | None = Header(default=None),
) -> ConversationResponse | StreamingResponse:
    """Run the configured orchestrator and stream / buffer the result."""
    orchestrator = orchestrators.create(
        settings.orchestrator.name,
        settings=settings,
        llm=llm,
        search=search,
    )

    events = run_chat(body.messages, orchestrator=orchestrator)

    if _wants_sse(accept):
        return StreamingResponse(
            _sse_stream(events, request),
            media_type=_SSE_MEDIA_TYPE,
        )

    return await _collect(events, conversation_id=body.conversation_id)


__all__ = ["router"]
