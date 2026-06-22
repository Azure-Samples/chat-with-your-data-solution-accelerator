# ADR 0022 — Incompatible effective-config overrides raise a reusable `ConfigResolutionError`

- **Status**: Accepted — decisions #2 (the pgvector + `agent_framework` rule) and #5 ("no silent fallback") are superseded by [ADR 0027](0027-agent-framework-app-side-rag-on-pgvector.md), which gives `agent_framework` an app-side pgvector grounding path; the reusable `ConfigResolutionError` mechanism (decisions #1 / #3 / #4) remains in force
- **Date**: 2026-06-09
- **Phase**: 8
- **Pillar**: Stable Core (the `ConfigResolutionError` primitive + app-level handler) over a Configuration Layer rule (the pgvector + `agent_framework` guard)
- **Deciders**: CWYD v2 maintainers (repo owner)
- **Supersedes / amends**: none
- **Companion**: [ADR 0021](0021-agent-framework-foundry-iq-kb-default.md) (`agent_framework` default + Foundry IQ KB)

## Context

[ADR 0021](0021-agent-framework-foundry-iq-kb-default.md) makes `agent_framework` the default orchestrator, grounded by a Foundry IQ Knowledge Base whose `searchIndex` knowledge source wraps the existing Azure AI Search index.

Foundry IQ knowledge sources are limited to: `searchIndex`, `azureBlob`, `file`, `indexedOneLake`, `indexedSql` (Azure SQL), SharePoint, web, `mcpServer`, and fabric. **There is no pgvector / PostgreSQL knowledge source.**

`DatabaseSettings._enforce_mode_consistency` in [settings.py](../../src/backend/core/settings.py) binds the two storage modes:

- `db_type == cosmosdb` ⟺ `index_store == AzureSearch`
- `db_type == postgresql` ⟺ `index_store == pgvector`

So a pgvector deployment has **no Azure AI Search index** for a Knowledge Base to wrap, and `agent_framework` + KB cannot ground in pgvector mode. With `agent_framework` as the global default (ADR 0021), a pgvector operator who keeps the default — or explicitly sets `agent_framework` — has selected an **incompatible configuration**.

Effective configuration is resolved in **one place**: `resolve_effective_config(settings, overrides)` in [services/admin.py](../../src/backend/services/admin.py), called from [routers/conversation.py](../../src/backend/routers/conversation.py) **before** the SSE stream starts. This is the natural choke point for cross-setting validation: every admin override flows through it, and a raise here fails the request cleanly before any streaming begins.

The repo owner's direction (2026-06-09): incompatible config resolution must produce **a clean, solid exception** carrying an **error message**, plus an **ERROR-level log in the telemetry** — applied as a **reusable pattern for all config-resolution overrides**, not a one-off pgvector branch. This **reverses this ADR's first draft**, which proposed a silent fallback to `langgraph` with a warning log.

## Decision

1. **Introduce a reusable domain exception `ConfigResolutionError`** — the first custom exception in the v2 backend. It is raised by `resolve_effective_config(...)` whenever an admin override (overlaid on settings) yields an **invalid or incompatible** effective configuration. It carries a human-readable `message` plus structured context (a `reason` code + the conflicting field/values). Pillar: **Stable Core**. Home: colocated with the resolver in `backend/services/admin.py` — no new module, so no Hard Rule #10 structural ask. (A dedicated `backend/core/errors.py` leaf is the alternative if/when a second domain needs the same base; that extraction would be its own structural ask.)
2. **The pgvector + `agent_framework` combination is the first encoded rule.** When `index_store == pgvector` **and** the effective `orchestrator.name == agent_framework`, the resolver raises `ConfigResolutionError(reason="orchestrator_requires_azure_search", ...)` with a message naming the fix (use `langgraph` for pgvector deployments — Foundry IQ has no pgvector knowledge source).
3. **ERROR-level telemetry.** The raise is logged once at **ERROR** with structured `extra={"operation": "resolve_effective_config", "reason": ..., "index_store": ..., "configured_orchestrator": ...}` (Hard Rule #14), flowing to Application Insights via the OpenTelemetry logging integration.
4. **A clean error response.** A new app-level handler `app.add_exception_handler(ConfigResolutionError, ...)` in [app.py](../../src/backend/app.py) (alongside the existing five) maps it to **HTTP 409 Conflict** with a JSON body `{"error": "...", "reason": "..."}`. Because resolution runs **before** the `StreamingResponse` is built, the caller gets a normal HTTP error — not a half-open SSE stream.
5. **No silent fallback.** The effective orchestrator is **never** silently rewritten. pgvector deployments must be configured with `langgraph`; selecting `agent_framework` there is a hard, observable error the operator fixes.

## Consequences

- **+** Misconfiguration is loud and unambiguous: a clean exception, a 409 with an actionable message, and an ERROR telemetry record — no silent behavior change to debug.
- **+** Reusable: any future cross-setting incompatibility (not just pgvector) raises the same `ConfigResolutionError` from the same choke point, with the same handler + telemetry shape.
- **+** Fails fast, before streaming — no partial SSE responses on a bad config.
- **+** Establishes the v2 backend's first domain-exception + app-handler pattern that later domains can follow.
- **−** A pgvector deployment that sets `agent_framework` (or inherits it as the ADR 0021 default) is **rejected at request time** until reconfigured — it does **not** degrade to `langgraph` automatically. Operators set `CWYD_ORCHESTRATOR_NAME=langgraph` for pgvector; this is documented in the env / runbook docs at task `B5b` / `C`.
- **−** Adds one exception class, one handler, and one resolver rule (two small units, `B5a` + `B5b`).
- **−** If Foundry IQ later ships a pgvector (or Azure SQL) knowledge source, the pgvector rule is removed; the `ConfigResolutionError` seam stays.

## Alternatives considered

- **A — Silent fallback to `langgraph` + warning log** (this ADR's first draft). Rejected by the repo owner: a default that silently swaps the orchestrator is hard to notice and debug; the misconfiguration must be explicit.
- **B — Documentation note only** ("don't set `agent_framework` with pgvector"). Rejected: relies on operator discipline; the ADR 0021 default flip would silently mis-ground existing pgvector envs.
- **C — pgvector function-tool exposed to the Foundry agent** (the agent calls a custom tool that queries pgvector). Rejected for Phase 8: adds a custom tool + plumbing surface for a non-default database; revisit only on concrete customer demand.
- **D — SSE `error` event instead of HTTP 409.** Rejected: resolution happens before the stream starts, so a plain HTTP error is cleaner than opening an SSE stream just to emit one error frame. (If a future rule is only detectable mid-stream, that case can emit on the `error` channel — Hard Rule #6 — without changing this decision.)
