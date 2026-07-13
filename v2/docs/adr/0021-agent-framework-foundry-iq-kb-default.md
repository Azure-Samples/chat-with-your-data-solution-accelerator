# ADR 0021 — `agent_framework` default + Foundry IQ Knowledge Base retrieval

- **Status**: Accepted
- **Date**: 2026-06-09
- **Phase**: 8
- **Pillar**: Configuration Layer (default orchestrator selection + env-pinned KB API version) over a Stable Core seam (KB tool binding on the existing `agent_framework` orchestrator)
- **Deciders**: CWYD v2 maintainers (repo owner)
- **Supersedes / amends**: none — no prior ADR ratified the default orchestrator selection; this is the first to do so. The previous `langgraph` default lived only as the `OrchestratorSettings.name` default value in [settings.py](../../src/backend/core/settings.py), never as an ADR-level decision.
- **Companion**: [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md) (config-resolution error on incompatible overrides)

## Context

v1 exposed a `CONVERSATION_FLOW` knob with two grounding strategies:

- **`byod`** — Azure OpenAI "On Your Data": the chat-completions call carried `extra_body={"data_sources": [...]}`, and Azure OpenAI performed retrieval *internally* against Azure AI Search. The platform grounded the answer.
- **`custom`** — the app orchestrated retrieval itself (Semantic Kernel / Prompt Flow / LangChain).

