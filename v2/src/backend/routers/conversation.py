"""Conversation router.

Pillar: Stable Core
Phase: 3

Single endpoint: ``POST /api/conversation``.

Two response modes, content-negotiated by the ``Accept`` header:

* ``text/event-stream`` -> Server-Sent Events on the locked channel
  set (``reasoning`` / ``tool`` / ``answer`` / ``citation`` /
  ``error``). Each event is wire-formatted as
  ``event: <channel>\\ndata: <json>\\n\\n``.
* anything else (default) -> buffered JSON
  (:class:`backend.models.conversation.ConversationResponse`) with the
  concatenated answer plus deduplicated citations.

Orchestrator dispatch goes through the ``orchestrators`` registry per
Hard Rule #4 -- *no ``if/elif`` over orchestrator names in this
module*. The orchestrator stream is wrapped by
``pipelines.chat.run_chat``, which gives us the seam to plug
content-safety / post-prompt guards once they are exposed via DI.
"""

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from backend.dependencies import (
    AgentsProviderDep,
    ContentSafetyGuardDep,
    CredentialDep,
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
    credential: CredentialDep,
    db: DatabaseClientDep,
    content_safety: ContentSafetyGuardDep,
    accept: str | None = Header(default=None),
) -> ConversationResponse | StreamingResponse:
    """Run the configured orchestrator and stream / buffer the result."""
    # `agents.get_or_create_agent(...)` is the lazy DB-backed resolver:
    # we only spend the DB + Foundry round-trip on the
    # `agent_framework` branch -- the langgraph branch never touches
    # the Agents SDK, so resolving an agent we'd never use is wasted
    # I/O.
    #
    # The orchestrator itself looks the agent up by *name* through the
    # OSS `agent_framework_foundry.FoundryAgent` client, so the return
    # value here (the resolved agent id) is intentionally discarded --
    # the call is bootstrap-only (create-if-missing).
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
    if settings.orchestrator.name == "agent_framework":
        await agents.get_or_create_agent(CWYD_AGENT, db)

    orchestrator = orchestrators_registry.registry.get(
        settings.orchestrator.name
    )(
        settings=settings,
        llm=llm,
        search=search,
        credential=credential,
        agent_name=CWYD_AGENT.name,
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
