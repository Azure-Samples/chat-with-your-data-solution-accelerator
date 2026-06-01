"""Conversation-response shaping helpers shared across routers.

Pillar: Stable Core
Phase: 7 (router cleanup -- conversation buffered-response helpers)
"""

from collections.abc import AsyncIterator

from backend.core.types import Citation, OrchestratorChannel, OrchestratorEvent
from backend.models.conversation import ConversationResponse

__all__ = ["collect_response"]


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
