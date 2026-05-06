# CWYD v2 — Development Plan

**Repo**: [Azure-Samples/chat-with-your-data-solution-accelerator](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator)
**Branch**: `dev-v2`
**Last updated**: 2026-05-06 (rewritten lean — see [development_plan.old.md](development_plan.old.md) for the historical Phase 1–5 + Cleanup-audit batch 1/2 ledger)

> This is the **canonical, forward-looking** plan. The historical CU/Q ledger and per-phase closure trails live in [development_plan.old.md](development_plan.old.md) (frozen 2026-05-06). New debt and phase deltas land in §0.1 below.

---

## 0. Status snapshot

Where we are against the 7-phase plan in §4. Status legend: ✅ done · ⏳ in progress · ⏭ next · ☐ not started.

| Phase | Title | Status | Summary |
|---|---|---|---|
| 1 | Infrastructure + Project Skeleton | ✅ done | Bicep (AVM-first, UAMI+RBAC, no Key Vault), frontend stub, backend stub, functions stub, `post_provision.sh`. |
| 2 | Configuration + LLM Integration | ✅ done | `shared/{registry,settings,types}` + `shared/providers/{credentials,llm}/` + `backend/{app,dependencies,routers/health}`. Per-app credential+LLM singletons via lifespan. `/api/health` (always 200) split from `/api/health/ready` (503-on-fail). |
| 3 | Conversation + RAG (Core Chat) | ✅ done | Chat router + LangGraph + Agent Framework orchestrators, content-safety/post-prompt/QA/text-processing tools, AzureSearch + pgvector handlers, citations, reasoning channel, indexing scripts. **#24 (FE SSE wiring) owned by frontend team.** |
| 3.5 | QA Remediation | ✅ done | Cleared 6 deployability blockers (Q1–Q9) + structural realignment Q10 (`shared/{providers,pipelines}/` consolidation). |
| 4 | Chat History + Both Databases | ✅ done | Cosmos + Postgres clients, DI wiring, pgvector with injected pool, chat-history router with fail-closed `get_user_id`, FE history panel, lifespan dispatch + auth + TOCTOU hardening, Bicep outputs + env-binding drift guard. |
| 5 | Admin + Frontend Merge | ⏳ in progress | #35a `GET /api/admin/config` ✅, #35b `RuntimeConfig` model ✅, #35c `PATCH /api/admin/config` ✅ (DB-backed, RFC 7396 merge). #35d (FE admin page merge), #35e (effective-config GET + live reload), #36+ (frontend admin merge) pending. |
| 5.5 | **Stable Core Refactor** (`shared/` → `backend/core/` + `functions/core/`) | ⏭ next | Backend becomes standalone (chat works without functions container); functions becomes opt-in extension layer for indexing. Mono-package via single `pyproject.toml`. Zero duplicated code. Pyright `--strict` extends to `src/functions/core/**`. Followed by exception-handling policy + try/catch sweep. |
| 6 | RAG Indexing Pipeline (Split Functions) | ☐ | `batch_start`, `batch_push`, `add_url`, `search_skill` blueprints land under `v2/src/functions/`; ingestion-only extensions land under `v2/src/functions/core/`. |
| 7 | Testing + Documentation | ☐ | Rolling — each phase ends with `azd up` green and updates this file. |

