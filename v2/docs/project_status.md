---
title: CWYD v2 — Project Status Snapshot
description: Current QA-readiness snapshot of CWYD v2, organized by review dimension. Replaces the stale qa_report_v2 narrative.
author: CWYD Engineering
ms.date: 2026-06-04
topic: status
keywords: status, qa, readiness, v2, snapshot
estimated_reading_time: 8
---

# CWYD v2 — Project Status Snapshot

This document is the **per-dimension QA readiness snapshot** of CWYD v2 for the QA review team. It is the entry point for the structured review that lives in [qa_review_plan.md](qa_review_plan.md) and is anchored against the canonical [development_plan.md](development_plan.md) (§0 status table + §0.1 / §0.2 debt queues).

For the historical, Phase 3.5-era QA report kept for archeology only, see [qa_report_v2.archived.md](qa_report_v2.archived.md).

---

## Executive Status

**Phase 7 backend tier is drained.** As of `U-P7-AUDIT-3` (2026-06-02), every backend §0.1 debt row originating in Phases 1–7 is ✅ cleared except a small handful that are externally blocked (FE-owned, upstream OSS SDK, or gated on `#39` tenant claim propagation). All 9 AST gates are green. Backend full suite runs `2047 passed / 1 skipped / 3 deselected / 6 warnings` as of the 2026-06-04 QA review baseline (up from 1986 passes on 2026-06-02; the two extra warnings are upstream `agent_framework` experimental notices). `pyright src/backend src/functions` is `0 errors / 0 warnings / 0 informations`.

**Phase 7 frontend tier is in progress.** `#50` feedback thumbs and `#53` Ingest Data admin UI (backend half) are ✅ done; `#54` Delete Data admin UI is ⏳ partial (backend route + ABC + 2 impls shipped, FE multi-select half open); `#35d` Streamlit-to-React admin merge is ⏳ in progress on the FE tier (prompt-editor route shell + Section-based dispatch refactor shipped 2026-06-04); `#24` SSE FE wiring is ⏳ partial (demo path live; citation cards / abort / reconnect remain on FE backlog). The FE conventions refactor (`U-P7-FE-REFAC`, 6 units) closed 2026-06-02; current FE numbers as of 2026-06-04 are `npm run lint` 0 errors / 7 advisory `react-refresh/only-export-components` warnings on the new admin pages, `npx tsc --noEmit` clean, and `vitest 361 tests / 32 suites` green.

---

## Verified Metrics (2026-06-04)

| Surface | Tool | Result |
|---|---|---|
| Backend test suite | `cd v2 ; uv run pytest -q` | 2047 passed / 1 skipped / 3 deselected / 6 warnings |
| Backend type check | `cd v2 ; uv run pyright src/backend src/functions` | 0 errors / 0 warnings / 0 informations |
| AST invariant gates | `uv run pytest tests/shared tests/test_no_silent_excepts.py -q` | 981 passed / 1 skipped — 9 gates green (8 tree-walking + 1 silent-except + router-only) |
| Frontend unit suite | `npm test -- --run` from `v2/src/frontend` | 361 passed / 32 suites |
| Frontend lint | `npm run lint` from `v2/src/frontend` | 0 errors / 7 react-refresh advisory warnings (HMR fast-refresh hints on Configuration / DeleteData / IngestData / ChatContext / themeContext — non-blocking) |
| Frontend type check | `npx tsc --noEmit` from `v2/src/frontend` | clean |

The two extra backend warnings (vs. 2026-06-02 baseline) are upstream `agent_framework` experimental notices for `SkillResource` and `MemoryStore`. The three additional FE lint warnings (vs. 2026-06-02 baseline) are new admin page modules that co-export helpers alongside their default component — advisory only.

Re-run baselines via [qa_review_plan.md](qa_review_plan.md) Phase B (validation snapshot).

---

## Per-Dimension Status

### Hard Rules (17 active in `.github/copilot-instructions.md`)

