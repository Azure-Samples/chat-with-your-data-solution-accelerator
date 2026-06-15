"""Chat pipeline.

Pillar: Stable Core
Phase: 3

Pure async generator that wraps the chat flow:

    user messages
      → content-safety pre-screen (optional)        ← ContentSafetyGuard (Azure REST)
      → RAI agent classifier pre-screen (optional)  ← rai_check (Foundry agent, CU-011a)
      → orchestrator.run()
      → post-prompt groundedness validation (optional)
      → SSE-channel events (ADR 0007)

The pipeline knows **nothing** about FastAPI: it consumes already-built
collaborators (orchestrator, optional ``ContentSafetyGuard``, optional
RAI screener callable, optional ``PostPromptValidator``) and yields
:class:`OrchestratorEvent` values.
``backend/routers/conversation.py`` is the FastAPI adapter that turns
this stream into JSON or SSE.

Behavior contracts
------------------

* **Content safety (REST)**: when a ``ContentSafetyGuard`` is supplied
  and the latest user message trips its severity threshold, the
  pipeline yields a single ``error`` event with
  ``metadata.code == "content_safety"`` and stops. The orchestrator is
  never invoked.
* **RAI agent (Foundry)**: when a ``rai_check`` callable is supplied
  and the latest user message classifies as **unsafe** (``rai_check``
  returns ``False``), the pipeline yields a single ``error`` event with
  ``metadata.code == "rai_blocked"`` and stops. Runs *after* the
  ``ContentSafetyGuard`` so the cheap REST screen short-circuits the
  more expensive Foundry round-trip. Both guards are independent and
  can be enabled together; the first to flag wins.
  The pipeline takes a callable (not a provider + db pair) so it stays
  free of DI plumbing -- the router binds ``rai_check`` as
  ``functools.partial(rai_check, agents=agents, db=db)`` (or a closure)
  before calling ``run_chat``.
* **Retrieval narration**: when ``retrieval_hint`` is supplied (the
  router passes it only when a knowledge source is wired), a single
  ``reasoning`` event carrying that text is emitted *before* the
  orchestrator runs -- and only after both guards pass -- so the
  client's thinking panel shows retrieval activity for the whole wait
  instead of a flash once retrieval has already completed. Orchestrator
  reasoning frames stream after it. Every orchestrator inherits this
  with zero per-provider code.
* **Post-prompt validation**: when a validator is supplied, ``answer``
  events are *buffered* until the orchestrator stream finishes, then
  validated, then emitted as a single ``answer`` event whose content
  is either the original answer (grounded) or the validator's filter
  message (not grounded). Citations / reasoning / tool events stream
  through as they arrive — only ``answer`` is buffered.
* **No validator**: ``answer`` events stream through unchanged
  (sub-second perceived latency for the streaming client).
"""

import logging
from typing import AsyncIterator, Awaitable, Callable, Sequence

from backend.core.providers.orchestrators.base import OrchestratorBase
from backend.core.tools.content_safety import ContentSafetyGuard
from backend.core.tools.post_prompt import PostPromptValidator
from backend.core.types import (
    ChatMessage,
    ChatRole,
    Citation,
    OrchestratorChannel,
    OrchestratorEvent,
    SearchResult,
)

logger = logging.getLogger(__name__)

# Canonical "thinking" narration surfaced on the `reasoning` channel
# while a grounded request is answered. Retrieval (knowledge-base query
# or search) dominates the wait, so narrating it keeps the client's
# thinking panel populated for the whole turn. The string lives here so
# every orchestrator surfaces identical wording; callers pass it via
# `run_chat(retrieval_hint=...)` only when a knowledge source is wired.
KB_SEARCH_NARRATION = "Searching the knowledge base for relevant sources\u2026"

# Type alias for the RAI screener callable. Returns True when input
# is safe, False when unsafe. The pipeline never inspects the
# implementation -- the router is responsible for binding the
# `agents` provider + `db` client into a partial / closure that
# matches this shape.
RaiScreener = Callable[[str], Awaitable[bool]]


def _latest_user_text(messages: Sequence[ChatMessage]) -> str:
    """Return the text of the most recent user message (empty string if none)."""
    for message in reversed(messages):
        if message.role is ChatRole.USER:
            return message.content
    return ""


