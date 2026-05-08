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
| 3 | Conversation + RAG (Core Chat) | ✅ done | Chat router + LangGraph + Agent Framework orchestrators, content-safety/post-prompt/QA/text-processing tools, AzureSearch + pgvector handlers, citations, reasoning channel, indexing scripts. **#24 (FE SSE wiring) owned by frontend team — partial advance 2026-05-07 (C1+C2a/b/c demo path); see §0.2 #24 for remaining backlog.** |
| 3.5 | QA Remediation | ✅ done | Cleared 6 deployability blockers (Q1–Q9) + structural realignment Q10 (`shared/{providers,pipelines}/` consolidation). |
| 4 | Chat History + Both Databases | ✅ done | Cosmos + Postgres clients, DI wiring, pgvector with injected pool, chat-history router with fail-closed `get_user_id`, FE history panel, lifespan dispatch + auth + TOCTOU hardening, Bicep outputs + env-binding drift guard. |
| 5 | Admin + Frontend Merge | ✅ done (backend) | Backend surface complete: #35a `GET /api/admin/config` ✅, #35b `RuntimeConfig` + `CosmosItemType.CONFIG` ✅, #35c `PATCH /api/admin/config` (DB-backed, RFC 7396 merge) ✅, #35e (a) live-reload `app.state.runtime_overrides` channel + (b) `GET /api/admin/config/effective` with per-field provenance ✅, #35f (a) Cosmos + (b) Postgres `write_admin_audit` + (c) router PATCH integration with best-effort policy ✅, #39 `requires_role("admin")` RBAC narrowing ✅. **Open (does NOT block Phase 6):** #35d FE-team admin route merge, #35g per-tenant overrides (deferred to post-#39 tenant claims). 784 tests / 0 pyright errors. |
| 5.5 | **Stable Core Refactor** (`shared/` → `backend/core/` + `functions/core/`) | ✅ done | Phase A (doc swap) + Phase B (B1-B5: shared→backend/core git mv, ~155 import sites swept, mono-package via single `pyproject.toml`, pyright `--strict` extends to `src/functions/core/**`) + Phase C (C1 policy doc + AST invariant `no_silent_excepts.py`; C2a-e SDK boundary sweep across cosmosdb/postgres/foundry_iq/azure_search/agents = 29 wrapped sites; C3 silent-swallow fix in `chat.py` clears `_EXEMPTIONS`; C4 5 app-level exception handlers in `app.py`). 747 tests / 0 pyright errors. C5 (functions sweep) deferred to Phase 6 task slots. |
| 6 | RAG Indexing Pipeline (Split Functions) | ⏭ next (unblocked 2026-05-07) | `batch_start`, `batch_push`, `add_url`, `search_skill` blueprints land under `v2/src/functions/`; ingestion-only extensions land under `v2/src/functions/core/`. |
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
| #35e | 5 | Live-reload of `app.state.settings` after `PATCH /api/admin/config` so config tweaks take effect without container restart; effective-config `GET /api/admin/config/effective` showing the merged result of env defaults + DB overrides. Deferred from #35c (Hard Rule #12). | `v2/src/backend/{app,routers/admin}.py`, `v2/src/backend/core/settings.py` | Phase 5 audit | ✅ done (2026-05-07: **(a) live-reload channel + (b) effective-config GET both landed.** (a) Lifespan in `backend/app.py` calls `await database_client.get_runtime_config()` once at startup and stashes the result on `app.state.runtime_overrides` (None when nothing persisted). PATCH `/api/admin/config` route reassigns the same attribute to the just-merged `RuntimeConfig` after every successful upsert (atomic Python attribute write). New `get_runtime_overrides(request)` dependency + `RuntimeOverridesDep` type alias in `backend/dependencies.py` is the read seam. 7 tests: 3 dep-level / 2 lifespan / 2 admin-route. (b) New `GET /api/admin/config/effective` route + `EffectiveAdminConfig` response model: returns `{values: AdminConfig, sources: dict[str, Literal["env","override"]], updated_at, updated_by}`. Merge rule: override field is None -> source = `"env"`, value comes from `AppSettings`; non-None -> source = `"override"`, value comes from `app.state.runtime_overrides`. Audit fields surface from override row even when every field is None (the row is the receipt that an operator interacted). 4 route tests: cold-start (all env / audit None) / partial overlay / explicit-None-treated-as-env / fully overridden. 767/0/0.) |
| #35f | 5 | Audit log for admin config mutations: every successful `PATCH /api/admin/config` writes a row to a new `admin_audit` Cosmos type / Postgres table capturing `who`, `when`, `before`, `after`. Deferred from #35c. | `v2/src/backend/core/providers/databases/**`, `v2/src/backend/routers/admin.py` | Phase 5 audit | ✅ done (2026-05-07: **(a) Cosmos `write_admin_audit` landed.** New `AdminAuditEntry` Pydantic model in `backend/core/types.py` (`actor / action / before: RuntimeConfig | None / after: RuntimeConfig`); router builds the entry and storage assigns id + `createdAt` on persist (mirrors `add_message`). New `CosmosItemType.ADMIN_AUDIT = "admin_audit"`. New abstract `BaseDatabaseClient.write_admin_audit(entry)`. CosmosDB impl uses `create_item` (not `upsert_item`) -- append-only at the SDK layer; UUID4 row id, pinned to `_system` partition (cardinality bounded by # of admin PATCHes); `before` serialized as JSON null when None (truthful first-PATCH receipt, distinct from empty `RuntimeConfig()`). 8 new tests. **(b) Postgres `write_admin_audit` landed (2026-05-07).** New `admin_audit` table in `_SCHEMA_SQL` (`id UUID PK, actor TEXT, action TEXT, before JSONB, after JSONB NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW()`) + `idx_admin_audit_created` on `(created_at DESC)`. INSERT binds 5 parameters via `$1..$5` (id = `str(uuid.uuid4())`, before via `model_dump_json()` or SQL NULL, after via `model_dump_json()`); `created_at` filled by DB default to avoid app-clock drift; SQL injection seam closed (actor/action bound, never interpolated); `asyncpg.PostgresError` logged via `logger.exception(extra={operation, provider, actor, action})` and re-raised. 6 new tests (schema DDL, canonical INSERT shape, parameterized binding, distinct UUIDs, before-as-JSON-when-set, log+reraise). **(c) Router PATCH integration landed (2026-05-07, T+8).** PATCH `/api/admin/config` now snapshots `before = await db.get_runtime_config()` *before* coercing the cold-start default (so `before is None` on the first-ever PATCH stays distinct from `RuntimeConfig()` with all-cleared overrides — the truthful first-PATCH receipt the storage layer already serializes as JSON null). After the existing `upsert_runtime_config(merged)` + `app.state.runtime_overrides = merged` write-back, the route fires `db.write_admin_audit(AdminAuditEntry(actor=user_id, action="patch_config", before=before, after=merged))`. **Best-effort policy**: the audit call is wrapped in a try/except whose body is `logger.exception("write_admin_audit failed; PATCH succeeded but audit row missing", extra={operation, actor, action})` and **does NOT re-raise** — the override is already persisted AND live-reloaded, so surfacing 500 to the operator would mislead them into retrying a PATCH that succeeded; the failure is observable in App Insights via the structured log. 422 validation failures (unknown field, wrong type) skip the audit entirely (no phantom rows for rejected PATCHes). `_fake_db` test helper extended with optional `audit` AsyncMock parameter; default `AsyncMock(return_value=None)` keeps every pre-existing PATCH test green. 4 new route tests in `tests/backend/test_admin.py`: success path locks the four forensic axes (actor `"u-1"` / action `"patch_config"` / before snapshot / after merged), first-PATCH `before is None`, no-audit-on-422, audit-failure-does-not-roll-back-PATCH (asserts 200 + caplog mentions `admin_audit` / `write_admin_audit`). Pyright `--strict` 0 errors; full suite 784/0/0 (was 780). Silent-except invariant clean (`logger.exception` body is policy-compliant per `test_no_silent_excepts`). **#35f fully closed.**) |
| #35g | 5 | Per-tenant config overrides (multi-tenant scenario): `RuntimeConfig` keyed by `tenantId` instead of singleton; PATCH route narrows by `request.tenantId`. Deferred from #35c — only relevant once #39 (RBAC) lands tenant claims. | `v2/src/backend/core/types.py`, `v2/src/backend/core/providers/databases/**` | Phase 5 audit (or later) | ☐ open |
| #39 | 5 | Admin RBAC narrowing: `/api/admin/*` routes guarded by `requires_role("admin")` dependency; role claim sourced from Easy Auth `X-MS-CLIENT-PRINCIPAL` header. Currently any authenticated user can call admin endpoints. | `v2/src/backend/dependencies.py`, `v2/src/backend/routers/admin.py` | Phase 5 audit | ✅ cleared (2026-05-06: `requires_role(role)` factory in `backend/dependencies.py` decodes Easy Auth claims, accepts both `typ="roles"` and full schema-URI role claims, returns user OID on success, raises 403 on missing role / 401 on missing/malformed Easy Auth in production, falls back to `"local-dev"` when no headers in `local`. `_REQUIRE_ADMIN_USER` cached at admin-router module import for stable `dependency_overrides` keying. Old placeholder `admin_user_id` deleted. 9 new tests: 8 unit-level role-claim variants in `test_dependencies.py` + route-level 200/401/403 smoke in `test_admin.py`.) |
| REFACTOR-A | 5.5 | **Phase A — Doc swap.** Renamed old plan to `development_plan.old.md` with deprecation banner; wrote fresh lean canonical `development_plan.md`. | `v2/docs/development_plan.{md,old.md}`, `/memories/repo/cwyd-tech-stack.md` | Phase 5.5 | ✅ cleared (2026-05-06) |
| REFACTOR-B | 5.5 | **Phase B — `shared/` → `backend/core/` + `functions/core/` skeleton.** All 5 sub-units (B1 AST invariant test xfail · B2 `git mv` shared→backend/core + create empty functions/core · B3 import sweep ~155 sites · B4 config + docs sweep · B5 validate + flip xfail strict) closed. `tests/no_legacy_shared_imports.py` enforces strictly with zero exemptions. | `v2/src/shared/**` → `v2/src/backend/core/**`, `v2/src/functions/core/__init__.py`, `v2/pyproject.toml`, `v2/docker/{docker-compose.dev.yml,Dockerfile.functions}`, `.github/instructions/v2-shared.instructions.md` (renamed → `v2-backend-core.instructions.md`), all `*.py` import sites | Phase 5.5 | ✅ cleared (2026-05-06) |
| REFACTOR-C | 5.5 | **Phase C — Try/catch policy + sweep.** `v2/docs/exception_handling_policy.md` defines per-layer catch/log/re-raise rules; AST invariant `v2/tests/no_silent_excepts.py` enforces ban on silent swallow + `except BaseException`. C2 wrapped 29 SDK boundaries (cosmosdb 7 + postgres 9 + foundry_iq 8 + azure_search 2 + agents 3) with `azure.core.exceptions.AzureError` / `openai.APIError` / `asyncpg.PostgresError` umbrellas + structured `logger.exception` extras. C3 cleared the last `_EXEMPTIONS` entry in `chat.py`. C4 installed 5 app-level exception handlers in `app.py` (openai 502 / Cosmos 503 / Postgres 503 / AzureError 503 / Exception 500). C5 (functions sweep) deferred to Phase 6 task slots. | `v2/docs/exception_handling_policy.md`, `v2/src/backend/core/providers/**`, `v2/src/backend/core/pipelines/**`, `v2/src/backend/app.py`, `v2/tests/no_silent_excepts.py`, `v2/tests/backend/test_app_exception_handlers.py` | Phase 5.5 | ✅ cleared (2026-05-06) |

