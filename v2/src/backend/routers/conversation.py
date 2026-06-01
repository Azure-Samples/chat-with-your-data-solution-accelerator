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

Orchestrator dispatch goes through the ``orchestrators`` registry per
ADR 0001 / Hard Rule #4 — *no ``if/elif`` over orchestrator names in
this module*. The orchestrator stream is wrapped by
``pipelines.chat.run_chat`` (#22b), which gives us the seam to plug
content-safety / post-prompt guards once they are exposed via DI.
Today both guards default to ``None`` (pipeline streams through
unchanged), preserving the original router behavior.
"""

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from backend.dependencies import (
    AgentsProviderDep,
    ContentSafetyGuardDep,
    DatabaseClientDep,
    LLMProviderDep,
    SearchProviderDep,
    SettingsDep,
)
from backend.models.conversation import ConversationRequest, ConversationResponse
from backend.core.agents.definitions import CWYD_AGENT
from backend.core.pipelines.chat import run_chat
from backend.core.providers.orchestrators import registry as orchestrators_registry
from backend.services.conversation import collect_response
from backend.services.sse import SSE_MEDIA_TYPE, sse_stream, wants_sse

router = APIRouter(prefix="/api", tags=["conversation"])


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
    agents: AgentsProviderDep,
    db: DatabaseClientDep,
    content_safety: ContentSafetyGuardDep,
    accept: str | None = Header(default=None),
) -> ConversationResponse | StreamingResponse:
    """Run the configured orchestrator and stream / buffer the result."""
    # `agents.get_client()` is lazy: the first call constructs the
    # AgentsClient against `settings.foundry.project_endpoint` and
    # caches it on the provider; subsequent requests reuse the same
    # HTTP transport for the lifetime of the process.
    #
    # `agents.get_or_create_agent(...)` is the lazy DB-backed resolver
    # landed in CU-010c (ADR 0008). We only spend the DB + Foundry
    # round-trip on the `agent_framework` branch -- the langgraph
    # branch swallows `agent_id` via `**_extras` and never touches the
    # Agents SDK, so resolving an id we'd never use is wasted I/O.
    #
    # Hard Rule #4 nuance: the `if name == "agent_framework"` check
    # below is *kwarg preparation*, not orchestrator dispatch.
    # `orchestrators_registry.registry.get(...)` remains the single
    # registry-keyed factory call -- the router never has a chain of
    # `if/elif` that *constructs* different orchestrator instances
    # per name. The invariant is enforced by
    # `test_router_uses_registry_dispatch_no_hardcoded_provider_names`
    # (asserts exactly one `orchestrators_registry.registry.get(`
    # call site).
    agent_id = ""
    if settings.orchestrator.name == "agent_framework":
        agent_id = await agents.get_or_create_agent(CWYD_AGENT, db)

    orchestrator = orchestrators_registry.registry.get(
        settings.orchestrator.name
    )(
        settings=settings,
        llm=llm,
        search=search,
        agents_client=agents.get_client(),
        agent_id=agent_id,
    )

    events = run_chat(
        body.messages,
        orchestrator=orchestrator,
        content_safety=content_safety,
    )

    if wants_sse(accept):
        return StreamingResponse(
            sse_stream(events, request),
            media_type=SSE_MEDIA_TYPE,
        )

    return await collect_response(events, conversation_id=body.conversation_id)


__all__ = ["router"]
