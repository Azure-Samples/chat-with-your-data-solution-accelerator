"""Conversation-response shaping helpers shared across routers.

Pillar: Stable Core
Phase: 7 (router cleanup -- conversation buffered-response helpers)
"""

from collections.abc import AsyncIterator

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

__all__ = ["build_post_prompt_validator", "collect_response", "persist_turn"]


def build_post_prompt_validator(
    llm: BaseLLMProvider,
    overrides: RuntimeConfig | None,
) -> PostPromptValidator | None:
    """Build a ``PostPromptValidator`` from runtime overrides, or ``None``.

    The post-answering knobs live only in ``RuntimeConfig`` -- there
    is no ``AppSettings`` env baseline -- so the cascade is simple:
    a validator is built only when the operator both opts in
    (``post_answering_enabled is True``) and supplies a non-empty
    ``post_answering_prompt`` template. Any other combination
    (overrides missing, toggle ``None``/``False``, blank prompt)
    returns ``None`` so the chat pipeline streams unbuffered. When
    set, ``post_answering_filter_message`` overrides the validator's
    built-in default; empty/whitespace keeps the default.
    """
    if overrides is None:
        return None
    if overrides.post_answering_enabled is not True:
        return None
    prompt = overrides.post_answering_prompt
    if prompt is None or not prompt.strip():
        return None
    filter_message = overrides.post_answering_filter_message
    if filter_message:
        return PostPromptValidator(
            llm,
            validation_prompt=prompt,
            filter_message=filter_message,
        )
    return PostPromptValidator(llm, validation_prompt=prompt)


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
) -> str:
    """Persist one completed chat turn and return its conversation id.

    A turn is the latest user ``question`` paired with the assistant's
    ``answer``. When ``conversation_id`` is ``None`` -- or names a
    conversation that does not exist or is not owned by ``user_id`` --
    a fresh conversation is created with its title set to ``question``,
    the first thing the user asked. Otherwise the named conversation is
    reused and its title left unchanged. The user message is appended
    before the assistant message so ``list_messages`` (oldest-first)
    replays the turn in spoken order, and the conversation's
    ``updated_at`` bump floats it to the top of the newest-first list.

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
    await db.add_message(
        resolved_id,
        user_id,
        ChatMessage(role=ChatRole.ASSISTANT, content=answer),
    )
    return resolved_id
