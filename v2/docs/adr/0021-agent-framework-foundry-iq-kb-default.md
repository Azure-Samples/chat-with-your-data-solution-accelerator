# ADR 0021 — `agent_framework` default + Foundry IQ Knowledge Base retrieval

- **Status**: Proposed
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
5. **Retrieval knobs for the agent path narrow to `temperature` / `max_tokens`** (threaded via `OpenAIChatOptions`); per-request `top_k` does not apply to agentic retrieval. `langgraph` keeps its `top_k` + semantic-search knobs.

## Consequences

- **+** The BYOD *intent* (platform-grounded retrieval) returns through a compliant, registry-dispatched, reasoning-channel-emitting path running on the Foundry agent runtime — not the `openai` SDK `data_sources` call.
- **+** No new ingestion path: the KB queries the live `cwyd-index`, so the existing push-upsert pipeline is untouched.
- **+** The KB API version is operator-tunable via env var without a redeploy.
- **+** No custom MCP server: the KB exposes a *managed* MCP endpoint hosted by Azure AI Search; the agent consumes it. The `mcpServer` (external-MCP) knowledge-source type is not used.
- **−** `agent_framework` + KB is **Azure-AI-Search-only** — Foundry IQ has no pgvector knowledge source, so pgvector deployments must use `langgraph`; selecting `agent_framework` there raises a clean `ConfigResolutionError` per [ADR 0022](0022-config-resolution-error-on-incompatible-overrides.md).
- **−** Adds a one-time KB / knowledge-source provisioning step (`post_provision.py`) and a Bicep per-KB project connection so the agent resolves the KB by name.
- **−** Couples the default path to Foundry IQ KB availability; health / diagnostics must classify KB reachability (`pass | degraded | fail`) per the resilience contract.

## Open questions (resolved before this ADR moves to Accepted at task `C`)

- **Consume path A vs B.** A = agent-side `MCPTool` pointed at the managed KB MCP endpoint (`{search_endpoint}/knowledgebases/{kb}/mcp`); B = app-side KB retrieve via the Search SDK, results handed to the agent. Resolved at task **B-Spike**.
- **Scoring profile.** `cwyd-index` already has the named semantic config `default`; whether a default *scoring profile* is also required for KB retrieval quality is confirmed at **B-Spike**.
- **Pinned SDK surface.** The exact `agent-framework` / `azure-ai-projects` call surface (current `AgentsClient.create_agent` vs MACAE's `PromptAgentDefinition` + `create_version` + `MCPTool`) is confirmed at **B-Spike** against the pinned dependency versions (ADR 0017).
