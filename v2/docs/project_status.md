---
title: CWYD v2 — Project Status Snapshot
description: Current QA-readiness snapshot of CWYD v2, organized by review dimension. Replaces the stale qa_report_v2 narrative.
author: CWYD Engineering
ms.date: 2026-06-10
topic: status
keywords: status, qa, readiness, v2, snapshot
estimated_reading_time: 8
---

# CWYD v2 — Project Status Snapshot

This document is the **per-dimension QA readiness snapshot** of CWYD v2 for the QA review team. It is the entry point for the structured review that lives in [qa_review_plan.md](qa_review_plan.md) and is anchored against the canonical [development_plan.md](development_plan.md) (§0 status table + §0.1 / §0.2 debt queues).

Observed defects (broken or wrong behavior) are tracked in [bugs.md](bugs.md); day-to-day work is logged under [worklog/](worklog/).

For the historical, Phase 3.5-era QA report kept for archeology only, see [qa_report_v2.archived.md](qa_report_v2.archived.md).

---

## Executive Status

**Phase 7 backend tier is drained.** As of `U-P7-AUDIT-3` (2026-06-02), every backend §0.1 debt row originating in Phases 1–7 is ✅ cleared except a small handful that are deferred or externally blocked (post-Phase-7 hardening `B-IMPL-FACTORY-CACHE`, multi-agent demos `B-IMPL-EXTRAS`, upstream OSS SDK typing `B-IMPL-FOUNDRY-STUBS-DEBT`). All 9 AST gates are green. Backend full suite runs `2198 passed / 1 skipped / 3 deselected / 10 warnings` as of the 2026-06-09 Phase 8 baseline (up from 2047 passes at the 2026-06-04 QA review; the added warnings are upstream `agent_framework` experimental notices + FastAPI `HTTP_422_UNPROCESSABLE_ENTITY` deprecation notices). `pyright src/backend src/functions` is `0 errors / 0 warnings / 0 informations`.

**Phase 7 is complete (`U-P7-AUDIT-4`, 2026-06-08).** `#50` feedback thumbs, `#53` Ingest Data admin UI, and `#54` Delete Data admin UI are all ✅ done (`#54` `DeleteData.tsx` ships loading/failed/empty/loaded states + multi-select with select-all + per-row error/retry + bulk delete + bulk retry-failed + confirmation dialog); `#35d` Streamlit-to-React admin merge is ✅ cleared (2026-06-08, `U-P7-35D-AUDIT`); `#24` SSE FE wiring is ✅ closed (A2.1–A2.5: citation cards verified end-to-end, deduped error toasts, `streamChat` retry-with-backoff, `AbortController` cancel, and clear-conversation + scroll-to-bottom sentinel). On top of the closed `#35d`, the post-Phase-7 (PP7) work stream landed the Vitest test-tree relocation to `v2/src/tests/frontend` as an npm-workspace member (`U-PP7-RELOC`, [ADR 0020](adr/0020-frontend-tests-under-src-tests-frontend.md)) and real browser URLs for the admin pages (`U-PP7-ROUTE` — `/admin/ingest|delete|config|prompt` via `react-router-dom`, with an `frontend_app.py` SPA catch-all). The FE conventions refactor (`U-P7-FE-REFAC`, 6 units) closed 2026-06-02; current FE numbers as of 2026-06-08 (all run from the `v2/` npm-workspace root) are `npm run lint` 0 errors / 9 advisory `react-refresh/only-export-components` warnings, `npx tsc -p src/frontend` + `npx tsc -p src/tests/frontend` both clean, and `npm test` 403 tests / 32 suites green.

**Phase 8 is complete (2026-06-09).** Phase 8 makes `agent_framework` the **default** orchestrator, grounded by a Foundry IQ Knowledge Base (a `searchIndex` knowledge source wrapping the existing `cwyd-index`, queried live so push-ingestion needs no reseed), with the KB REST API version supplied via the new `AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION` env var (default `2025-11-01-preview`). This is the rules-compliant successor to the v1 BYOD *intent* (platform-grounded retrieval) — **not** a re-introduction of the removed Azure OpenAI `data_sources` mechanism (see [development_plan.md](development_plan.md) §2.1 BYOD clarifier + §4 Phase 8 for the ordered task table; [ADR 0021](adr/0021-agent-framework-foundry-iq-kb-default.md) + [ADR 0022](adr/0022-config-resolution-error-on-incompatible-overrides.md), both **Accepted**). `OrchestratorSettings.name` now defaults to `agent_framework`; because that orchestrator is grounded by a Foundry IQ KB over the Azure AI Search index, pgvector deployments must override to `langgraph` (the dev `docker-compose.dev.yml` pins `CWYD_ORCHESTRATOR_NAME=langgraph`), and selecting `agent_framework` in pgvector mode is rejected at request time with a clean `ConfigResolutionError` (HTTP 409) per ADR 0022 — never a silent fallback.

---

## Verified Metrics (backend 2026-06-09 · frontend 2026-06-08)

| Surface | Tool | Result |
|---|---|---|
| Backend test suite | `cd v2 ; uv run pytest -q` | 2198 passed / 1 skipped / 3 deselected / 10 warnings |
| Backend type check | `cd v2 ; uv run pyright src/backend src/functions` | 0 errors / 0 warnings / 0 informations |
| AST invariant gates | `uv run pytest tests/shared tests/test_no_silent_excepts.py -q` | 1021 passed / 1 skipped — 9 gates green (8 tree-walking + 1 silent-except + router-only) |
| Frontend unit suite | `npm test` from `v2/` | 403 passed / 32 suites |
| Frontend lint | `npm run lint` from `v2/` | 0 errors / 9 react-refresh advisory warnings (HMR fast-refresh hints on the admin pages, chat/theme contexts, and `models/sections.tsx` — non-blocking) |
| Frontend type check | `npx tsc -p src/frontend` + `npx tsc -p src/tests/frontend` from `v2/` | both clean (0 errors) |
| Frontend SPA fallback (ASGI) | `uv run pytest tests/frontend/test_frontend_app.py` from `v2/` | 4 passed |

