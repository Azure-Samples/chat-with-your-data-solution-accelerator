"""SSE wire-format helpers shared across streaming routers."""

import json
import logging
from collections.abc import AsyncIterator

from fastapi import Request

from backend.core.types import OrchestratorChannel, OrchestratorEvent

__all__ = ["SSE_MEDIA_TYPE", "format_sse", "sse_stream", "wants_sse"]


logger = logging.getLogger(__name__)

SSE_MEDIA_TYPE = "text/event-stream"
"""Media type for Server-Sent Events streams (RFC ``text/event-stream``)."""


def format_sse(event: OrchestratorEvent) -> bytes:
    """Encode one ``OrchestratorEvent`` as an SSE frame.

    Wire format per the SSE spec: ``event: <channel>\\ndata: <json>\\n\\n``.
    The JSON payload carries ``content`` and ``metadata`` only -- the
    ``channel`` is hoisted onto the ``event:`` line so EventSource clients
    can dispatch by channel without parsing the body.
    """
    payload = json.dumps(
        {"content": event.content, "metadata": event.metadata},
        ensure_ascii=False,
    )
    return f"event: {event.channel}\ndata: {payload}\n\n".encode("utf-8")


def wants_sse(accept: str | None) -> bool:
    """Return ``True`` when the client's ``Accept`` header asks for the SSE feed.

    Case-insensitive substring match against ``SSE_MEDIA_TYPE`` so a header
    like ``text/event-stream, application/json;q=0.9`` still routes to the
    streaming branch.
    """
    if not accept:
        return False
    return SSE_MEDIA_TYPE in accept.lower()


async def sse_stream(
    events: AsyncIterator[OrchestratorEvent],
    request: Request,
) -> AsyncIterator[bytes]:
    """Pump orchestrator events to the client as SSE frames, aborting on disconnect.

    Wraps ``format_sse`` to drain the orchestrator's event stream, checks
    ``request.is_disconnected()`` on each event so the server stops doing
    work for a walked-away browser, and converts any exception raised by
    the underlying stream into a final ``error``-channel frame -- giving
    the EventSource client the failure on the locked channel rather than
    as a torn connection.
    """
    try:
        async for event in events:
            if await request.is_disconnected():
                logger.info("Client disconnected; aborting SSE stream.")
                break
            yield format_sse(event)
    except Exception as exc:  # noqa: BLE001 -- surfaced to the client channel
        logger.exception("Orchestrator failed during SSE stream.")
        yield format_sse(
            OrchestratorEvent(channel=OrchestratorChannel.ERROR, content=str(exc))
        )
