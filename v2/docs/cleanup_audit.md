# CWYD v2 Cleanup Audit

> **Audit pass — read-only.** This file is the **single tracker** for v2 quality, modularity, and rewrite-discipline issues. Each finding becomes one CU-XXX entry. We work through them **one at a time** via planner → implementer → tester (Hard Rule #1).
>
> Do not edit code as part of this file's lifecycle. Edits land in their own one-unit work orders, and the matching CU-XXX entry below is then marked `✅ Done — <ref>`.

- **Date:** 2026-05-04
- **Scope:** `v2/src/**`, `v2/infra/**`, `v2/docker/**`, `v2/scripts/**`
- **Reference plan:** [/memories/session/plan.md](../../memories/session/plan.md)
- **Out of scope:** v1 `code/` tree (touched only for documented removals per [development_plan.md](development_plan.md) §2.1), `v2/docs/qa_report_v2.md` (historical phase report), `v2/docs/development_plan.md` §0.1 (this file replaces it as the source of truth for cleanup issues).

## Baselines (this run)

| Suite | Result | Command |
|---|---|---|
| Backend pytest | **263 / 263 passed (4.50s)** | `cd v2 && uv run pytest tests -q --disable-warnings` |
| Frontend vitest | **30 / 30 passed (3.54s)** | `cd v2/src/frontend && npm test -- --run` |
| Frontend prod build | **exit 0** (`dist/index.html` 0.33 kB, `dist/assets/index-*.js` 199 kB) | `cd v2/src/frontend && npm run build` |
| Bicep build (default `databaseType=cosmosdb`) | **exit 0** (4 × BCP081 warnings on `Microsoft.Web/*@2025-03-01` previews — informational only) | `cd v2/infra && az bicep build --file main.bicep` |
| docker compose `backend-only` config | **exit 0** | `docker compose -f v2/docker/docker-compose.dev.yml --profile backend-only config` |
| docker compose `frontend-only` config | **exit 0** | `docker compose -f v2/docker/docker-compose.dev.yml --profile frontend-only config` |

## Gate summary

Legend: ✅ pass · ⚠️ pass with notes · ❌ fail (becomes a CU)

| Gate | Phase | Result | Evidence | Linked CUs |
|---|---|---|---|---|
| A.1 Foundry-only (`from openai`/`AzureOpenAI(`) | A | ✅ | only docstring at [foundry_iq.py L11](../src/shared/providers/llm/foundry_iq.py#L11) | — |
| A.2 Registry-dispatch (no `if/elif` on orchestrator/db_type/index_store) | A | ✅ | [health.py L76](../src/backend/routers/health.py#L76) now noqa-marked (CU-003 ✅); [settings.py L114](../src/shared/settings.py#L114) validator already exempt | CU-003 ✅ |
| A.3 Banned tech (streamlit/promptflow/semantic_kernel/keyvault-secret/poetry) | A | ✅ | 0 production hits | — |
| A.4 V1-only env vars (Form Recognizer, Computer Vision, Speech, ORCHESTRATION_STRATEGY, ADMIN_WEBSITE_NAME) | A | ✅ | 0 hits | — |
| A.5 `os.getenv`/`os.environ` minimal | A | ✅ | Both lifespan reads typed: App Insights via `ObservabilitySettings.app_insights_connection_string` and CORS via `NetworkSettings.cors_origins`. `import os` removed from [app.py](../src/backend/app.py). Only remaining `os.environ` in v2/src is the frontend static-asset path resolver (out of scope). | CU-002 (a ✅ / b ✅) |
| A.6 Hardcoded secrets | A | ✅ | 0 hits outside tests | — |
| A.7 Pillar header on every `.py` | A | ✅ | [shared/tools/__init__.py](../src/shared/tools/__init__.py) now carries Pillar=Stable Core / Phase=3 (CU-005 ✅) | CU-005 ✅ |
| B.8 Foundry IQ is the sole LLM provider | B | ✅ | exactly one `@registry.register("foundry_iq")`; uses `AIProjectClient.get_openai_client()` | — |
| B.9 Orchestrator-switch contract end-to-end | B | ❌ | router never passes `agents_client` / `agent_id`; selecting `agent_framework` will raise at construct time | CU-001 |
| B.10 `Registry[T]` plug-and-play call sites | B | ✅ | Folder + registry domain stays `databases/` (broader scope than just chat-history; will host vector-store metadata + config storage); 4 stale `chat_history.create(...)` references corrected; new `test_factory.py` regression-guards that registry keys (`cosmosdb`, `postgresql`) match `DatabaseSettings.db_type` Literal | CU-006 |
| B.11 Provider lifecycle / reverse-order `aclose()` | B | ✅ | lifespan in [app.py](../src/backend/app.py) closes in reverse construction order; pgvector borrows postgres pool | — |
| C.12 Conditional Bicep modules | C | ✅ | aiSearch L586, aiProjectSearchConnection L655, cosmosDb L814, postgresServer L921 — all gated on `databaseType` | — |
| C.13 `DatabaseSettings._enforce_mode_consistency` | C | ✅ | rejects all 4 cross-mode combos and missing endpoints — see [settings.py L109-L129](../src/shared/settings.py#L109) | — |
| C.14 Provider mode parity (databases + search) | C | ✅ | `databases.create("cosmosdb"\|"postgresql")` and `search.create("AzureSearch"\|"pgvector")` registered | — |
| C.15 `bicep build` both modes | C | ⚠️ | default mode (cosmosdb) compiles. Postgres-mode compile not run because `bicep build` accepts no parameter overrides; covered by `_validatePostgresAdminPrincipalName` runtime guard at [main.bicep L919-L921](../infra/main.bicep#L919). Add CI step at Phase 7 if desired. | — |
| D.16 No v1 modules ported into v2 | D | ✅ | 0 hits for `formrecognizer`/`cognitiveservices.speech`/`semantic_kernel`/`promptflow` under `v2/src` or `v2/infra` | — |
| D.17 Backend modularity vs `python_agent_framework_dev_template-main` | D | ✅ | v2 uses `Registry[T]` + lifespan injection — same boundary discipline, intentionally different DI primitive (per plan note) | — |
| D.18 Backend layout vs unified-data-foundation sample | D | ✅ | `routers/`, `models/`, `dependencies.py` — no v1-style monolith reintroduced | — |
| D.19 Credential audit on env drafts | D | ✅ | [v2/docker/.env.dev.example](../docker/.env.dev.example) rewritten using AppSettings/Bicep names; new round-trip test in [tests/shared/test_settings.py](../tests/shared/test_settings.py) prevents drift (CU-007 ✅) | CU-007 ✅ |
| E.20 `uv run pytest v2/tests` | E | ✅ | 263 / 263 passed | — |
| E.21 `npm test -- --run` | E | ✅ | 30 / 30 passed | — |
| E.22 `npm run build` | E | ✅ | exit 0, 199 kB bundle | — |
| E.23 `docker compose --profile {backend,frontend}-only config` | E | ✅ | both exit 0 | — |
| E.24 SSE channel coverage in tests | E | ⚠️ | `reasoning` events emitted from `pipelines/chat.py` and `foundry_iq.py` but **never** from `langgraph` or `agent_framework` orchestrators themselves — visible reasoning is gated on the validator path | CU-004 |

## Issues (work queue)

> Format is fixed: severity, pillar, target phase, location, evidence, why-it-violates, recommended one-unit fix, acceptance test, dependencies. Do not expand a CU into multiple units in-place — split into CU-NNNa, CU-NNNb if needed.

### CU-001 — Wire `AgentsClient` + `agent_id` so `agent_framework` orchestrator is actually selectable

- **Severity:** blocker
- **Pillar:** Stable Core
- **Target phase:** 4 (matches the explicitly-deferred task #28 in [development_plan.md](development_plan.md), and is the user-stated v2 invariant: "the user can switch between agent_framework or langchain (langgraph)")
- **Location:**
  - [v2/src/backend/routers/conversation.py](../src/backend/routers/conversation.py#L120) — `orchestrators.create(settings.orchestrator.name, settings=settings, llm=llm, search=search)` does not pass `agents_client` or `agent_id`.
  - [v2/src/shared/providers/orchestrators/agent_framework.py L49-L63](../src/shared/providers/orchestrators/agent_framework.py#L49) — constructor requires both kwargs and raises `ValueError` on empty `agent_id`.
  - [v2/src/backend/dependencies.py](../src/backend/dependencies.py) — has `LLMProviderDep`, `SearchProviderDep`, `DatabaseClientDep` but **no `AgentsClientDep`**.
  - [v2/src/backend/app.py](../src/backend/app.py) — lifespan never builds an `AgentsClient`.
  - [v2/infra/main.bicep](../infra/main.bicep) — outputs `AZURE_AI_AGENT_API_VERSION` but no `AZURE_AI_AGENT_ID`; `FoundrySettings` / `OrchestratorSettings` have no `agent_id` field either.
- **Evidence:** Already reproduced in [qa_report_v2.md Q6d](qa_report_v2.md#L69) — selecting `agent_framework` would crash at construction. Confirmed unchanged at this audit (`grep`d the router; only one `orchestrators.create(...)` call site, no agents_client/agent_id kwargs).
- **Why it violates v2 rules:** Hard Rule #5 (multi-agent ready — both orchestrators must be live behind a runtime switch). User invariant: "the user can switch between agent_framework or langchain". Today the switch is mechanically present but the second branch is unreachable.
- **Recommended fix (one unit per Hard Rule #1) — split into 4 ordered units:**
  1. **CU-001a — settings:** add `OrchestratorSettings.agent_id: str = ""` + a model validator that, when `name == "agent_framework"`, requires `agent_id` non-empty. (one model + one validator) — **✅ Done 2026-05-04.** Field uses `validation_alias=AliasChoices("AZURE_AI_AGENT_ID", "CWYD_ORCHESTRATOR_AGENT_ID", "agent_id")` — primary name matches the future Bicep output (CU-001e); CWYD-prefixed alias kept for admin-UI runtime overrides. `model_validator(mode="after")` raises with a clear "create the agent in Foundry portal/SDK" hint when the agent_framework branch is selected without an id (carries `noqa: registry-dispatch -- config validator` per Hard Rule #4 exception). Also folded in: env example renamed legacy `APPLICATIONINSIGHTS_CONNECTION_STRING=` → typed `AZURE_APP_INSIGHTS_CONNECTION_STRING=` (the actual name AppSettings reads post-CU-002b); commented `#AZURE_AI_AGENT_ID=` line added with usage hint; `_ENV_EXAMPLE_EXEMPTIONS` tightened (dropped now-obsolete `APPLICATIONINSIGHTS_CONNECTION_STRING` exemption, added `AZURE_AI_AGENT_ID` alias-only exemption). Pytest suite **279 / 279 passed** (+4 new tests: agent_id default empty under langgraph, agent_framework w/o id raises, agent_id accepts CWYD-prefixed alias, agent_id ignored when name is langgraph).
  2. **CU-001b — agents provider domain:** add a new `shared/providers/agents/` registry domain with `BaseAgentsProvider` ABC and `FoundryAgentsProvider` self-registered as `"foundry"`, exposing `get_client() -> AgentsClient` and `aclose()`. (one new package + one concrete class) — **✅ Done 2026-05-04.** User picked Option B (new top-level package under `providers/`, parity with `llm`/`databases`/`search`). Package structure mirrors `llm/` exactly: `__init__.py` (Registry primitive + `create()` helper + side-effect import), `base.py` (ABC with `get_client()` + `aclose()` abstract methods + Phase-3 imports gated under `TYPE_CHECKING`), `foundry.py` (`@registry.register("foundry")` + lazy `AgentsClient` construction against `settings.foundry.project_endpoint` + caller-owned-override aware `aclose()`). Pytest suite **287 / 287 passed** (+8 new tests: registry key parity, `create()` returns ABC subclass, override honored even when endpoint empty, lazy + cached construction, RuntimeError when endpoint empty, `aclose()` closes constructed client + idempotent, `aclose()` does NOT close caller-injected override).
  3. **CU-001c — DI seam:** add `AgentsProviderDep` to `backend/dependencies.py` + lifespan construction + reverse-order `aclose()` in `backend/app.py`. (one Depends + lifespan wiring) — **✅ Done 2026-05-05.** `dependencies.py` now exports `get_agents_provider(request)` (raises `RuntimeError("agents_provider missing")` when lifespan didn't run, parity with `get_database_client`) and the `AgentsProviderDep` annotation. Lifespan in `app.py` constructs `agents.create("foundry", settings=settings, credential=credential)` immediately after the LLM provider, stashes it on `app.state.agents_provider`, and `await agents_provider.aclose()` runs in reverse order between `database_client.aclose()` and `llm_provider.aclose()`. The provider is **always wired** (the SDK client itself is lazy — no HTTP session opens until the first `get_client()` call), so the `langgraph` orchestrator sees zero overhead and the `agent_framework` orchestrator gets a process-wide singleton. Pytest **291 / 291 passed** (+4 new tests: DI raises when missing, DI returns state instance, lifespan dispatches `agents.create("foundry", settings=..., credential=...)`, `aclose()` is awaited on shutdown).
  4. **CU-001d — router wiring:** pass `agents_client=agents, agent_id=settings.orchestrator.agent_id` from `routers/conversation.py` into `orchestrators.create(...)`. The two existing `**_extras` swallows on the orchestrator constructors keep langgraph happy. (one router edit)
  5. **CU-001e — Bicep output:** add `AZURE_AI_AGENT_ID` parameter (default `""`) to [main.bicep](../infra/main.bicep) and surface it on the backend container app's env vars. (one parameter + one env var)
- **Acceptance test:** extend `v2/tests/backend/test_conversation.py` with a parametrize over `["langgraph", "agent_framework"]`; the agent_framework path uses a `FakeAgentsClient` injected via `dependency_overrides`. Plus a new `v2/tests/shared/test_settings.py::test_orchestrator_requires_agent_id_when_agent_framework`.
- **Blocked by / blocks:** none / blocks Phase 4 task #28 verification.

### CU-002 — Route the two `os.getenv` lifespan reads through `AppSettings`

- **Severity:** high
- **Pillar:** Configuration Layer
- **Target phase:** 4 (touches lifespan during chat-history pool wiring anyway)
- **Location:**
  - [v2/src/backend/app.py L36](../src/backend/app.py#L36) — `os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")`
  - [v2/src/backend/app.py L146](../src/backend/app.py#L146) — `os.getenv("BACKEND_CORS_ORIGINS")`
- **Evidence:** `ObservabilitySettings.app_insights_connection_string` already exists in [settings.py](../src/shared/settings.py); `NetworkSettings.cors_origins` was missing — now added by CU-002a.
- **Why it violates v2 rules:** Hard Rule #4 (typed settings are the single source of truth) + the user-stated cleanup goal ("we are cleaning up with credentials that are in the sample code"). `os.getenv` in production code makes config invisible to the validator and bypasses the `lru_cache` invariant of `get_settings()`.
- **Recommended fix (one unit) — split into 2 ordered units:**
  1. **CU-002a — settings field:** add `NetworkSettings.cors_origins: list[str]` with a `field_validator` that splits comma-separated `BACKEND_CORS_ORIGINS`. (one field + one validator) — **✅ Done 2026-05-04.** Implementation uses `Annotated[list[str], NoDecode]` + `validation_alias=AliasChoices("BACKEND_CORS_ORIGINS", "cors_origins")` + a `mode="before"` validator that accepts comma-separated strings, JSON lists, or already-parsed Python lists. Pytest suite **268 / 268 passed** (was 264 — 4 new tests).
  2. **CU-002b — lifespan rewire:** replace both `os.getenv` reads with `settings.observability.app_insights_connection_string` and `settings.network.cors_origins`. (two-line replacement). Also fold in the bare `LOG_LEVEL: INFO` typo in `v2/docker/docker-compose.dev.yml` line 41 → `AZURE_LOG_LEVEL: INFO` while editing the lifespan touch-zone (single concern). — **✅ Done 2026-05-04.** `import os` removed from [app.py](../src/backend/app.py); lifespan now reads `settings.observability.app_insights_connection_string` (and emits a typed-name skip log when empty); `create_app()` reads `NetworkSettings()` standalone (avoids triggering DB cross-validators at import time) and feeds `cors_origins` into `CORSMiddleware` with credentials enabled when origins are non-wildcard. Docker compose line 41 fixed (`AZURE_LOG_LEVEL: INFO`). Pytest suite **272 / 272 passed** (+4 new acceptance tests: AppInsights configured-from-typed-settings, AppInsights skipped-when-typed-empty-even-if-legacy-alias-set, CORS uses-typed-settings, CORS wildcard-fallback).
- **Acceptance test:** new `v2/tests/shared/test_settings.py::test_cors_origins_*` tests (CU-002a, 4 tests, all passing). For CU-002b, an existing lifespan smoke test will gain assertions that AppInsights initialization and CORSMiddleware configuration both come from the typed settings path.
- **Blocked by / blocks:** CU-002a now done / CU-002b unblocked.

### CU-003 — Add `# noqa: registry-dispatch` to the diagnostic branch in `health.py`

- **Status:** ✅ Done — 2026-05-04 (in-tree edit; no commit ref captured)
- **Severity:** medium
- **Pillar:** Stable Core
- **Target phase:** 3.5 (debt — single line, can land any phase)
- **Location:** [v2/src/backend/routers/health.py L76](../src/backend/routers/health.py#L76) (was L72 before the 4-line diagnostic comment was added above the `if`)
- **Evidence:** the matching cosmos branch at L58 already carries the noqa marker; the index-store branch (`if settings.database.index_store == "AzureSearch"`) was missing it. The Phase A.2 grep tripped on this line.
- **Why it violates v2 rules:** Hard Rule #4 (no `if/elif` provider dispatch outside marked diagnostic branches). The intent here is diagnostic-only (read-only health check), so the noqa marker is the documented escape — it just hadn't been applied.
- **Recommended fix (one unit):** append `  # noqa: registry-dispatch -- diagnostic` to the `if` line. (one-line edit) — **DONE.** Mirrored the cosmos pattern by also adding a 4-line diagnostic comment above the `if` so the noqa is self-documenting.
- **Acceptance test:** existing `v2/tests/backend/test_health.py` continues to pass — confirmed **11 / 11 passed** on `cd v2 && uv run pytest tests/backend/test_health.py -q`.
- **Follow-up note (not a new CU):** the nested `if self.index_store != "AzureSearch"` and `if self.index_store != "pgvector"` at [settings.py L119, L128](../src/shared/settings.py#L119) live *inside* an already-noqa'd validator block, so they are correct under Hard Rule #4 today. A future Phase 7 CI grep that is not block-aware will trip on them; if/when that gate lands, the right move is to teach the gate about scope rather than scatter additional markers across one validator. Logged here so CI-design time has the context.
- **Blocked by / blocks:** none / none.

### CU-004 — Emit `reasoning` events from both orchestrators (not just from the LLM provider's `reason()`)

- **Severity:** medium
- **Pillar:** Stable Core
- **Target phase:** 5 (matches the o-series reasoning-rendering work)
- **Location:** [v2/src/shared/providers/orchestrators/langgraph.py](../src/shared/providers/orchestrators/langgraph.py) and [agent_framework.py](../src/shared/providers/orchestrators/agent_framework.py) — neither implementation yields `OrchestratorEvent(channel="reasoning", ...)` today. The only `reasoning` emitter today is [foundry_iq.py L191](../src/shared/providers/llm/foundry_iq.py#L191) (only triggered via `reason()`) and the post-prompt buffer-replace path in [pipelines/chat.py L120](../src/shared/pipelines/chat.py#L120).
- **Evidence:** `grep "channel=\"reasoning\""` returns 3 matches, none under `providers/orchestrators/`. The frontend's collapsible "Reasoning" panel will therefore stay empty for the normal chat path.
- **Why it violates v2 rules:** Hard Rule #6 (the reasoning channel is the contract — never bury reasoning inside the answer string). Hard Rule #5 (multi-agent parity — both orchestrators must emit the same channel set).
- **Recommended fix (one unit per orchestrator) — split into 2 units:**
  1. **CU-004a — langgraph:** in the LLM-node callback, when the underlying `LLMProvider.complete()` returns chain-of-thought metadata, surface it as a `reasoning` event before the final `answer`. (one method)
  2. **CU-004b — agent_framework:** map Foundry agent thread `run_steps` of type `MessageCreation` with `role == "assistant"` and `metadata.reasoning == True` to `reasoning` events. (one method)
- **Acceptance test:** new `v2/tests/shared/providers/orchestrators/test_event_channels.py` parametrize over both providers — assert at least one `reasoning` event when the underlying LLM yields one.
- **Blocked by / blocks:** CU-001 (need agent_framework wiring before CU-004b can be exercised in integration tests).

### CU-005 — Add Pillar header to `shared/tools/__init__.py`

- **Status:** ✅ Done — 2026-05-04 (in-tree edit; no commit ref captured)
- **Severity:** low
- **Pillar:** Stable Core
- **Target phase:** 3.5 (debt — landing any phase is fine)
- **Location:** [v2/src/shared/tools/__init__.py](../src/shared/tools/__init__.py) — was empty.
- **Evidence:** Hard Rule #3 requires every new module to open with `Pillar:` + `Phase:` docstring. Empty `__init__.py` files are a grey zone; we treat them as in-scope because they're real modules under `v2/src/`.
- **Why it violates v2 rules:** Hard Rule #3.
- **Recommended fix (one unit):** add a 4-line module docstring identifying Pillar=Stable Core, Phase=3, Purpose=tool-namespace marker. (one file edit) — **DONE.** Also added a one-line note that the package intentionally does not re-export sibling modules so adding a new tool does not require editing this file.
- **Acceptance test:** Phase 7 will add a CI gate enforcing the header; until then no test required. Confirmed full suite still green: **263 / 263 passed** on `cd v2 && uv run pytest tests -q`.
- **Blocked by / blocks:** none / none.

### CU-006 — Resolve naming inconsistency: domain folder `databases/` vs docstrings calling it `chat_history.create(...)`

- **Severity:** medium
- **Pillar:** Stable Core (naming convention — Hard Rule #11)
- **Target phase:** 4 (when chat-history routes land — better to settle the name now than rename later when API contracts ship)
- **Location:**
  - Folder: [v2/src/shared/providers/databases/](../src/shared/providers/databases) — registry key `databases`.
  - Stale docstrings: [settings.py L87, L112](../src/shared/settings.py#L87) and [health.py L56](../src/backend/routers/health.py#L56) all reference `chat_history.create(...)` / `providers.chat_history.create(...)`.
  - Plan reference: [development_plan.md L564](development_plan.md#L564) task #31 = "Chat history router".
- **Evidence:** `grep "chat_history\."` — 3 hits outside `.venv` and the dev plan, all in production source comments referring to a domain that doesn't exist by that name.
- **Why it violates v2 rules:** Hard Rule #11 (naming-convention stability). A registry key is a public symbol; the docs and the code disagree on what it's called. Future readers will hunt for `providers/chat_history/` and find nothing.
- **Recommended fix (one unit) — pick exactly one option and execute it:**
  - **Option A (recommended):** rename the folder to `chat_history/` and the registry key from `cosmosdb`/`postgresql` to `cosmosdb`/`postgresql` under domain `chat_history` (key labels stay; the *domain name* changes). Update settings/health docstrings to match. One folder rename + import-path sweep — qualifies as one unit because it's a single mechanical refactor.
  - **Option B (chosen):** keep `databases/` and update the stale docstrings to say `databases.create(...)`. The `databases` provider domain owns chat-history CRUD plus future DB-backed concerns (vector-store metadata, config storage); chat history is one functionality of the database, not its only one.
  - **Decision required from user before planner emits the work order.** (Per Hard Rule #10 — structural decisions require explicit confirmation.) — **✅ Done 2026-05-04.** User picked Option B (keep folder name `databases/`, rationale: "the functionality of the databases is more than chat_history and can be expanded"). Implementation:
    - 4 stale references corrected: [settings.py L87, L112](../src/shared/settings.py#L87) and [health.py L56](../src/backend/routers/health.py#L56) and [databases/__init__.py L17](../src/shared/providers/databases/__init__.py#L17) (the latter also had a `"postgres"` typo, now `"postgresql"` to match the registered key).
    - Verified factory pattern is sound: `Registry("databases")` + `BaseDatabaseClient` ABC + `databases.create(key, **kwargs)` single dispatch + `DatabaseSettings.db_type: Literal["cosmosdb", "postgresql"]` infrastructure-driven selection. No structural change required.
    - New regression test [tests/shared/providers/databases/test_factory.py](../tests/shared/providers/databases/test_factory.py) asserts: (1) registered keys exactly equal the `db_type` Literal value set, (2) `databases.create(key, ...)` returns a `BaseDatabaseClient` subclass for every Literal value. Pytest suite **275 / 275 passed** (was 272 — 3 new tests).
- **Acceptance test:** existing tests under `v2/tests/shared/providers/databases/` (or renamed path) continue to pass; one new `test_registry_keys.py::test_chat_history_domain_keys` asserts `"cosmosdb"` and `"postgresql"` are registered under whichever name we keep.
- **Blocked by / blocks:** none / blocks chat-history router work in Phase 4 task #31.

### CU-007 — Align `v2/docker/.env.dev.example` env names with `AppSettings` (and Bicep outputs)

- **Status:** ✅ Done — 2026-05-04 (in-tree edit; no commit ref captured)
- **Severity:** medium
- **Pillar:** Configuration Layer
- **Target phase:** 3.5 (debt — must land before Phase 4 onboarding docs are written)
- **Location:** [v2/docker/.env.dev.example](../docker/.env.dev.example)
- **User decisions captured before edit:**
  - search var → `AZURE_AI_SEARCH_ENDPOINT` (full https URL; matches `SearchSettings.endpoint`)
  - orchestrator var → `CWYD_ORCHESTRATOR_NAME` (already what `OrchestratorSettings` reads via `env_prefix="CWYD_ORCHESTRATOR_"`)
  - Foundry endpoint var → `AZURE_AI_PROJECT_ENDPOINT` only (project endpoint covers both Agent Framework and the OpenAI-compatible client; account endpoint not needed in local-dev shape)
- **Recommended fix (one unit):** rewrite [v2/docker/.env.dev.example](../docker/.env.dev.example) using exact `AppSettings`/Bicep names — **DONE.** Replaced 7 v1 aliases (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_MODEL`, `AZURE_OPENAI_EMBEDDING_MODEL`, `AZURE_SEARCH_SERVICE`, `AZURE_SEARCH_INDEX`, `AZURE_CLIENT_ID`, `ORCHESTRATOR`, bare `LOG_LEVEL`) with the canonical names. Added inline comments naming the AppSettings field each var maps to. Added a header note explaining that `AZURE_DB_TYPE`/`AZURE_INDEX_STORE`/`AZURE_POSTGRES_ENDPOINT`/storage URLs are forced by docker-compose.dev.yml and so are intentionally **not** in the example file (setting them there has no effect on the default profile).
- **Acceptance test:** new [tests/shared/test_settings.py::test_env_dev_example_keys_round_trip_through_appsettings](../tests/shared/test_settings.py) parses the example file and asserts every non-comment key is either consumed by `AppSettings` (introspected from each sub-model's `env_prefix` + field names) or in a documented `_ENV_EXAMPLE_EXEMPTIONS` dict (3 entries: `VITE_BACKEND_URL`, `BACKEND_CORS_ORIGINS`, `APPLICATIONINSIGHTS_CONNECTION_STRING`; the latter two are tagged for collapse by CU-002). Suite **264 / 264 passed** (was 263 — new test).
- **Follow-up note (not a new CU):** `v2/docker/docker-compose.dev.yml` line 41 hard-codes `LOG_LEVEL: INFO` on the backend service. AppSettings reads `AZURE_LOG_LEVEL` (env_prefix `AZURE_`), so the bare `LOG_LEVEL` is silently ignored — the default `INFO` survives by coincidence. Recommend collapsing into CU-002b (lifespan rewire) since both touch the same config-routing concern; tracking under CU-002b's scope rather than spawning CU-008.
- **Blocked by / blocks:** none / blocks LOCAL_DEPLOYMENT.md rewrite in Phase 7.

## Suggested execution order

Grouped by dependency. Pick the next CU that has no open prerequisites.

1. **CU-003** — one-line noqa marker. Trivial. Unblocks Phase A.2 going green in CI later.
2. **CU-005** — Pillar header on empty `__init__.py`. Trivial. Unblocks Phase A.7.
3. **CU-007** — env-example rewrite. Self-contained.
4. **CU-002a → CU-002b** — settings field then lifespan rewire. Closes A.5.
5. **CU-006** — chat-history naming decision — **✅ Done** (Option B chosen).
6. **CU-001a → CU-001b → CU-001c → CU-001d → CU-001e** — full agent_framework wiring chain. The user-stated runtime-switch invariant becomes real here.
7. **CU-004a → CU-004b** — reasoning channel parity. CU-004b depends on CU-001 to be exercisable end-to-end.

## Out-of-scope notes

- **Phase C.15 dual `bicep build`:** standalone `bicep build` cannot accept Bicep parameter overrides; the postgres-mode compile is enforced at deploy-time by `_validatePostgresAdminPrincipalName` (fail-fast guard). A real two-mode validation belongs in Phase 7 CI as `azd provision --preview` against both `databaseType` values — not a CU here.
- **Frontend SSE consumer for `reasoning` channel:** out of scope until CU-004 lands and emits real events to assert against. Track separately under Phase 5.
- **Removing the v1 `code/` tree:** governed by [development_plan.md](development_plan.md) §2.1 removal list — those removals are tracked in their own checklist, not duplicated here.

## Working loop

For each CU-ID in the order above:

1. User says **"do CU-XXX"**.
2. Planner emits a one-unit work order in [/memories/session/plan.md](../../memories/session/plan.md) (replacing the previous one), referencing CU-XXX and the schema above.
3. Implementer makes the single class/method change + matching test stub (Hard Rule #1, Hard Rule #2 test-first).
4. Tester fills the test, runs it, confirms green.
5. Update the CU-XXX entry below with `**Status:** ✅ Done — <commit/PR ref> — <date>` (and any follow-up CU-IDs spawned).