| # | Rule | Status |
|---|---|---|
| 0 | Step 0 — sync agent guidance before any change | ✅ enforced procedurally |
| 1 | One unit per turn (class or method) | ✅ enforced procedurally |
| 2 | Test-first contract | ✅ enforced procedurally |
| 3 | `Pillar:` / `Phase:` docstring header | ✅ AST gate `test_pillar_phase_header.py` |
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
| `requires_role("admin")` Easy Auth RBAC gate | ✅ shipped (#39) |
| `POST /api/admin/documents/url` (URL ingest) | ✅ shipped (`U-P7-53-BE` BE-1) |
| `POST /api/admin/documents` (multipart upload, 50 MiB cap) | ✅ shipped (`U-P7-53-BE` BE-2) |
| `POST /api/admin/documents/reprocess` (reprocess all in container) | ✅ shipped (`U-P7-53-BE` BE-3) |
| `DELETE /api/admin/documents/{source}` (delete by source) | ✅ shipped (`U-P7-54-BE`) |
| Per-tenant config overrides | ☐ blocked on `#39` tenant claim propagation (`#35g`) |
| FE admin route merge | ⏳ in progress (`#35d`) |

### Chat History

| Route | Status |
|---|---|
| `GET /api/history/status` | ✅ shipped |
| `GET /api/history/conversations` | ✅ shipped |
| `POST /api/history/conversations` | ✅ shipped |
| `GET /api/history/conversations/{id}` | ✅ shipped |
| `PATCH /api/history/conversations/{id}` (rename) | ✅ shipped |
| `POST /api/history/messages/{message_id}/feedback` | ✅ shipped (#32b) |
| Cosmos + Postgres provider impls | ✅ both registered under `databases` registry |
| Fail-closed `get_user_id` (401 in prod, `local-dev` only when `Environment.LOCAL`) | ✅ shipped + `requires_role` parity |

### Phases

| Phase | Status | Notes |
|---|---|---|
| 1 — Infrastructure + Project Skeleton | ✅ done | Bicep AVM-first, UAMI + RBAC, no Key Vault, `post_provision.sh` |
| 2 — Configuration + LLM Integration | ✅ done | `shared` → `backend/core` consolidated in 5.5 |
| 3 — Conversation + RAG (Core Chat) | ✅ done | LangGraph + Agent Framework orchestrators, AzureSearch + pgvector handlers |
| 3.5 — QA Remediation | ✅ done | Q1–Q14 + Q10 structural realignment |
| 4 — Chat History + Both Databases | ✅ done | Cosmos + Postgres clients + pgvector injected pool |
| 5 — Admin + Frontend Merge | ✅ done (backend); ⏳ in progress (FE `#35d`) | All 7 admin routes + RBAC shipped |
| 5.5 — Stable Core Refactor | ✅ done | `shared/` → `backend/core/` + `functions/core/` + `try/except` policy + 29 SDK boundary wraps |
| 6 — RAG Indexing Pipeline (Split Functions) | ✅ done | 4 blueprints (`batch_start`, `batch_push`, `add_url`, `search_skill`) + standalone-backend smoke CI |
| 7 — Testing + Documentation | ⏳ in progress | Backend tier drained 2026-06-02; FE tier in progress |

---

## Open Debt by Dimension

### Backend (`development_plan.md` §0.1)

| ID | Item | Status |
|---|---|---|
| `#35d` | FE admin route merge — FE-team-owned; backend surface complete | ⏳ in progress |
| `#35g` | Per-tenant config overrides | ☐ open — blocked on `#39` tenant claim propagation |
| `B-IMPL-FACTORY-CACHE` | Cache `FoundryAgent` instances at orchestrator registry layer | ☐ open — post-Phase-7 hardening |
| `B-IMPL-EXTRAS` | OSS MAF multi-agent demos (Magentic, Handoff, workflows) | ☐ deferred — awaiting concrete demand |
| `B-IMPL-FOUNDRY-STUBS-DEBT` | `agent_framework_foundry` PyPI distribution missing `py.typed` | ☐ open — upstream OSS SDK |

### Frontend (`development_plan.md` §0.2)

| ID | Item | Status |
|---|---|---|
| `DV1` | Re-verify `docker compose build frontend` | ⏸ blocked (Docker daemon down on dev machine) |
| `#24` | FE SSE wiring — citation cards, abort/cancel, reconnect, multi-turn UX polish | ⏳ partial (demo path live since 2026-05-07) |

### `#39`-blocked items

`#35g` is the only backend row formally blocked on `#39` tenant claim propagation. `#39` itself is ✅ cleared (`requires_role("admin")` gate shipped 2026-05-06) — `#35g` waits for tenant-id propagation in the Easy Auth principal claims surface, a separate slice not yet scheduled.

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
