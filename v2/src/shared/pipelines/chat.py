"""Chat pipeline.

Pillar: Stable Core
Phase: 3 (task #22b) + Cleanup audit batch 2 (CU-011b)

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
* **Post-prompt validation**: when a validator is supplied, ``answer``
  events are *buffered* until the orchestrator stream finishes, then
  validated, then emitted as a single ``answer`` event whose content
  is either the original answer (grounded) or the validator's filter
  message (not grounded). Citations / reasoning / tool events stream
  through as they arrive — only ``answer`` is buffered.
* **No validator**: ``answer`` events stream through unchanged
  (sub-second perceived latency for the streaming client).
"""

from typing import AsyncIterator, Awaitable, Callable, Sequence

from shared.providers.orchestrators.base import OrchestratorBase
from shared.tools.content_safety import ContentSafetyGuard
from shared.tools.post_prompt import PostPromptValidator
from shared.types import ChatMessage, Citation, OrchestratorEvent, SearchResult

# Type alias for the RAI screener callable. Returns True when input
# is safe, False when unsafe. The pipeline never inspects the
# implementation -- the router is responsible for binding the
# `agents` provider + `db` client into a partial / closure that
# matches this shape.
RaiScreener = Callable[[str], Awaitable[bool]]


def _latest_user_text(messages: Sequence[ChatMessage]) -> str:
    """Return the text of the most recent user message (empty string if none)."""
    for message in reversed(messages):
        if message.role == "user":
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
) -> AsyncIterator[OrchestratorEvent]:
    """Run the configured chat flow and yield typed SSE events."""
    user_text = _latest_user_text(messages)

    if content_safety is not None:
        verdict = await content_safety.screen(user_text)
        if verdict.flagged:
            yield OrchestratorEvent(
                channel="error",
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
                channel="error",
                content="Input was blocked by the RAI safety classifier.",
                metadata={"code": "rai_blocked"},
            )
            return

    answer_buffer: list[str] = []
    citations: list[Citation] = []
    seen_citation_ids: set[str] = set()
    buffering_answer = post_prompt is not None

    async for event in orchestrator.run(messages):
        if event.channel == "answer" and buffering_answer:
            answer_buffer.append(event.content)
            continue
        if event.channel == "citation":
            cid = event.metadata.get("id")
            if isinstance(cid, str) and cid not in seen_citation_ids:
                seen_citation_ids.add(cid)
                try:
                    citations.append(Citation(**event.metadata))
                except Exception:  # noqa: BLE001 -- malformed metadata is non-fatal
                    pass
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
            channel="reasoning",
            content="Post-prompt groundedness check failed; replacing answer with filter message.",
            metadata={"code": "post_prompt_filtered"},
        )
    yield OrchestratorEvent(channel="answer", content=result.answer)


__all__ = ["RaiScreener", "run_chat"]
