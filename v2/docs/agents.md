# Foundry agents in CWYD v2 — Lazy DB-backed bootstrap

**Pillar:** Stable Core (`BaseAgentsProvider.get_or_create_agent`) + Scenario Pack (`BUILTIN_AGENTS`)
**Cleanup audit batch 2 / CU-012b**
**Last updated:** 2026-05-05
**See also:** [ADR 0008](adr/0008-lazy-foundry-agent-bootstrap.md), [env-vars.md](env-vars.md)

> **Naming caveat (`B1-MAF-MISLABEL`, [development_plan.md](development_plan.md) §0.1):** every reference to the orchestrator value `agent_framework` in this document is the **registry key**, not the OSS [`agent-framework`](https://pypi.org/project/agent-framework-core/) PyPI package. The orchestrator behind that key today wraps the `azure.ai.agents` SDK (Foundry hosted-agents) — which is exactly the lazy-bootstrap layer this document describes. The swap to the real OSS `agent_framework` + `agent-framework-foundry` packages is Phase B-IMPL work; the registry key `"agent_framework"` will be preserved across that swap, so every code path, env var, and operator instruction below stays valid.

This document is the contributor + operator runbook for the v2 Foundry-agent layer. It covers:

1. Why agent identity is **not** in env vars.
2. The lazy bootstrap algorithm (sequence + invariants).
3. The two built-in agents (`CWYD_AGENT`, `RAI_AGENT`).
4. Operations: force-recreate, inspection, troubleshooting.
5. How to add a third built-in agent.

---

## 1. Why agent identity is not env-driven

v1 (and MACAE) carried Foundry agent identity in env vars: `AZURE_AI_AGENT_ID`, `AZURE_OPENAI_RAI_DEPLOYMENT_NAME`, etc. Two problems:

* **Drift.** Re-creating a Foundry environment without redeploying the workload leaves a stale id pointing at a deleted agent. Operators have no signal until the next user prompt fails.
* **Bootstrap chicken-and-egg.** `azd up` cannot know the agent id ahead of time because the agent has to be created against the deployed Foundry account. v1 worked around this with a post-deploy hook; v2 deletes the workaround.

**v2 decision (CU-009, ADR 0008):** the Foundry agent identity is a **runtime concern**, not an infra concern. `AZURE_AI_AGENT_ID` was removed from `.env.sample`, `AppSettings`, and the Bicep outputs. The first request to the backend on a fresh deployment performs the bootstrap; subsequent requests hit a process-local cache.

---

## 2. Lazy bootstrap algorithm

### 2.1 Where the code lives

| Concern | File | Symbol |
|---|---|---|
| Agent definitions (data) | [v2/src/backend/core/agents/definitions.py](../src/backend/core/agents/definitions.py) | `AgentDefinition`, `CWYD_AGENT`, `RAI_AGENT`, `BUILTIN_AGENTS` |
| Lazy resolver (algorithm) | [v2/src/backend/core/providers/agents/base.py](../src/backend/core/providers/agents/base.py) | `BaseAgentsProvider.get_or_create_agent(definition, db)` |
| Concrete provider (Foundry) | [v2/src/backend/core/providers/agents/foundry.py](../src/backend/core/providers/agents/foundry.py) | `FoundryAgentsProvider.get_client()` |
| DB persistence — Cosmos | [v2/src/backend/core/providers/databases/cosmos.py](../src/backend/core/providers/databases/cosmos.py) | `get_agent_id`, `upsert_agent_id` |
| DB persistence — Postgres | [v2/src/backend/core/providers/databases/postgres.py](../src/backend/core/providers/databases/postgres.py) | `get_agent_id`, `upsert_agent_id` |
| Router call site | [v2/src/backend/routers/conversation.py](../src/backend/routers/conversation.py) | `agents.get_or_create_agent(CWYD_AGENT, db)` |
| RAI gate call site | [v2/src/backend/core/tools/content_safety.py](../src/backend/core/tools/content_safety.py) | `rai_check(text, agents, db)` |

### 2.2 Sequence (first request)

```text
HTTP request
   │
   ▼
backend/routers/conversation.py::conversation
   │  (only on `agent_framework` orchestrator branch — `langgraph` swallows agent_id)
   ▼
BaseAgentsProvider.get_or_create_agent(CWYD_AGENT, db)
   │
   ├─ 1. cache hit? ── yes ──▶ return cached id        (steady state)
   │  no
   ▼
   ├─ 2. db.get_agent_id("cwyd")
   │       │
   │       ├─ hit ──▶ client.get_agent(persisted_id)
   │       │             │
   │       │             ├─ ok       ──▶ cache + return
   │       │             └─ 404      ──▶ fall through (orphan recovery)
   │       └─ miss  ──▶ fall through
   ▼
   ├─ 3. asyncio.Lock(per name)  (concurrent-first-request guard)
   │       │
   │       └─ double-checked cache inside lock (winner short-circuits losers)
   ▼
   └─ 4. client.create_agent(model=deployment, name, description, instructions, tools)
            │
            ├─ db.upsert_agent_id(name, agent.id)        (DB write second so a
            │                                              DB failure leaves a
            │                                              recoverable orphan)
            ├─ self._agent_cache[name] = agent.id
            └─ return agent.id
```

### 2.3 Steady state (every subsequent request, all processes)

```text
HTTP request ─▶ BaseAgentsProvider.get_or_create_agent ─▶ cache hit ─▶ return
                                          (~1µs dict lookup, no I/O)
```

### 2.4 Invariants

| Invariant | Where enforced | Why |
|---|---|---|
| `langgraph` orchestrator never resolves an agent id | router `if settings.orchestrator.name == "agent_framework":` guard | `langgraph` swallows `agent_id` via `**_extras`; resolving an unused id wastes a DB round-trip + Foundry call. |
| Process-local cache is the source of truth (not the DB) | `get_or_create_agent` step 1 + step 4 ordering | Cache write is the **last** step of the create path. If the cache has a value, the DB row exists too. |
| One Foundry agent per `AgentDefinition.name` per environment | `db.upsert_agent_id` uses `name` as the primary key (Cosmos: `id` field; Postgres: `PRIMARY KEY (name)`) | Repeated bootstraps with the same name update-in-place; never duplicate. |
| Stale Foundry id auto-recovers | step 2 catches `ResourceNotFoundError` and falls through to step 4 | An operator deleting the agent in the Foundry portal does **not** brick the workload — the next request re-creates it. |
| Concurrent first-requests for the same name create the agent **once** | step 3 per-key `asyncio.Lock` + double-checked cache | Without this, two concurrent first-callers would each create a Foundry agent and race on `upsert_agent_id`, leaving an orphan. |
| Foundry write happens before DB write | step 4 ordering | A DB failure leaves an orphan Foundry agent (recoverable on next request) instead of a stale DB id pointing at no agent (would cause every subsequent request to fail). |

---

## 3. Built-in agents (`BUILTIN_AGENTS`)

Defined in [v2/src/backend/core/agents/definitions.py](../src/backend/core/agents/definitions.py). Both are frozen Pydantic models — they are **scenario data**, not configuration. Operators do not edit them via env vars; they edit them by editing the file (or, later, via the admin UI write seam).

### 3.1 `CWYD_AGENT`

| Field | Value |
|---|---|
| `name` (registry + DB key) | `cwyd` |
| model | `AZURE_OPENAI_GPT_DEPLOYMENT` (the chat deployment) |
| `tools` | `("search",)` — the agent_framework orchestrator binds this to the Foundry IQ knowledge-base search tool |
| Role | Primary chat assistant. Answers user questions by calling the search tool and synthesising grounded responses with citations. |
| Caller | [`backend/routers/conversation.py`](../src/backend/routers/conversation.py) on the `agent_framework` orchestrator branch only. |

### 3.2 `RAI_AGENT`

| Field | Value |
|---|---|
| `name` (registry + DB key) | `rai` |
| model | `AZURE_OPENAI_GPT_DEPLOYMENT` (the shared chat deployment; v2 runs the RAI classifier on the chat model rather than the reference architecture's dedicated `AZURE_OPENAI_RAI_DEPLOYMENT_NAME`) |
| `tools` | `()` — pure classifier, no tool calls |
| Role | TRUE/FALSE safety classifier. Returns exactly one token; TRUE = safe (allow), FALSE = unsafe (block). |
| Caller | [`backend/core/tools/content_safety.py::rai_check`](../src/backend/core/tools/content_safety.py) → wired into the chat pipeline as a pre-orchestrator gate by [`backend/core/pipelines/chat.py`](../src/backend/core/pipelines/chat.py) (CU-011b). |
| Fail-closed | An unparseable verdict, a failed run, an empty agent reply, or an explicit `FALSE` all return **unsafe** (block). The guard never fails open. |

### 3.3 What's intentionally absent

* No content-safety REST endpoint as a "built-in agent". `ContentSafetyGuard` (Azure AI Content Safety REST API, v1-style) is a **parallel seam**, not an agent — it lives next to `rai_check` in [`content_safety.py`](../src/backend/core/tools/content_safety.py) and the pipeline can run either, both, or neither.
* No prompt-flow / semantic-kernel "skills". Both technologies are banned in v2 (Hard Rule #7).
* No per-tenant agent variants. Single agent per `name` per Foundry environment is the v2 contract; multi-tenant separation belongs at the Foundry-project level, not the agent level.

---

## 4. Operations runbook

### 4.1 Force-recreate an agent

The DB row is the persistence anchor. Delete it; the next request bootstraps a fresh Foundry agent.

**Cosmos (`databaseType=cosmosdb`):**

```bash
# Items live in the chat-history container with `type="agent"` + partition `_system`.
az cosmosdb sql container query \
  --account-name "$AZURE_COSMOS_ACCOUNT_NAME" \
  --database-name "$AZURE_COSMOS_DATABASE_NAME" \
  --name "$AZURE_COSMOS_CONTAINER_NAME" \
  --query-text "SELECT c.id, c.agent_id FROM c WHERE c.type = 'agent'"

# Then DELETE the row by id (id == AgentDefinition.name, partition == "_system").
```

**Postgres (`databaseType=postgresql`):**

```sql
-- Table created lazily on first `_ensure_pool()` call.
SELECT name, agent_id, updated_at FROM agents;
DELETE FROM agents WHERE name = 'cwyd';
```

After deletion, the **next** request to the backend on the `agent_framework` branch will re-run the bootstrap. The previous Foundry agent is **orphaned, not deleted** — clean it up in the Foundry portal if it matters.

> **Note:** the in-process cache (`BaseAgentsProvider._agent_cache`) is not invalidated by a DB delete. To force-recreate without restarting the backend, also restart the Container App (or, in dev, the `docker compose` backend service). Production hot-reload of agent definitions is **not** in scope.

### 4.2 Inspect Foundry agents

Use the Foundry portal under the AI Project → Agents pane, or the `azure-ai-agents` SDK:

```python
from azure.identity.aio import DefaultAzureCredential
from azure.ai.agents.aio import AgentsClient

async with DefaultAzureCredential() as cred:
    async with AgentsClient(endpoint=AZURE_AI_PROJECT_ENDPOINT, credential=cred) as client:
        async for agent in client.list_agents():
            print(agent.id, agent.name, agent.model)
```

Filter by `agent.name in {"cwyd", "rai"}` to find the v2-managed agents. Foundry-side names match `AgentDefinition.name` exactly.

### 4.3 Common issues

| Symptom | Cause | Fix |
|---|---|---|
| Every request fails with `ResourceNotFoundError` from `client.get_agent` | Bug — step 2 should catch this and fall through. Filed as a defect. | Restart backend (clears stale cache) + delete DB row + re-request. |
| First request after `azd up` is slow (~3-5s) | Cold-start: Foundry `create_agent` round-trip + DB `upsert` | Expected. Subsequent requests are <1ms (cache hit). To pre-warm, hit the `/api/conversation` endpoint with `CWYD_ORCHESTRATOR_NAME=agent_framework` once after deploy. |
| Two Foundry agents with the same `name` appear after a deploy | Concurrent first-request race **without** the per-key lock | Cannot happen with current code (CU-010c per-key `asyncio.Lock`). If observed, file a defect — do not work around with manual deletes. |
| `ResourceNotFoundError` on `get_agent` after manual Foundry-portal delete | Step 2 orphan-recovery branch | Auto-heals on next request. No operator action needed. |
| `langgraph` orchestrator hits the Foundry SDK | Bug — the `if name == "agent_framework"` guard in the router was removed | Restore the guard ([routers/conversation.py](../src/backend/routers/conversation.py)). |

---

## 5. Adding a third built-in agent

The whole point of `AgentDefinition` + `BUILTIN_AGENTS` is that adding an agent is a **one-file change**.

### 5.1 Declare the definition

Edit [v2/src/backend/core/agents/definitions.py](../src/backend/core/agents/definitions.py):

```python
SUMMARIZER_AGENT = AgentDefinition(
    name="summarizer",
    description="Summarises long documents into 3-5 bullet points.",
    instructions=(
        "You are a summarization assistant. Produce 3-5 bullet points, "
        "each ≤ 20 words. Preserve numerical facts verbatim."
    ),
    tools=(),
)


BUILTIN_AGENTS: dict[str, AgentDefinition] = {
    CWYD_AGENT.name: CWYD_AGENT,
    RAI_AGENT.name: RAI_AGENT,
    SUMMARIZER_AGENT.name: SUMMARIZER_AGENT,  # <-- add row
}
```

### 5.2 Wire the caller

The agent does nothing until something calls `get_or_create_agent`. Pick one:

* **As a tool inside another agent:** add the tool key to `CWYD_AGENT.tools` and bind it in the agent_framework orchestrator's tool registry.
* **As a parallel pipeline gate:** add a screener function next to `rai_check` (e.g. `summarize_check(text, agents, db) -> str`) and add a corresponding kw-arg to `run_chat` (mirror the `RaiScreener` / `rai_check` parameter pattern).
* **As a standalone endpoint:** add a new FastAPI router that calls `await agents.get_or_create_agent(SUMMARIZER_AGENT, db)` and then drives the agent directly via the SDK.

### 5.3 Test

* Update `BUILTIN_AGENTS` count assertion in [v2/tests/backend/core/agents/test_definitions.py](../tests/backend/core/agents/test_definitions.py).
* Add identity / wire-shape tests for the new agent in the same file.
* If wired into a pipeline gate, mirror the CU-011b test suite in [v2/tests/backend/core/pipelines/test_chat.py](../tests/backend/core/pipelines/test_chat.py).

### 5.4 Deploy

No infra change required. No `.env.sample` change required. No Bicep change required. The next request that calls `agents.get_or_create_agent(SUMMARIZER_AGENT, db)` will create the Foundry agent + persist the id.

---

## 6. Acceptance gates (CU-012b)

* This file lists `CWYD_AGENT` + `RAI_AGENT` with `name` / model / `tools` / role / caller — and only those two — matching `BUILTIN_AGENTS`.
* Sequence diagram lines up exactly with `BaseAgentsProvider.get_or_create_agent` step ordering (cache → DB → 404-fallthrough → lock → create → upsert → cache → return).
* Force-recreate runbook covers both `cosmosdb` and `postgresql` modes.
* "Adding a third built-in agent" section requires zero infra / Bicep / env changes (one-file change in `definitions.py` + caller wiring + test).
