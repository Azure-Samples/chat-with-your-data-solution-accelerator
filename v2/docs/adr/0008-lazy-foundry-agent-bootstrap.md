# ADR 0008 — Foundry agents are bootstrapped lazily on first request and cached in the application database

- **Status**: Accepted
- **Date**: 2026-05-05
- **Phase**: Cleanup audit batch 2 (Phase 4 prep)
- **Pillar**: Configuration Layer (lifecycle decision) + Stable Core (registry + DB seam consequence)
- **Deciders**: CWYD v2 maintainers
- **Supersedes (in part)**: [CU-001a](../cleanup_audit.md) `OrchestratorSettings.agent_id` field; [CU-001e](../cleanup_audit.md) `azureAiAgentId` Bicep parameter and `AZURE_AI_AGENT_ID` env binding.

## Context

CWYD v2 selects between two orchestrators via the registry: `langgraph` (the default; talks to Foundry IQ via the OpenAI-compatible client and needs no server-side Foundry agent) and `agent_framework` (talks to a real, named Foundry agent through `azure.ai.agents.aio.AgentsClient`). The `agent_framework` path needs an **agent identity** — an opaque server-side id like `asst_…` — to call `client.create_run(thread_id, agent_id=…)`.

The recently shipped Phase 4 prep work in [CU-001](../cleanup_audit.md) wired that identity through configuration: a Bicep parameter `azureAiAgentId`, a container env binding `AZURE_AI_AGENT_ID`, an `OrchestratorSettings.agent_id` field with a `model_validator` requiring the value when `name == "agent_framework"`, and a router that read the value and forwarded it to the orchestrator constructor. That shape worked but pushed the agent's lifecycle entirely outside the app: an operator was expected to create the agent in the Foundry portal (or via a script we never shipped), copy the id back into `azd env set AZURE_AI_AGENT_ID asst_…`, and re-deploy. Three problems made that untenable:

1. **Operator burden**: every fresh `azd up` required a manual portal step before the `agent_framework` orchestrator was reachable. Default `azd up` would silently produce a broken `agent_framework` deployment until that step ran.
2. **Drift between code and Foundry state**: the agent's `instructions` and `model` live in source control under [`v2/src/backend/core/agents/`](../../src/backend/core/agents) (CU-010a). Out-of-band creation lets the deployed Foundry agent diverge from the code's expectations — exactly the v1 "what's the prompt actually running in production" problem we replaced `env_helper.py` to escape.
3. **No multi-agent path**: CU-011 needs a second Foundry agent (the MACAE-style RAI classifier). A single `AZURE_AI_AGENT_ID` env var doesn't generalize; adding `AZURE_AI_RAI_AGENT_ID`, `AZURE_AI_<NEXT>_AGENT_ID` per agent reproduces v1's env-var sprawl ([`code/backend/batch/utilities/helpers/env_helper.py`](../../../code/backend/batch/utilities/helpers/env_helper.py) reads 80+ such values).

We surveyed two adjacent Microsoft GSAs:

- **MACAE** (`common/utils/utils_af.py`) creates a fresh Foundry agent on **every request** via `agent_registry.register_agent`. The agent definition (name, instructions, deployment) lives in code, which solves the drift problem. But per-request `client.create_agent(...)` calls leak server-side agents — Foundry retains every created agent until explicitly deleted, and MACAE never deletes them. Acceptable for a sample; not acceptable for a production accelerator that runs for months.
- **CGSA** creates agents in-process at boot inside the lifespan handler, then caches them in module state. Solves the leak (one create per process boot). But it couples application boot to a successful Foundry round trip — a transient Foundry outage during ACA cold start prevents the container from passing readiness, even for the `langgraph` path that doesn't need an agent at all. It also creates a fresh agent on every container restart, which still drifts faster than necessary.

Neither pattern is right as-is. We need: code-owned definitions (drift fix), no-leak lifecycle (production fix), no boot-time Foundry coupling (availability fix), generalizable to N agents (CU-011 fix), and zero operator steps in the default `azd up` flow (UX fix).

## Decision

**Foundry agents are created on first request, cached in the application database, and re-validated against Foundry on cache miss. The agent registry storage is the same database used for chat history (Cosmos in cosmosdb mode, Postgres in postgresql mode). Agent identity never appears in environment variables or Bicep parameters.**

This is the "Option C" lifecycle from the cleanup-audit-batch-2 planning matrix. Concretely:

