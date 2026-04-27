---
description: "CWYD v2 always-on workflow contract. Use when: editing anything under v2/, adding a class, adding a method, building a feature, planning work, scoping a change, deciding what to test, classifying by pillar, wiring a new orchestrator, adding plug-and-play surface, exposing a reasoning channel, or before opening a PR for v2."
applyTo: "v2/**"
---

# v2 Workflow Contract

This file applies to every edit under `v2/`. It encodes the non-negotiable process.

## Step 0 — sync agent guidance first (gate)

Before any reorganization, refactor, or error fix under `v2/`, read the agent instructions and prompt files that scope the change (`.github/copilot-instructions.md` + the relevant `.github/instructions/v2-*.instructions.md`). If guidance is stale, contradicts the requested change, or is silent on a decision the change implies, **propose an instruction update first and wait for user approval** before touching code or other docs. Skipping Step 0 causes re-work and re-introduces removed concepts. The pillars file (`v2/docs/pillars_of_development.md`) is read-only product policy — never edit it.

## The loop (per request)

1. **Plan.** Identify the ONE class or ONE method to implement. Map it to a phase in [v2/docs/development_plan.md](../../v2/docs/development_plan.md) and to a pillar in [v2/docs/pillars_of_development.md](../../v2/docs/pillars_of_development.md). If the user's request implies multiple units, list them and implement only the first; report the rest as next steps.
2. **Implement.** Write the unit. Add the pillar/phase docstring header. Keep public surface minimal.
3. **Test.** In the same turn, add or extend a test file that exercises the new unit. The test must execute. Prefer failing-then-fixing over green-by-default.
4. **Verify.** Run the relevant test (`uv run pytest <path>`, `npm test -- <pattern>`) and report the result.
5. **Stop.** Do not proceed to the next unit until the user (or the orchestrating agent) approves.

## Pillar header (required)

Every new file in `v2/src/**` must start with one of:

```python
"""
Pillar: Stable Core
Phase: 1
Purpose: <one sentence>
"""
```

```ts
/**
 * Pillar: Stable Core
 * Phase: 1
 * Purpose: <one sentence>
 */
```

Valid pillars: `Stable Core`, `Scenario Pack`, `Configuration Layer`, `Customization Layer`.

## Plug-and-play rules

- **Backend-only deployments must work.** No code path may assume the bundled frontend is reachable. Health check, OpenAPI docs (`/docs`), and all routers must function with the frontend container removed.
- **Frontend-only deployments must work.** All API calls go through a single `apiClient` that reads `VITE_BACKEND_URL`. Never hardcode `/api`. Never assume same-origin.
- **OpenAPI is the contract.** Backend changes that affect request/response shapes must regenerate the TS client (`make openapi` or pre-commit hook). Do not hand-edit `v2/src/frontend/src/api/generated/`.

## Multi-agent readiness

All orchestrators implement `v2/src/providers/orchestrators/base.py::OrchestratorBase` with:

```python
async def run(self, request: ConversationRequest) -> AsyncIterator[OrchestratorEvent]:
    ...
```

Concrete orchestrators self-register via `@registry.register("langgraph")` / `@registry.register("agent_framework")` against the registry in `v2/src/providers/orchestrators/__init__.py`. Caller code is `orchestrators.create(settings.orchestrator, ...)` — no `if/elif` over orchestrator names anywhere.

`OrchestratorEvent` is a discriminated union over channels: `reasoning | tool | answer | citation | error`. Never collapse reasoning into the answer string. A future multi-agent coordinator will route `tool` and `reasoning` events between agents — keep them clean.

## Reasoning feed (SSE)

- Endpoint: `POST /api/conversation` with `Accept: text/event-stream`.
- Each event: `event: <channel>\ndata: <json>\n\n`.
- Channels:
  - `reasoning` — chain-of-thought / o-series scratchpad. Frontend renders in a collapsible panel, never inline.
  - `tool` — tool invocation start/end with `{name, args, result_summary}`.
  - `answer` — incremental tokens of the final answer.
  - `citation` — `{id, source, snippet, score}` as they are referenced.
  - `error` — terminal; client closes connection.

## Banned in v2 / removed features (binding)

**Tech bans:** `streamlit`, `promptflow`, `semantic_kernel`, `poetry`, direct `from openai import …` / `AzureOpenAI(...)`, `azure-keyvault-secrets` for app secrets. Importing any of these in `v2/**` is a review-block.

**Removed features (do not re-add, do not re-document as a feature):** one-click "Deploy to Azure" ARM button (v2 is `azd`-only), Streamlit admin app (merged into the React/Vite frontend), Azure Bot Service integration, Teams extension. Full list: [v2/docs/development_plan.md](../../v2/docs/development_plan.md) §2.1.

**Forbidden code patterns:** `if/elif` provider dispatch outside a `Registry[T]`; lazy in-function imports of provider classes; module-level client instantiation. Pluggable concerns belong under `v2/src/providers/<domain>/` and self-register.

## Anti-overengineering gate (4 questions, all must pass)

Before introducing **any** new file, container, sidecar, package, Bicep module, abstraction, factory, or config format, answer all four. If any answer is unclear, stop and escalate to the user.

1. **Which dev_plan task # does this implement?** Cite [v2/docs/development_plan.md](../../v2/docs/development_plan.md) §3.4 (project structure) or §4 (phase task table) by line/task number. "It seems useful" is not a citation.
2. **Which pillar does it belong to?** Pick exactly one from [v2/docs/pillars_of_development.md](../../v2/docs/pillars_of_development.md): Stable Core, Scenario Pack, Configuration Layer, or Customization Layer. Declare it in the file/class docstring.
3. **Does it preserve plug-and-play?** Both `--profile backend-only` and `--profile frontend-only` (in `v2/docker/docker-compose.dev.yml`) must still boot independently after the change. No hidden coupling, no shared in-process state, no mandatory sidecar.
4. **Is this the simplest thing that works?** One runtime per container. No reverse proxies, no collectors, no caches, no message buses, no factories without ≥2 concrete callers *today*. v1 is **not** a reference — v1 is the spaghetti we are replacing.

**Worked examples of overengineering to reject:**

- Adding `nginx` to serve the built React app → reject. The frontend image is single-runtime FastAPI/uvicorn serving `dist/` (Stable Core, dev_plan §3.4 `frontend/`). Two runtimes in one image is unjustified complexity.
- Adding an `otel-collector` sidecar → reject. `azure-monitor-opentelemetry` exports direct to Application Insights (Stable Core, dev_plan Phase 1 task #5 + 6.3 telemetry). A standalone collector is not in the plan.
- Adding Redis / a message broker / a cache layer → reject unless dev_plan lists it.
- Adding Make targets, pre-commit hooks, or new CI workflows → reject unless explicitly requested.

## Structure changes require user confirmation

The following require an explicit user prompt **before** any agent acts:

- New top-level folder under `v2/`.
- New package directory under `v2/src/**` (anything beyond what dev_plan.md §3.4 enumerates).
- New entry in `pyproject.toml` `[project] dependencies` or `v2/src/frontend/package.json` `dependencies`.
- Renames or moves of existing modules.
- New module layout (e.g., splitting `providers/orchestrators/` into sub-packages, or moving anything between `shared/`, `providers/`, and `pipelines/`).

The planner must ask the user, get a yes, and record the decision in the Work Order's `## References` section before proceeding.

## When in doubt

Open a planner pass first (`cwyd-planner` agent). Do not guess scope.
