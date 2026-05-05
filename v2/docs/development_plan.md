# CWYD v2 — Development Plan

**Repo**: [Azure-Samples/chat-with-your-data-solution-accelerator](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator)
**Branch**: `dev-v2`
**Last updated**: April 28, 2026

---

## 0. Status snapshot

Where we are against the 7-phase plan in §4. Status legend: ✅ done · ⏳ in progress · ⏭ next · ☐ not started.

| Phase | Title | Status | Notes |
|---|---|---|---|
| 1 | Infrastructure + Project Skeleton | ✅ done | Bicep ✅ (AVM-first, UAMI+RBAC, no Key Vault, two-mode `databaseType`, P1 polish shipped). Frontend stub ✅ (Vite+React 19+TS, no UI lib, `/api/health` ping, 3/3 vitest). Backend stub ✅ (subsumed by Phase 2 #13). Functions stub ✅ (#7 cleared 2026-04-28, 4/4). `post_provision.sh` ✅ (#8 verified 2026-04-28). |
| 2 | Configuration + LLM Integration | ✅ done | `shared/{registry,settings,types}` ✅ (incl. `OrchestratorEvent`). `shared/providers/{credentials,llm}/` ✅ (20/20). `backend/{app,dependencies,routers/health,models/health}` ✅ (11/11). 55/55 tests pass overall. **Post-build review pass** locked in: per-app credential+LLM singleton via lifespan (no per-request leaks), `/api/health` (always 200) split from `/api/health/ready` (503 on fail), `skip` is neutral in aggregation, `BaseLLMProvider.reason()` returns `AsyncIterator[OrchestratorEvent]` to match the SSE channel contract. |
| 3 | Conversation + RAG (Core Chat) | ✅ BE done | Tasks #17 ✅ (skeleton, 6/6), #18 ✅ (LangGraph, 11/11 — incl. citation wiring), #19 ✅ (Agent Framework, 9/9), #20 ✅ (tools: content_safety 10/10 + text_processing 9/9 + post_prompt 14/14 + qa 13/13), #21 ✅ (search domain + AzureSearch, 13/13), #22a ✅ (router, 6/6 → 7/7 after Q6c), #22b ✅ (chat pipeline, 6/6), #23 ✅ (citations, 10/10), #25 ✅ (reasoning, 14/14), #26 ✅ (indexing scripts, 10/10). 179/179 baseline → 186/186 after Phase 3.5 QA remediation. **#24 (FE SSE wiring) owned by frontend team.** |
| 3.5 | QA Remediation (post-Phase-3 audit) | ✅ done | QA report `v2/docs/qa_report_v2.md` (2026-04-28) found 6 deployability blockers + 5 medium risks. Cleared: Q2 (App.tsx React 19 JSX), Q3 (`frontend_app.py`), Q4 (`azure.yaml services:`), Q5 (compose env vars + optional `.env.dev`), Q6a/b/c (chat-route DI + lifespan + search wiring), Q7 (CI mask removal), Q8 (re-run all gates). Deferred: Q1 (Docker build, awaiting Docker Desktop), Q6d (agent_framework 503 guard → Phase 4 task #28). 186/186 backend, 20/20 frontend, both compose profiles green, registry-dispatch grep gate clean. |
| 4 | Chat History + Both Databases | ☐ | |
| 5 | Admin + Frontend Merge | ☐ | |
| 6 | RAG Indexing Pipeline (Split Functions) | ☐ | |
| 7 | Testing + Documentation | ☐ | Rolling — each phase ends with `azd up` green and updates this file. |

See §10 for the file-level inventory of work already shipped.

> **Phase closure discipline** (Hard Rule #12 in [copilot-instructions.md](../../.github/copilot-instructions.md)): debt items discovered while working on Phase N are appended to §0.1 below — **never implemented inline**. The queue is cleared in a single dedicated audit turn at the end of the phase. Within a phase, tasks execute in numeric order from §4; no out-of-order pulls from later phases.

---

## 0.1 Debt Queue

Debt items carried over from earlier phases. Appended-only during normal work; **cleared in batch during the originating phase's end-of-phase audit, or the next available audit turn if discovered after the originating phase closed**.

**Team split (decision 2026-04-28)**: backend debt is cleared in backend phase audits; **frontend debt is owned by the dedicated frontend team and is out of scope for backend phase audits.** Frontend audits run on their own cadence and are tracked in §0.2 below.

### Backend debt

| ID | Origin Phase | Item | Files | Cleared in | Status |
|---|---|---|---|---|---|
| 7 | 1 | Functions stub: minimal `function_app.py` + `host.json` + `pyproject.toml` (no blueprints — those are Phase 6) | `v2/src/functions/` | Phase 3 audit (pre-pulled 2026-04-28) | ✅ 2026-04-28 (4/4 tests) |
| 8 | 1 | `post_provision.sh` POSIX wrapper (env-var validation parity with `.ps1`, exec's `python scripts/post_provision.py`) | `v2/scripts/post-provision.sh` | n/a — shipped during Phase 1, ledger entry only | ✅ 2026-04-28 (verified existing) |
| Q2 | 3.5 | Frontend prod build TS error: `App.tsx` used global `JSX.Element` (dropped from React 19 `@types/react`); imported `type JSX` from `react` | `v2/src/frontend/src/App.tsx` | Phase 3.5 QA remediation | ✅ 2026-04-28 (`npm run build` exit 0; vitest 20/20) |
| Q3 | 3.5 | Frontend prod stage missing `frontend_app.py`; created tiny FastAPI + StaticFiles(html=True) ASGI app with `DIST_DIR` env override | `v2/src/frontend/frontend_app.py`, `v2/tests/frontend/test_frontend_app.py` | Phase 3.5 QA remediation | ✅ 2026-04-28 (2/2 new tests; 181/181 total) |
| Q4 | 3.5 | `azure.yaml` `services:` block was empty (blocked `azd deploy`); wired `backend` (containerapp), `frontend` (appservice), `function` (function), each pointing at its Dockerfile and matching the `azd-service-name` tags in `infra/main.bicep` | `v2/azure.yaml` | Phase 3.5 QA remediation | ✅ 2026-04-28 (YAML parse OK, 3 services; full `azd package` deferred until env provisioned) |
| Q5 | 3.5 | Compose backend used `AZURE_DB_ENDPOINT` (not in `AppSettings`) + required `.env.dev` blocked clean-checkout `compose config`; renamed to `AZURE_POSTGRES_ENDPOINT`, added `AZURE_INDEX_STORE=pgvector` (validator requirement), and marked `env_file` as `required: false` (compose v2.24+) for both backend + functions services | `v2/docker/docker-compose.dev.yml` | Phase 3.5 QA remediation | ✅ 2026-04-28 (`compose config` exit 0 from clean checkout, both backend-only and frontend-only profiles) |
| Q7 | 3.5 | CI entrypoint masked pytest + frontend test failures with `\|\| true` so the validation image always reported green; removed the masks so `failures` accumulator + non-zero exit actually trigger | `v2/docker/ci-entrypoint.sh` | Phase 3.5 QA remediation | ✅ 2026-04-28 |
| Q6a | 3.5 | Chat router had no DI seam for the search provider, so production `langgraph` ran in pass-through mode (no citations) despite tests proving the path; added `get_search_provider` + `SearchProviderDep` returning `Optional[BaseSearch]` from `app.state.search_provider`, matching langgraph's optional contract | `v2/src/backend/dependencies.py`, `v2/tests/backend/test_dependencies.py` | Phase 3.5 QA remediation | ✅ 2026-04-28 (2 new tests, 183/183 total) |
| Q6b | 3.5 | Lifespan never built a search provider, so `app.state.search_provider` was always missing; added optional construction (`search.create("azure_search", ...)` when `settings.search.endpoint` set AND `index_store == "AzureSearch"`) + reverse-order `aclose()` in shutdown; pgvector path deferred to Phase 4 | `v2/src/backend/app.py`, `v2/tests/backend/test_app_lifespan.py` | Phase 3.5 QA remediation | ✅ 2026-04-28 (2 new tests, 185/185 total) |
| Q6c | 3.5 | Conversation route still constructed orchestrator without `search=`, so production langgraph ran in pass-through mode (no citations); injected `SearchProviderDep`, forwarded `search=search` through `orchestrators.create(...)`, added `**_extras` swallow on both langgraph + agent_framework `__init__` so the route can pass uniform kwargs without name-based dispatch (Hard Rule #4) | `v2/src/backend/routers/conversation.py`, `v2/src/shared/providers/orchestrators/{langgraph,agent_framework}.py`, `v2/tests/backend/test_conversation.py` | Phase 3.5 QA remediation | ✅ 2026-04-28 (1 new test, 186/186 total; agent_framework 503 guard deferred to Phase 4 task #28 when AgentsClient lifespan wiring lands — currently unreachable) |
| Q8 | 3.5 | Re-ran all QA gates after Q2-Q7 remediation: backend pytest 186/186, frontend vitest 20/20, frontend `npm run build` exit 0 (built in 630ms), `compose config` exit 0 for both backend-only + frontend-only profiles, registry-dispatch grep gate 0 hits (refined to skip explicit `# noqa: registry-dispatch` markers on `health.py` diagnostic display + `settings.py` config validator — neither is provider dispatch), `azure.yaml` parses; bicep build + docker build deferred (CLI/daemon unavailable) | `v2/src/backend/routers/health.py`, `v2/src/shared/settings.py` (noqa markers + clarifying comments) | Phase 3.5 QA remediation | ✅ 2026-04-28 |
| Q9 | 3.5 | Reconciliation pass: §0 status snapshot rolled forward (Phase 1 ⚠️→✅, Phase 3 test count 179→186, new Phase 3.5 row); QA report `v2/docs/qa_report_v2.md` got a Phase 3.5 Re-Run Update table mapping each original blocker to its cleared-or-deferred status | `v2/docs/development_plan.md` (§0), `v2/docs/qa_report_v2.md` | Phase 3.5 QA remediation | ✅ 2026-04-28 |
| Q10 | 3.5 | Pre-Phase-4 structural realignment: moved `v2/src/providers/` → `v2/src/shared/providers/` and `v2/src/pipelines/` → `v2/src/shared/pipelines/` (test mirrors moved too); rewrote 35 import sites across 19 files; folded `chat_history` domain into a new `databases` domain (DB client owns CRUD, no separate chat_history factory). Side effects: silently fixed two latent packaging bugs — (a) `pyproject.toml` packages list omitted `providers/` + `pipelines/` (would not have shipped in wheel); (b) `docker-compose.dev.yml` dev-mounts omitted them (no hot-reload in dev). Both are now covered by the existing `src/shared` package + mount. Updated dev_plan §3.4 tree, §3.5 swappable list, §4 Phase 4 task table (#27-#30), §6.5 customization points; updated `.github/copilot-instructions.md` Hard Rule #4 path; updated all `v2-*.instructions.md` glob + path refs (incl. v2-shared `applyTo` collapsed from `v2/src/{shared,providers,pipelines}/**` → `v2/src/shared/**`) | `v2/src/shared/{providers,pipelines}/**`, `v2/tests/shared/{providers,pipelines}/**`, `v2/src/{backend,shared}/**/*.py` (imports), `v2/docs/development_plan.md`, `v2/docs/qa_report_v2.md`, `.github/copilot-instructions.md`, `.github/instructions/v2-*.instructions.md` | Phase 3.5 → Phase 4 prep | ✅ 2026-04-28 (186/186 tests still green; zero `from providers.` / `from pipelines.` leftovers) |
| CU-008 | Cleanup audit batch 2 | Move env file to `v2/` root + delete docker variant: create `v2/.env.sample` + `v2/.env` (gitignored via new `v2/.gitignore`); delete `v2/docker/.env.dev.example` + `v2/docker/.env.dev`; rewire `docker-compose.dev.yml` `env_file: ../.env`; update CU-007 drift-guard test path; update onboarding docs (CU-008b) | `v2/.env.sample`, `v2/.gitignore`, `v2/docker/docker-compose.dev.yml`, `v2/tests/shared/test_settings.py`, `v2/docs/development_plan.md` | Cleanup audit batch 2 | ✅ 2026-05-05 (CU-008-plan + CU-008-adr ([adr/0008](adr/0008-lazy-foundry-agent-bootstrap.md)) + CU-008a (pytest 295/295, both compose profiles exit 0) + CU-008b (§6.6 rewrite). Followup Q11 logged for §6.3/§6.5 v1-alias drift.) |
| CU-009 | Cleanup audit batch 2 | Reverse CU-001a/e env-only assumptions on agent IDs: drop `azureAiAgentId` Bicep param + `AZURE_AI_AGENT_ID` env binding (CU-001e undo); drop `OrchestratorSettings.agent_id` field + `model_validator` (CU-001a undo); update CU-007 exemption list. Replaced by lazy DB-backed resolution in CU-010 | `v2/infra/main.bicep`, `v2/src/shared/settings.py`, `v2/tests/infra/test_main_bicep.py`, `v2/tests/shared/test_settings.py` | Cleanup audit batch 2 | ✅ 2026-05-05 (CU-009a Bicep param + env binding removed, presence-tests rewritten as absence-tests, `az bicep build` exit 0; CU-009b `OrchestratorSettings.agent_id` field + validator removed, exemption dropped, four CU-001a tests removed + two absence tests added, downstream `routers/conversation.py` updated to forward `agent_id=""` literal until CU-010d wires lazy resolver. Pytest 293/293 ✅) |
| CU-010 | Cleanup audit batch 2 | Lazy DB-backed Foundry agent bootstrap: new `v2/src/shared/agents/` package (`AgentDefinition` + `CWYD_AGENT` + `RAI_AGENT` + `BUILTIN_AGENTS`); add `get_agent_id` / `upsert_agent_id` to `BaseDatabaseClient` + Cosmos + Postgres + post_provision schema bootstrap; add `get_or_create_agent` to `BaseAgentsProvider` + `FoundryAgentsProvider` with per-key `asyncio.Lock`; redo `routers/conversation.py` to call resolver only on `agent_framework` branch (CU-001d redo) | `v2/src/shared/agents/**`, `v2/src/shared/providers/databases/**`, `v2/scripts/post_provision.py`, `v2/src/shared/providers/agents/**`, `v2/src/backend/routers/conversation.py` | Cleanup audit batch 2 | ✅ 2026-05-05 (CU-010a ✅ 2026-05-05 — `AgentDefinition` + `CWYD_AGENT` + `RAI_AGENT` + `BUILTIN_AGENTS` landed under `v2/src/shared/agents/`, 9 new tests, pytest 302/302; CU-010b1 ✅ 2026-05-05 — `get_agent_id` ABC + Cosmos (`type="agent"` + `_system` partition) + Postgres (`agents` table in lazy `_SCHEMA_SQL`), 10 new tests, pytest 312/312; CU-010b2 ✅ 2026-05-05 — `upsert_agent_id` ABC + Cosmos (`upsert_item` with `CosmosItemType.AGENT` enum + `_system` partition) + Postgres (`INSERT ... ON CONFLICT (name) DO UPDATE SET agent_id = EXCLUDED.agent_id, updated_at = NOW()`), 8 new tests (3 cosmos + 3 postgres + 2 base ABC), pytest 320/320; CU-010b3 ✅ 2026-05-05 — no-op closure: confirmed `v2/scripts/post_provision.py` requires no edit (Cosmos reuses chat-history container; Postgres bootstraps `agents` lazily via `_SCHEMA_SQL` on first `_ensure_pool()`), 2 lock-in tests added asserting post_provision contains no `agents` DDL / no `_system` partition seed / no `CosmosItemType` reference, pytest 322/322; CU-010c ✅ 2026-05-05 — `BaseAgentsProvider.get_or_create_agent(definition, db) -> str` lazy resolver: cache hit -> early return; DB hit + Foundry validate (`get_agent`) -> cache + return; `ResourceNotFoundError` 404 -> fall through to recreate (orphan recovery); per-key `asyncio.Lock` (`setdefault`) + double-checked cache inside the lock prevents concurrent first-requests from double-creating; deployment resolved via `getattr(settings.openai, definition.deployment_attr)`. Implemented as a concrete method on the base (deviation from cleanup_audit prose: algorithm is provider-agnostic, uses `self.get_client()` as the only seam). 6 new tests in `test_base.py` (cache hit short-circuit, DB hit + cache-on-validate, 404 orphan recovery, cold-start create+persist+cache, reasoning_deployment indirection, concurrency lock guarantees single create). Pytest 328/328; CU-010d ✅ 2026-05-05 — router redo wires `agents.get_or_create_agent(CWYD_AGENT, db)` on the `agent_framework` branch only (langgraph keeps `agent_id=""` swallowed by `**_extras`); the `if name == "agent_framework"` check is *kwarg preparation*, not dispatch (`orchestrators.create(...)` remains the single registry-keyed factory call); Hard Rule #4 invariant test tightened from naive substring search to AST `ast.Call` walk (1 call site enforced); `_FakeAgentsProvider` extended with `get_or_create_agent` + resolver-call ledger, new `_FakeDatabaseClient` sentinel + `get_database_client` override in fixture; 3 new tests (agent_framework branch resolves + forwards id, non-agent_framework branch zero round-trips + empty literal, resolver receives CWYD_AGENT singleton + DI'd db by identity); existing parametrized test updated to assert resolved-id on agent_framework / empty-literal on langgraph. Pytest 331/331. **CU-010 fully complete.**) |
| CU-011 | Cleanup audit batch 2 | RAI agent invocation seam: add `rai_check(text, agents, db) -> bool` to `shared/tools/content_safety.py` (MACAE TRUE/FALSE classifier with attribution); wire pre-orchestrator gate in `shared/pipelines/chat.py` emitting `OrchestratorEvent(channel="error", payload="blocked-by-rai")` on unsafe input | `v2/src/shared/tools/content_safety.py`, `v2/src/shared/pipelines/chat.py`, `v2/tests/shared/{tools,pipelines}/**` | Cleanup audit batch 2 | ✅ done 2026-05-05 (CU-011a + CU-011b shipped. CU-011a: `async def rai_check(text, agents, db) -> bool` added to `shared/tools/content_safety.py`; lazy CU-010c resolver; fail-closed semantics; TRUE→safe per `RAI_AGENT.instructions` (corrected an audit-prose typo); 11 new tests. CU-011b: `run_chat` accepts `rai_check: RaiScreener | None = None` (`RaiScreener = Callable[[str], Awaitable[bool]]` exported); REST content-safety runs first, RAI agent second, orchestrator third — either guard short-circuits with `metadata.code="content_safety"` or `"rai_blocked"`; 6 new tests covering pass/block/latest-user/order-of-operations/two-guard interplay/`__all__`. Pipeline stays DI-free — router will bind agents+db via `functools.partial` later when content-safety toggle is exposed. Pytest 348/348) |
| CU-012 | Cleanup audit batch 2 | Documentation + ledger close: new `v2/docs/env-vars.md` (canonical inventory + v1 cross-reference); new `v2/docs/agents.md` (lazy bootstrap sequence + operational notes); ADR `v2/docs/adr/0008-lazy-foundry-agent-bootstrap.md`; mark CU-008..CU-012 ✅ Done in cleanup_audit.md + close ledger rows here | `v2/docs/env-vars.md`, `v2/docs/agents.md`, `v2/docs/adr/0008-lazy-foundry-agent-bootstrap.md`, `v2/docs/cleanup_audit.md`, `v2/docs/development_plan.md` | Cleanup audit batch 2 | ✅ done 2026-05-05 (CU-012a ✅ [env-vars.md](docs/env-vars.md): nine `AppSettings` sub-tables + 18-row "Removed in v2" + 16-row v1→v2 cross-reference; explicit `AZURE_AI_AGENT_ID` deprecation row points to CU-009 / ADR 0008. CU-012b ✅ [agents.md](docs/agents.md): 6 sections (why-not-env-driven / algorithm + 6 invariants / `BUILTIN_AGENTS` per-agent tables / ops runbook with cosmos+postgres force-recreate + troubleshooting / adding-a-third-agent worked example / acceptance gates); cross-links to ADR 0008 + env-vars.md. CU-012c ✅ ledger close: CU-010..CU-012 got top-level `**Status:** ✅ Done` rows in cleanup_audit.md, new "Cleanup audit batch 2 — closure summary" section ships the per-CU rollup table + 301→348 test movement + Q11/Q12/Q13/CU-004 follow-up list. Acceptance gates verified: `grep AZURE_AI_AGENT_ID v2/` returns only docs hits (zero source/infra); all five batch CUs show ✅ Done; ADR 0008 Accepted. **Cleanup audit batch 2 fully closed.**) |
| CU-013 | Cleanup audit batch 2 follow-on | Drop `if TYPE_CHECKING:` and `from __future__ import annotations` everywhere in `v2/` (reverses the Hard Rule #11 amendment added during CU-010c). User decision 2026-05-05 (*"we are doing type always available"*): types must always be available at runtime; no exceptions; all of `v2/` (src + tests + scripts + functions). Genuine circular imports get fixed by extracting the shared type to a leaf module (Hard Rule #10 — ask first). 5 sub-CUs: (a) Hard Rule #11 amendment + AST invariant test (lands red, xfail); (b) sweep `v2/src/shared/**`; (c) sweep `v2/src/{backend,functions,frontend}/**` + `v2/scripts/**`; (d) sweep `v2/tests/**` (test xpass→remove xfail); (e) close + ADR 0009 if any leaf-extraction was required | `.github/copilot-instructions.md`, `.github/instructions/v2-shared.instructions.md`, `v2/tests/shared/test_no_type_checking_or_future_annotations.py`, `v2/src/**`, `v2/tests/**`, `v2/scripts/**`, possibly `v2/docs/adr/0009-runtime-type-imports.md` | Cleanup audit batch 2 follow-on | 🔄 in progress (CU-013a ✅ 2026-05-05 — Hard Rule #11 Python bullet rewritten in [.github/copilot-instructions.md](../../.github/copilot-instructions.md): `if TYPE_CHECKING:` + `from __future__ import annotations` declared **banned in v2/**, no exceptions, leaf-module extraction documented as the only escape hatch. Synced [v2-shared.instructions.md](../../.github/instructions/v2-shared.instructions.md) with a new "Runtime types" section + added both constructs to the Banned list. New [v2/tests/shared/test_no_type_checking_or_future_annotations.py](../tests/shared/test_no_type_checking_or_future_annotations.py): AST walker over every `*.py` under `v2/{src,tests,scripts}` (skips `__pycache__` / `.venv` / `build`), parametrised one-case-per-file (clean failure output), three checks per file (no `from __future__ import annotations`, no `if TYPE_CHECKING:` block, no `from typing import TYPE_CHECKING` symbol — the third catches dead imports lingering after a guard delete). Marked `@pytest.mark.xfail(strict=False)` so the suite stays green through CU-013b/c/d; CU-013e removes the marker. Sanity guard test asserts the parametrise input is non-empty and walks both `src/` + `tests/`. Pytest **349 passed, 74 xfailed, 15 xpassed** (the 74 xfails are exactly the violation surface the sweep will clear; the 15 xpasses are files that already comply). Q13 updated to drop the "TYPE_CHECKING preferred" sub-task — superseded by CU-013. **CU-013b next — sweep `v2/src/shared/**`.**) |
| Q11 | Cleanup audit batch 2 | Discovered during CU-008b: §6.3 Pydantic code sample and §6.5 Customization Points table contain v1 alias names that no longer match `AppSettings` (e.g. `AZURE_OPENAI_MODEL` should be `AZURE_OPENAI_GPT_DEPLOYMENT`, `AZURE_SEARCH_SERVICE` should be `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_DB_ENDPOINT` should be `AZURE_COSMOS_ENDPOINT` / `AZURE_POSTGRES_ENDPOINT`, `AZURE_CLIENT_ID` should be `AZURE_UAMI_CLIENT_ID`, `ORCHESTRATOR` should be `CWYD_ORCHESTRATOR_NAME`). Out of CU-008b scope (which covers `.env.dev.example` references only). Will be cleared by CU-012a (`env-vars.md` becomes the canonical reference) and a follow-up doc-only sync of §6.3 / §6.5 | `v2/docs/development_plan.md` §6.3, §6.5 | CU-012a + post-CU-012c sync | ☐ open |
| Q12 | Cleanup audit batch 2 | Sweep remaining bare-string closed-set constants to `enum.StrEnum` per the new Hard Rule #11 sub-rule (added 2026-05-05 alongside the CU-010b1 `CosmosItemType` refactor). Known sites: SSE channel literals on `OrchestratorEvent.channel` (`"reasoning"|"tool"|"answer"|"citation"|"error"`) — currently a Pydantic `Literal[...]` annotation but produced as bare strings at every emit site in `routers/conversation.py` + orchestrators + pipeline; any provider keys hard-coded in tests as bare strings instead of registry constants. Audit + sweep in a single dedicated turn at end of cleanup-audit batch (after CU-012c) so the existing CU-001/CU-004 SSE work is not disturbed mid-stream | `v2/src/shared/types.py`, `v2/src/backend/routers/conversation.py`, `v2/src/shared/providers/orchestrators/**`, `v2/src/shared/pipelines/chat.py`, related tests | Post-CU-012c audit turn | ☐ open |
| Q13 | Cleanup audit batch 2 | Wire CI-enforced **static type checking** (recommend `pyright --strict`) into v2 (raised 2026-05-05 by user *"we always check the type"*). Plan: (1) add `[tool.pyright]` to `v2/pyproject.toml` with `pythonVersion = "3.13"`, `strict = ["src/shared/**", "src/backend/**"]`, `reportMissingTypeStubs = "warning"`; (2) add `pyright>=1.1.380` to `[dependency-groups].dev`; (3) add `make typecheck` target to `v2/Makefile` running `uv run pyright`; (4) add `.github/workflows/v2-typecheck.yml` (subject to Hard Rule #10 confirmation on CI workflow location); (5) triage discovered errors — trivial fixes inline, substantive issues filed as Q14. **Note (2026-05-05):** the original Q13 framing recommended keeping `if TYPE_CHECKING:` guards as the "preferred pattern" for type-only imports. That recommendation has been **reversed by CU-013** (Hard Rule #11 amendment 2026-05-05) per user request *"we are doing type always available"*. Q13 now ships pyright on a codebase where every annotation already resolves to a real runtime symbol; the leaf-module-extraction pattern from CU-013 means there is no longer any structural reason to need the guard | `v2/pyproject.toml`, `v2/Makefile`, `.github/workflows/v2-typecheck.yml` (new), various `v2/src/**` only if pre-existing type errors surface | Dedicated CU after CU-013 lands | ☐ open |

### 0.2 Frontend debt (separate team)

| ID | Origin Phase | Item | Files | Cleared in | Status |
|---|---|---|---|---|---|
| DV1 | 1 | Re-verify `docker compose -f v2/docker/docker-compose.dev.yml build frontend` (currently blocked: Docker Desktop daemon down on dev machine) | n/a | Frontend team audit | ⏸ blocked — FE team owns |

Legend: ☐ open · ⏸ blocked · ✅ cleared (date)

---

## Summary

Modernize the Chat With Your Data Solution Accelerator from a monolithic Flask application with four co-installed orchestrators into a modular **FastAPI + Azure Functions** architecture. Replace the direct Azure OpenAI SDK with **Foundry IQ** (Knowledge Base, Embeddings), remove Prompt Flow, Semantic Kernel, Streamlit admin, one-click deploy, and Poetry references, add the **Azure AI Agent Framework** with reasoning model support, upgrade **LangChain to LangGraph** for PostgreSQL indexing, and split **Azure Functions** into a modular RAG indexing pipeline. Azure Bot Service and Teams plugin are deferred to a future version.

**Key principle**: Infrastructure is Phase 1. Every phase results in a deployable `azd up` solution — some infra, some data, some scripts, some backend, and some frontend — even if they don't look great yet.

---

## 1. Current State (v1)

### 1.1 Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask + Uvicorn, monolithic `code/` directory |
| Admin | Streamlit (`code/backend/Admin.py`) — separate Python web app |
| Frontend | React 19, TypeScript, Vite, Fluent UI |
| Functions | Azure Functions (Python 3.11) — batch document processing |
| Model Access | Direct Azure OpenAI SDK (GPT-\*, text-embedding-3-small) |
| Databases | Azure Cosmos DB **or** PostgreSQL Flexible Server (switchable at deploy time) |
| Configuration | Monolithic `EnvHelper` singleton — 100+ environment variables |
| Infrastructure | Bicep IaC, Azure Developer CLI (`azd`), one-click "Deploy to Azure" ARM button |
| Package Managers | `uv` (Python), `npm` (Node) |

### 1.2 Orchestration Strategies (4, runtime-switchable)

| Strategy | Implementation |
|----------|---------------|
| **OpenAI Functions** | Direct Azure OpenAI function/tool calling |
| **Semantic Kernel** | Microsoft SK framework with plugins |
| **LangChain** | `ZeroShotAgent` + `AgentExecutor` (legacy pattern) |
| **Prompt Flow** | Azure ML deployed endpoint invocation |

### 1.3 Azure Services

- Azure OpenAI (GPT-\*, embeddings) — direct SDK calls
- Azure AI Search (vector + semantic search)
- Azure Storage (Blob + Queue)
- Azure Cosmos DB / PostgreSQL Flexible Server (pgvector)
- Azure Key Vault, Document Intelligence, Content Safety, Speech Services
- Azure App Service (frontend + admin), Azure Functions
- Application Insights, Log Analytics, Event Grid
- Optional: Computer Vision, VNet + Private Endpoints, Bastion

### 1.4 Deployment

- One-click "Deploy to Azure" button (ARM template)
- Azure Developer CLI (`azd up`)
- Docker Compose (local development)
- Supported regions: australiaeast, eastus2, japaneast, uksouth

### 1.5 Architecture Diagram (v1)

```
┌─────────────────────────────────────────────────────────┐
│                       USERS                             │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────▼──────────────┐
          │   React/Vite Frontend       │
          │   Azure App Service         │
          └──────────────┬──────────────┘
                         │
          ┌──────────────▼──────────────┐
          │   Flask Backend (Uvicorn)   │
          │   code/create_app.py        │
          │   Azure App Service         │
          └──┬───────────┬──────────┬───┘
             │           │          │
    ┌────────▼───┐  ┌────▼────┐  ┌─▼──────────────────┐
    │ Orchestrator│  │Chat     │  │ Azure OpenAI       │
    │ (4 options) │  │History  │  │ (Direct SDK)       │
    │ SK / LC /   │  │CosmosDB │  │ GPT-* + Embeddings │
    │ PF / OAI    │  │or PG    │  └────────────────────┘
    └──────┬──────┘  └─────────┘
           │
    ┌──────▼─────────────┐    ┌───────────────────────┐
    │ Shared Tools        │    │ Streamlit Admin       │
    │ QA, TextProc,       │    │ code/backend/Admin.py │
    │ ContentSafety       │    │ Azure App Service     │
    └──────┬──────────────┘    └───────────────────────┘
           │
    ┌──────▼─────────────┐
    │ Search Handlers     │
    │ AI Search / PG      │
    └─────────────────────┘

    ┌─────────────────────────────────────────┐
    │  Azure Functions (Monolithic)            │
    │  Batch processing — blob → queue → index │
    └─────────────────────────────────────────┘
```

---

## 2. What Changes in v2

### 2.1 Removals

| Component | Reason |
|-----------|--------|
| **One-click "Deploy to Azure" button** | Simplify to `azd`-only; ARM template maintenance overhead |
| **Poetry references** | Fully standardized on `uv`; remove any lingering Poetry config |
| **Prompt Flow orchestrator** | Replaced by Agent Framework; drops Azure ML dependency |
| **Semantic Kernel orchestrator** | Consolidate to fewer, more strategic orchestrators |
| **Streamlit admin app** | Admin features merged into the React/Vite frontend |
| **Direct Azure OpenAI SDK** | Replaced by Foundry IQ for knowledge base and embeddings |
| **Azure Bot Service / Teams extension** | Deferred to a future version |
| **Key Vault for app secrets** | Replaced by RBAC + direct env vars (MACAE pattern) |

### 2.2 Additions

| Component | Purpose |
|-----------|---------|
| **Azure AI Agent Framework** | Modern agent orchestration — replaces Semantic Kernel and Prompt Flow |
| **Foundry IQ** (Knowledge Base, Embeddings) | Centralized knowledge base, embeddings, and model access (GPT-\*, o-series reasoning) |

### 2.3 Updates

| Component | From → To |
|-----------|-----------|
| **Web framework** | Flask → **FastAPI** (async-native, OpenAPI docs, dependency injection) |
| **LangChain orchestrator** | `ZeroShotAgent` / `AgentExecutor` → **LangGraph** (`StateGraph` + `ToolNode`) |
| **Azure Functions** | Monolithic → **split into modular RAG indexing pipeline** |
| **Configuration** | `EnvHelper` singleton → **Pydantic `BaseSettings`** (typed, validated, nested) |
| **Project structure** | Monolithic `code/` → **modular `v2/src/`** (backend, frontend, functions, shared) |
| **Admin UI** | Standalone Streamlit app → **merged into React/Vite frontend** |
| **Bicep infrastructure** | Updated to add Foundry IQ resources, remove Azure ML references, remove one-click ARM |

---

## 3. v2 Target Architecture

### 3.1 High-Level Architecture

```
                    ┌──────────────────────────────────┐
                    │           USERS (Browser)         │
                    └───────────────┬──────────────────┘
                                    │
                    ┌───────────────▼──────────────────┐
                    │   React/Vite Frontend             │
                    │   (Chat + Admin — unified)        │
                    │   Azure App Service               │
                    └───────────────┬──────────────────┘
                                    │ REST API
                    ┌───────────────▼──────────────────┐
                    │   FastAPI Backend                  │
                    │   Routers: conversation, admin,    │
                    │   chat_history, files, speech,     │
                    │   auth, health                     │
                    │   Azure App Service                │
                    └──┬────────────┬───────────────┬──┘
                       │            │               │
              ┌────────▼───┐  ┌─────▼──────┐  ┌────▼──────────────┐
              │ Orchestrator│  │ Chat       │  │  Foundry IQ       │
              │ Router      │  │ History    │  │  (Knowledge Base, │
              │             │  │ CosmosDB   │  │   Embeddings)     │
              │ ┌─────────┐ │  │ or         │  │  ├─ GPT-*        │
              │ │LangGraph│ │  │ PostgreSQL │  │  ├─ o-series     │
              │ └─────────┘ │  └────────────┘  │  │  (reasoning)  │
              │ ┌─────────┐ │                  │  └─ Embeddings  │
              │ │Agent    │ │                  └──────────────────┘
              │ │Framework│ │
              │ └─────────┘ │
              │ ┌─────────┐ │
              │ │OpenAI   │ │
              │ │Functions │ │
              │ └─────────┘ │
              └──────┬──────┘
                     │
              ┌──────▼──────────────────────┐
              │  Shared Tools Layer           │
              │  Question & Answer            │
              │  Text Processing              │
              │  Content Safety               │
              │  Post-Prompt Formatting       │
              └──────┬──────────────────────┘
                     │
              ┌──────▼──────────────────────┐
              │  Search Handlers              │
              │  Azure AI Search              │
              │  PostgreSQL (pgvector)         │
              │  Integrated Vectorization      │
              └──────────────────────────────┘
```

### 3.2 RAG Indexing Pipeline (Split Azure Functions)

```
 ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
 │ Blob Storage  │────▶│ Event Grid   │────▶│ Queue Storage    │
 │ (Documents)   │     │ (Trigger)    │     │ (Processing Msgs)│
 └──────────────┘     └──────────────┘     └────────┬─────────┘
                                                     │
                      ┌──────────────────────────────▼──────────┐
                      │      Azure Functions (Split / Modular)   │
                      │                                          │
                      │  ┌──────────────────┐                    │
                      │  │ batch_start      │ List blobs,        │
                      │  │                  │ queue messages      │
                      │  └────────┬─────────┘                    │
                      │           │                              │
                      │  ┌────────▼─────────┐                    │
                      │  │ batch_push       │ Parse, chunk,      │
                      │  │                  │ embed, push to     │
                      │  │                  │ search index        │
                      │  └────────┬─────────┘                    │
                      │           │                              │
                      │  ┌────────▼─────────┐                    │
                      │  │ add_url          │ Fetch URL content, │
                      │  │                  │ parse, embed        │
                      │  └──────────────────┘                    │
                      │                                          │
                      │  ┌──────────────────┐                    │
                      │  │ search_skill     │ Custom AI Search   │
                      │  │                  │ skill endpoint     │
                      │  └──────────────────┘                    │
                      └──────────────────────────────────────────┘
                                     │
                      ┌──────────────▼──────────────────┐
                      │  LangChain (PostgreSQL indexing)  │
                      │  pgvector embeddings              │
                      │  Azure AI Search indexing          │
                      └───────────────────────────────────┘
```

### 3.3 Orchestrator Migration (v1 → v2)

```
v1 Orchestrators                   v2 Orchestrators
─────────────────────              ─────────────────────────
OpenAI Functions      ──────────▶  OpenAI Functions (kept, via Foundry)
Semantic Kernel       ─────╳────▶  REMOVED
LangChain Agent       ──────────▶  LangGraph Agent (upgraded)
Prompt Flow           ─────╳────▶  REMOVED
                                   Agent Framework (NEW)

Model Access:
v1: Direct Azure OpenAI SDK  ──▶  v2: Foundry IQ
                                       (Knowledge Base, Embeddings)
                                       ├── GPT-*
                                       ├── o-series (reasoning)
                                       └── Embeddings
```

### 3.4 Project Structure (v2)

> **On-disk layout** (already adopted; replaces the earlier "everything-under-`shared/`" sketch). Cross-cutting **primitives** live in `shared/`. Every **swappable concern** lives under `shared/providers/<domain>/` and is wired through the registry pattern in §3.5. **Composed flows** that wire providers together live in `shared/pipelines/`.

```
v2/
├── src/
│   ├── shared/                       # primitives + plug-ins + composed flows
│   │   ├── registry.py               # generic Registry[T]                     [done]
│   │   ├── settings.py               # Pydantic AppSettings (Bicep outputs)    [Phase 2]
│   │   ├── types.py                  # OrchestratorEvent, Citation, SearchResult
│   │   ├── observability.py          # OTel + App Insights wiring
│   │   ├── tools/                    # cross-cutting helpers (content_safety, post_prompt)
│   │   │
│   │   ├── providers/                # registry-keyed plug-ins (§3.5)
│   │   │   ├── credentials/          # managed_identity · cli
│   │   │   ├── llm/                  # foundry_iq
│   │   │   ├── embedders/            # foundry_kb · pgvector
│   │   │   ├── parsers/              # pdf · docx · html · md · txt
│   │   │   ├── search/               # azure_search · pgvector · integrated_vectorization
│   │   │   ├── databases/            # cosmosdb · postgres (chat-history CRUD on the client)
│   │   │   └── orchestrators/        # langgraph · agent_framework
│   │   │
│   │   └── pipelines/                # composed flows — NOT pluggable
│   │       ├── ingestion.py          # parse → chunk → embed → index
│   │       └── chat.py               # user msg → orchestrator → SSE
│   │
│   ├── backend/                      # FastAPI app    (azd service)
│   │   ├── app.py                    # App factory, lifespan, CORS, OpenTelemetry
│   │   ├── dependencies.py           # DI (settings, providers, credentials)
│   │   ├── routers/                  # conversation · admin · chat_history · files · speech · auth · health
│   │   └── models/                   # Pydantic request/response models
│   │
│   ├── functions/                    # Azure Functions app    (azd service)
│   │   ├── function_app.py           # blueprint registration
│   │   └── blueprints/               # batch_start · batch_push · add_url · search_skill
│   │
│   ├── frontend/                     # React + Vite (Chat + Admin merged)    (azd service)
│   │   └── src/
│   │       ├── pages/                # chat/  admin/
│   │       ├── stores/               # Zustand state
│   │       └── api/                  # generated OpenAPI client
│   │
│   └── config_assets/                # data, not code
│       ├── default.json              # default orchestrator/tools/chunking config
│       └── schemas/                  # JSON schemas validating default.json + active.json
│
├── infra/                            # Bicep + AVM modules                  [done]
│   ├── main.bicep                    # entry point with databaseType param
│   ├── main.parameters.json
│   ├── main.waf.parameters.json
│   └── modules/                      # ai-project, ai-project-search-connection, virtualNetwork (custom; rest are AVM)
│
├── docker/                           # Dockerfiles + docker-compose dev stack
├── scripts/                          # post_provision.{sh,ps1,py}
├── azure.yaml                        # azd manifest
├── pyproject.toml                    # uv project root for v2                [done]
└── tests/                            # mirrors src/
    ├── conftest.py                                                          [done]
    ├── shared/                       # test_registry.py [done] + test_settings.py [Phase 2]
    │   ├── providers/                # one folder per registered domain
    │   └── pipelines/
    ├── backend/routers/
    └── functions/blueprints/
```

**Why this layout** (rather than the older monolithic `shared/{orchestrator,llm,embedders,...}/` tree):

1. **Only deployable units sit at the top of `src/`** — `backend/`, `functions/`, `frontend/` map 1:1 to azd services + Docker build contexts. Everything not packaged as its own runtime lives under `shared/`.
2. **`shared/providers/` makes "what's pluggable" explicit** — every subfolder is a registry-keyed domain with the same recipe (§3.5). Adding a new provider = drop a file + 1 import in `__init__.py`. No grep to find the plug-in surface.
3. **`shared/pipelines/` separates orchestration from plug-points** — ingestion and chat are *composed code* that wires providers together, not providers themselves. They have one implementation each and don't belong in a registry.
4. **One `shared/` package = one wheel + one dev-mount** — `pyproject.toml`'s `packages = ["src/shared", ...]` and the dev compose mount of `src/shared` automatically cover providers + pipelines. No risk of forgetting to ship them (the bug Q10 closed).
5. **`config_assets/`** — default config JSON + JSON schemas are *data*, not code. Keeping them out of `shared/` keeps the code tree clean.

### 3.5 Pluggability contract (registry-first) — stated once, referenced from every phase

Every swappable concern in v2 (credentials, llm, embedders, parsers, search, databases, orchestrators) follows the **same** registry recipe — driven by the generic `Registry[T]` primitive in [`v2/src/shared/registry.py`](../src/shared/registry.py).

#### 3.5.1 The recipe (3 files per domain)

```python
# v2/src/shared/providers/<domain>/base.py
from abc import ABC, abstractmethod

class Base<Domain>(ABC):
    @abstractmethod
    async def do_thing(self, ...): ...
```

```python
# v2/src/shared/providers/<domain>/__init__.py
from shared.registry import Registry
from .base import Base<Domain>

registry: Registry[type[Base<Domain>]] = Registry("<domain>")

from . import provider_a, provider_b   # eager import — triggers @register

def create(key: str, **kwargs) -> Base<Domain>:
    return registry.get(key)(**kwargs)
```

```python
# v2/src/shared/providers/<domain>/provider_a.py
from . import registry
from .base import Base<Domain>

@registry.register("a")
class ProviderA(Base<Domain>):
    def __init__(self, settings, ...): ...
    async def do_thing(self, ...): ...
```

**Caller code is one line** anywhere in the codebase:

```python
from providers import embedders
embedder = embedders.create(settings.database.index_store, settings=settings, llm=llm)
```

#### 3.5.2 Two anti-patterns are banned

1. **`if/elif` over provider names anywhere outside a `Registry[T]`.** Forbidden by Hard Rule #4 in [`copilot-instructions.md`](../../.github/copilot-instructions.md). Greppable: `grep -rn "if .*== .['\"]cosmosdb['\"]"` must return 0 hits in `v2/src/`.
2. **Lazy in-function imports of provider classes.** Imports happen once per domain in `__init__.py`. A function body never `import`s a provider.

#### 3.5.3 How to add new tech in 3 steps (uniform across domains)

| Want to add… | Step 1 | Step 2 | Step 3 |
|---|---|---|---|
| **A new orchestrator** (e.g., CrewAI) | Create `v2/src/shared/providers/orchestrators/crewai.py` with `class CrewAIOrchestrator(OrchestratorBase)` | Decorate the class: `@registry.register("crewai")` | Add `from . import crewai` to `shared/providers/orchestrators/__init__.py` |
| **A new chat-history backend** (e.g., Redis) | Create `v2/src/shared/providers/databases/redis.py` with `class RedisDatabaseClient(BaseDatabaseClient)` (chat-history CRUD on the client) | `@registry.register("redis")` | Add `from . import redis` to `shared/providers/databases/__init__.py` |
| **A new embedder** (e.g., local sentence-transformers) | Create `v2/src/shared/providers/embedders/sentence_transformers.py` | `@registry.register("sentence_transformers")` | Add `from . import sentence_transformers` to `shared/providers/embedders/__init__.py` |

No central factory file to edit. No `if/elif` chain to extend. The new provider is selectable by setting the corresponding env var (e.g., `AZURE_DB_TYPE=redis`).

#### 3.5.4 What the registry buys CWYD at multi-container scale

- **Per-container imports.** Backend imports `shared/providers/orchestrators/`, `shared/providers/databases/`, `shared/providers/search/`. Functions imports `shared/providers/embedders/`, `shared/providers/parsers/`, `shared/providers/search/`. Heavy SDKs (`azure-ai-projects`, `langgraph`, `psycopg`) load only where used — smaller cold starts, smaller images, lower memory per replica.
- **Independent deployment.** Each azd service ships only the providers it needs; adding a provider in one service has zero impact on the other.
- **Scenario Pack / Customization Layer plug-ins** can ship out-of-tree: a customer fork drops `shared/providers/embedders/customer_aoai.py` with `@register("customer_aoai")` — no upstream patch required.
- **Configuration-driven swaps.** The provider key *is* the config value (`settings.database.db_type` → `databases.create(...)`). No drift between config strings and dispatch labels.

See §3.6 below for the parallel rule applied to **infrastructure** modules.

### 3.6 Infrastructure extensibility (parallel of §3.5 for Bicep)

The Bicep infra (`v2/infra/`) follows three rules so adding a new backend (DB, search, AI service) costs the same as adding a new code provider:

#### 3.6.1 Three rules

1. **Each pluggable backend is its own Bicep module** under `infra/modules/` (or AVM module under `br/public:avm/...`). Each module exposes a **uniform output contract**: `endpoint` URI, `resourceId`, and `principalIdsToGrantRbac` (list of UAMI principal IDs the module wires into its data-plane RBAC). This mirrors how `BaseLLMProvider` looks the same across `foundry_iq` / future providers.
2. **Single dispatch point.** `main.bicep` selects backends via the `databaseType` param (today: `cosmosdb` | `postgresql`). Adding a third mode (e.g., `mongodb`) means: add the allowed value, instantiate one conditional module, expose its outputs to the same env-var names. **No other file changes** — backend code reads the same `AZURE_*` env vars regardless of mode.
3. **WAF flags never branch topology, only sizing.** The four flags (`enableMonitoring`, `enableScalability`, `enableRedundancy`, `enablePrivateNetworking`) only adjust SKU / replica count / VNet integration on existing resources. Adding a new resource means deciding *how it responds to each flag*, not duplicating the resource per flag.

#### 3.6.2 Phase 1 follow-up — P1 polish tweaks (✅ shipped 2026-04-27)

From the infra audit (8.5/10, AVM coverage ≈95%); landed alongside the next Phase 2 unit so `AzurePostgresSettings` reads a single URI from day one:

| # | Tweak | File | Status |
|---|---|---|---|
| P1.1 | Added `AZURE_POSTGRES_ENDPOINT` Bicep output (full `postgresql://<fqdn>:5432/cwyd?sslmode=require` URI form, no credentials — the workload supplies an Entra token; the user comes from `AZURE_UAMI_CLIENT_ID`). Mirrors `AZURE_COSMOS_ENDPOINT` shape. | `infra/main.bicep` | ✅ |
| P1.2 | Validate `postgresAdminPrincipalName` non-empty when `databaseType == 'postgresql'` via a fail-fast `_validatePostgresAdminPrincipalName` guard variable that aborts ARM expansion before any resource is provisioned. | `infra/main.bicep` | ✅ |
| P1.3 | Refreshed `enablePrivateNetworking` description — work is complete (VNet + private DNS + private endpoints + regional VNet integration + Bastion all wired); flag is the supported WAF-aligned topology. | `infra/main.bicep` | ✅ |

---

## 4. Implementation Phases

> **Principle**: Every phase ends with a working `azd up`. Each phase delivers a vertical slice: infra + data + backend + frontend — even if minimal. This ensures continuous deployability and early validation.

### Phase 1 — Infrastructure + Project Skeleton

**Goal**: `azd up` deploys all Azure resources and stub applications. A browser can hit the frontend and see a placeholder page; the backend responds to `/api/health`.

| # | Task | Key Files | Status |
|---|---|---|---|
| 1 | Clean Bicep infra with `databaseType` parameter (Cosmos DB or PostgreSQL); follows §3.6 uniform output contract | `infra/main.bicep`, `infra/modules/` | ✅ |
| 2 | User-assigned managed identity + RBAC roles (no Key Vault secrets) | `infra/main.bicep` (UAMI inline + role assignments per AVM) | ✅ |
| 3 | Foundry IQ resource (AI Services account, Foundry Project, model deployments) | `infra/modules/ai-project.bicep`, `infra/modules/ai-project-search-connection.bicep` | ✅ |
| 4 | `azure.yaml` with v2 service paths (backend, frontend, functions) | `azure.yaml` | ✅ — infra+params+hooks shipped Phase 1; `services:` block deferred and wired in Phase 3.5 audit (debt #Q4, 2026-04-28) |
| 5 | Stub FastAPI backend — `GET /api/health` returns 200 | `src/backend/app.py`, `src/backend/routers/health.py` | ✅ (subsumed by task #13) |
| 6 | Stub React frontend — placeholder page with "CWYD v2" | `src/frontend/src/` | ✅ (3/3 vitest) — Vite+React 19+TS scaffold, no UI library, no router, pings `/api/health` via `VITE_BACKEND_URL`. *Back-filled 2026-04-28 during Phase 3 deep-clean.* |
| 7 | Dockerfiles for backend + frontend | `docker/` | ⏳ partial |
| 8 | Post-deploy script — loads sample data + default config to Blob Storage | `scripts/post_provision.{sh,ps1,py}` | ⏳ partial |
| 9 | Sample documents for bootstrap | `data/` (root) | ✅ |
| P1.1–3 | P1 polish tweaks (§3.6.2) | `infra/main.bicep` | ✅ |

**`azd up` result**: All infra provisioned, stub apps running in Azure, sample data loaded, health check passes.

### Phase 2 — Configuration + LLM Integration

**Goal**: Backend has a real configuration system, connects to Foundry IQ, and health check validates all dependencies. Frontend shows a basic chat shell (no backend integration yet).

All provider work in this phase follows the registry recipe in §3.5.

| # | Task | Key Files | Status |
|---|---|---|---|
| 2.0 | Generic `Registry[T]` primitive (Phase 2 prerequisite) | `src/shared/registry.py` + `tests/shared/test_registry.py` | ✅ (11/11) |
| 10 | Pydantic `AppSettings` replacing `EnvHelper` (nested models per Azure service; reads every Bicep output env var; cached `get_settings()`) | `src/shared/settings.py` + `tests/shared/test_settings.py` | ✅ (13/13) |
| 11 | Credentials providers (registry domain): `BaseCredentialFactory` ABC + `managed_identity` + `cli` | `src/shared/providers/credentials/{base,managed_identity,cli,__init__}.py` | ✅ (9/9) |
| 12 | LLM provider (registry domain): `BaseLLMProvider` ABC + `foundry_iq` (AIProjectClient-backed; methods `chat`, `chat_stream`, `embed`, `reason`) | `src/shared/providers/llm/{base,foundry_iq,__init__}.py` | ✅ (11/11) — `reason()` stubbed, see task #25 |
| 13 | Health router with dependency checks (DB, search, Foundry IQ connectivity) — reads providers via DI | `src/backend/routers/health.py` | ✅ (8/8) — shallow probes; deep liveness deferred to Phase 6 |
| 14 | Dependency injection wiring (settings + credentials + llm registries → routers) | `src/backend/dependencies.py` | ✅ (covered by health router tests) |
| 15 | Frontend: basic chat UI shell (input box, message list, layout) | `src/frontend/src/pages/chat/` | ✅ ChatContext + MessageList + MessageInput + ChatPage shipped, mounted from App.tsx (20/20 vitest). *Back-filled 2026-04-28 during Phase 3 deep-clean.* |
| 16 | Bicep outputs wired to backend env vars (no Key Vault) | `infra/main.bicep` outputs section | ✅ |

**`azd up` result**: Configured backend with detailed health check, frontend shell visible, all Azure service connections validated.

### Phase 3 — Conversation + RAG (Core Chat)

**Goal**: A user can type a message and get a streamed answer grounded in indexed documents. This is the first "it works!" moment.

Orchestrators and search providers follow the registry recipe in §3.5. Caller code is `orchestrators.create(settings.orchestrator, ...)` and `search.create(settings.database.index_store, ...)` — no `if/elif` dispatch.

| # | Task | Key Files | Status |
|---|---|---|---|
| 17 | Orchestrator domain registry + `OrchestratorBase` ABC (async `run()` yielding `OrchestratorEvent`) | `src/shared/providers/orchestrators/{base,__init__}.py` | ✅ (6/6) |
| 18 | LangGraph orchestrator (`StateGraph` + `ToolNode`); `@register("langgraph")` | `src/shared/providers/orchestrators/langgraph.py` | ✅ (7/7) — single LLM node today; `ToolNode` wires in via task #20 |
| 19 | Azure AI Agent Framework orchestrator; `@register("agent_framework")` | `src/shared/providers/orchestrators/agent_framework.py` | ✅ (8/8) — DI-injected `AgentsClient` + `agent_id`; production wiring in task #22 |
| 20 | Cross-cutting tool helpers (QA, text processing, content safety, post-prompt). Tools are NOT a registry domain — they are imported directly. | `src/shared/tools/*` | ✅ content_safety (10/10) + text_processing (9/9) + post_prompt (14/14) + qa (13/13). All four DI'd, async, no SDK leakage. |
| 21 | Search domain: `BaseSearch` ABC + `azure_search` provider (async); `@register("azure_search")` | `src/shared/providers/search/{base,azure_search,__init__}.py` | ✅ (13/13) — hybrid (text+vector), semantic re-ranking, OData filter pass-through. Citation/SearchResult types added to `shared/types.py`. |
| 22 | Conversation router (streaming SSE + non-streaming, BYOD + custom); composes `orchestrators.create(...)` | `src/backend/routers/conversation.py`, `src/shared/pipelines/chat.py` | ✅ (12/12) — router 6/6, pipeline 6/6, registry dispatch + pipeline delegation enforced |
| 23 | Citation extraction and formatting | `src/shared/types.py` (Citation), tool helpers | ✅ (10/10) — `shared/tools/citations.py`; wired into LangGraph orchestrator |
| 24 | Frontend: chat connected to `/api/conversation`, SSE stream consumption (channels: `reasoning`, `tool`, `answer`, `citation`, `error`) | `src/frontend/src/pages/chat/` | ⏸ FE team |
| 25 | Reasoning model support via Foundry IQ (o-series routing in `foundry_iq.reason()`) | `src/shared/providers/llm/foundry_iq.py` | ✅ (14/14) |
| 26 | Scripts: create search index + index sample documents | `scripts/post_provision.py` | ✅ (10/10) — idempotent `_ensure_search_index` (skipped/dry-run/exists/created), `--dry-run` CLI flag, fail-fast on bad embedding dimensions |

**Phase 3 sub-plan (execution order — Hard Rule #12)**

Tasks below execute in this order; `audit` is the final turn(s) and clears all open §0.1 Debt Queue items targeted at this phase.

| Order | Task # | Description | Unit count | Status |
|---|---|---|---|---|
| 1 | 22a | Conversation router (`POST /api/conversation`, JSON + SSE) | 1 | ✅ |
| 2 | 22b | Chat pipeline (`shared/pipelines/chat.py` — pure async generator) | 1 | ✅ |
| 3 | 23 | Citation extraction + formatting | 1 | ✅ |
| 4 | 25 | Reasoning model routing in `foundry_iq.reason()` | 1 | ✅ |
| 5 | 26 | Indexing scripts (extend `post_provision.py`, idempotent, `--dry-run`) | 1 | ✅ |
| 6 | audit | Greppable gates · clear debt #7 + #8 · ship #24 FE SSE wiring · re-verify DV1 if Docker up · update §0/§4/§0.1 · run full test suite | 3-4 | ✅ BE side (6a-6d, 6f) — 6e (#24 FE SSE) and DV1 owned by FE team |

**`azd up` result**: Working chat experience — user asks a question, gets a streamed answer with citations from sample documents.

### Phase 4 — Chat History + Both Databases

**Goal**: Conversations persist across sessions. Both Cosmos DB and PostgreSQL work as chat history backends. pgvector search enabled for PostgreSQL deployments.

Chat history and search-pgvector are registry domains (§3.5). Picking the backend is one line: `databases.create(settings.database.db_type, ...)`.

| # | Task | Key Files | Status |
|---|---|---|---|
| 27 | `databases` domain: `BaseDatabaseClient` ABC + `cosmosdb` client (async; connection lifecycle + chat-history CRUD on the client; later: vector store metadata, config storage); `@register("cosmosdb")` | `src/shared/providers/databases/{base,cosmosdb,__init__}.py` | ☐ |
| 28 | `postgres` database client (async asyncpg pool + chat-history CRUD; pool injectable into pgvector search); `@register("postgres")` | `src/shared/providers/databases/postgres.py` | ☐ |
| 29 | Caller wiring — backend reads `databases.create(settings.database.db_type, ...)` via DI; chat-history routes consume the database client directly (the registry IS the factory; no separate chat_history domain) | `src/backend/dependencies.py` | ☐ |
| 30 | `pgvector` search provider (async; DI-injects the `PostgresPool` from `databases.create('postgres', ...)` — single pool per process); `@register("pgvector")` | `src/shared/providers/search/pgvector.py` | ☐ |
| 31 | Chat history router (CRUD, feedback, status) | `src/backend/routers/chat_history.py` | ☐ |
| 32 | Frontend: conversation history panel (list, select, rename, delete) | `src/frontend/src/pages/chat/` | ☐ |
| 32a | **Phase 4 hardening (B1, BLOCKER)**: pgvector dead code in lifespan -- the `if index_store == "AzureSearch"` gate hardcoded `search.create("azure_search", ...)`, leaving `app.state.search_provider = None` whenever `index_store=pgvector`. Fixed: lifespan now dispatches `search.create(settings.database.index_store, ...)` directly (no name-string translation), bootstraps the database client first, and DI-injects the postgres pool via `database_client.ensure_pool()` only when `search_key == "pgvector"`. Reordered shutdown so search closes before the database client (pgvector borrows that pool). Aligned the search registry key from `azure_search` -> `AzureSearch` so it equals the `settings.database.index_store` Literal value (Hard Rule #4). Shutdown order is now: search -> database -> llm -> credential. | `v2/src/backend/app.py`, `v2/src/shared/providers/search/{azure_search,__init__}.py`, `v2/tests/backend/test_app_lifespan.py`, `v2/tests/shared/providers/search/test_azure_search.py` | ✅ (261/261, +2 lifespan tests `test_lifespan_wires_pgvector_with_postgres_pool`, `test_lifespan_pgvector_does_not_require_search_endpoint`) |
| 32b | **Phase 4 hardening (H1, HIGH)**: `get_user_id` silent auth bypass -- when the Easy Auth `x-ms-client-principal-id` header was missing, **every** request fell through to a single `"local-dev"` partition, including in production. A misconfigured Easy Auth would silently fold every anonymous caller into one tenant. Fixed: added `AppSettings.environment: Literal["local","production"] = "local"` (env var `AZURE_ENVIRONMENT`); `get_user_id` now takes `SettingsDep` and only returns `"local-dev"` when `environment == "local"`. In production a missing header raises `401 Unauthorized` -- fail closed. | `v2/src/shared/settings.py`, `v2/src/backend/routers/history.py`, `v2/tests/backend/test_history.py` | ✅ (262/262, +1 test `test_get_user_id_raises_401_in_production_when_header_missing`) |
| 32c | **Phase 4 hardening (H3, HIGH)**: `_ensure_pool` TOCTOU race -- two coroutines hitting `_ensure_pool` simultaneously both passed the `self._pool is None` check and both called `asyncpg.create_pool`, leaking a pool. The schema bootstrap had a lock; the pool creation didn't. Fixed: renamed `_schema_lock` -> `_init_lock` and wrapped both pool creation AND schema bootstrap inside one `async with self._init_lock` (with the `is None` re-check inside the lock). Fast path (`pool is not None and schema_ready`) stays lock-free. `_ensure_schema` is retained as a thin wrapper that delegates to `_ensure_pool` so the same lock is used. | `v2/src/shared/providers/databases/postgres.py`, `v2/tests/shared/providers/databases/test_postgres.py` | ✅ (263/263, +1 test `test_concurrent_ensure_pool_creates_pool_only_once`) |
| 33 | (Phase 4 is for backends; Agent Framework was added in Phase 3 §19.) | — | — |
| 34 | Bicep: ensure both DB conditional modules output the same env-var names per §3.6 contract | `infra/main.bicep` | ✅ |

**`azd up` result**: Chat with persistent history — user returns later and sees previous conversations. Works with either database type.

### Phase 5 — Admin + Frontend Merge

**Goal**: Unified frontend with admin capabilities. Document management, system status, configuration view — all inside the React app.

| # | Task | Key Files | Status |
|---|---|---|---|
| 35 | Admin API router (settings, config, SAS tokens, orchestrator switching via `settings.orchestrator`) | `src/backend/routers/admin.py` | ☐ |
| 36 | Admin pages in React frontend (data ingestion, config, exploration) | `src/frontend/src/pages/admin/` | ☐ |
| 37 | Files router (blob serving) | `src/backend/routers/files.py` | ☐ |
| 38 | Speech router (Azure Speech token) | `src/backend/routers/speech.py` | ☐ |
| 39 | Auth router + middleware (RBAC, role-based admin access) | `src/backend/routers/auth.py` | ☐ |
| 40 | Confirm no Streamlit references remain (v1 admin permanently removed per §2.1) | project-wide | ☐ |

**`azd up` result**: Full frontend with chat + admin pages. Users can upload documents, view system config, check index status — all in one app.

### Phase 6 — RAG Indexing Pipeline (Split Functions)

**Goal**: Modular Azure Functions process uploaded documents end-to-end: blob → parse → chunk → embed → index. Completes the full ingestion loop.

Parsers and embedders are registry domains (§3.5). The blueprint invokes `pipelines.ingestion.run(...)`; the pipeline uses `parsers.create(file_type, ...)` and `embedders.create(settings.database.index_store, ...)`. No parse/chunk/embed code lives in the blueprint.

| # | Task | Key Files | Status |
|---|---|---|---|
| 41 | Function app shell + `batch_start` blueprint (list blobs, queue per-doc messages) | `src/functions/function_app.py`, `src/functions/blueprints/batch_start.py` | ☐ |
| 42 | `batch_push` blueprint (queue trigger → `pipelines.ingestion.run`) | `src/functions/blueprints/batch_push.py` | ☐ |
| 43 | `add_url` blueprint (queue trigger; URL fetch → ingestion pipeline) | `src/functions/blueprints/add_url.py` | ☐ |
| 44 | `search_skill` blueprint (HTTP trigger; custom AI Search skill endpoint) | `src/functions/blueprints/search_skill.py` | ☐ |
| 45 | Parsers domain: `BaseParser` ABC + 5 providers (`pdf`, `docx`, `html`, `md`, `txt`); each `@register("<ext>")` | `src/shared/providers/parsers/{base,pdf,docx,html,md,txt,__init__}.py` | ☐ |
| 46 | Embedders domain: `BaseEmbedder` ABC + 2 providers (`foundry_kb` Knowledge-Base upsert, `pgvector` chunk+embed+insert); each `@register("<key>")` | `src/shared/providers/embedders/{base,foundry_kb,pgvector,__init__}.py` | ☐ |
| 47 | Ingestion pipeline (composes parsers + embedders; NOT a registry) | `src/shared/pipelines/ingestion.py` | ☐ |
| 48 | Default config + post-provision (`config_assets/default.json`, `ConfigHelper.ensure_default_uploaded`, `scripts/post_provision.py` hook) | `src/config_assets/default.json`, `src/shared/config_helper.py`, `scripts/post_provision.py` | ☐ |

**`azd up` result**: End-to-end pipeline — upload a document via admin UI → functions process it → document appears in search → user can chat about it.

### Phase 7 — Testing + Documentation

**Goal**: Comprehensive test coverage, migration guide, and updated documentation.

| # | Task | Key Files | Status |
|---|---|---|---|
| 49 | Pytest suite for FastAPI (`httpx.AsyncClient` + `ASGITransport`); cover both orchestrators end-to-end via fakes | `tests/backend/`, `tests/providers/orchestrators/` | ☐ |
| 50 | Update frontend Jest/Vitest tests for admin features | `src/frontend/` | ☐ |
| 51 | Update root `README.md` with v2 architecture + setup; add `v2/README.md` quickstart | `README.md`, `v2/README.md` | ☐ |
| 52 | Write v2 migration guide | `v2/docs/migration.md` | ☐ |
| 53 | Update docs for new configuration, deployment, and orchestrator options | `v2/docs/`, `docs/` | ☐ |
| 54 | Confirm no references remain to Prompt Flow, Semantic Kernel, Streamlit, Poetry, direct Azure OpenAI SDK, one-click deploy (greppable gates) | project-wide | ☐ |

**`azd up` result**: Production-ready deployment — fully tested, documented, and clean.

---

## 5. Phase Dependency Graph

```
Phase 1 (Infra + Skeleton)          ← azd up: stub apps + all Azure resources
  │
  ▼
Phase 2 (Config + LLM)              ← azd up: configured backend, chat UI shell
  │
  ▼
Phase 3 (Conversation + RAG)        ← azd up: working chat with streaming + citations
  │
  ├──────────┐
  │          │
  ▼          ▼
Phase 4    Phase 5
(History    (Admin +
 + DBs)     Frontend)
  │          │
  └────┬─────┘
       ▼
Phase 6 (RAG Indexing Pipeline)      ← azd up: full ingestion + chat pipeline
       │
       ▼
Phase 7 (Testing + Docs)            ← azd up: production-ready
```

---

## 6. Configuration & Customization

### 6.1 Configuration Architecture

v2 uses a layered configuration system with **no Key Vault secrets**:

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: Bicep Parameters                           │
│  (deploy-time choices: databaseType, region, SKU)    │
├─────────────────────────────────────────────────────┤
│  Layer 2: Bicep Outputs → Environment Variables      │
│  (service endpoints, resource names, connection info) │
├─────────────────────────────────────────────────────┤
│  Layer 3: Pydantic Settings (runtime config)         │
│  (typed, validated, composable, loaded from env)     │
├─────────────────────────────────────────────────────┤
│  Layer 4: active.json (assistant/prompt config)      │
│  (system prompts, orchestrator choice, UI behavior)  │
└─────────────────────────────────────────────────────┘
```

### 6.2 Deploy-Time Configuration (Bicep Parameters)

These are set once at `azd up` time and determine what Azure resources are provisioned:

| Parameter | Options | Default | Description |
|-----------|---------|---------|-------------|
| `databaseType` | `cosmosdb`, `postgresql` | `cosmosdb` | Which database engine to deploy |
| `location` | Azure regions | — | Primary deployment region |
| `azureAiServiceLocation` | AI-supported regions | — | Region for AI model deployments |
| `enableMonitoring` | `true`, `false` | `false` | Deploy Log Analytics + App Insights |
| `enableScalability` | `true`, `false` | `false` | Higher SKUs, autoscaling rules |
| `enableRedundancy` | `true`, `false` | `false` | Multi-region, zone-redundant |
| `enablePrivateNetworking` | `true`, `false` | `false` | VNet, private endpoints, bastion |
| `gptModelName` | Model names | `gpt-4.1` | Primary chat model |
| `embeddingModelName` | Model names | `text-embedding-3-small` | Embedding model |

### 6.3 Runtime Configuration (Environment Variables → Pydantic Settings)

These are set via Bicep outputs (deployed) or `.env` file (local dev):

```python
# Grouped by service — each group is a nested Pydantic model
class AzureOpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_OPENAI_")
    endpoint: str                    # From Bicep output
    model: str = "gpt-4.1"
    embedding_model: str = "text-embedding-3-small"
    temperature: float = 0.0
    max_tokens: int = 1000
    api_version: str = "2024-12-01-preview"

class AzureSearchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_SEARCH_")
    service: str                     # From Bicep output
    index: str = "cwyd-index"
    use_semantic_search: bool = True
    semantic_search_config: str = "my-semantic-config"
    top_k: int = 5

class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_DB_")
    type: Literal["cosmosdb", "postgresql"] = "cosmosdb"
    endpoint: str                    # From Bicep output
    name: str = "cwyd"

class AppSettings(BaseSettings):
    """Root settings — composes all service settings."""
    model_config = SettingsConfigDict(env_file=".env")
    openai: AzureOpenAISettings = AzureOpenAISettings()
    search: AzureSearchSettings = AzureSearchSettings()
    database: DatabaseSettings = DatabaseSettings()
    orchestrator: Literal["openai_functions", "langgraph", "agent_framework"] = "langgraph"
    auth_type: Literal["rbac"] = "rbac"
    log_level: str = "INFO"
```

### 6.4 Assistant / Prompt Customization (active.json)

The assistant behavior, system prompts, and UI customization are controlled by `active.json`:

```json
{
  "orchestrator": {
    "strategy": "langgraph"
  },
  "prompts": {
    "system_message": "You are a helpful AI assistant...",
    "follow_up_questions_prompt": "Generate 3 follow-up questions...",
    "post_answering_prompt": "Validate the answer against the sources..."
  },
  "document_processors": [
    { "type": "pdf", "use_document_intelligence": true },
    { "type": "docx", "chunking_strategy": "layout" },
    { "type": "txt", "chunk_size": 500 }
  ],
  "ui": {
    "title": "Chat With Your Data",
    "logo_url": "/static/logo.png",
    "show_citations": true,
    "show_follow_up_questions": true
  }
}
```

### 6.5 Customization Points

| What to Customize | How | File(s) |
|---|---|---|
| **System prompt** | Edit `active.json` → `prompts.system_message` | `data/active.json` |
| **Orchestrator strategy** | Set `ORCHESTRATOR` env var or `active.json` | `.env` / `active.json` |
| **Database backend** | Set `databaseType` Bicep param at deploy time | `main.parameters.json` |
| **Chat model** | Set `AZURE_OPENAI_MODEL` env var | `.env` |
| **Embedding model** | Set `AZURE_OPENAI_EMBEDDING_MODEL` env var | `.env` |
| **Search behavior** | Modify `AzureSearchSettings` defaults or env vars | `env_settings.py` / `.env` |
| **Document processing** | Edit `active.json` → `document_processors` | `data/active.json` |
| **UI branding** | Edit `active.json` → `ui` section | `data/active.json` |
| **Add a new tool** | Implement helper in `shared/tools/`, import where needed (tools are not a registry domain) | `src/shared/tools/` |
| **Add a new orchestrator** | Follow §3.5 recipe: subclass `OrchestratorBase`, decorate with `@registry.register("<key>")`, add `from . import <module>` to `__init__.py` | `src/shared/providers/orchestrators/` |
| **Add a new database backend** (chat history + later: vector store metadata, config storage) | §3.5 recipe under `shared/providers/databases/`; client implements `BaseDatabaseClient` with chat-history CRUD methods | `src/shared/providers/databases/` |
| **Add a new search / embedder / parser / credential** | Same §3.5 recipe under the matching `shared/providers/<domain>/` folder | `src/shared/providers/<domain>/` |
| **WAF-aligned deployment** | Enable `enableMonitoring`, `enableScalability`, `enableRedundancy`, `enablePrivateNetworking` | `main.parameters.json` |

### 6.6 Local Development Configuration

For local dev, all configuration comes from a `v2/.env` file (gitignored). The canonical template lives at [`v2/.env.sample`](../.env.sample) — every variable name there matches the `AppSettings` field names in [`v2/src/shared/settings.py`](../src/shared/settings.py) and the corresponding Bicep outputs in [`v2/infra/main.bicep`](../infra/main.bicep). Pydantic-settings ignores unknown variables, so a typo silently does nothing — copy from the template, do not hand-craft.

```bash
# From repo root:
cp v2/.env.sample v2/.env
# then edit v2/.env to fill in real endpoints / deployment names.
```

When the project is already deployed via `azd up`, `azd env get-values` outputs the same canonical names — pipe directly into `v2/.env` to skip manual entry.

> **Path note (CU-008a, 2026-05-05):** the previous `v2/docker/.env.dev.example` was deleted in favor of the v2-root template. Compose loads `v2/.env` via the `env_file: ../.env` directive in [`v2/docker/docker-compose.dev.yml`](../docker/docker-compose.dev.yml).
>
> **Variable inventory:** see [`v2/.env.sample`](../.env.sample) for the authoritative list and inline comments naming the `AppSettings` field each variable maps to. (`v2/docs/env-vars.md` will land in CU-012a with the cross-reference table to v1 `env_helper.py`.)

---

## 7. Key Decisions

| Decision | Rationale |
|----------|-----------|
| **Foundry IQ** (Knowledge Base, Embeddings) for knowledge management; **LangChain / Agent Framework** for orchestration | Clean separation: knowledge management vs. agent logic |
| **Reasoning models** (o-series) enabled through Foundry IQ | Centralized model management; no per-orchestrator model wiring |
| **Infra is Phase 1** — every phase results in deployable `azd up` | Continuous validation, early issue detection, always-working baseline |
| **Azure Bot Service + Teams plugin** deferred to future version | Focus v2 on core modernization; extensibility built in for later |
| **Both Cosmos DB and PostgreSQL** kept as switchable backends | Preserves deployment flexibility for different enterprise needs |
| **Admin UI** merged into React/Vite frontend | Eliminates Streamlit dependency; unified user experience |
| **3 orchestrators** in v2: OpenAI Functions, LangGraph, Agent Framework | Covers direct tool calling, graph-based agents, and managed agent service |
| **`uv`** remains the Python package manager | Fast, modern, already adopted; Poetry fully removed |
| **No Key Vault for app secrets** | RBAC + Managed Identity; env vars from Bicep outputs (MACAE pattern) |
| **v2/src scaffolding** is a starting point — implement from scratch where needed | Don't assume scaffolding is complete or correct |

---

## 8. Deferred to Future Versions

- Azure Bot Service integration
- Microsoft Teams extension / plugin
- Additional Azure region support
- Advanced image processing (Computer Vision vectorization)
- MCP server integration
- Multi-agent coordination

---

## 9. Verification Criteria

1. `uv sync` succeeds with updated dependencies (no Poetry, no Semantic Kernel)
2. `pytest` passes for all three orchestrator strategies
3. FastAPI backend starts locally; `/api/health` returns 200
4. Conversation endpoint works through Foundry IQ (streaming + non-streaming)
5. Chat history CRUD works with both Cosmos DB and PostgreSQL
6. Admin pages render in the React frontend; document upload functional
7. Azure Functions pipeline processes blob uploads → embed → index
8. `azd up` deploys the full stack (no one-click button)
9. Frontend Jest tests pass
10. No references remain to Prompt Flow, Semantic Kernel, Streamlit, Poetry, or direct Azure OpenAI SDK
11. Every phase from 1–7 can be deployed independently via `azd up`
12. **Greppable pluggability gates** (added by §3.5):
    - `grep -rn "if .*== .['\"]\(cosmosdb\|postgres\|langgraph\|agent_framework\|foundry_iq\|pgvector\)['\"]" v2/src/` returns 0 hits outside `tests/` (no `if/elif` provider dispatch).
    - No `import` of a provider class inside a function body in `v2/src/{backend,functions,pipelines}/**` (registries handle provider loading).

---

## 10. Inventory of done work

> Single source of truth for what is already shipped, so no agent re-does work that's complete. Update this section whenever a phase task lands.

### 10.1 Phase 0 — Workspace foundations (✅ done)

| File | Purpose |
|---|---|
| [`v2/pyproject.toml`](../pyproject.toml) | uv project root for v2 (Python ≥3.11; deps include fastapi, azure-functions, azure-ai-projects, azure-ai-agents, langgraph, langchain-openai, azure-identity, azure-storage-blob/queue, azure-cosmos, asyncpg, psycopg2-binary, pgvector, azure-monitor-opentelemetry, pydantic-settings; dev: pytest, pytest-asyncio, pytest-cov). |
| [`v2/.venv/`](../.venv) | v2-scoped venv (Python 3.13.13, 141 packages via `uv sync`). |
| [`v2/.vscode/settings.json`](../.vscode/settings.json) | Pinned interpreter `${workspaceFolder}/v2/.venv/Scripts/python.exe`; pytest enabled with `args=["v2/tests"]`; analysis extraPaths `["v2/src"]`. |
| [`v2/tests/conftest.py`](../tests/conftest.py) | `_reset_env` autouse fixture stripping `AZURE_*` / `CWYD_*` / `LOAD_*` env vars between tests. |

### 10.2 Phase 1 — Infrastructure (✅ done; 3 P1 polish tweaks pending — §3.6.2)

| File | Purpose |
|---|---|
| [`v2/infra/main.bicep`](../infra/main.bicep) | Entry-point template. AVM-first (~95% coverage). UAMI + RBAC end-to-end (no Key Vault). Single `databaseType` param selects chat-history + vector-index in lockstep. 4 WAF flags drive cost/posture without branching topology. |
| [`v2/infra/main.parameters.json`](../infra/main.parameters.json) | Default parameter file (cosmosdb mode). |
| [`v2/infra/main.waf.parameters.json`](../infra/main.waf.parameters.json) | WAF-aligned parameter file (all 4 flags on). |
| [`v2/infra/abbreviations.json`](../infra/abbreviations.json) | Resource type → abbreviation map for naming. |
| [`v2/infra/modules/ai-project.bicep`](../infra/modules/ai-project.bicep) | Foundry Project (child of AI Services account; AVM lacks coverage). |
| [`v2/infra/modules/ai-project-search-connection.bicep`](../infra/modules/ai-project-search-connection.bicep) | Foundry Project ↔ AI Search connection (cosmosdb mode only). |
| [`v2/infra/modules/virtualNetwork.bicep`](../infra/modules/virtualNetwork.bicep) | Opinionated VNet wrapper (private-networking mode only). |
| [`v2/azure.yaml`](../azure.yaml) | azd manifest with v2 service paths. |
| [`v2/docker/`](../docker/) | Dockerfiles + docker-compose dev stack (backend-only / frontend-only profiles). |
| [`v2/scripts/`](../scripts/) | post-provision hooks (`.sh`, `.ps1`, `.py`). |
| [`v2/docs/infrastructure.md`](infrastructure.md) | Operator guide for the v2 substrate (resource topology, SKU table per WAF flag, troubleshooting). |

### 10.3 Phase 2 prerequisite + first unit (✅ done)

| File | Purpose |
|---|---|
| [`v2/src/shared/registry.py`](../src/shared/registry.py) | Generic `Registry[T]` class. Case-insensitive keys, idempotent re-register, `KeyError` listing available providers. Methods: `register("key")` decorator, `get(key)`, `keys()`, `__contains__`, `__len__`. Underpins every provider domain in §3.5. |
| [`v2/tests/shared/test_registry.py`](../tests/shared/test_registry.py) | 11 tests covering registration, lookup, case-insensitivity, double-register rejection, empty domain/key validation, sorted keys. |
| [`v2/src/shared/settings.py`](../src/shared/settings.py) | Pydantic v2 `AppSettings` root composing 9 nested `BaseSettings` (Identity, Foundry, OpenAI, Database, Search, Storage, Observability, Network, Orchestrator). Reads only `AZURE_*` env vars (37 verified) + `CWYD_ORCHESTRATOR_*`. `model_validator` enforces db_type ↔ endpoint consistency. `get_settings()` is `@lru_cache(maxsize=1)`. No secrets. |
| [`v2/tests/shared/test_settings.py`](../tests/shared/test_settings.py) | 13 tests covering env loading (cosmosdb + postgresql), enum validation, model validators (mode consistency, index-store mismatch), `get_settings` caching + `cache_clear`, no-secret-fields gate, observability optional. |
| [`v2/src/shared/providers/__init__.py`](../src/shared/providers/__init__.py) + [`v2/src/shared/providers/credentials/`](../src/shared/providers/credentials/) | First registry-keyed provider domain. `BaseCredentialProvider` ABC + `ManagedIdentityCredentialProvider` (production default; `azure.identity.aio.DefaultAzureCredential` pinned to `AZURE_UAMI_CLIENT_ID`) + `CliCredentialProvider` (local dev; `AzureCliCredential`). `credentials.create(key, settings=...)` + `credentials.select_default(uami_client_id)` heuristic. |
| [`v2/tests/providers/credentials/test_credentials.py`](../tests/providers/credentials/test_credentials.py) | 9 tests covering registry registration (case-insensitive), unknown-key rejection, `select_default` heuristic (uami present → managed_identity, missing → cli), `get_credential()` returns the right SDK type for each provider, settings reference stored on the provider. |
| [`v2/src/shared/types.py`](../src/shared/types.py) | Pydantic value types shared by providers and pipelines. `ChatMessage` (role + content), `ChatChunk` (streamed delta + finish_reason), `EmbeddingResult` (vectors + model + dimensions). |
| [`v2/src/shared/providers/llm/`](../src/shared/providers/llm/) | Second registry-keyed provider domain. `BaseLLMProvider` ABC (`chat`, `chat_stream`, `embed`, `reason`) + `FoundryIQ` wrapping `azure.ai.projects.aio.AIProjectClient.get_openai_client()`. Lazily constructs the project client; resolves deployments from `OpenAISettings`; never imports `openai` (banned tech rule #7). `reason()` is a `NotImplementedError` stub reserved for task #25 (Phase 7). |
| [`v2/tests/providers/llm/test_foundry_iq.py`](../tests/providers/llm/test_foundry_iq.py) | 11 tests covering registry registration, `chat` (deployment resolution + temperature/max_tokens passthrough + missing-deployment guard), `chat_stream` (async iterator + `stream=True` flag), `embed` (vector + dimensions + model passthrough), `reason` (NotImplementedError pointer to task #25), lazy AIProjectClient construction (raises when `AZURE_AI_PROJECT_ENDPOINT` missing), `aclose()` does not close an injected client. |
| [`v2/src/backend/`](../src/backend/) | FastAPI app skeleton. `app.py` (factory + lifespan that lazy-configures Application Insights when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set, **builds credential + LLM provider once and stashes on `app.state`, closes both on shutdown**, plus a CORS wildcard guard that drops `allow_credentials=True` when origins is `*`), `dependencies.py` (DI reads from `app.state` -- no per-request credential construction), `routers/health.py` (`GET /api/health` always 200 diagnostic + `GET /api/health/ready` returning 503 on fail; `skip` is neutral in aggregation), `models/health.py` (`HealthResponse`, `DependencyCheck`). |
| [`v2/tests/backend/test_health.py`](../tests/backend/test_health.py) | 11 tests using `httpx.ASGITransport` + `dependency_overrides` for the diagnostic endpoint, plus a real lifespan exercise (`async with _lifespan(app)`) confirming `app.state` population and `aclose()`/`close()` on shutdown: pass when all checks succeed, fail when Foundry endpoint missing, fail when Search endpoint missing, **`skip` does not degrade overall status (pgvector mode)**, response shape gate, **`/api/health/ready` returns 200 on pass and 503 on fail**, DI raises clearly when lifespan never ran. |

### 10.4 Documentation (✅ live)

| File | Purpose |
|---|---|
| [`v2/docs/development_plan.md`](development_plan.md) | This file. Source of truth for **what** to build and **when**. |
| [`v2/docs/pillars_of_development.md`](pillars_of_development.md) | Read-only product policy (Stable Core / Scenario Pack / Configuration Layer / Customization Layer). Never edited by agents. |
| [`v2/docs/infrastructure.md`](infrastructure.md) | Phase 1 infra design + operator guide. |
| [`v2/docs/adr/`](adr/) | Architecture Decision Records (MADR-lite). 7 ADRs covering Phase 0–2: registry-first dispatch (0001), no Key Vault (0002), Pydantic settings (0003), Foundry IQ + no `openai` import (0004), credential/LLM lifespan singleton (0005), split health endpoints (0006), `OrchestratorEvent` typed SSE channel (0007). Read-only history once Accepted. |
| [`v2/docs/plan/`](plan/) | Modernization plan, MVP, business-case docs (background reading). |

### 10.5 Agent guidance (✅ live; gate per Hard Rule #0)

| File | Purpose |
|---|---|
| [`.github/copilot-instructions.md`](../../.github/copilot-instructions.md) | Repo-wide always-loaded rules. Hard Rule #0 (sync agent guidance first), #4 (registry-first plug-and-play), #7 (banned tech + removed features incl. one-click). |
| [`.github/instructions/v2-workflow.instructions.md`](../../.github/instructions/v2-workflow.instructions.md) | "Step 0" gate; per-turn loop; banned/removed/forbidden split. |
| [`.github/instructions/v2-shared.instructions.md`](../../.github/instructions/v2-shared.instructions.md) | `applyTo: v2/src/shared/**`. Pluggability contract code template. |
| [`.github/instructions/v2-backend.instructions.md`](../../.github/instructions/v2-backend.instructions.md) | FastAPI conventions; routers consume `shared/providers/<domain>/` via DI. |
| [`.github/instructions/v2-functions.instructions.md`](../../.github/instructions/v2-functions.instructions.md) | Blueprints invoke `shared/pipelines/ingestion.py`; no parse/embed code in blueprints. |
| [`.github/instructions/v2-frontend.instructions.md`](../../.github/instructions/v2-frontend.instructions.md) | React/Vite conventions; consumes generated OpenAPI client. |
| [`.github/instructions/v2-infra.instructions.md`](../../.github/instructions/v2-infra.instructions.md) | Bicep + AVM conventions; matches §3.6 extensibility rules. |
| [`.github/instructions/v2-tests.instructions.md`](../../.github/instructions/v2-tests.instructions.md) | `tests/` mirrors `src/`; pytest + pytest-asyncio; `httpx.AsyncClient` for backend. |