The backend warnings (10 as of the 2026-06-09 Phase 8 baseline, up from 6 at 2026-06-04) are upstream `agent_framework` experimental notices (e.g. `SkillResource`, `MemoryStore`) plus FastAPI `HTTP_422_UNPROCESSABLE_ENTITY` deprecation notices surfaced by the admin 422 validation tests — all advisory. The FE lint warnings (9 as of 2026-06-08, up from 7 at the 2026-06-04 baseline) are modules that co-export helpers alongside their default component — the two added by the PP7 routing work live in `models/sections.tsx` — advisory only.

Re-run baselines via [qa_review_plan.md](qa_review_plan.md) Phase B (validation snapshot).

---

## Per-Dimension Status

### Hard Rules (17 active in `.github/copilot-instructions.md`)

| # | Rule | Status |
|---|---|---|
| 0 | Step 0 — sync agent guidance before any change | ✅ enforced procedurally |
| 1 | One unit per turn (class or method) | ✅ enforced procedurally |
| 2 | Test-first contract | ✅ enforced procedurally |
| 3 | Pillar awareness (no docstring header) | ✅ enforced procedurally (header mandate retired; gate `test_pillar_phase_header.py` removed) |
| 4 | Plug-and-play via registry | ✅ 8 domain registries under `backend/core/providers/<domain>/registry.py` |
| 5 | Multi-agent ready (shared `OrchestratorBase` + typed reasoning channel) | ✅ contracted |
| 6 | Reasoning feed on dedicated SSE channels | ✅ `OrchestratorEvent` typed contract |
| 7 | No banned tech / no removed features | ✅ docs aligned with development_plan.md §2.1 |
| 8 | Every phase ends green | ✅ Phase 7 backend tier drained at green |
| 9 | Clean, modular, anchored to dev_plan + pillars | ✅ procedural |
| 10 | Ask before changing structure | ✅ procedural |
| 11 | Naming-convention stability + `StrEnum` for closed sets | ✅ AST gate `test_no_type_checking_or_future_annotations.py` + manual review |
| 12 | No mid-phase back-fills (debt → §0.1) | ✅ procedural |
| 13 | `__init__.py` is a package marker | ✅ AST gate `test_init_files_are_marker_only.py` |
| 14 | SDK boundary resilience (`try/except` + structured log + re-raise) | ✅ AST gate `test_no_silent_excepts.py` |
| 15 | Closed-set dict returns must be typed Pydantic models | ✅ AST gate `test_no_anonymous_dict_returns.py` |
| 16 | No process narrative in production code | ✅ AST gate `test_no_process_narrative_in_src.py` |
| 17 | All imports at module top | ✅ AST gate `test_imports_at_top_only.py` |

A full audit walk lives in [qa_review_plan.md](qa_review_plan.md) Phase C.

### Libraries

| Concern | Status |
|---|---|
| Microsoft Agent Framework (OSS) pinning | ✅ `agent-framework-core>=1.7,<2.0` + `agent-framework-foundry>=1.7,<2.0` exact pins per ADR 0017 |
| Foundry IQ wiring | ✅ rebuilt on OSS `agent_framework_foundry.FoundryAgent` runtime (`B-IMPL-AUDIT`, 2026-06-02) |
| Banned packages (Streamlit, Prompt Flow, Semantic Kernel, Poetry, direct `openai`/`AzureOpenAI`) | ✅ zero references in `v2/src/**` |
| Azure SDK boundary discipline | ✅ Hard Rule #14 + AST gate |
| Document Intelligence SDK | ✅ `azure-ai-documentintelligence>=1.0,<2.0` swap (`U-P7-B0`, 2026 turn) |