def _citation_to_search_result(citation: Citation) -> SearchResult:
    """Adapt a streamed citation back to a `SearchResult` for post-prompt."""
    return SearchResult(
        id=citation.id,
        content=citation.snippet,
        title=citation.title,
        url=citation.url,
        score=citation.score,
        metadata=citation.metadata,
    )


async def run_chat(
    messages: Sequence[ChatMessage],
    *,
    orchestrator: OrchestratorBase,
    content_safety: ContentSafetyGuard | None = None,
    rai_check: RaiScreener | None = None,
    post_prompt: PostPromptValidator | None = None,
    retrieval_hint: str | None = None,
) -> AsyncIterator[OrchestratorEvent]:
    """Run the configured chat flow and yield typed SSE events."""
    user_text = _latest_user_text(messages)

    if content_safety is not None:
        verdict = await content_safety.screen(user_text)
        if verdict.flagged:
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ERROR,
                content="Input was blocked by the content safety guard.",
                metadata={"code": "content_safety", "triggered": verdict.triggered},
            )
            return

    if rai_check is not None:
        # Order matters: REST content-safety runs first (cheap, ~50ms
        # per call), Foundry RAI agent second (more expensive, full
        # thread + run round-trip). Either guard flagging the input
        # short-circuits before orchestrator dispatch -- the user
        # message never reaches the model.
        is_safe = await rai_check(user_text)
        if not is_safe:
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ERROR,
                content="Input was blocked by the RAI safety classifier.",
                metadata={"code": "rai_blocked"},
            )
            return

    # Orchestrator-agnostic thinking narration: emitted only after both
    # guards pass (a blocked request must not claim it is "searching")
    # and before the orchestrator runs, so the client's thinking panel
    # shows retrieval activity for the whole wait rather than a flash
    # once retrieval has already completed. Marked `placeholder` on the
    # metadata so the client surfaces it only until the orchestrator's
    # own reasoning frames begin: a reasoning-capable model replaces it
    # with real thinking, while a non-reasoning model keeps it as the
    # sole reasoning-panel content. The flag is the wire contract with
    # the frontend SSE consumer.
    if retrieval_hint is not None:
        yield OrchestratorEvent(
            channel=OrchestratorChannel.REASONING,
            content=retrieval_hint,
            metadata={"placeholder": True},
        )

    answer_buffer: list[str] = []
    citations: list[Citation] = []
    seen_citation_ids: set[str] = set()
    buffering_answer = post_prompt is not None

    async for event in orchestrator.run(messages):
        if event.channel == OrchestratorChannel.ANSWER and buffering_answer:
            answer_buffer.append(event.content)
            continue
        if event.channel == OrchestratorChannel.CITATION:
            cid = event.metadata.get("id")
            if isinstance(cid, str) and cid not in seen_citation_ids:
                seen_citation_ids.add(cid)
                try:
                    citations.append(Citation(**event.metadata))
                except Exception as exc:  # noqa: BLE001 -- malformed metadata is non-fatal
                    # Per v2/docs/exception_handling_policy.md "Pipelines" row:
                    # the citation metadata schema can drift across orchestrator
                    # versions (extra keys, wrong types). The cited document is
                    # already streaming through the SSE channel as the original
                    # event below, so dropping the structured `Citation` for
                    # post-prompt grounding is non-fatal -- log at DEBUG so the
                    # decision is visible in App Insights without spamming
                    # WARN/ERROR for routine schema drift.
                    logger.debug(
                        "ignoring malformed citation metadata",
                        extra={
                            "operation": "citation_parse",
                            "pipeline": "chat",
                            "citation_id": cid,
                            "error": str(exc),
                        },
                    )
        yield event

    if not buffering_answer:
        return

    answer = "".join(answer_buffer)
    sources = [_citation_to_search_result(c) for c in citations]
    result = await post_prompt.validate(  # type: ignore[union-attr]
        question=user_text,
        answer=answer,
        sources=sources,
    )
    if not result.grounded:
        yield OrchestratorEvent(
            channel=OrchestratorChannel.REASONING,
            content="Post-prompt groundedness check failed; replacing answer with filter message.",
            metadata={"code": "post_prompt_filtered"},
        )
    yield OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content=result.answer)


__all__ = ["KB_SEARCH_NARRATION", "RaiScreener", "run_chat"]