### 0.2 Frontend debt (separate team)

| ID | Origin Phase | Item | Files | Cleared in | Status |
|---|---|---|---|---|---|
| DV1 | 1 | Re-verify `docker compose -f v2/docker/docker-compose.dev.yml build frontend` (currently blocked: Docker Desktop daemon down on dev machine) | n/a | Frontend team audit | ⏸ blocked — FE team owns |
| #24 | 3 | **FE SSE wiring** for `POST /api/conversation`. Owned by FE team. **Partial advance landed 2026-05-07** to unblock a boss-demo (backend-only profile + LangGraph + gpt-5 in eastus2): C1 typed `streamChat()` SSE client (`fetch` + `ReadableStream` + `TextDecoder` + line parser, drops unknown channels); C2a `ChatContext` reducer extension (`reasoning?: string[]` / `streaming?: boolean` / `error?: string` on `ChatMessage`; new `append_answer` / `append_reasoning` / `finish_stream` / `set_error` actions, no-op-on-missing-id); C2b `MessageInput` wires submit → user msg + assistant placeholder → `for await` over `streamChat(history)` folding events via reducer (input + Send disabled while streaming, no re-entry); C2c `MessageList` renders collapsible `<details>` "▸ Show reasoning" panel + inline `role="alert"` error notice. **Citations + tools intentionally dropped from the demo path** (events parsed but discarded). 61/61 frontend vitest green; tsc strict clean. **Remaining sub-units stay on FE backlog**: citation cards, error toast/UX polish, reconnect on dropped stream, abort/cancel button, multi-turn UX (clear button, scroll-to-bottom). | `v2/src/frontend/src/api/streamChat.ts`, `v2/src/frontend/src/pages/chat/ChatContext.tsx`, `v2/src/frontend/src/pages/chat/components/{MessageInput,MessageList}.tsx`, `v2/src/frontend/tests/**` | Frontend team backlog | ⏳ partial (2026-05-07) |
| FE-UI-1 | 6 (pulled forward) | **Phase 6 frontend polish — pulled forward for boss demo.** Re-skin v2's existing chat skeleton in place (no SSE rewiring): G1 dev-port move 5173→5273 (`vite.config.ts` + `BACKEND_CORS_ORIGINS`); G2 `ThemeProvider` + `useTheme()` hook + `tokens.css` (light/dark palette via `data-theme` attribute on `<html>`, persisted to `localStorage["cwyd.theme"]`) — a v2 capability v1 lacked; G3 `<AppHeader>` component (Azure logo + title + history button with `aria-pressed` + theme toggle button with sun/moon SVG); G4 page-layout grid (`ChatPage.module.css` `grid-template-columns: var(--history-col, 0) 1fr`, sidebar `display: none` when `data-history-open="false"`) + chat bubble polish (`MessageList.module.css`: user-right accent bg / assistant-left surface bg / capitalized role label / styled reasoning `<details>` / danger error banner) + `historyOpen` state lift in `App.tsx`; G5 composer pill (`MessageInput.module.css`: `:focus-within` accent border + focus-ring, accent send button with paper-airplane SVG, `aria-label="Send"` preserved, sr-only "Message" label preserved); G6 history-toggle integration tests (3 new). **Zero new dependencies** — CSS Modules + `fireEvent` only (no `@testing-library/user-event`). **Asset exception (per Hard Rule #9)**: `v2/src/frontend/src/assets/Azure.svg` copied verbatim from v1 (static asset, not code). **Pillar = Stable Core** declared in every new module's docstring. **Test count 61 → 74** (+6 theme + +4 AppHeader + +3 history toggle); all pre-existing 61 tests green via preserved `data-testid` + `data-role` attributes + accessible names. G7 browser smoke verified server-side (health 200 / `text/html` root 200 / SSE end-to-end gpt-5 200) — manual UI walkthrough handed to user with checklist. **Remaining canonical Phase 6 tasks (RAG indexing pipeline — `batch_start` / `batch_push` / `add_url` / `search_skill` blueprints under `v2/src/functions/`) untouched** and remain ⏭ next per §0 status snapshot. **Polish batch 2 (2026-05-08, also pulled forward for boss demo):** sidebar L→R move (`ChatPage.module.css` `grid-template-columns: 1fr var(--history-col, 0)`, `.sidebar { border-left }`, JSX child re-order so `<aside>` follows `<div .main>`); H0 added `lucide-react@^1.14.0` (verified latest via `npm view`); H1 message avatars (`MessageList.tsx` / `MessageList.module.css` — 28×28 round per-row avatar with `User` / `Sparkles` lucide icons, role-flipped row direction, sr-only role text); H2 history-panel icon buttons + Slack/Outlook hover-reveal pattern (`HistoryPanel.tsx` + new `HistoryPanel.module.css` — `Plus` New / `Pencil` Rename / `Trash2` Delete, every `data-testid` + `aria-label` preserved verbatim, `.actions { opacity: 0 → 1 on :hover, :focus-within, [data-selected="true"] }`); H3 empty-chat-state `MessageCircle size={64}` icon above the existing `<p data-testid="message-list-empty">` (testid + visible text preserved); H4 header `Plus` New chat button wired through new required `onNewChat` prop on `<AppHeader>` → `App.tsx` owns a `newChatNonce` counter → `<ChatPage key={newChatNonce}>` cleanly remounts and resets `ChatProvider` state + `selectedId` without lifting the provider (no structural change, no Hard Rule #10 trigger). Also added `v2/src/frontend/src/components/icons.ts` barrel so pages never import from `lucide-react` directly (one-line swap point if the icon set changes). **Test count 74 → 75** (+1 AppHeader new-chat click); all pre-existing tests green; pillar/phase docstrings declared on every new module. **Polish batch 3 (H6, 2026-05-08, also pulled forward for boss demo — live "Thinking…" panel UX fix):** Foundry IQ already emits per-token `OrchestratorChannel.REASONING` deltas and the SSE → reducer → `m.reasoning: string[]` wire was verified end-to-end intact (no backend / no `streamChat.ts` / no `ChatContext.tsx` change). UX bug: panel only appeared *after* `finish_stream` and rendered each delta as its own `<li>`, so the boss demo saw a static post-hoc list instead of a live trace. Fix isolated to `MessageList.tsx` + `MessageList.module.css`: render-condition flipped from `m.reasoning?.length > 0` → `m.streaming === true || (m.reasoning && m.reasoning.length > 0)` so the panel pops open immediately on first chunk; `<details open={m.streaming}>` keeps it open while streaming and lets the user toggle it after; summary swaps `Thinking` + three CSS-keyframed dots (`@keyframes cwydThink`, `data-streaming="true"` accent color) ↔ `▸ Thought process` on completion; body switched from per-delta `<ol><li>` to a single `<div className={styles.reasoningBody}>{m.reasoning?.join("") ?? ""}</div>` (pre-wrap, scrollable `max-height: 200px`) so token deltas concatenate into the actual reasoning prose at render time. Every existing `data-testid` (`message-{id}-reasoning`) preserved. **Zero new dependencies** (pure CSS animation). **Test count 75 → 77** (2 reasoning tests rewritten for new copy + joined body; +2 new streaming tests: panel open with "Thinking" when no chunks yet, panel open with joined live deltas mid-stream); all pre-existing tests green. Pillar/phase docstring header on `MessageList.tsx` updated to `Phase: 5 + 6 (visual polish — bubble layout, pulled forward for boss demo; H6 patch 2026-05-08: live "Thinking…" panel)`. | `v2/.env`, `v2/src/frontend/vite.config.ts`, `v2/src/frontend/package.json` (`lucide-react@^1.14.0`), `v2/src/frontend/src/{App.tsx,assets/Azure.svg}`, `v2/src/frontend/src/theme/{themeContext.tsx,tokens.css}`, `v2/src/frontend/src/components/{icons.ts,AppHeader/{AppHeader.tsx,AppHeader.module.css}}`, `v2/src/frontend/src/pages/chat/{ChatPage.tsx,ChatPage.module.css}`, `v2/src/frontend/src/pages/chat/components/{MessageList.tsx,MessageList.module.css,MessageInput.tsx,MessageInput.module.css,HistoryPanel.tsx,HistoryPanel.module.css}`, `v2/src/frontend/tests/{theme/themeContext.test.tsx,components/AppHeader.test.tsx,AppHistoryToggle.test.tsx,pages/chat/components/MessageList.test.tsx}` | Phase 6 audit | ✅ cleared (2026-05-08, supersedes 2026-05-07 batch 1 + 2026-05-08 batch 2) |

Legend: ☐ open · ⏳ in progress · ⏭ next · ⏸ blocked · ✅ cleared (date)

---

## 1. Architecture goals

The v2 architecture rests on three invariants:

1. **Pillars** ([pillars_of_development.md](pillars_of_development.md)) — every new core element declares one of: Stable Core, Scenario Pack, Configuration Layer, Customization Layer. Read-only product policy; never edited by agents.
2. **Plug-and-play via registry** — all swappable concerns (credentials, llm, embedders, parsers, search, chat_history, orchestrators) live under `v2/src/backend/core/providers/<domain>/` and self-register via `@registry.register("key")`. Caller code does `domain.create(key, ...)` — never `if/elif` provider dispatch (Hard Rule #4).
3. **Standalone backend, optional functions** (new in Phase 5.5) — backend runs end-to-end (chat + history + admin) without the functions container. Functions is opt-in: it ships only when the operator wants to upload + index their own files. **No code is duplicated**: anything used by both lives in `backend/core/`; functions extends via `functions/core/` (subclass / extension module that imports the base from `backend.core`).

Fourth supporting invariant — **runtime types always available** (Hard Rule #11 sub-rule, ratified 2026-05-05 in CU-013): no `if TYPE_CHECKING:`, no `from __future__ import annotations`. Genuine circular imports get fixed by extracting the shared type to a leaf module (Hard Rule #10 — ask first). Enforced by AST invariant `v2/tests/shared/test_no_type_checking_or_future_annotations.py` (a follow-up turn will move this file to `v2/tests/backend/core/_invariants/` to colocate with the source under test — pending user approval per Hard Rule #10).

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

### 3.4 File-level inventory

> Phase 5.5 closed 2026-05-06: `v2/src/shared/**` was `git mv`'d to `v2/src/backend/core/**` and `v2/src/functions/core/` exists as the empty extension skeleton (populated in Phase 6). The tree below is the **current** on-disk state.

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

### Phase 5 (backend closed 2026-05-07) — Admin + Frontend Merge

Backend surface (#35a–#35c, #35e, #35f, #39) all ✅ done. **Open items
that do NOT block Phase 6:** #35d is FE-team owned (React admin
routes) and tracked separately; #35g (per-tenant overrides) is
explicitly deferred to post-#39 hardening, since it requires tenant
claims that #39's RBAC dependency does not yet surface. Phase 6
(Functions blueprints — modular RAG indexing pipeline) is unblocked.

| # | Task | Status | Notes |
|---|---|---|---|
| 35a | `GET /api/admin/config` | ✅ done | 6-field shape: orchestrator key, OpenAI temperature/max_tokens, search semantic-toggle/top_k, log_level. |
| 35b | `RuntimeConfig` model + `CosmosItemType.CONFIG` enum | ✅ done | Cosmos `_system` partition (mirrors CU-010b1 `AGENT` precedent); Postgres `runtime_config` single-row JSONB table. |
| 35c | `PATCH /api/admin/config` (DB-backed, RFC 7396 merge) | ✅ done | `get_runtime_config` + `upsert_runtime_config` on `BaseDatabaseClient` + Cosmos + Postgres impls; PATCH route with `_WRITABLE_FIELDS` frozenset; explicit `null` reverts to env default. |
| 35d | Frontend admin merge | ☐ open (FE team) | Configuration form + document upload + prompt editor as React routes. |
| 35e | Live-reload + effective-config GET | ✅ done (2026-05-07) | (a) `app.state.runtime_overrides` channel landed (lifespan seed + PATCH writeback + `get_runtime_overrides` dep); (b) `GET /api/admin/config/effective` landed (env+overrides merge with per-field provenance + audit fields). |
| 35f | Admin audit log | ✅ done (2026-05-07) | (a) Cosmos `write_admin_audit` + `AdminAuditEntry` type + `CosmosItemType.ADMIN_AUDIT` + ABC method landed; (b) Postgres `write_admin_audit` + `admin_audit` table + `idx_admin_audit_created` landed; (c) router PATCH integration landed (T+8): PATCH `/api/admin/config` snapshots `before` from prior `db.get_runtime_config()` (None on first PATCH, distinct from `RuntimeConfig()`) and fires `db.write_admin_audit(AdminAuditEntry(actor=user_id, action="patch_config", before, after=merged))` after `upsert_runtime_config` + `app.state.runtime_overrides` write-back; **best-effort policy** -- audit failure is `logger.exception`'d but does NOT roll back the PATCH (the override is already persisted + live-reloaded); 422 validation failures skip the audit (no phantom rows). 4 new route tests (success, first-PATCH `before=None`, no-audit-on-422, audit-failure-does-not-roll-back-PATCH). |
| 35g | Per-tenant overrides | ☐ open (deferred to post-#39) | Requires #39 RBAC tenant claims. |
| 39 | Admin RBAC narrowing | ✅ done (2026-05-06) | `requires_role("admin")` dependency on all `/api/admin/*` routes; details in §0.1. |

### Phase 5.5 (closed 2026-05-06) — Stable Core Refactor

| Sub | Title | Status | Notes |
|---|---|---|---|
| A | Doc swap | ✅ done | Renamed old plan to `.old.md` + banner; wrote fresh canonical doc. |
| B | `shared/` → `backend/core/` + `functions/core/` skeleton | ✅ done | All 5 sub-units (B1 AST invariant xfail → B5 strict) green. `git log --follow v2/src/backend/core/settings.py` preserves full history. `tests/no_legacy_shared_imports.py` enforces strictly with zero exemptions. |
| C | Try/catch policy + sweep | ✅ done | C1 policy doc + AST invariant; C2a-e SDK boundary sweep (29 wrapped sites across cosmosdb/postgres/foundry_iq/azure_search/agents); C3 silent-swallow fix in `chat.py`; C4 5 app-level exception handlers in `app.py`. C5 (functions) deferred to Phase 6. 747 tests / 0 pyright errors at close. |

**Phase 5.5 explicit non-goals (held)**: did not introduce new orchestrators; did not change the SSE event contract; did not modify provider interfaces beyond adding narrow SDK catches.

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
