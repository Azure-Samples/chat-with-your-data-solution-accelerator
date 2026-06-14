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
    PostPromptValidatorDep,
    RuntimeOverridesDep,
    SearchProviderDep,
    SettingsDep,
)
from backend.models.conversation import ConversationRequest, ConversationResponse
from backend.core.agents.definitions import CWYD_AGENT
from backend.core.pipelines.chat import KB_SEARCH_NARRATION, run_chat
from backend.core.providers.orchestrators import registry as orchestrators_registry
from backend.services.admin import resolve_effective_config
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
    post_prompt: PostPromptValidatorDep,
    overrides: RuntimeOverridesDep,
    accept: str | None = Header(default=None),
) -> ConversationResponse | StreamingResponse:
    """Run the configured orchestrator and stream / buffer the result."""
    # Orchestrator selection honors the admin-saved override:
    # `resolve_effective_config` overlays a persisted
    # `RuntimeConfig.orchestrator_name` (loaded into
    # `app.state.runtime_overrides` by the lifespan + PATCH writeback
    # channel) on top of the `CWYD_ORCHESTRATOR_NAME` env default. The
    # resolved `orchestrator_name` is the single registry key fed into
    # dispatch below, so flipping the orchestrator in the admin UI
    # takes effect on the next request without a redeploy.
    effective = resolve_effective_config(settings, overrides)
    orchestrator_name = effective.orchestrator_name

    # Orchestrator construction is registry-keyed (Hard Rule #4): the
    # single `orchestrators_registry.registry.get(...)` call below is
    # the only place an orchestrator is instantiated -- there is no
    # `if/elif` chain that constructs different orchestrators per name.
    # The invariant is enforced by
    # `test_router_uses_registry_dispatch_no_hardcoded_provider_names`.
    #
    # Every orchestrator receives the same uniform kwargs and keeps
    # only what it needs (swallowing the rest via `**_extras`):
    #   * `agents` / `db` -- the `agent_framework` orchestrator resolves
    #     (create-if-missing) and builds its runtime agent through the
    #     agents provider's `build_agent`; `langgraph` swallows them.
    #   * `system_prompt` -- the effective `cwyd_agent_instructions`
    #     (admin-saved override or the `CWYD_AGENT.instructions`
    #     default); `langgraph` injects it as the leading system
    #     message, `agent_framework` resolves instructions through
    #     `build_agent` and swallows this kwarg.
    #   * `search_top_k` / `search_use_semantic_search` -- per-request
    #     retrieval knobs `langgraph` forwards to `BaseSearch.search`
    #     and `agent_framework` swallows.
    orchestrator = orchestrators_registry.registry.get(
        orchestrator_name
    )(
        settings=settings,
        llm=llm,
        search=search,
        agents=agents,
        db=db,
        credential=credential,
        agent_name=CWYD_AGENT.name,
        system_prompt=effective.cwyd_agent_instructions,
        search_top_k=effective.search_top_k,
        search_use_semantic_search=effective.search_use_semantic_search,
    )

    # Retrieval narration is gated on a wired search backend: when
    # `search` is None the deployment runs pass-through (no knowledge
    # source) and the thinking panel must not claim it is searching.
    # The orchestrator-agnostic emit lives in `run_chat`; the router
    # owns the gate because it holds the resolved `search` provider --
    # every orchestrator that grounds on the injected search backend
    # (or the Foundry IQ KB derived from the same endpoint) inherits
    # the during-the-wait narration with no per-orchestrator code.
    retrieval_hint = KB_SEARCH_NARRATION if search is not None else None

    events = run_chat(
        body.messages,
        orchestrator=orchestrator,
        content_safety=content_safety,
        post_prompt=post_prompt,
        retrieval_hint=retrieval_hint,
    )

    if wants_sse(accept):
        return StreamingResponse(
            sse_stream(events, request),
            media_type=SSE_MEDIA_TYPE,
        )

    return await collect_response(events, conversation_id=body.conversation_id)


__all__ = ["router"]