1. **Definitions live in code** under [`v2/src/backend/core/agents/`](../../src/backend/core/agents) (CU-010a). Each `AgentDefinition` is a pydantic model with `key`, `name`, `description`, `instructions`, `model_deployment_alias`. Two are exported as built-ins: `CWYD_AGENT` (the main RAG conversational agent, instructions adapted from v1 [`llm_helper.py`](../../../code/backend/batch/utilities/helpers/llm_helper.py)) and `RAI_AGENT` (MACAE-style TRUE/FALSE classifier, instructions adapted with attribution from MACAE `utils_af.create_RAI_agent`).
2. **Registry storage uses the same DB as chat history** (CU-010b). `BaseDatabaseClient` grows two methods: `async get_agent_id(key) -> str | None` and `async upsert_agent_id(key, agent_id) -> None`. Cosmos uses a new `agents` container with partition key `/key`. Postgres uses a new table `agents(key TEXT PRIMARY KEY, agent_id TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW())`. Schema bootstrap happens in `scripts/post_provision.py`. No new Azure resource is provisioned — we follow the existing `databaseType` switch.
3. **The `agents` provider owns the resolver** (CU-010c). `BaseAgentsProvider` grows `async get_or_create_agent(definition: AgentDefinition, db: BaseDatabaseClient) -> str`. The `FoundryAgentsProvider` implementation does:

   ```text
   1. Process-local cache check (dict[str, str], keyed by AgentDefinition.key).
   2. db.get_agent_id(key). On hit: validate by calling client.get_agent(id).
      - 200 → cache + return.
      - 404 → fall through to create.
   3. client.create_agent(model=settings.openai.deployments[definition.model_deployment_alias],
                          name=definition.name,
                          instructions=definition.instructions)
      → db.upsert_agent_id(key, new_id) → cache + return.
   ```

   A per-key `asyncio.Lock` serializes the create path so concurrent first requests don't both create and orphan one. The lock is per `definition.key`, so different agents (CWYD vs RAI) don't block each other.

