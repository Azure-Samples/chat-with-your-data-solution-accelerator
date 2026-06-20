# ADR 0027 — `agent_framework` grounds app-side on pgvector (supersede the ADR 0022 pgvector block)

- **Status**: Accepted
- **Date**: 2026-06-19
- **Phase**: 8 (agent runtime — both orchestrators on pgvector; `BUG-0066` / `BUG-0067`)
- **Pillar**: Stable Core (the orchestrator grounding contract) over a Configuration Layer rule (the removed pgvector + `agent_framework` guard)
- **Deciders**: CWYD v2 maintainers (repo owner)
- **Supersedes / amends**: amends [ADR 0021](0021-agent-framework-foundry-iq-kb-default.md) (`agent_framework` grounding is no longer Foundry-IQ-only); supersedes decisions **#2** and **#5** of [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md) (the pgvector + `agent_framework` rejection rule, and "no silent fallback — pgvector must use `langgraph`"); updates the runtime matrix in [ADR 0026](0026-shared-citation-format-contract.md)
- **Companion**: [ADR 0021](0021-agent-framework-foundry-iq-kb-default.md), [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md), [ADR 0026](0026-shared-citation-format-contract.md)

## Context

The product requirement is that **both** orchestrators — `langgraph` and `agent_framework` — serve grounded, cited chat on a **pgvector** deployment, switchable from the admin UI without a redeploy.

[ADR 0021](0021-agent-framework-foundry-iq-kb-default.md) made `agent_framework` ground **only** through a Foundry IQ Knowledge Base whose `searchIndex` knowledge source wraps the Azure AI Search index. Foundry IQ has **no pgvector / PostgreSQL knowledge source** (its sources are `searchIndex`, `azureBlob`, `file`, `indexedOneLake`, `indexedSql`, SharePoint, web, `mcpServer`, fabric). So on pgvector `agent_framework` had no retrieval at all, and [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md) rejected the `index_store == pgvector` + `agent_framework` pairing at the config-resolution choke point with `ConfigResolutionError` → HTTP 409.

That made pgvector a **single-orchestrator** deployment (`langgraph` only), which contradicts the requirement above ([BUG-0066](../bugs.md)). The frontend compounded it: the 409 blanked the chat page instead of surfacing the error ([BUG-0067](../bugs.md)).

The key observation comes from [ADR 0026](0026-shared-citation-format-contract.md): the **retrieval mechanism** legitimately differs by storage, but the **citation format is shared**. `langgraph` already runs client-side RAG over the `index_store`-keyed `BaseSearch` provider (Hard Rule #4 registry dispatch) and emits `[docN]` citations through the single `citations.py` seam. `agent_framework` can run that **same** client-side RAG when no Knowledge Base exists — reusing the shared retrieval path and the shared citation seam — instead of being rejected.

## Decision

1. **`agent_framework` gains an app-side pgvector grounding path.** When `AgentFrameworkOrchestrator._build_kb_tool()` returns `None` (no Knowledge Base — the pgvector case) **and** a `BaseSearch` provider is wired, `run()` embeds the latest user query (`self.llm.embed([query])`), retrieves via the `index_store`-keyed `self._search.search(query, vector=…, top_k, use_semantic_search)`, injects the numbered `[docN]` sources block into the **user turn** (the Agents Responses thread drops system messages, so grounding cannot ride a system message), and emits `citation` events through the shared `citations.py` formatter. This is the **same** retrieval + citation path `langgraph` uses (the one fixed in `BUG-0065`); only the model-driving runtime differs.
2. **Azure AI Search deployments are unchanged.** When `_build_kb_tool()` returns a tool (a Knowledge Base is configured — cosmosdb mode), `agent_framework` still grounds on the Foundry IQ Knowledge Base ([ADR 0021](0021-agent-framework-foundry-iq-kb-default.md) holds for that mode). The KB path versus the app-side path is selected solely by whether `_build_kb_tool()` returns a tool.
3. **The pgvector + `agent_framework` config rule is removed.** `resolve_effective_config` no longer raises `ConfigResolutionError` for that pairing. Every orchestrator / index-store cell is now served, so the admin orchestrator switch works on either index store.
4. **The general `ConfigResolutionError` → 409 mechanism is retained.** ADR 0022 decisions **#1** (the reusable `ConfigResolutionError` primitive), **#3** (ERROR-level telemetry), and **#4** (the app-level 409 handler) stay in force as the standing pattern for any *future* incompatible effective configuration. Only ADR 0022 decision **#2** (the pgvector rule) and **#5** ("no silent fallback; pgvector must use `langgraph`") are superseded.
5. **The frontend handles non-2xx `/api/conversation` responses** ([BUG-0067](../bugs.md)): `streamChat` parses the structured `{error, reason}` body and the chat renders it inline, and a React error boundary prevents a render failure from blanking the page. Tracked and implemented separately; it does not gate this ADR.

## Consequences

- **+** Both orchestrators serve grounded, cited chat on pgvector; the admin switch works on either index store — the product requirement is met.
- **+** **Zero** new prompt text and **zero** new citation formatter: the app-side path reuses the [ADR 0026](0026-shared-citation-format-contract.md) shared seam (`format_sources_block` / `build_citations` / `filter_to_referenced`), so the emitted citation wire shape is identical across orchestrators.
- **+** The reusable `ConfigResolutionError` seam survives for genuine future incompatibilities — superseding the rule did not delete the mechanism.
- **−** On pgvector, `agent_framework` does **not** use Foundry IQ — that is impossible, as Foundry IQ cannot index pgvector — it runs app-side RAG like `langgraph`. The two orchestrators therefore differ less on pgvector (both client-side RAG); `agent_framework`'s value-add there is the Agent runtime (tool-calling, agent thread, reasoning summary), not KB retrieval.
- **−** `AgentFrameworkOrchestrator.run()` now carries two grounding paths (the server-side KB-tool path and the app-side retrieval path), gated on `_build_kb_tool()`. Slightly more branching in one method; the citation seam stays shared.
- **−** [ADR 0026](0026-shared-citation-format-contract.md)'s runtime-matrix row `agent_framework | pgvector | — (rejected at config)` is updated to `agent_framework | pgvector | app-side BaseSearch.search → [docN]`.

## Alternatives considered

- **A — Keep the 409; pgvector stays `langgraph`-only.** Rejected: directly contradicts the explicit product requirement that both orchestrators serve pgvector.
- **B — Agentic client-side `search_documents()` function tool** exposed to the Foundry agent (the agent decides *when* to retrieve). More agentic, but adds a tool-call event + citation-correlation surface for a non-default database; [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md) alternative C already leaned against it. Deferred — the static pre-retrieval injection chosen here reuses the `langgraph` seam byte-for-byte and is the minimal coherent change. Revisit only on concrete demand for agentic retrieval on pgvector.
- **C — Foundry IQ over an `mcpServer` knowledge source wrapping pgvector.** The only path that would keep `agent_framework` grounding *through Foundry IQ* on pgvector, but it requires standing up a hosted MCP server and re-adding an Azure AI Search service as the Foundry IQ orchestrator, on preview APIs. Heavy; deferred.

## Follow-ups

- **Governing-instruction updates (separate approval, Step 0).** Hard Rule #20 R3 in `.github/copilot-instructions.md` and R3 in `.github/instructions/v2-backend-core.instructions.md` both state the `agent_framework` + pgvector cell is "rejected at config (`ConfigResolutionError` → 409, ADR 0022)". With this ADR that cell is **served** (app-side RAG), so both rule texts need updating to point at ADR 0027. These are governing instructions, so the edit is proposed to the repo owner before it is applied.