> **Phase closure discipline** (Hard Rule #12 in [.github/copilot-instructions.md](../../.github/copilot-instructions.md)): debt items discovered while working on Phase N are appended to §0.1 — **never implemented inline**. Within a phase, tasks execute in numeric order from §4; no out-of-order pulls from later phases. The queue is cleared in a single dedicated audit turn at the end of the phase.

---

## 0.1 Active debt queue

Forward-looking debt only. **Closed historical items live in [development_plan.old.md](development_plan.old.md) §0.1** (CU-001 through CU-013, CU-004a/b/c, Q1 through Q14, plus #7/#8/#35c).

Append-only during normal work; cleared in batch during the originating phase's end-of-phase audit.

### Backend debt

| ID | Origin Phase | Item | Files | Cleared in | Status |
|---|---|---|---|---|---|
| #35d | 5 | Frontend merge: pull v1 Streamlit admin features (configuration form, document upload, prompt editor) into the React/Vite frontend as an admin route gated by RBAC. **Out of scope: backend changes.** Owned by frontend team. | `v2/src/frontend/**` | Phase 5 audit | ☐ open |
| #35e | 5 | Live-reload of `app.state.settings` after `PATCH /api/admin/config` so config tweaks take effect without container restart; effective-config `GET /api/admin/config/effective` showing the merged result of env defaults + DB overrides. Deferred from #35c (Hard Rule #12). | `v2/src/backend/{app,routers/admin}.py`, `v2/src/shared/settings.py` | Phase 5 audit | ☐ open |
| #35f | 5 | Audit log for admin config mutations: every successful `PATCH /api/admin/config` writes a row to a new `admin_audit` Cosmos type / Postgres table capturing `who`, `when`, `before`, `after`. Deferred from #35c. | `v2/src/shared/providers/databases/**`, `v2/src/backend/routers/admin.py` | Phase 5 audit | ☐ open |
| #35g | 5 | Per-tenant config overrides (multi-tenant scenario): `RuntimeConfig` keyed by `tenantId` instead of singleton; PATCH route narrows by `request.tenantId`. Deferred from #35c — only relevant once #39 (RBAC) lands tenant claims. | `v2/src/shared/types.py`, `v2/src/shared/providers/databases/**` | Phase 5 audit (or later) | ☐ open |
| #39 | 5 | Admin RBAC narrowing: `/api/admin/*` routes guarded by `requires_role("admin")` dependency; role claim sourced from Easy Auth `X-MS-CLIENT-PRINCIPAL` header. Currently any authenticated user can call admin endpoints. | `v2/src/backend/dependencies.py`, `v2/src/backend/routers/admin.py` | Phase 5 audit | ☐ open |
| REFACTOR-A | 5.5 | **Phase A — Doc swap (this turn).** Renamed old plan to `development_plan.old.md` with deprecation banner; wrote fresh lean canonical `development_plan.md`. | `v2/docs/development_plan.{md,old.md}`, `/memories/repo/cwyd-tech-stack.md` | Phase 5.5 | ⏳ in progress (active turn) |
| REFACTOR-B | 5.5 | **Phase B — `shared/` → `backend/core/` + `functions/core/` skeleton.** 5 sub-units (B1 AST invariant test xfail · B2 `git mv` shared→backend/core + create empty functions/core · B3 import sweep ~155 sites · B4 config + docs sweep · B5 validate + flip xfail strict). See plan in `/memories/session/plan.md`. | `v2/src/shared/**` → `v2/src/backend/core/**`, `v2/src/functions/core/__init__.py`, `v2/pyproject.toml`, `v2/docker/{docker-compose.dev.yml,Dockerfile.functions}`, `.github/instructions/v2-shared.instructions.md` (rename), all `*.py` import sites | Phase 5.5 | ☐ next |
| REFACTOR-C | 5.5 | **Phase C — Try/catch policy + sweep.** New `v2/docs/exception_handling_policy.md` defining per-layer catch/log/re-raise rules; mechanical sweep of providers + pipelines + routers + lifespan with one failure-path test per new `try/except` (Hard Rule #2). New AST invariant `v2/tests/no_silent_excepts.py` (bans `except Exception: pass` + `except BaseException`). Functions sweep (C5) deferred to Phase 6 task slots. | `v2/docs/exception_handling_policy.md`, `v2/src/backend/core/providers/**`, `v2/src/backend/core/pipelines/**`, `v2/src/backend/routers/**`, `v2/src/backend/app.py`, `v2/tests/no_silent_excepts.py` | Phase 5.5 | ☐ pending Phase B |

### 0.2 Frontend debt (separate team)

| ID | Origin Phase | Item | Files | Cleared in | Status |
|---|---|---|---|---|---|
| DV1 | 1 | Re-verify `docker compose -f v2/docker/docker-compose.dev.yml build frontend` (currently blocked: Docker Desktop daemon down on dev machine) | n/a | Frontend team audit | ⏸ blocked — FE team owns |

Legend: ☐ open · ⏳ in progress · ⏭ next · ⏸ blocked · ✅ cleared (date)

---

## 1. Architecture goals

The v2 architecture rests on three invariants:

1. **Pillars** ([pillars_of_development.md](pillars_of_development.md)) — every new core element declares one of: Stable Core, Scenario Pack, Configuration Layer, Customization Layer. Read-only product policy; never edited by agents.
2. **Plug-and-play via registry** — all swappable concerns (credentials, llm, embedders, parsers, search, chat_history, orchestrators) live under `v2/src/backend/core/providers/<domain>/` and self-register via `@registry.register("key")`. Caller code does `domain.create(key, ...)` — never `if/elif` provider dispatch (Hard Rule #4).
3. **Standalone backend, optional functions** (new in Phase 5.5) — backend runs end-to-end (chat + history + admin) without the functions container. Functions is opt-in: it ships only when the operator wants to upload + index their own files. **No code is duplicated**: anything used by both lives in `backend/core/`; functions extends via `functions/core/` (subclass / extension module that imports the base from `backend.core`).

Fourth supporting invariant — **runtime types always available** (Hard Rule #11 sub-rule, ratified 2026-05-05 in CU-013): no `if TYPE_CHECKING:`, no `from __future__ import annotations`. Genuine circular imports get fixed by extracting the shared type to a leaf module (Hard Rule #10 — ask first). Enforced by AST invariant `v2/tests/shared/test_no_type_checking_or_future_annotations.py` (will move to `v2/tests/backend/core/...` in Phase B).

---

## 2. What changes from v1 to v2

### 2.1 Removals

These are **binding** (Hard Rule #7). Never re-introduce.

| Component | Reason |
|-----------|--------|
| **One-click "Deploy to Azure" button** | Simplify to `azd`-only; ARM template maintenance overhead |
| **Poetry references** | Fully standardized on `uv`; remove any lingering Poetry config |
| **Prompt Flow orchestrator** | Replaced by Agent Framework; drops Azure ML dependency |
| **Semantic Kernel orchestrator** | Consolidate to fewer, more strategic orchestrators |
| **Streamlit admin app** | Admin features merged into the React/Vite frontend (Phase 5) |
| **Direct Azure OpenAI SDK** | Replaced by Foundry IQ for knowledge base, embeddings, chat, reasoning |
| **Azure Bot Service / Teams extension** | Deferred to a future version |
| **Key Vault for app secrets** | Replaced by RBAC + UAMI + direct env vars (MACAE pattern) |

### 2.2 Additions

| Component | Purpose |
|-----------|---------|
| **Azure AI Agent Framework** | Modern agent orchestration — replaces Semantic Kernel and Prompt Flow |
| **Foundry IQ** (Knowledge Base, Embeddings, Models) | Centralized knowledge base, embeddings, and model access (GPT-\*, o-series reasoning) — sole inference + retrieval surface |
| **LangGraph orchestrator** | Replaces v1's `ZeroShotAgent` / `AgentExecutor` LangChain pattern |

### 2.3 Updates

| Component | From → To |
|-----------|-----------|
| **Web framework** | Flask → **FastAPI** (async-native, OpenAPI docs, dependency injection, lifespan-managed singletons) |
| **Configuration** | `EnvHelper` singleton → **Pydantic `BaseSettings`** (typed, validated, nested) + DB-backed `RuntimeConfig` for live tweaks |
| **Project structure** | Monolithic `code/` → **modular `v2/src/`** (`backend/`, `backend/core/`, `frontend/`, `functions/`, `functions/core/`) — Phase 5.5 refactor |
| **Admin UI** | Standalone Streamlit app → **merged into React/Vite frontend** (Phase 5) |
| **Bicep infrastructure** | AVM-first; UAMI + RBAC; no Key Vault for app secrets; no one-click ARM |
| **Static type checking** | None → **`pyright --strict`** as a hard CI gate (`include = src/backend, src/functions`; `strict = src/backend/**, src/functions/core/**` post-refactor) |

---

## 3. v2 Target Architecture

### 3.1 High-level

```
                   ┌──────────────────────────────┐
                   │       USERS (Browser)         │
                   └───────────────┬──────────────┘
                                   │
                   ┌───────────────▼──────────────┐
                   │  React/Vite Frontend          │
                   │  Chat + Admin (unified)       │
                   │  Azure App Service            │
                   └───────────────┬──────────────┘
                                   │ REST / SSE
                   ┌───────────────▼──────────────┐
                   │  FastAPI Backend              │
                   │  Routers: conversation,       │
                   │           history, admin,     │
                   │           health              │
                   │  Azure Container App          │
                   └──┬──────────┬──────────────┬─┘
                      │          │              │
              ┌───────▼───┐  ┌───▼────┐  ┌──────▼────────┐
              │backend.   │  │backend.│  │  Foundry IQ   │
              │core.      │  │core.   │  │  (Knowledge,  │
              │orchestra- │  │data-   │  │   Embeddings, │
              │tors       │  │bases   │  │   Models)     │
              │ (langgraph│  │(cosmos │  │  ├─ GPT-*    │
              │  + agent_ │  │ + pg-  │  │  ├─ o-series │
              │  framework│  │ vector)│  │  └─ Embed.   │
              └───────────┘  └────────┘  └───────────────┘
```

### 3.2 RAG indexing pipeline (Phase 6 — split Azure Functions, **opt-in**)

Functions container only spins up when the operator wants user file uploads. Backend container runs chat end-to-end without it.

```
 ┌──────────────┐    ┌──────────────┐    ┌─────────────────┐
 │ Blob Storage │───▶│ Event Grid   │───▶│ Queue Storage   │
 │ (Documents)  │    │ (Trigger)    │    │ (Process Msgs)  │
 └──────────────┘    └──────────────┘    └────────┬────────┘
                                                  │
                  ┌───────────────────────────────▼────────────┐
                  │  Azure Functions (Modular)                  │
                  │  ┌──────────────┐  ┌──────────────┐         │
                  │  │ batch_start  │  │ batch_push   │         │
                  │  │ (list+queue) │  │ (parse+chunk │         │
                  │  └──────────────┘  │  +embed+push)│         │
                  │  ┌──────────────┐  └──────────────┘         │
                  │  │ add_url      │  ┌──────────────┐         │
                  │  │ (URL fetch+  │  │ search_skill │         │
                  │  │  embed)      │  │ (custom AI   │         │
                  │  └──────────────┘  │  Search skill│         │
                  │                    └──────────────┘         │
                  │  Each blueprint lives in v2/src/functions/  │
                  │  Ingestion-only extensions in functions/core│
                  │  Imports backend.core for shared providers  │
                  └─────────────────────────────────────────────┘
```

### 3.3 Orchestrator migration (v1 → v2)

```
v1 Orchestrators                     v2 Orchestrators
───────────────────                  ─────────────────────────
OpenAI Functions     ──────────▶     (Removed; Agent Framework + Foundry replaces)
Semantic Kernel      ─────╳────▶     REMOVED
LangChain Agent      ──────────▶     LangGraph (StateGraph + ToolNode)
Prompt Flow          ─────╳────▶     REMOVED
                                     Agent Framework (NEW; via Foundry agents)

Model Access:
v1: Direct Azure OpenAI SDK   ──▶   v2: Foundry IQ
                                         ├── GPT-* (chat)
                                         ├── o-series (reasoning)
                                         └── text-embedding-3-* (embed)
```

### 3.4 File-level inventory (post-Phase-5.5 target)

> Phase 5.5 refactor moves `v2/src/shared/**` to `v2/src/backend/core/**` and creates an empty `v2/src/functions/core/` skeleton. Until Phase B lands, the actual on-disk tree still has `v2/src/shared/`. The tree below is the **target** state.

```
v2/
├── azure.yaml                          # azd service definitions
├── pyproject.toml                      # mono-package (backend + functions)
├── Makefile                            # typecheck / test / lint targets
├── docker/
│   ├── docker-compose.dev.yml          # backend-only + frontend-only profiles
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   ├── Dockerfile.functions            # copies src/backend (for backend.core) + src/functions
│   └── ci-entrypoint.sh
├── docs/
│   ├── development_plan.md             # this file (canonical)
│   ├── development_plan.old.md         # historical ledger (frozen 2026-05-06)
│   ├── pillars_of_development.md       # read-only product policy
│   ├── exception_handling_policy.md    # NEW in Phase 5.5 (Phase C)
│   ├── env-vars.md
│   ├── agents.md
│   └── adr/
│       ├── 0001..0008-*.md             # accepted ADRs
│       └── 0009-runtime-type-imports.md (only if Phase B needed leaf-extraction)
├── infra/                              # Bicep AVM-first
│   ├── main.bicep
│   └── modules/...
├── scripts/
│   ├── post_provision.{sh,ps1}
│   └── post_provision.py
├── src/
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── app.py                      # FastAPI app + lifespan
│   │   ├── dependencies.py             # DI seams
│   │   ├── core/                       # ← shared/ moved here in Phase B
│   │   │   ├── __init__.py
│   │   │   ├── registry.py
│   │   │   ├── settings.py             # Pydantic BaseSettings + AppSettings
│   │   │   ├── types.py                # OrchestratorEvent + RuntimeConfig + StrEnums
│   │   │   ├── agents/
│   │   │   │   ├── __init__.py
│   │   │   │   └── definitions.py      # CWYD_AGENT, RAI_AGENT, BUILTIN_AGENTS
│   │   │   ├── providers/
│   │   │   │   ├── credentials/        # cli, managed_identity
│   │   │   │   ├── llm/                # foundry_iq + BaseLLMProvider.complete()
│   │   │   │   ├── search/             # azure_search, pgvector
│   │   │   │   ├── databases/          # cosmosdb, postgres
│   │   │   │   ├── agents/             # foundry (lazy DB-backed bootstrap)
│   │   │   │   └── orchestrators/      # langgraph, agent_framework
│   │   │   ├── pipelines/
│   │   │   │   └── chat.py             # run_chat() — content-safety + RAI gates + orchestrator iteration
│   │   │   └── tools/                  # content_safety, post_prompt, qa, text_processing, citations
│   │   ├── models/                     # Pydantic request/response
│   │   │   ├── conversation.py
│   │   │   └── health.py
│   │   └── routers/
│   │       ├── conversation.py         # POST /api/conversation (SSE)
│   │       ├── history.py              # /api/history/*
│   │       ├── health.py               # /api/health, /api/health/ready
│   │       └── admin.py                # /api/admin/config (GET + PATCH)
│   ├── frontend/                       # React 19 + Vite + TS (no UI library)
│   │   ├── src/
│   │   ├── frontend_app.py             # tiny FastAPI + StaticFiles prod shim
│   │   └── package.json
│   └── functions/
│       ├── __init__.py
│       ├── function_app.py             # currently a stub; blueprints land in Phase 6
│       ├── host.json
│       └── core/                       # ← created empty in Phase B; populated in Phase 6
│           └── __init__.py             # ingestion-only extensions; imports backend.core
└── tests/
    ├── backend/
    │   ├── core/                       # ← tests/shared/ moved here in Phase B
    │   ├── test_app_lifespan.py
    │   ├── test_admin.py
    │   ├── test_conversation.py
    │   ├── test_history.py
    │   └── test_health.py
    ├── frontend/
    ├── functions/
    │   └── core/                       # mirror of src/functions/core/
    ├── infra/
    │   └── test_main_bicep.py
    └── shared/                         # AST invariant tests (cross-cutting)
        └── test_no_type_checking_or_future_annotations.py
```

**The four "what lives where" rules** (locked in for Phase 5.5):

| Rule | Destination |
|---|---|
| Used **only** by backend at chat/query time | `v2/src/backend/core/` |
| Used **only** by functions for indexing/RAG ingestion | `v2/src/functions/core/` |
| Used by **both** backend and functions | `v2/src/backend/core/` (functions imports from it) |
| Used **only** by functions but extends a `backend.core` library | `v2/src/functions/core/` (subclass / extension module that imports the base from `backend.core`) |

**Anti-duplication invariant**: no symbol is defined twice. If functions needs to add behavior to a `backend.core` provider (e.g., a chunking strategy on a parser), the subclass lives in `functions.core` and inherits from `backend.core`. Enforced by code review — no automated check today.

---

## 4. Phases

### Phase 5 (in progress) — Admin + Frontend Merge

| # | Task | Status | Notes |
|---|---|---|---|
| 35a | `GET /api/admin/config` | ✅ done | 6-field shape: orchestrator key, OpenAI temperature/max_tokens, search semantic-toggle/top_k, log_level. |
| 35b | `RuntimeConfig` model + `CosmosItemType.CONFIG` enum | ✅ done | Cosmos `_system` partition (mirrors CU-010b1 `AGENT` precedent); Postgres `runtime_config` single-row JSONB table. |
| 35c | `PATCH /api/admin/config` (DB-backed, RFC 7396 merge) | ✅ done | `get_runtime_config` + `upsert_runtime_config` on `BaseDatabaseClient` + Cosmos + Postgres impls; PATCH route with `_WRITABLE_FIELDS` frozenset; explicit `null` reverts to env default. |
| 35d | Frontend admin merge | ☐ open (FE team) | Configuration form + document upload + prompt editor as React routes. |
| 35e | Live-reload + effective-config GET | ☐ open | `app.state.settings` reload after PATCH; `GET /api/admin/config/effective` returning env+DB merge. |
| 35f | Admin audit log | ☐ open | `admin_audit` Cosmos type / Postgres table; written on every successful PATCH. |
| 35g | Per-tenant overrides | ☐ open (deferred to post-#39) | Requires #39 RBAC tenant claims. |
| 39 | Admin RBAC narrowing | ☐ open | `requires_role("admin")` dependency on all `/api/admin/*` routes. |

### Phase 5.5 (next) — Stable Core Refactor

Plan locked in `/memories/session/plan.md`. Three sub-phases:

| Sub | Title | Decomposition | Verification |
|---|---|---|---|
| A | Doc swap (this turn) | Rename `development_plan.md` → `.old.md` + banner; write fresh canonical doc. | Markdown link integrity; `git log --follow` shows preserved history. |
| B | `shared/` → `backend/core/` + `functions/core/` skeleton | B1 AST invariant test (xfail) · B2 `git mv` shared→backend/core + create empty functions/core · B3 import sweep (~155 sites) · B4 config + docs sweep (pyproject, docker-compose, Dockerfile.functions, .env.sample, all `v2/docs/*.md`, `.github/copilot-instructions.md`, `.github/instructions/v2-shared.instructions.md` rename) · B5 validate + flip xfail strict. | `uv run pytest` 547/547 green · `uv run pyright` 0 errors · `docker compose config` exit 0 · `git log --follow v2/src/backend/core/settings.py` shows full history. |
| C | Try/catch policy + sweep | C1 `exception_handling_policy.md` + AST invariant `no_silent_excepts.py` · C2 provider sweep · C3 pipeline sweep · C4 router + lifespan sweep · C5 functions sweep deferred to Phase 6. | `uv run pytest` green after each sub-phase · one failure-path test per new `try/except` (Hard Rule #2). |

**Phase 5.5 explicit non-goals**: do not introduce new orchestrators, do not change the SSE event contract, do not modify provider interfaces beyond adding narrow SDK catches.

### Phase 6 — RAG Indexing Pipeline (Split Functions)

Land the four blueprints under `v2/src/functions/`:

| # | Blueprint | Trigger | Notes |
|---|---|---|---|
| 40 | `batch_start` | HTTP / Timer | List blobs, fan-out to queue. |
| 41 | `batch_push` | Queue (Storage) | Parse → chunk → embed → push to search index. Uses parser/chunker from `functions.core` (extensions of `backend.core` parsers). |
| 42 | `add_url` | HTTP | Fetch URL content, parse, embed. |
| 43 | `search_skill` | HTTP (custom AI Search skill endpoint) | Sync embed-on-the-fly used by AI Search indexer. |

Each blueprint ships with the per-trigger try/except pattern from Phase 5.5 §C1 policy doc. Poison queue handling per Functions retry policy.

**Phase 6 also lands**: standalone-backend smoke test (CI job that boots `docker compose --profile backend-only up` and runs `/api/conversation` against a mocked OpenAI to prove the "backend works without functions" claim).

### Phase 7 — Testing + Documentation

Rolling work; each phase already ends with `azd up` green. Phase 7 adds:

- End-to-end Playwright tests against the deployed environment (`v2/tests/e2e/`).
- Coverage report gate (`uv run pytest --cov=src/backend --cov-fail-under=80`).
- Operator runbook expansion in `v2/docs/`.
- ADR backfill for any Phase 5.5 / Phase 6 architectural decisions not already captured.

---

## 5. Pillars

See [pillars_of_development.md](pillars_of_development.md) — read-only product policy. Every new module/class in `v2/src/**` opens with:

```
Pillar: <Stable Core | Scenario Pack | Configuration Layer | Customization Layer>
Phase: <1..7 from this development_plan.md>
```

Agents reference the pillars file but never edit it. Any proposed change to pillars must be raised with the user as a separate request.

---

## 6. Naming conventions

Pointer to [.github/copilot-instructions.md](../../.github/copilot-instructions.md) Hard Rule #11. Highlights:

- **Python**: `snake_case` functions/methods/vars/modules, `PascalCase` classes, `UPPER_SNAKE_CASE` constants, `_leading_underscore` private. Closed-set string literals → `enum.StrEnum` (Python 3.11+), not module constants.
- **TypeScript**: `camelCase` vars/functions, `PascalCase` types/interfaces/components, `UPPER_SNAKE_CASE` constants, no `I`-prefix on interfaces.
- **Bicep**: `camelCase` for params/vars/modules/resources/outputs.
- **Cross-cutting**: env vars `UPPER_SNAKE_CASE` with prefixes (`AZURE_*`, `VITE_*`, `CWYD_*`); Azure resource names `<type-abbrev>-<solutionSuffix>` per `v2/infra/abbreviations.json`.
- **Public API names** (HTTP routes, OpenAPI operationIds, SSE event types, `OrchestratorEvent` fields) require user confirmation to rename once shipped.

---

## 7. Local development

Pointers to operational tooling:

- **Editable install**: `uv sync` from repo root.
- **Backend-only profile** (Phase 5.5 invariant: chat works without functions): `docker compose -f v2/docker/docker-compose.dev.yml --profile backend-only up`.
- **Frontend-only profile** (`VITE_BACKEND_URL` required): `docker compose -f v2/docker/docker-compose.dev.yml --profile frontend-only up`.
- **Full dev stack**: `docker compose -f v2/docker/docker-compose.dev.yml up`.
- **CI validation image**: `docker build -f v2/docker/Dockerfile.ci-validate -t cwyd-ci .` then run.
- **Type-check gate**: `uv run pyright` (CI hard-gate via `.github/workflows/v2-typecheck.yml` since Q14e closed 2026-05-06).
- **Test gate**: `uv run pytest` (547/547 baseline at start of Phase 5.5).
- **Provision-then-deploy**: `azd up` (one-shot) or `azd provision` → `azd deploy` (split).