4. **Router calls the resolver, not env vars** (CU-010d, redoing CU-001d). `routers/conversation.py` calls `agent_id = await agents.get_or_create_agent(CWYD_AGENT, database_client)` only when `settings.orchestrator.name == "agent_framework"`. The langgraph branch passes `agent_id=""` and the orchestrator swallows it via `**_extras` ([ADR 0001](0001-registry-over-factory-dispatch.md), Hard Rule #4). The router does **not** branch on orchestrator name to dispatch — it always calls `orchestrators.create(name, ...)` — but it does decide whether to *resolve* an agent id beforehand. Resolution is not dispatch.

5. **CU-009 reverses the env-var path** (intentional supersession). `azureAiAgentId` Bicep parameter and `AZURE_AI_AGENT_ID` container env binding are removed. `OrchestratorSettings.agent_id` field and its `model_validator` are removed. `v2/.env.sample` (CU-008a) does not list the variable. The only surviving public lever for agent identity is "delete the row in the `agents` table to force re-creation" (documented in [`v2/docs/agents.md`](../agents.md), CU-012b).

## Consequences

### Positive

- **Zero operator steps in `azd up`.** The first chat request after deployment pays a one-time ~1-2s create latency per agent; subsequent requests hit cache.
- **Definitions and runtime stay in sync.** Editing `RAI_AGENT.instructions` doesn't auto-rotate the deployed Foundry agent (that would surprise operators who edited the row), but the operational doc tells you to delete the row to force re-creation. We considered hashing instructions and auto-invalidating; rejected as YAGNI for v2.0 (see "Alternatives" #4).
- **Generalizes to N agents trivially.** Adding a third built-in is a single-file change in `backend/core/agents/definitions.py`. The provider, the DB schema, and the router are unchanged.
- **No agent leak.** `get_or_create_agent` only creates when the cache misses, the DB misses, and Foundry doesn't recognize the cached id. Steady state = one create per agent per Foundry project, ever.
- **Boot decouples from Foundry.** Lifespan does not call Foundry. ACA cold start completes even if Foundry is briefly unhealthy; only the first `agent_framework` request degrades.
- **Hard Rule #4 preserved.** Orchestrator dispatch stays registry-only. The router's `if name == "agent_framework"` branch decides *whether to resolve*, not *which orchestrator class to instantiate* — the latter is always `orchestrators.create(name, ...)`.
- **Hard Rule #11 preserved.** `agent_id` is no longer a public symbol that operators are encouraged to set; the public lever is "DB row in the `agents` table". One source of truth, one rename surface.

### Negative

- **First request after deployment is slower.** A cold container that hasn't seen `agent_framework` yet pays the create latency. We accept the one-time cost for the lifecycle simplification; operators that care can add a synthetic warm-up to their post-deploy script.
- **Per-key `asyncio.Lock` adds tiny first-request contention.** A second request that arrives during the create wins the lock right after the first commits and finds the cache warm — single Foundry create, no orphan. Trade-off accepted.
- **Database now stores opaque Foundry ids.** A migration to a different agent backend (hypothetical) requires a new resolver, not just a config flip. Considered acceptable: agents and chat history live in the same DB by design (Decision #2 in the planning matrix), and both are scoped to the deployment's Foundry project.
- **Dropping the env-var path is a breaking change for any operator who was already setting `AZURE_AI_AGENT_ID`.** The accelerator hadn't shipped this var to GA yet — it lived only on the Phase 4 prep branch — but the reversal is documented in [CU-009](../cleanup_audit.md#cu-009) and called out in [`v2/docs/env-vars.md`](../env-vars.md) (CU-012a).

### Neutral

- **The `agents` table/container is the only `agents`-domain DB shape.** No other agent metadata is stored alongside (no version history, no instruction snapshots). If we later want auto-invalidation on instructions change, an `instructions_hash` column is the obvious extension.
- **Foundry Project provisioning was already correct.** [`v2/infra/main.bicep`](../../infra/main.bicep) provisions the `aiProject` module (L565) and exports `AZURE_AI_PROJECT_ENDPOINT` (L1607). This ADR doesn't change the infra surface beyond the CU-009a reversal.

## Alternatives considered

1. **Option A — Pre-create at `azd up` via a Bicep deployment script (or `azd hook postprovision`).** Resolves the "no operator step" goal and avoids first-request latency. Rejected for two reasons: (a) couples deployment to Foundry availability — a transient Foundry hiccup during `azd up` aborts the whole deploy, including infra changes that would otherwise have succeeded; (b) needs its own retry / idempotency story (re-run `azd up` should not orphan agents) which duplicates the resolver logic we already need at request time.
2. **Option B — In-process bootstrap during FastAPI lifespan (CGSA pattern).** Single create per process boot, cached in module state. Rejected: couples `langgraph`-only deployments to Foundry's availability for no benefit, creates a fresh agent on every container restart (worse drift than DB-backed), and gives no path to cache across containers in the same revision.
3. **Option C — First-request lazy + DB cache (chosen).** Accepts the one-time per-agent first-request latency in exchange for: zero operator steps, no boot coupling, no leak, persistence across container restarts, generalization to N agents.
4. **Option D — Hash `instructions` and auto-invalidate.** Editing `RAI_AGENT.instructions` would force re-creation on next request. Rejected for v2.0 as YAGNI: it requires careful storage of the hash, breaks the "delete-the-row" mental model, and silently rotates the agent id under operators who didn't intend to. Documented as a future extension in [`v2/docs/agents.md`](../agents.md).
5. **Option E — Separate `agents` provider domain stays the same; storage moves to a dedicated Azure Table Storage account.** Considered for tenant-isolation cleanliness. Rejected: adds a new Azure resource for ~16 bytes of state per agent, and we already pay for either Cosmos or Postgres for chat history — co-locating is the lower-friction choice.
6. **MACAE per-request creation verbatim.** Rejected: leaks Foundry agents on a multi-month-running deployment.

## References

- [v2/docs/cleanup_audit.md — Cleanup Audit Batch 2](../cleanup_audit.md) — full CU-008..CU-012 specification, decision matrix, intentional reversals.
- [v2/docs/development_plan.md §0.1 Backend debt](../development_plan.md) — ledger rows for CU-008..CU-012.
- [ADR 0001 — Registry over factory dispatch](0001-registry-over-factory-dispatch.md) — Hard Rule #4 reasoning that the resolver does not violate.
- [ADR 0002 — No Key Vault, UAMI + RBAC](0002-no-key-vault-uami-rbac.md) — pattern that justifies storing Foundry-issued ids (not secrets) in the application DB.
- [ADR 0004 — Foundry IQ, no OpenAI SDK import](0004-foundry-iq-no-openai-sdk-import.md) — establishes the Foundry-first stance this ADR extends.
- [v2/src/backend/core/agents/](../../src/backend/core/agents) — built-in `AgentDefinition` constants (CU-010a).
- [v2/src/backend/core/providers/agents/](../../src/backend/core/providers/agents) — `BaseAgentsProvider` + `FoundryAgentsProvider` (CU-010c).
- [v2/src/backend/core/providers/databases/](../../src/backend/core/providers/databases) — `get_agent_id` / `upsert_agent_id` ABC + implementations (CU-010b).
- [v2/scripts/post_provision.py](../../scripts/post_provision.py) — schema bootstrap (CU-010b).
- [v2/docs/agents.md](../agents.md) — operational doc for the bootstrap flow (CU-012b).
- [v2/docs/env-vars.md](../env-vars.md) — canonical env inventory + the deprecation note for `AZURE_AI_AGENT_ID` (CU-012a).
- MACAE `create_RAI_agent` pattern (read-only reference, attribution required in code): <https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator>.
- CGSA pydantic-settings + `.env.sample` pattern (read-only reference): <https://github.com/microsoft/content-generation-solution-accelerator>.