**Full ADR → library/decision mapping**: see [v1 → v2 Feature Parity > section L](#l-library--architectural-decision-crosswalk-adrs-0001-0017) for the canonical crosswalk (one row per ADR, before / after / live-on-disk evidence). This block is a summary; section L is the source of truth.

### Modularity

| Concern | Status |
|---|---|
| Provider registries (`agents`, `credentials`, `databases`, `embedders`, `llm`, `orchestrators`, `parsers`, `search`) | ✅ 8 domain `registry.py` files under `v2/src/backend/core/providers/` |
| Entry-point discovery for 3rd-party plugins | ✅ `backend/core/discovery.py` + `load_entry_points("cwyd.providers.<domain>")` wired into all 8 domain registries (`EXTENSION-DISCOVERY-PIPELINE` U1–U13) |
| Plug-and-play profiles (backend-only / frontend-only) | ✅ `docker compose --profile backend-only` and `--profile frontend-only` both boot |
| Router discipline (routes only) | ✅ AST gate `test_routers_contain_only_routes.py` enforces all 5 router files |
| `__init__.py` discipline (package marker only) | ✅ AST gate `test_init_files_are_marker_only.py` enforces zero `__all__`, zero re-exports, zero side effects |
| Import discipline (top of module only) | ✅ AST gate `test_imports_at_top_only.py` enforces zero in-function imports under `v2/{src,scripts,tests}/` |

### Admin Configuration + Save

| Route | Status |
|---|---|
| `GET /api/admin/status` | ✅ shipped (#35a) |
| `GET /api/admin/config` | ✅ shipped (#35b) |
| `PATCH /api/admin/config` (RFC 7396 merge, DB-backed) | ✅ shipped (#35c) |
| `GET /api/admin/config/effective` (per-field provenance) | ✅ shipped (#35e) |
| Live-reload of `app.state.runtime_overrides` after PATCH | ✅ shipped (#35e) |
| Admin audit on PATCH (Cosmos + Postgres) | ✅ shipped (#35f) |
| Admin routes gated by role | — removed (BUG-0090); admin routes now use the header-GUID `get_user_id`, no application-layer role gate (see [ADR 0031](adr/0031-backend-admin-auth-header-only-ingress-enforced.md)) |
| `POST /api/admin/documents/url` (URL ingest) | ✅ shipped (`U-P7-53-BE` BE-1) |
| `POST /api/admin/documents` (multipart upload, 50 MiB cap) | ✅ shipped (`U-P7-53-BE` BE-2) |
| `POST /api/admin/documents/reprocess` (reprocess all in container) | ✅ shipped (`U-P7-53-BE` BE-3) |
| `GET /api/admin/documents` (list indexed sources with chunk counts) | ✅ shipped (`U-P7-54-BE`) |
| `DELETE /api/admin/documents/{source}` (delete by source) | ✅ shipped (`U-P7-54-BE`) |
| Per-tenant config overrides | — withdrawn (out of scope, single-tenant); see [ADR 0024](adr/0024-withdraw-per-tenant-runtime-config-single-tenant.md) (`#35g`) |
| FE admin route merge | ✅ cleared (`#35d`, 2026-06-08) + real admin URLs (`U-PP7-ROUTE`) |

### Chat History

| Route | Status |
|---|---|
| `GET /api/history/status` | ✅ shipped |
| `GET /api/history/conversations` | ✅ shipped |
| `POST /api/history/conversations` | ✅ shipped |
| `GET /api/history/conversations/{id}` | ✅ shipped |
| `PATCH /api/history/conversations/{id}` (rename) | ✅ shipped |
| `DELETE /api/history/conversations/{id}` (idempotent, 204) | ✅ shipped |
| `POST /api/history/conversations/{id}/messages` (append) | ✅ shipped |
| `POST /api/history/messages/{message_id}/feedback` | ✅ shipped (#32b) |
| Cosmos + Postgres provider impls | ✅ both registered under `databases` registry |
| Header-GUID `get_user_id` (validates `x-ms-client-principal-id` is a GUID, else the anonymous default GUID; never 401) | ✅ shipped (BUG-0090) |

### Phases

| Phase | Status | Notes |
|---|---|---|
| 1 — Infrastructure + Project Skeleton | ✅ done | Bicep AVM-first, UAMI + RBAC, no Key Vault, `post_provision.sh` |
| 2 — Configuration + LLM Integration | ✅ done | `shared` → `backend/core` consolidated in 5.5 |
| 3 — Conversation + RAG (Core Chat) | ✅ done | LangGraph + Agent Framework orchestrators, AzureSearch + pgvector handlers |
| 3.5 — QA Remediation | ✅ done | Q1–Q14 + Q10 structural realignment |
| 4 — Chat History + Both Databases | ✅ done | Cosmos + Postgres clients + pgvector injected pool |
| 5 — Admin + Frontend Merge | ✅ done | All 9 admin routes + RBAC + audit log shipped; FE merge `#35d` cleared 2026-06-08 |
| 5.5 — Stable Core Refactor | ✅ done | `shared/` → `backend/core/` + `functions/core/` + `try/except` policy + 29 SDK boundary wraps |
| 6 — RAG Indexing Pipeline (Split Functions) | ✅ done | 4 blueprints (`batch_start`, `batch_push`, `add_url`, `search_skill`) + standalone-backend smoke CI |
| 7 — Testing + Documentation | ✅ done | Backend tier drained 2026-06-02; FE `#35d` + `#24` + `#54` closed at Phase 7 close (`U-P7-AUDIT-4`, 2026-06-08); PP7 relocation/routing landed 2026-06-08 |

---

## v1 → v2 Feature Parity

This section is the **canonical v1 → v2 mapping** for the QA review team. Every row anchors against a verifiable v1 file path and the live v2 surface that replaces it (or the [development_plan.md](development_plan.md) §2.1 removal that explains its absence). Counts in section A are the audit truth as of 2026-06-05.

### A. Executive parity summary

| Category | v1 surface items | Disposition |
|---|---|---|
| Flask routes (`code/create_app.py`) | 8 | 5 ✅ ported, 1 ❌ removed (`/api/assistanttype`), 1 ✅ replaced (`/api/checkauth` → Easy Auth + `/api/admin/status`), 1 ⏳ partial (`/api/files/<filename>` — no v2 user-facing serve route) |
| Chat history blueprint (`code/backend/api/chat_history.py`) | 7 | All ✅ replaced by 8 RESTful routes under `/api/history/*` (RFC 7396 compliant, both DB backends) |
| Streamlit admin pages (`code/backend/pages/`) | 5 | 3 ✅ replaced by React routes (Configuration, IngestData, DeleteData), 1 ⏳ partial (Explore Data → no v2 equivalent), 1 ✅ replaced (Admin shell → React app) |
| Azure Functions (`code/backend/batch/`) | 5 | 3 ✅ replaced (`add_url`, `batch_push`, `batch_start` blueprints), 1 ❌ removed (`bp_get_conversation_response` — chat is FastAPI now), 1 ⏳ gap (`bp_combine_pages_and_chunknos` page-restitching not wired) |
| Documentation (`docs/`) | 35 | 19 ✅ ported, 5 ❌ replaced, 5 📄 docs-only, 3 ⏳ pending, 3 🚫 removed-by-design |
| Infrastructure (`infra/` root) | 4 trees | 2 ✅ ported (`main.bicep`, `workbooks/`), 1 ✅ ported with rewrite (`modules/`), 1 🚫 removed (`prompt-flow/`) |
| Integrations (`extensions/`) | 1 | 1 🚫 removed (Teams extension — §2.1) |

**Net coverage**: every v1 capability not on the §2.1 removal list either has a live v2 equivalent or is captured in [development_plan.md](development_plan.md) §0.1 / §0.2 as tracked debt. Three small gaps (file-serve route, Explore Data admin page, page-number restitching pipeline) are documented in subsection M below.

### B. Chat surface

| v1 surface | v2 surface | Status | Evidence |
|---|---|---|---|
| `POST /api/conversation` (Flask, sync + custom streaming) | `POST /api/conversation` (FastAPI, SSE-native, typed `OrchestratorEvent` channel) | ✅ replaced | [v2/src/backend/routers/conversation.py](../src/backend/routers/conversation.py); ADR 0007 |
| v1 `conversation_with_data` / `stream_with_data` (BYOD via Azure OpenAI `data_sources`) | n/a (mechanism); *intent* → default `agent_framework` + Foundry IQ KB | 🚫 mechanism removed-by-design / ✅ intent restored compliantly | §2.1 — the `data_sources` *mechanism* violates Hard Rules #4/#5/#6/#7 (never written in v2); the platform-grounded *intent* returns via the default `agent_framework` orchestrator grounded by a Foundry IQ Knowledge Base ([ADR 0021](adr/0021-agent-framework-foundry-iq-kb-default.md)) |
| v1 `conversation_without_data` / `stream_without_data` (Custom flow via Semantic Kernel) | `AgentFrameworkOrchestrator` (**default**) + `LangGraphOrchestrator` (registry-dispatched) | ✅ replaced | [v2/src/backend/core/providers/orchestrators/](../src/backend/core/providers/orchestrators/); ADRs 0004, 0007, 0016, 0017, 0021 |
| v1 `get_citations(...)` server-side citation shaping | SSE `citation` channel — FE renders | ✅ replaced (responsibility moved) | [v2/src/backend/core/providers/orchestrators/events.py](../src/backend/core/providers/orchestrators/events.py); ADR 0007 |
| `GET /api/assistanttype` (returns `"OpenAI"` literal) | n/a | ❌ removed | No client-side model selector in v2 — Foundry IQ owns model selection programmatically |
| `GET /api/checkauth` | Easy Auth `x-ms-client-principal` + `GET /api/admin/status` (whoami + role) | ✅ replaced | [v2/src/backend/routers/admin.py](../src/backend/routers/admin.py); ADR 0002 |
| `GET /api/files/<filename>` (serve uploaded files via Blob SAS) | n/a (admin can list/upload via `/api/admin/documents`; no public file-serve route) | ⏳ partial | Tracked in section M (Open gaps) |

### C. Admin surface

| v1 Streamlit page | v2 React route + backend | Status | Evidence |
|---|---|---|---|
| `Admin.py` (top-level tab shell) | React admin shell merged into frontend (per Phase 5) | ✅ replaced | Phase 5 closed; `#35d` FE merge ✅ cleared (2026-06-08) |
| `01_Ingest_Data.py` (URL + upload + reprocess) | `POST /api/admin/documents/url`, `POST /api/admin/documents`, `POST /api/admin/documents/reprocess` + IngestData FE route | ✅ replaced | `U-P7-53-BE` BE-1/2/3 + `U-P7-53-FE` |
| `02_Explore_Data.py` (chunk preview + search-against-index) | no v2 equivalent | ⏳ gap | Tracked in section M |
| `03_Delete_Data.py` (delete by source) | `GET /api/admin/documents`, `DELETE /api/admin/documents/{source}` + DeleteData FE | ✅ replaced | `U-P7-54-BE` + `#54` FE closed (`U-P7-AUDIT-4`) |
| `04_Configuration.py` (edit prompts + flags) | `GET/PATCH /api/admin/config` + Configuration FE route (PromptEditor persistence shipped with `#35d`) | ✅ replaced | All 9 admin routes per Per-Dimension Status; ADR 0003 |

### D. Ingestion + Search

| v1 surface | v2 surface | Status | Evidence |
|---|---|---|---|
| `bp_batch_start_processing` (HTTP trigger, scans Blob container, enqueues messages) | `functions/batch_start/blueprint.py` | ✅ replaced | Phase 6 done; smoke CI green |
| `bp_batch_push_results` (Queue trigger, processes chunks, pushes to Search) | `functions/batch_push/blueprint.py` | ✅ replaced | Phase 6 done; smoke CI green |
| `bp_add_url_embeddings` (HTTP trigger, URL ingest pipeline) | `functions/add_url/blueprint.py` | ✅ replaced | Phase 6 done; smoke CI green |
| `bp_get_conversation_response` (legacy HTTP chat) | n/a — chat is FastAPI (`/api/conversation`) | ❌ removed | Architectural; chat doesn't belong in Functions |
| `bp_combine_pages_and_chunknos` (post-processing chunk metadata restitching) | n/a | ⏳ gap | Tracked in section M |
| v1 search via `search_skill` Azure Function (cognitive skill) | `functions/search_skill/blueprint.py` | ✅ replaced | Phase 6 done |
| v1 direct Form Recognizer SDK calls | `azure-ai-documentintelligence` via parser registry | ✅ replaced | `U-P7-B0` SDK swap; ADR 0001 |
| v1 direct `AzureSearch` SDK chunks | Foundry IQ knowledge sources + `azure-search-documents` via search registry | ✅ replaced | ADRs 0001, 0004 |

### E. Chat history

| v1 blueprint route | v2 route | Status |
|---|---|---|
| `GET /history/list` | `GET /api/history/conversations` (paginated) | ✅ replaced |
| `POST /history/read` | `GET /api/history/conversations/{id}` | ✅ replaced |
| `POST /history/rename` | `PATCH /api/history/conversations/{id}` | ✅ replaced |
| `DELETE /history/delete` | `DELETE /api/history/conversations/{id}` (204, idempotent) | ✅ replaced |
| `DELETE /history/delete_all` | (covered by per-conversation DELETE; bulk-delete deferred) | ⏳ partial |
| `POST /history/update` | `POST /api/history/conversations/{id}/messages` (append) + `POST /api/history/conversations` (create) | ✅ replaced |
| `GET /history/frontend_settings` | `GET /api/history/status` (feature flag surface) | ✅ replaced |
| (n/a in v1) | `POST /api/history/messages/{message_id}/feedback` (#32b) | ➕ added in v2 |
| Cosmos-only backend | Cosmos + Postgres both registered under `databases` registry | ✅ expanded |

Fail-closed `get_user_id` (401 in prod; `local-dev` only when `Environment.LOCAL`) — see Per-Dimension Status > Chat History row.

### F. Speech

v1 `GET /api/speech` → v2 `GET /api/speech` (kept; equivalent surface; same Azure AI Speech token-issuing pattern). Implementation: [v2/src/backend/routers/speech.py](../src/backend/routers/speech.py).

### G. Auth

| v1 | v2 | Status |
|---|---|---|
| App Service Easy Auth + custom `/api/checkauth` JSON | Easy Auth on ACA + `x-ms-client-principal` parsing + `requires_role("admin")` RBAC gate | ✅ replaced (`#39` cleared 2026-05-06) |
| Anonymous endpoints (toggle) | Same toggle preserved for `local-dev` only; prod fails closed | ✅ ported (hardened) |
| v1 Key Vault for app secrets | n/a — RBAC + UAMI + direct env vars (MACAE pattern) | 🚫 removed-by-design (§2.1; ADR 0002) |

### H. Orchestrators

| v1 orchestrator | v2 orchestrator | Status |
|---|---|---|
| Prompt Flow DAG | n/a | 🚫 removed-by-design (§2.1) |
| Semantic Kernel | n/a | 🚫 removed-by-design (§2.1) |
| LangChain `ZeroShotAgent` / `AgentExecutor` | `LangGraphOrchestrator` | ✅ replaced (ADR 0007) |
| Custom Python conversation flow (`OrchestratorBase`) | `AgentFrameworkOrchestrator` (OSS MAF + Foundry IQ runtime) | ✅ replaced (ADRs 0004, 0008, 0016, 0017) |
| BYOD (Azure OpenAI `data_sources`) | n/a | 🚫 removed-by-design (§2.1; Hard Rule #7) |

All v2 orchestrators implement the shared async interface (Hard Rule #5) and emit typed events on `reasoning`/`tool`/`answer`/`citation`/`error` SSE channels (Hard Rule #6, ADR 0007).

### I. Scenarios (Scenario Pack pillar)

v1 baked scenario content (contract assistance, employee assistance) into the core distribution under `data/contract_data/` and example docs. v2 reclassifies these as **Scenario Pack** pillar (per [pillars_of_development.md](pillars_of_development.md)) — opt-in, not in Stable Core. The reference scenario docs are preserved at `docs/contract_assistance.md` + `docs/employee_assistance.md` and reclassified `📄 docs-only` in subsection J below; no Stable Core wiring depends on them.

### J. Infra + deploy

| v1 | v2 | Status | Evidence |
|---|---|---|---|
| One-click "Deploy to Azure" ARM button | n/a — `azd up` only | 🚫 removed-by-design (§2.1; Hard Rule #7) |
| App Service hosting | Azure Container Apps (backend + function), App Service (frontend SPA) | ✅ replaced | [v2/azure.yaml](../azure.yaml) services block |
| Ad-hoc Bicep modules | AVM-first Bicep + UAMI + RBAC + no Key Vault for app secrets | ✅ replaced | [v2/infra/main.bicep](../infra/main.bicep); ADR 0002 |
| Azure Monitor workbook | Same workbook ported | ✅ ported | [v2/infra/workbooks/](../infra/workbooks/) |
| Prompt Flow Bicep module | n/a | 🚫 removed-by-design (§2.1) |
| Teams bot infra | n/a | 🚫 removed-by-design (§2.1) |
| Manual quota check scripts | AVM quota checks + `v2/scripts/post-provision.{sh,ps1}` | ✅ replaced |
| Poetry / pip / requirements.txt sprawl | `uv` + single `pyproject.toml` per surface | ✅ replaced (§2.1) |

### K. Removed-by-design (binding — never re-introduce)

This table mirrors [development_plan.md](development_plan.md) §2.1 verbatim. Hard Rule #7 makes every row binding.

| Component | Reason |
|---|---|
| One-click "Deploy to Azure" button | Simplify to `azd`-only; ARM template maintenance overhead |
| Poetry references | Fully standardized on `uv`; remove any lingering Poetry config |
| Prompt Flow orchestrator | Replaced by Agent Framework; drops Azure ML dependency |
| Semantic Kernel orchestrator | Consolidate to fewer, more strategic orchestrators |
| Streamlit admin app | Admin features merged into the React/Vite frontend (Phase 5) |
| Direct Azure OpenAI SDK | Replaced by Foundry IQ for knowledge base, embeddings, chat, reasoning |
| Azure Bot Service / Teams extension | Deferred to a future version |
| Key Vault for app secrets | Replaced by RBAC + UAMI + direct env vars (MACAE pattern) |
| BYOD conversation flow (`CONVERSATION_FLOW=byod` in v1) | Incompatible with Hard Rules #4/#5/#6/#7; v2 ships the Custom flow only |

### L. Library + architectural decision crosswalk (ADRs 0001–0017)

| ADR | Decision | v1 state (before) | v2 state (after) | Status | Evidence |
|---|---|---|---|---|---|
| [0001](adr/0001-registry-over-factory-dispatch.md) | Registry over factory dispatch | `if/elif provider == "x"` factories | `Registry[T]` + `@registry.register("key")` self-registration; 8 domains | ✅ live | `v2/src/backend/core/providers/<domain>/registry.py`; Hard Rule #4 |
| [0002](adr/0002-no-key-vault-uami-rbac.md) | No Key Vault for app secrets | Key Vault + connection strings | UAMI + RBAC + direct env vars (MACAE pattern) | ✅ live | [v2/infra/main.bicep](../infra/main.bicep); §2.1 |
| [0003](adr/0003-pydantic-settings-over-envhelper.md) | Pydantic Settings over EnvHelper | `EnvHelper` singleton, dict-shaped | Pydantic v2 `BaseSettings` + nested DB-backed `RuntimeConfig` | ✅ live | [v2/src/backend/core/settings.py](../src/backend/core/settings.py) |
| [0004](adr/0004-foundry-iq-no-openai-sdk-import.md) | Foundry IQ — no direct OpenAI SDK | Direct `openai`/`AzureOpenAI` SDK calls | Foundry IQ runtime; zero `openai` imports in `v2/src/**` | ✅ live | `grep -r "^import openai\|from openai" v2/src/` → 0 |
| [0005](adr/0005-credential-and-llm-singleton-via-lifespan.md) | Credential + LLM singleton via FastAPI lifespan | Per-request client creation | Lifespan-managed singletons in `app.state` | ✅ live | [v2/src/backend/main.py](../src/backend/main.py) lifespan |
| [0006](adr/0006-health-endpoint-split.md) | Health endpoint split (liveness / readiness) | Single `/api/health` boolean | `/api/health` (liveness) + `/api/health/ready` (full dependency probe) | ✅ live | [v2/src/backend/routers/health.py](../src/backend/routers/health.py) |
| [0007](adr/0007-orchestrator-event-typed-sse-channel.md) | `OrchestratorEvent` typed SSE channel | String-tagged events in answer body | Typed `OrchestratorEvent` on 5 channels (`reasoning`, `tool`, `answer`, `citation`, `error`) | ✅ live | [v2/src/backend/core/providers/orchestrators/events.py](../src/backend/core/providers/orchestrators/events.py); Hard Rule #6 |
| [0008](adr/0008-lazy-foundry-agent-bootstrap.md) | Lazy `FoundryAgent` bootstrap | n/a | Bootstrap on first request; failure isolated to that request | ✅ live | `B-IMPL-FACTORY-CACHE` (caching layer) tracked in §0.1 |
| [0009](adr/0009-single-owner-no-separate-team-framing.md) | Single-owner — no separate team framing | n/a | Solo-maintainer mental model in docs + workflow | ✅ procedural |
| [0010](adr/0010-chronological-debt-queue-drainage.md) | Chronological debt queue drainage | Ad-hoc TODOs scattered | §0.1 / §0.2 ledger; drained per-phase (Hard Rule #12) | ✅ live | [development_plan.md](development_plan.md) §0.1 + §0.2 |
| [0011](adr/0011-frontend-model-extraction.md) | Frontend model extraction | n/a | TS models in `v2/src/frontend/src/models/`; OpenAPI client generated | ✅ live | [v2/src/frontend/src/models/](../src/frontend/src/models/) |
| [0012](adr/0012-frontend-test-folder-mirror.md) | Frontend test folder mirror | n/a | `v2/src/frontend/tests/` mirrors `src/` 1:1 | ✅ live | [v2/src/frontend/tests/](../src/frontend/tests/) |
| [0013](adr/0013-frontend-strict-ts-and-tsx-everywhere.md) | Strict TS + `.tsx` everywhere | n/a | TS strict; every first-party file uses `.tsx` | ✅ live | [v2/src/frontend/tsconfig.json](../src/frontend/tsconfig.json); Hard Rule #11 |
| [0014](adr/0014-frontend-ci-workflow.md) | Frontend CI workflow | n/a | `v2-frontend-checks.yml` (lint + tsc + vitest) | ✅ live | [.github/workflows/v2-frontend-checks.yml](../../.github/workflows/v2-frontend-checks.yml) |
| [0015](adr/0015-frontend-path-alias-cross-folder-imports.md) | Frontend path alias for cross-folder imports | n/a | `@/` alias wired in Vite + tsconfig | ✅ live | [v2/src/frontend/vite.config.ts](../src/frontend/vite.config.ts) |
| [0016](adr/0016-agent-framework-foundry-iq-tas27-parity-review.md) | Agent Framework + Foundry IQ TAS-27 parity review | n/a | Parity audit closing OSS-SDK-vs-internal gap | ✅ recorded |
| [0017](adr/0017-agent-framework-foundry-pinned-dependency-policy.md) | Agent Framework + Foundry pinned dependency policy | n/a | `agent-framework-core>=1.7,<2.0` + `agent-framework-foundry>=1.7,<2.0` exact pins | ✅ live | [v2/pyproject.toml](../pyproject.toml); see Libraries section |

All 17 ADRs are live or recorded; none reverted. ADR index: [adr/README.md](adr/README.md).

### M. Open gaps (v1 surface without v2 equivalent AND not on §2.1 removal list)

Three small gaps surfaced in the audit. None block the QA acceptance gate. Each maps to a tracked debt row or is logged here for future scheduling.

| Gap | v1 source | v2 status | Disposition |
|---|---|---|---|
| Public file-serve route | v1 `GET /api/files/<filename>` (Blob SAS-backed) | No v2 user-facing serve route; admin can list/upload via `/api/admin/documents` | ⏳ deferred — citation rendering returns Foundry IQ source URIs; standalone serve route not needed unless reintroduced |
| Explore Data admin page | v1 `code/backend/pages/02_Explore_Data.py` (chunk preview + index search) | No v2 React route | ⏳ deferred — chunk inspection not on Phase 5/7 backlog; can re-scope as Customization Layer if requested |
| Page-number restitching pipeline | v1 `bp_combine_pages_and_chunknos` Function | No v2 equivalent | ⏳ tracked — depends on whether Foundry IQ knowledge sources need post-processing chunk metadata; revisit after first cloud E2E |
| `DELETE /history/delete_all` (bulk) | v1 chat_history blueprint | No v2 bulk delete; per-conversation DELETE only | ⏳ deferred — per-row DELETE covers UI need; bulk-delete deferred until customer ask |

Gaps that are **already tracked in §0.1 / §0.2** (mirror — do not re-list here, see Per-Dimension Status > Open Debt by Dimension): `B-IMPL-FACTORY-CACHE`, `B-IMPL-EXTRAS`, `B-IMPL-FOUNDRY-STUBS-DEBT`, `DV1`. (`#35d`, `#24`, `#54` closed at Phase 7 close 2026-06-08; `#35g` withdrawn — see [ADR 0024](adr/0024-withdraw-per-tenant-runtime-config-single-tenant.md).)

### Pending v1 docs that need a v2 counterpart (not blocking)

Three v1 docs describe concepts that still apply in v2 but lack a v2-side authored guide. Same status as Bucket M gaps — deferred, not blocking. Track ad-hoc in a future doc sprint.

| v1 doc | v2 mapping | Status |
|---|---|---|
| [docs/advanced_image_processing.md](../../docs/advanced_image_processing.md) | `document_intelligence_parser` exists (Phase 6 U8m); user-facing enable guide missing | ⏳ pending |
| [docs/conversation_flow_options.md](../../docs/conversation_flow_options.md) | Orchestrators handle multi-turn; design guide missing | ⏳ pending |
| [docs/integrated_vectorization.md](../../docs/integrated_vectorization.md) | v2 uses client-side embedder; if integrated-vectorization pivot happens, doc this | ⏳ pending |

---

## Open Debt by Dimension

### Backend (`development_plan.md` §0.1)

| ID | Item | Status |
|---|---|---|
| `#35d` | FE admin route merge — backend surface + React merge complete | ✅ cleared (2026-06-08, `U-P7-35D-AUDIT`) |
| `#35g` | Per-tenant config overrides | — withdrawn (out of scope, single-tenant); [ADR 0024](adr/0024-withdraw-per-tenant-runtime-config-single-tenant.md) supersedes ADR 0023 |
| `B-IMPL-FACTORY-CACHE` | Cache `FoundryAgent` instances at orchestrator registry layer | ☐ open — post-Phase-7 hardening |
| `B-IMPL-EXTRAS` | OSS MAF multi-agent demos (Magentic, Handoff, workflows) | ☐ deferred — awaiting concrete demand |
| `B-IMPL-FOUNDRY-STUBS-DEBT` | `agent_framework_foundry` PyPI distribution missing `py.typed` | ☐ open — upstream OSS SDK |

### Frontend (`development_plan.md` §0.2)

| ID | Item | Status |
|---|---|---|
| `DV1` | Re-verify `docker compose build frontend` | ⏸ blocked (Docker daemon down on dev machine) |
| `#24` | FE SSE wiring — citation cards, abort/cancel, retry, multi-turn UX | ✅ cleared (2026-06-08, `U-P7-AUDIT-4` A2.1–A2.5) |

### `#39`-blocked items

**None.** `#35g` was previously listed here as blocked on `#39` tenant claim propagation; it is now **withdrawn as out of scope** — the deployment is single-tenant, so tenant-keyed config is a no-op over the singleton (see [ADR 0024](adr/0024-withdraw-per-tenant-runtime-config-single-tenant.md), which supersedes ADR 0023). `#39` itself (`requires_role("admin")`) shipped 2026-05-06.

---

## Recommended Acceptance Gate

A v2 build is QA-ready when **all** of the following are simultaneously green from a fresh clone:

1. `cd v2 ; uv sync` succeeds.
2. `cd v2 ; uv run pyright src/backend src/functions` returns `0 errors / 0 warnings / 0 informations`.
3. `cd v2 ; uv run pytest -q` returns `1986 passed / 1 skipped / 3 deselected / 4 warnings` (or higher pass count after additions, zero failures).
4. `cd v2 ; uv run pytest tests/shared tests/test_no_silent_excepts.py -q` returns all 9 AST gates green.
5. From `v2/src/frontend`: `npm install` then `npm test -- --run` returns `147 passed / 18 suites` (or higher), `npm run lint` returns `0 errors`, `npx tsc --noEmit` is clean.
6. `docker compose -f v2/docker/docker-compose.dev.yml --profile backend-only up` boots the backend headless (no frontend dependency).
7. `docker compose -f v2/docker/docker-compose.dev.yml --profile frontend-only up` boots the frontend with `VITE_BACKEND_URL` pointed at the backend.
8. Manual smoke against the deployed `azd up` environment exercises: chat with reasoning panel; admin status; admin config PATCH; document upload; document delete; chat history list + rename + feedback.

Detailed sub-checks for each gate live in [qa_review_plan.md](qa_review_plan.md).

---

## Local run readiness

**Single-command boot path** (from repo root):

```
docker compose -f v2/docker/docker-compose.dev.yml up -d --build
```

Containers: `cwyd-v2-backend` (port 8000) + `cwyd-v2-frontend` (port 5173) + `cwyd-v2-postgres` (port 5432) + `cwyd-v2-azurite` (port 10000). Wait ≤120 s for the backend healthcheck to pass.

**4 checks that constitute "local OK"**:

| # | Check | How to verify |
|---|---|---|
| 1 | Backend boots + health probe responds | `curl http://localhost:8000/api/health` → 200 with `{status, version: "v2", checks: [...]}` |
| 2 | OpenAPI surface is complete | `curl http://localhost:8000/openapi.json` lists `/api/conversation`, all 9 `/api/admin/*` routes, all 8 `/api/history/*` routes |
| 3 | Chat round-trip works end-to-end | POST to `/api/conversation`, observe SSE `reasoning` + `answer` + ≥1 `citation` event (requires real Foundry IQ + Search creds in `.env`) |
| 4 | Admin PATCH live-reload | `PATCH /api/admin/config` → next request reflects the new value (no restart needed) |

Backend-only and frontend-only profiles are both supported per Hard Rule #4 plug-and-play:

```
docker compose -f v2/docker/docker-compose.dev.yml --profile backend-only up
docker compose -f v2/docker/docker-compose.dev.yml --profile frontend-only up   # set VITE_BACKEND_URL
```

Tear-down: `docker compose -f v2/docker/docker-compose.dev.yml down -v`.

---

## Cloud deploy readiness

**Single-command deploy path** (from `v2/`):

```
cd v2
azd auth login           # interactive: pick subscription
azd up                   # interactive: env name, region, 6 azure.yaml prompts
```

All Bicep parameters have defaults in [v2/infra/main.parameters.json](../infra/main.parameters.json) (Bash-style `${VAR=default}` fallback). The 6 interactive prompts declared in [v2/azure.yaml](../azure.yaml) (`databaseType`, `azureAiServiceLocation`, `enableMonitoring`, `enableScalability`, `enableRedundancy`, `enablePrivateNetworking`) are surfaced by `azd up` and captured into the azd env file. No pre-flight `azd env set` calls required.

**8 checks that constitute "cloud OK"** (mirrors [qa_review_plan.md](qa_review_plan.md) Phase J2 manual QA matrix):

| # | Scenario | Pass criterion |
|---|---|---|
| 1 | Cold `azd up` succeeds | `azd provision` + `azd deploy` + `postprovision` hook all return 0 |
| 2 | Health probe | `GET <backend>/api/health` and `/api/health/ready` both return 200 |
| 3 | OpenAPI surface | Deployed `/openapi.json` lists every expected route |
| 4 | Chat round-trip | SSE `reasoning` + `answer` + ≥1 `citation` event from real Foundry IQ + Search |
| 5 | Admin PATCH live-reload | Change a setting → next chat request reflects the new value |
| 6 | History persist + resume | Send 3 messages → reload → reopen → resume |
| 7 | Delete by source | Admin → delete data → confirm removal from search index |
| 8 | Backend-agnostic DB | The chosen `databaseType` works; the other backend's CI gate already passed |

**Tear-down (cost control)**: `azd down --purge --force` from `v2/`. Per user direction, the stack is left running after first deploy validation.

---

## Local run validation 2026-06-05 — BLOCKED

A QA-driven attempt to boot the local stack from a fresh `docker compose up -d --build` and run the `backend-only` smoke suite surfaced a real regression that affects both the local dev story and the `v2-backend-only-smoke` GitHub Actions workflow.

### Observed

| Surface | Result |
|---|---|
| `docker compose -f v2/docker/docker-compose.dev.yml up -d --build` | 5 containers process-up (`cwyd-v2-backend`, `cwyd-v2-frontend`, `cwyd-v2-postgres`, `cwyd-v2-azurite`, `cwyd-v2-functions`). |
| `cwyd-v2-postgres` healthcheck | ✅ healthy. |
| `cwyd-v2-backend` healthcheck | ❌ unhealthy after 120 s. Lifespan crashes; uvicorn exits; healthcheck never reaches `/api/health`. |
| `docker compose ... -f v2/docker/docker-compose.smoke.yml --profile backend-only up -d --build` (the CI configuration verbatim) | ❌ same crash. The smoke overlay clears `env_file: ../.env` and injects dummy Foundry/OpenAI/identity values, but it does not override the Postgres dispatch defaults baked into the dev compose file. |
| `cd v2 ; uv run pytest -m smoke tests/smoke/` | ⏸ not attempted — preconditioned on a healthy backend. |

### Root cause

Backend lifespan ([v2/src/backend/app.py](../src/backend/app.py) line 125) calls `database_client.get_runtime_config()` unconditionally on startup. With `AZURE_DB_TYPE=postgresql` selected (the dev compose default and the smoke overlay default), that call routes through `PostgresClient._ensure_pool` ([v2/src/backend/core/providers/databases/postgres.py](../src/backend/core/providers/databases/postgres.py) line 301), which raises:

```
RuntimeError: AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME is not set.
PostgresClient requires the Entra principal name to connect as.
```

The dev compose file pins `AZURE_POSTGRES_ENDPOINT=postgresql://cwyd:cwyd@postgres:5432/cwyd?sslmode=disable` (a vanilla `pgvector/pgvector:pg16` container) but the v2 `PostgresClient` is hardwired to AAD-token authentication — `_password_provider` calls `self._credential.get_token(AadScope.POSTGRES_FLEX)`. There is no plain-password / dev fallback path. Setting `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME=cwyd` would clear the strict-name check but the subsequent `asyncpg.create_pool(..., password=self._password_provider, ...)` would issue an AAD token that the vanilla pgvector container cannot validate.

### Regression timeline

| Commit | Date | Effect |
|---|---|---|
| `fcd1b45 "Move shared package to backend/core"` | early May 2026 | Introduced the strict `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME is not set` runtime check in `PostgresClient._ensure_pool`. |
| `e62c07b "Add search_skill and backend-only smoke CI"` | Thu May 28 12:07 ET | Shipped `.github/workflows/v2-backend-only-smoke.yml` + `tests/smoke/test_backend_only.py`. Presumably green at the time. |
| `da5a0f9 "Respect runtime override for content safety guard"` | Thu May 28 22:36 ET | Added `app.state.runtime_overrides = await database_client.get_runtime_config()` to lifespan — now lifespan calls `_ensure_pool()` unconditionally on every backend boot when `AZURE_DB_TYPE=postgresql`. **The smoke CI has been silently broken since this commit.** |
| `958f0e1 "Support plugin discovery and pgvector schema"` | Tue Jun 2 2026 | Added unconditional `await search_provider.ensure_schema()` in lifespan — second consumer of the same pool, same failure mode. |

### Acceptance Gate impact

This invalidates **two rows** of the [Recommended Acceptance Gate](#recommended-acceptance-gate) above on a fresh clone:

- Gate 6 (`docker compose ... --profile backend-only up boots the backend headless`) — currently fails.
- Gate 7 (`docker compose ... --profile frontend-only up`) — frontend itself boots, but the demo path against `VITE_BACKEND_URL=http://localhost:8000` cannot exercise live chat because the backend never reaches healthy.

The pyright / pytest / vitest / lint / OpenAPI gates are unaffected — this is a runtime / wiring regression, not a type or unit-test regression.

### Required fix (separate, planned work — not in scope for this QA pass)

The discovered gap requires a deliberate one-unit change governed by Hard Rules #0, #1, #10. Two reasonable shapes (the actual choice is a future design decision the user must direct):

1. **Add a `local_dev` credential mode** to `PostgresClient` that uses a static password from env (`AZURE_POSTGRES_PASSWORD`) when set, falling back to the existing AAD path otherwise. Adds one settings field, one branch in `_password_provider`, no registry change. Smallest blast radius.
2. **Register a separate `postgres_local` provider** under `providers.databases` that always uses plain-password auth, and switch the dev compose `AZURE_DB_TYPE` to that key. Larger surface (new provider class + tests + registry registration) but keeps the production `PostgresClient` AAD-only with zero conditionals.

Either option must also (a) re-green the smoke CI workflow, and (b) add a regression test that boots the lifespan in dev mode and asserts `/api/health` returns 200. Track as a new `DV2` row alongside `DV1` in [Open Debt by Dimension](#open-debt-by-dimension) once the user picks a shape.

### Cloud path is unaffected

The cloud deploy path is **not** impaired by this regression: the Bicep wires `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` from the UAMI's display name, the UAMI is granted the Entra-DB-admin role on the Postgres Flexible Server, and `AadScope.POSTGRES_FLEX` token acquisition works against the real service. The regression bites only configurations where the database side cannot honor an AAD token — i.e., the vanilla pgvector container in `docker-compose.dev.yml`.

Cloud deploy validation therefore proceeds on its own track in the [Cloud deploy readiness](#cloud-deploy-readiness) section above.
