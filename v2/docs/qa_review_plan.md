---
title: CWYD v2 — QA Review Plan
description: Phase-by-phase QA review checklist for CWYD v2. Drives the structured QA pass against the dimensions enumerated in project_status.md.
author: CWYD Engineering
ms.date: 2026-06-04
topic: qa-plan
keywords: qa, review, plan, v2, checklist
estimated_reading_time: 15
---

# CWYD v2 — QA Review Plan

This document is the **structured QA review checklist** for CWYD v2. It pairs with the per-dimension snapshot in [project_status.md](project_status.md) and stays anchored against the canonical [development_plan.md](development_plan.md) (§0 status table, §0.1 backend debt queue, §0.2 frontend debt queue, §4 task ledger).

Each phase below (B–J) carries one-unit-per-turn sub-tasks. Every sub-task has:

- **Acceptance criteria** — the binary pass/fail signal.
- **Evidence pointer** — file path / grep pattern / command that produces the proof.
- **Default outcome** — what "compliant" looks like today; deviations open a tracked debt row in dev_plan §0.1 (never patched inline per Hard Rule #12).

Phase A — snapshot + archive — closed 2026-06-04 (see [project_status.md](project_status.md) and [qa_report_v2.archived.md](qa_report_v2.archived.md)).

---

## Phase B — Validation snapshot baseline

Re-run the four baseline checks before the QA pass starts. Numbers go into [project_status.md](project_status.md) "Verified Metrics" table. Any drift from the recorded baseline blocks the QA pass.

Baseline recorded **2026-06-04** (matches [project_status.md](project_status.md) Verified Metrics). Re-run before every QA pass; record the *current* triplet and flag any *regression* (failures or new errors). Advisory-warning growth is non-blocking provided it remains `react-refresh/only-export-components` HMR hints or upstream-SDK experimental notices.

| Unit | Description | Command | Acceptance (2026-06-04 baseline) |
|---|---|---|---|
| B1 | Scoped pyright | `cd v2 ; uv run --project . pyright src/backend src/functions` | `0 errors, 0 warnings, 0 informations` |
| B2 | Backend pytest | `cd v2 ; uv run pytest -q --tb=no` | `2047 passed, 1 skipped, 3 deselected, 6 warnings`, 0 failed |
| B3 | Frontend triple gate | `cd v2/src/frontend ; npm test -- --run ; npm run lint ; npx tsc --noEmit` | `361 tests / 32 suites passed`, lint `0 errors` (≤ 7 advisory warnings, all `react-refresh/only-export-components`), tsc clean |
| B4 | AST gate sweep | `cd v2 ; uv run pytest tests/shared tests/test_no_silent_excepts.py -q` | `981 passed, 1 skipped` — all 9 gates green (`test_imports_at_top_only`, `test_init_files_are_marker_only`, `test_no_anonymous_dict_returns`, `test_no_legacy_shared_imports`, `test_no_process_narrative_in_src`, `test_no_type_checking_or_future_annotations`, `test_pillar_phase_header`, `test_routers_contain_only_routes`, `test_no_silent_excepts`) |

**Evidence file pointers**

- Scoped-pyright contract recorded in dev_plan §2.3.
- AST gate sources: [v2/tests/shared/](../tests/shared/) + [v2/tests/test_no_silent_excepts.py](../tests/test_no_silent_excepts.py).

---

## Phase C — Hard Rules 1–17 compliance audit

Walk every Hard Rule from [.github/copilot-instructions.md](../../.github/copilot-instructions.md). One rule per turn. Each row records: rule shorthand, enforcement (AST gate if any), spot-check command, default outcome, debt pointer if non-compliant.

| Unit | Rule | Enforcement | Spot-check | Default outcome |
|---|---|---|---|---|
| C1 | #1 One unit per turn | Convention | `git log --oneline -- v2/src/ | head -30` — diffs should be small (1 class / 1 method + tests) | Compliant — workflow contract holds |
| C2 | #2 Test-first | Convention | `grep -RL "^def test_" v2/src/**/tests/` — every prod module pairs with a test sibling | Compliant — Phase 7 backend tier left 0 untested units |
| C3 | #3 Pillar header | AST gate `test_pillar_phase_header.py` | `cd v2 ; uv run pytest tests/shared/test_pillar_phase_header.py -q` | Green |
| C4 | #4 Registry dispatch | Manual + convention | `grep -RnE "^(if|elif).*provider" v2/src/backend/core/providers/` — zero hits | Compliant — 8 registries enforce dispatch |
| C5 | #5 Multi-agent ready | Convention | `grep -Rn "class.*Orchestrator.*Base" v2/src/backend/core/providers/orchestrators/` — base ABC + ≥ 2 impls | Compliant — `langgraph` + `agent_framework` registered |
| C6 | #6 SSE reasoning channel | Manual | `grep -RnE 'event:\s*(reasoning|tool|answer|citation|error)' v2/src/backend/` | Compliant — 5 channels live |
| C7 | #7 No banned tech | Manual | `grep -RnE 'streamlit|prompt-flow|semantic-kernel|^from openai|^import openai|AzureOpenAI\(' v2/src/ v2/pyproject.toml` — zero hits | Compliant — see [project_status.md](project_status.md) Libraries section |
| C8 | #8 Phase-end green | Manual | dev_plan §0 status table — every closed phase row carries the green checkpoint | Compliant — Phases 1–6 ✅, Phase 7 backend ✅ |
| C9 | #9 Plan + pillar citation | Convention | Spot-check 3 recent commits — each touches §3.4 / §4 task # + a pillar | Compliant — workflow contract holds |
| C10 | #10 Structural confirmation | Convention | dev_plan §0.0 / §0.0a / §0.0b — every new folder traced to a user-confirmed turn | Compliant — no unsolicited top-level additions |
| C11 | #11 Naming + no `TYPE_CHECKING` | AST gate `test_no_type_checking_or_future_annotations.py` + pyright | `cd v2 ; uv run pytest tests/shared/test_no_type_checking_or_future_annotations.py -q` | Green — `_EXEMPTIONS = frozenset()` |
| C12 | #12 No mid-phase backfills | Convention | dev_plan §0.1 debt-queue history — backfill rows annotated with originating phase | Compliant — Q-row discipline preserved |
| C13 | #13 `__init__.py` marker-only | AST gate `test_init_files_are_marker_only.py` | `cd v2 ; uv run pytest tests/shared/test_init_files_are_marker_only.py -q` | Green — `_EXEMPTIONS = frozenset()` |
| C14 | #14 SDK resilience | AST gate `test_no_silent_excepts.py` + manual | `cd v2 ; uv run pytest tests/test_no_silent_excepts.py -q` + spot-check `extra={"operation"` in 3 providers | Green; manual spot-check pending |
| C15 | #15 Typed dict returns | AST gate `test_no_anonymous_dict_returns.py` | `cd v2 ; uv run pytest tests/shared/test_no_anonymous_dict_returns.py -q` | Green — allow-list reviewed |
| C16 | #16 No process narrative | AST gate `test_no_process_narrative_in_src.py` | `cd v2 ; uv run pytest tests/shared/test_no_process_narrative_in_src.py -q` | Green — no growable allow-list |
| C17 | #17 Imports at top | AST gate `test_imports_at_top_only.py` | `cd v2 ; uv run pytest tests/shared/test_imports_at_top_only.py -q` | Green — `_EXEMPTIONS = frozenset()` |

**Non-compliance handling**: any failing spot-check is recorded as a new `U-QA-CN-*` row in dev_plan §0.1 with the AST gate name + reproduction command. The QA review does **not** patch the violation inline.

---

## Phase D — Library hygiene audit

Verify every dependency surface against ADR 0017 (Agent Framework pins), ADR 0011–0014 (frontend pins), and Hard Rule #7 (banned packages).

| Unit | Surface | Spot-check | Default outcome |
|---|---|---|---|
| D1 | Backend deps | `cd v2 ; grep -E '^(agent[-_]framework|azure-search|azure-cosmos|openai|prompt-flow|semantic-kernel|streamlit)' pyproject.toml` | `agent-framework == <ADR-0017 pin>`, `agent-framework-foundry == <ADR-0017 pin>`; zero banned-package hits |
| D2 | Frontend deps | `cat v2/src/frontend/package.json` + `grep -E '"(react|@fluentui/react-components|vitest|eslint)"' package.json` | React 19, Fluent v9, Vitest, ESLint 9 flat config — pins match ADR 0011/0012/0013/0014 |
| D3 | Functions deps | `cd v2 ; grep -RnE '^from azure\.functions|^import azure\.functions' src/functions/` + `grep -RnE 'azure-ai-formrecognizer' .` | Functions consume `backend.core` + `functions.core`; zero `formrecognizer` regression |
| D4 | Infra deps | `grep -RnE '(Microsoft\.KeyVault|allowProjectManagement)' v2/infra/` + `cat v2/infra/abbreviations.json | head -20` | Unified `kind=AIServices` account with `allowProjectManagement=true`; Key Vault present only for infra plumbing, never for app secrets |

**Evidence file pointers**

- ADR 0017 — [v2/docs/adr/0017-agent-framework-pins.md](adr/0017-agent-framework-pins.md) (if present).
- ADR 0011–0014 — frontend stack ADRs under `v2/docs/adr/`.

---

## Phase E — Modularity audit

Verify the registry surface, the plug-and-play profile boots, and the AST gates that enforce structural discipline.

| Unit | Target | Spot-check | Default outcome |
|---|---|---|---|
| E1 | Registry surface (8 domains) | `for d in agents credentials databases embedders llm orchestrators parsers search; do echo "--- $d ---"; grep -E 'registry\s*=\s*Registry|load_entry_points\(' v2/src/backend/core/providers/$d/registry.py; done` | Every domain exposes a `Registry[T]` instance + eager side-effect imports of concretes + `load_entry_points("cwyd.providers.<domain>")` |
| E2 | Plug-and-play profiles | `docker compose -f v2/docker/docker-compose.dev.yml --profile backend-only config ; docker compose -f v2/docker/docker-compose.dev.yml --profile frontend-only config` | Both render exit 0 (currently ⏸ blocked on `DV1` until Docker daemon available — carry the blocker forward if still down) |
| E3 | AST gate state | `cd v2 ; uv run pytest tests/shared tests/test_no_silent_excepts.py -q` + `grep -E '_EXEMPTIONS\s*=\s*frozenset\(\)' v2/tests/shared/*.py` | 9 gates green; 3 absolute gates carry `_EXEMPTIONS = frozenset()` (init-marker, imports-at-top, no-future-annotations) |

**Evidence file pointers**

- EXTENSION-DISCOVERY-PIPELINE contract — [extending.md](extending.md).
- 8 provider registries — [v2/src/backend/core/providers/](../src/backend/core/providers/).

---

## Phase F — Admin config + save flow audit

Walk the admin surface end to end: backend routes, RuntimeConfig lifecycle, audit log, frontend route closure, sensitive-field allow-list.

| Unit | Target | Spot-check | Default outcome |
|---|---|---|---|
| F1 | Backend route surface | `grep -E '@router\.(get|patch|post|delete)' v2/src/backend/routers/admin.py` + `cd v2 ; uv run pytest tests/shared/test_routers_contain_only_routes.py -q` | All admin routes present (status / config GET+PATCH / config/effective / documents URL+upload+reprocess+DELETE-by-source); router-only gate green |
| F2 | RuntimeConfig lifecycle | `grep -RnE 'runtime_overrides|EffectiveAdminConfig' v2/src/backend/` + `grep -Rn 'requires_role\("admin"\)' v2/src/backend/routers/admin.py` | Lifespan seeds `app.state.runtime_overrides`; PATCH writes live-reload; RBAC `requires_role("admin")` on every mutating route |
| F3 | Audit log | `grep -RnE 'AdminAuditEntry|admin_audit' v2/src/backend/` + spot-check Cosmos + Postgres impls | `AdminAuditEntry` append-only in Cosmos `_system` partition + Postgres `admin_audit` table; PATCH writes after upsert; failure does NOT roll back PATCH |
| F4 | FE admin route closure | dev_plan §0.2 row for `#35d` | `#35d` ⏳ partial — prompt-editor route shell shipped 2026-06-04, persistence wiring open (decision pending on local-draft vs. backend-persist) |
| F5 | Sensitive-field allow-list | `grep -Rn 'test_status_does_not_leak_sensitive_settings\|test_config_does_not_leak_sensitive_settings' v2/tests/` + `cd v2 ; uv run pytest -q -k 'leak_sensitive_settings'` | Tests cover every UAMI / tenant / connection-string / api-version / Cosmos key / Postgres password / embedding key / Foundry endpoint field |

**Evidence file pointers**

- Admin surface contract — [admin_runtime_config.md](admin_runtime_config.md).
- Backend router — [v2/src/backend/routers/admin.py](../src/backend/routers/admin.py).

---

## Phase G — Chat history flow audit

Verify backend routes, both database backends, continuation contract, and frontend history panel.

| Unit | Target | Spot-check | Default outcome |
|---|---|---|---|
| G1 | Backend route surface | `grep -E '@router\.(get\|post\|patch\|delete)' v2/src/backend/routers/history.py` | 6 routes: `GET /conversations`, `GET /conversations/{id}`, `POST /conversations`, `PATCH /conversations/{id}`, `DELETE /conversations/{id}`, `POST /conversations/{id}/messages`; router-only gate green |
| G2 | Both backends | `grep -RnE 'class (Cosmos|Postgres)DatabaseClient' v2/src/backend/core/providers/databases/` + read each `__init__` for partition / FK / index setup | Cosmos partitions by `/userId`; Postgres has FK cascade + `(user_id, updated_at DESC)` index |
| G3 | Continuation contract | `grep -RnE 'POST.*conversation' v2/src/backend/routers/conversation.py` + verify no auto-load history call | `POST /api/conversation` does NOT auto-load history (FE responsibility); no SSE replay; idempotent DELETE; UUID4 server-assigned IDs |
| G4 | FE history panel | `cat v2/src/frontend/src/pages/chat/components/HistoryPanel.tsx | head -50` + dev_plan §0.2 row for `#24` | Typed-client consumption; `#24` ⏳ partial — citations + cancel + reconnect remain |

**Evidence file pointers**

- Chat history flow — [chat_history.md](chat_history.md).
- Backend router — [v2/src/backend/routers/history.py](../src/backend/routers/history.py).

---

## Phase H — Per-phase closure verification

Walk every closed phase from dev_plan §0 status table. One phase per turn. Verify the phase-end green signal is reproducible.

| Unit | Phase | Spot-check | Default outcome |
|---|---|---|---|
| H1 | Phase 1 — infra + project skeleton | `az bicep build --file v2/infra/main.bicep` + `cat v2/azure.yaml` + `ls v2/scripts/post_provision.sh` | Bicep validates; `azure.yaml` `services:` populated; `post_provision.sh` exists |
| H2 | Phase 2 — settings + LLM | `curl -s http://localhost:8000/api/health` + `curl -si http://localhost:8000/api/health/ready` (failure case) | `/api/health` returns 200; `/api/health/ready` returns 503 when a dependency is down |
| H3 | Phase 3 — RAG core chat | `grep -E 'class.*Orchestrator' v2/src/backend/core/providers/orchestrators/*.py` + verify SSE channel emission via integration test | `langgraph` + `agent_framework` orchestrators reach `search_registry`; SSE channels `reasoning/tool/answer/citation/error` all emit; Agent Framework on OSS `agent_framework_foundry.FoundryAgent` |
| H4 | Phase 4 — chat history + both DBs | `grep -RnE 'PgVector\.ensure_schema|lifespan' v2/src/backend/` + manual two-backend round-trip | Both Cosmos + Postgres seed via lifespan; `PgVector.ensure_schema()` runs idempotently |
| H5 | Phase 5 — admin + FE merge | dev_plan §0 row 5 + §0.2 row for `#35d` | Backend ✅; FE `#35d` ⏳ tracked (carry forward) |
| H6 | Phase 6 — RAG ingestion pipeline | `ls v2/src/functions/{batch_start,batch_push,add_url,search_skill}/` + `.github/workflows/v2-backend-only-smoke.yml` job result | All 4 blueprints present + green in smoke CI |
| H7 | Phase 7 — testing + docs | B1–B4 baseline + dev_plan §0 row 7 | Backend tier drained 2026-06-02; FE tier in progress per [project_status.md](project_status.md) Phases table |

---

## Phase I — Open debt drain plan

Mirror dev_plan §0.1 (backend) + §0.2 (frontend) open rows exactly. **No new debt invented here.** One row per open item.

| Unit | Debt row | Origin | Status | Drain action |
|---|---|---|---|---|
| I1 | `#35d` FE admin merge | dev_plan §0.2 | ⏳ partial | Prompt-editor backend persistence decision (local-draft vs. `PATCH /api/admin/config` wiring) + FE acceptance test coverage |
| I2 | `#35g` per-tenant overrides | dev_plan §0.1 | ☐ blocked on `#39` | Hold; document dependency. Cannot proceed until Easy Auth tenant claim propagation lands |
| I3 | `#24` SSE FE remaining | dev_plan §0.2 | ⏳ partial | Citation cards, reconnect, cancel button, abort, multi-turn UX polish (FE backlog) |
| I4 | `B-IMPL-FACTORY-CACHE` | dev_plan §0.1 | ☐ open | Cache `FoundryAgent` per `(project_endpoint, agent_name, credential_identity)` at orchestrator-registry layer with lifespan shutdown hook |
| I5 | `B-IMPL-EXTRAS` | dev_plan §0.1 | ☐ deferred | Optional Agent Framework extras (`a2a`, `copilotstudio`, `microsoft`, `redis`); add only if a Scenario Pack needs them |
| I6 | `B-IMPL-FOUNDRY-STUBS-DEBT` | dev_plan §0.1 | ☐ upstream | Track upstream OSS SDK `py.typed` shipment; remove suppression when fixed. Not actionable on our side |
| I7 | `DV1` docker compose | dev_plan §0.2 | ⏸ blocked | Re-run `docker compose --profile {backend,frontend}-only config` once Docker daemon is restored |

**Discipline**: Each open row stays exactly as it appears in dev_plan. The QA review does NOT shorten, edit, or close debt rows — only mirrors them.

---

## Phase J — QA acceptance pack

Final three units: smoke contract, manual QA matrix, sign-off ceremony.

| Unit | Deliverable | Acceptance |
|---|---|---|
| J1 | Smoke contract | `.github/workflows/v2-backend-only-smoke.yml` reviewed; "ready for QA" gate = backend smoke green + frontend gate green + 9 AST gates green + scoped pyright `0/0/0` + B2 pytest `1986/1/0` |
| J2 | Manual QA matrix | Deploy-ready matrix authored below: `azd up` end-to-end success + chat round-trip + admin PATCH live-reload visible next request + history persist+resume + delete-by-source round-trip |
| J3 | Sign-off ceremony | "QA Sign-Off" grid below populated by reviewer: one row per phase (H1–H7) + one row per dimension (Rules / Libraries / Modularity / Admin / Chat History), each with owner + date + evidence link |

### J2 — Manual QA matrix

| Scenario | Steps | Pass condition |
|---|---|---|
| Cold deploy | `azd up` from a clean azure subscription | Exit 0; all Bicep modules deploy; backend + frontend reachable via App URLs |
| Chat round-trip | Open chat UI → ask a grounded question → observe SSE | `reasoning` panel renders; `answer` streams; ≥ 1 `citation` event fires; no `error` event |
| Admin PATCH live-reload | Admin UI → change a setting → save → ask a new question | New value visible in next request without backend restart; `EffectiveAdminConfig` reflects override |
| History persist + resume | Send 3 messages → reload page → reopen conversation | Conversation visible in history panel; messages render in order; resume continues with full context |
| Delete by source | Admin → Delete Data → pick source → confirm | All chunks with that `source` removed from index; subsequent chat does not cite that source |

### J3 — QA sign-off grid

| Row | Owner | Date | Evidence link |
|---|---|---|---|
| Phase 1 (H1) |  |  |  |
| Phase 2 (H2) |  |  |  |
| Phase 3 (H3) |  |  |  |
| Phase 4 (H4) |  |  |  |
| Phase 5 (H5) |  |  |  |
| Phase 6 (H6) |  |  |  |
| Phase 7 (H7) |  |  |  |
| Dimension — Hard Rules |  |  |  |
| Dimension — Libraries |  |  |  |
| Dimension — Modularity |  |  |  |
| Dimension — Admin Config + Save |  |  |  |
| Dimension — Chat History |  |  |  |

---

## Cross-reference

- [project_status.md](project_status.md) — per-dimension snapshot.
- [development_plan.md](development_plan.md) — canonical ledger (§0, §0.1, §0.2, §4).
- [pillars_of_development.md](pillars_of_development.md) — read-only pillar policy.
- [.github/copilot-instructions.md](../../.github/copilot-instructions.md) — Hard Rules 1–17.
- [qa_report_v2.archived.md](qa_report_v2.archived.md) — historical narrative (archived 2026-06-04).