v2 **removed** the BYOD `data_sources` mechanism (see [development_plan.md](../development_plan.md) §2.1; binding under Hard Rule #7) because it is a monolithic, non-registry, Azure-OpenAI-SDK-internal path that hard-codes Azure AI Search, forbids the pgvector provider, and buries reasoning inside the answer string — violating Hard Rules #4/#5/#6/#7.

v2 ships **two registry-dispatched orchestrators** under `providers/orchestrators/`:

- **`langgraph`** — app-owned explicit RAG. Calls `BaseSearch.search()` directly, builds the prompt, streams the answer. Works against **both** index stores (Azure AI Search *and* pgvector).
- **`agent_framework`** — delegates retrieval to a Foundry agent (OSS Microsoft Agent Framework + Foundry IQ runtime). Today the agent is created with a bare `tools=["search"]`; **KB-grounded retrieval is not yet wired.**

The repo owner's direction (2026-06-09 planning turns): make **`agent_framework` the default**, grounded by a **Foundry IQ Knowledge Base**, with the KB REST API version supplied as an **environment variable**. This restores the *intent* of v1's BYOD flow (let the platform ground the answer) through a rules-compliant mechanism.

Key enabling fact: a Foundry IQ Knowledge Base can use a **`searchIndex` knowledge source** that **wraps an existing Azure AI Search index** (`cwyd-index`) and is queried **live at query time**. CWYD's ingestion is an idempotent push-upsert (`merge_or_upload_documents` on Azure AI Search; `ON CONFLICT (id) DO UPDATE` on pgvector), so the KB needs **no per-document reseed** — KB creation is a **one-time structural** step, analogous to creating the index itself. This is the decisive difference from MACAE's upload-once managed-vector-store pattern; CWYD does not use managed vector stores.

## Decision

1. **`agent_framework` becomes the default orchestrator.** The flip of `OrchestratorSettings.name` from `"langgraph"` to `"agent_framework"` lands **last** (Phase 8 task `C`), only after KB retrieval is wired and verified. Flipping earlier would ship an ungrounded default.
2. **Grounding source = a Foundry IQ Knowledge Base over a `searchIndex` knowledge source** that wraps the existing `cwyd-index`. The knowledge source + KB are created **once** at provision time (`post_provision.py`, idempotent create-or-update); ingestion is unchanged and needs no reseed.
3. **The KB REST API version is pinned via a new env var** `AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION` (default `2025-11-01-preview`), following the existing `AZURE_*_API_VERSION` convention. Operators can re-pin without a code change.
4. **`langgraph` remains a first-class registry peer** for app-owned RAG and is the **required** orchestrator for pgvector deployments. Selecting `agent_framework` in pgvector mode is rejected at request time with a clean `ConfigResolutionError` (HTTP 409 + ERROR telemetry) — never a silent fallback (see [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md)). Both orchestrators stay registry-dispatched; no `if/elif` provider dispatch is introduced.
5. **Retrieval knobs for the agent path narrow to `temperature` / `max_tokens`** (threaded via the `FoundryAgent` `default_options` / run `options` — the pinned `agent-framework==1.7.0` does **not** ship MACAE's `OpenAIChatOptions`); per-request `top_k` does not apply to the KB/MCP agentic-retrieval path. `langgraph` keeps its `top_k` + semantic-search knobs.

## Consequences

- **+** The BYOD *intent* (platform-grounded retrieval) returns through a compliant, registry-dispatched, reasoning-channel-emitting path running on the Foundry agent runtime — not the `openai` SDK `data_sources` call.
- **+** No new ingestion path: the KB queries the live `cwyd-index`, so the existing push-upsert pipeline is untouched.
- **+** The KB API version is operator-tunable via env var without a redeploy.
- **+** No custom MCP server: the KB exposes a *managed* MCP endpoint hosted by Azure AI Search; the agent consumes it. The `mcpServer` (external-MCP) knowledge-source type is not used.
- **−** `agent_framework` + KB is **Azure-AI-Search-only** — Foundry IQ has no pgvector knowledge source, so pgvector deployments must use `langgraph`; selecting `agent_framework` there raises a clean `ConfigResolutionError` per [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md).
- **−** Adds a one-time KB / knowledge-source provisioning step (`post_provision.py`) and a Bicep per-KB project connection so the agent resolves the KB by name.
- **−** Couples the default path to Foundry IQ KB availability; health / diagnostics must classify KB reachability (`pass | degraded | fail`) per the resilience contract.

## Spike findings (B-Spike, 2026-06-09 — open questions resolved)

The three open questions were resolved by an empirical reflection probe against the pinned dependency versions (`azure-ai-projects==2.2.0`, `azure-ai-agents==1.2.0b6`, `agent-framework==1.7.0`, `agent-framework-foundry==1.7.0`, `azure-search-documents>=11.6.0b1`).

- **Consume path A vs B → A, specifically sub-variant A2 (`agent_framework.MCPStreamableHTTPTool` on the existing `FoundryAgent` runtime).** Path **B is not viable on the current pin** — `azure.search.documents.agent` (the app-side agentic-retrieval client) does not exist in the installed `azure-search-documents`, so an app-side KB retrieve would need hand-rolled REST. Within path A: **A1** = re-arch onto `AIProjectClient.agents.create_version` + `PromptAgentDefinition` + `azure.ai.projects.models.MCPTool` (full MACAE pattern; KB tool persisted server-side on the agent definition); **A2** = keep the current `agent_framework_foundry.FoundryAgent` runtime and attach an `agent_framework.MCPStreamableHTTPTool` at invoke time. **A2 is chosen** as the smallest delta that delivers a KB-grounded default: `FoundryAgent.run(...)` accepts the broad `tools: ToolTypes | ...` union, so the MCP tool binds per-run without re-arching the agents provider (`agents/base.py` keeps `AgentsClient.create_agent`) or the orchestrator's run loop. `MCPStreamableHTTPTool(name=<kb>, url="{search_endpoint}/knowledgebases/{kb}/mcp?api-version=<ver>", approval_mode="never_require", allowed_tools=["knowledge_base_retrieve"], header_provider=<bearer for https://search.azure.com/.default>)` maps 1:1 onto MACAE's managed-KB-MCP tool. Retrieval calls arrive as `function_call` updates, which the orchestrator already maps to `TOOL` reasoning-channel events. (B4 will likely drop the bare `"search"` placeholder from `CWYD_AGENT.tools` since the real tool is the runtime MCP tool. A1 remains the documented fallback if A2's client-side MCP execution proves insufficient.)
- **Scoring profile → not required for MVP.** Agentic retrieval requires a *named semantic configuration*, which `cwyd-index` already has (`default`). A default *scoring profile* is optional ranking tuning, not a prerequisite, so **B2 does not add one** to the index build. Revisit only if retrieval relevance proves inadequate in testing.
- **Pinned SDK surface → confirmed, with two corrections to the working assumptions.** (1) `azure-ai-projects==2.2.0` exposes agents via `AIProjectClient.agents` = `AgentsOperations.create_version(...)` — there is **no `create_agent`** on this SDK (that lives on the *separate* `azure-ai-agents==1.2.0b6` `AgentsClient`, which CWYD uses today). `MCPTool` + `PromptAgentDefinition` + `AzureAISearchToolResource` exist in `azure.ai.projects.models`, but **`KnowledgeBase` / `KnowledgeSource` model classes do not** — the KB itself is created via the **Azure AI Search REST API** (`knowledgesources` / `knowledgebases`, api-version `2025-11-01-preview`), not a typed SDK model (this is what `post_provision.py` / B2 calls). (2) `agent-framework==1.7.0` ships `Agent` + `MCPStreamableHTTPTool` but **not** `OpenAIChatOptions`, `ChatAgent`, or `HostedMCPTool` (MACAE targets a different agent-framework build), so **Decision 5's knob-threading is via `FoundryAgent` `default_options` / run `options`, not `OpenAIChatOptions`** (this ADR and the dev_plan B4 row are corrected accordingly). The classic `azure.ai.agents.models.AzureAISearchTool(index_connection_id, index_name, top_k=...)` exists and is the smallest possible binding, but it targets the **index directly, not a Foundry IQ KB**, so it is off-table for this ADR's committed KB decision (recorded only to document why it was not chosen).

These resolutions hold for the pinned versions. The ADR is **Accepted** as of task `C`: `OrchestratorSettings.name` now defaults to `agent_framework` with the KB tool bound on the `AgentFrameworkOrchestrator` (task `B4`) and the pgvector incompatibility rejected at request time via `ConfigResolutionError` / HTTP 409 (task `B5`, [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md)).
