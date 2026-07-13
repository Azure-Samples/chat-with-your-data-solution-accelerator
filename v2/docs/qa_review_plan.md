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

**Reviewed 2026-06-04** — every rule below is **compliant**; no new debt rows opened. See the "Notes from the 2026-06-04 pass" subsection for one finding that *looks* non-compliant under a naive grep but is sanctioned by Hard Rule #14's SDK-boundary allowed-list.

| Unit | Rule | Enforcement | Spot-check | Outcome (2026-06-04) |
|---|---|---|---|---|
| C1 | #1 One unit per turn | Convention | `git log --oneline -- v2/src/ \| head -30` — diffs should be small (1 class / 1 method + tests) | ✅ Compliant — workflow contract holds; recent CU commits all single-unit |
| C2 | #2 Test-first | Convention | every prod module pairs with a test sibling (count check via `Get-ChildItem v2/src/**/tests` + `Get-ChildItem v2/tests`) | ✅ Compliant — 2047 backend tests + 361 FE tests; every Phase 7 unit shipped with test |
| C3 | #3 Pillar header | AST gate `test_pillar_phase_header.py` | `cd v2 ; uv run pytest tests/shared/test_pillar_phase_header.py -q` | ✅ Green (B4) |
| C4 | #4 Registry dispatch | Manual + convention | `grep -RnE '^\s*(if\|elif).*(provider\|db_type\|index_store)\s*==' v2/src/backend/core/providers/` | ✅ Zero hits — 8 registries enforce dispatch via `Registry.get` |
| C5 | #5 Multi-agent ready | Manual | `grep -RnE 'class\s+\w+Orchestrator' v2/src/backend/core/providers/orchestrators/` + base ABC | ✅ `OrchestratorBase(ABC)` + 2 impls: `AgentFrameworkOrchestrator`, `LangGraphOrchestrator` |
| C6 | #6 SSE reasoning channel | Manual + typed enum | `grep -n 'class OrchestratorChannel' v2/src/backend/core/types.py` | ✅ `OrchestratorChannel(StrEnum)` with `REASONING / TOOL / ANSWER / CITATION / ERROR` at `v2/src/backend/core/types.py:79-83`; emitted via typed `OrchestratorEvent` (no raw string-literal channel names) |
| C7 | #7 No banned tech | Manual | `grep -RnE '^(import\|from)\s+(streamlit\|promptflow\|semantic_kernel)' v2/src/` + `grep -E '^\s*"(streamlit\|promptflow\|prompt-flow\|semantic-kernel)' v2/pyproject.toml` + `grep -RnE '^(from openai\|import openai\|AzureOpenAI\()' v2/src/` | ✅ Compliant — zero `streamlit / promptflow / semantic_kernel` hits in either source or pyproject. **Two `import openai` hits** (`v2/src/backend/app.py:24`, `v2/src/backend/core/providers/llm/foundry_iq.py:27`) are exception-class identifiers for `openai.APIError` exception handlers — explicitly allowed by Hard Rule #14's SDK-boundary list. The `openai==2.32.0` pin in `pyproject.toml` is required for that exception class identity + the `AsyncOpenAI`-compatible client returned by Foundry's `AIProjectClient.get_openai_client()`. See "Notes" below for full detail. **No direct client construction** (no `AzureOpenAI(...)`, no `OpenAI(...)`, no `from openai import AsyncOpenAI`). |
| C8 | #8 Phase-end green | Manual | dev_plan §0 status table — every closed phase row carries the green checkpoint | ✅ Phases 1–6 ✅, Phase 7 backend tier ✅ (2026-06-02), Phase 7 FE in progress |
| C9 | #9 Plan + pillar citation | Convention | spot-check 3 recent commits — each touches §3.4 / §4 task # + a pillar | ✅ Compliant — recent CU commits cite §4 task IDs + carry `Pillar:` headers |
| C10 | #10 Structural confirmation | Convention | dev_plan §0.0 / §0.0a / §0.0b — every new folder traced to a user-confirmed turn | ✅ Compliant — no unsolicited top-level additions in §0.0a/§0.0b ledger |
| C11 | #11 Naming + no `TYPE_CHECKING` | AST gate `test_no_type_checking_or_future_annotations.py` + pyright | `cd v2 ; uv run pytest tests/shared/test_no_type_checking_or_future_annotations.py -q` + B1 pyright | ✅ Green (B4); `_EXEMPTIONS = frozenset()`; pyright `0/0/0` (B1) |
| C12 | #12 No mid-phase backfills | Convention | dev_plan §0.1 debt-queue history — backfill rows annotated with originating phase | ✅ Compliant — Q-row discipline preserved; debt drained in audit sweeps not mid-phase |
| C13 | #13 `__init__.py` marker-only | AST gate `test_init_files_are_marker_only.py` | `cd v2 ; uv run pytest tests/shared/test_init_files_are_marker_only.py -q` | ✅ Green (B4); `_EXEMPTIONS = frozenset()` |
| C14 | #14 SDK resilience | AST gate `test_no_silent_excepts.py` + manual | `grep -RnE 'extra=\{"operation":' v2/src/backend/` | ✅ Green (B4); 5+ hits for structured-log pattern in `agents/base.py`, `llm/foundry_iq.py`, `search/pgvector.py`, `search/azure_search.py`, `databases/postgres.py` |
| C15 | #15 Typed dict returns | AST gate `test_no_anonymous_dict_returns.py` | `cd v2 ; uv run pytest tests/shared/test_no_anonymous_dict_returns.py -q` | ✅ Green (B4); allow-list reviewed |
| C16 | #16 No process narrative | AST gate `test_no_process_narrative_in_src.py` | `cd v2 ; uv run pytest tests/shared/test_no_process_narrative_in_src.py -q` | ✅ Green (B4); no growable allow-list |
| C17 | #17 Imports at top | AST gate `test_imports_at_top_only.py` | `cd v2 ; uv run pytest tests/shared/test_imports_at_top_only.py -q` | ✅ Green (B4); `_EXEMPTIONS = frozenset()` |

### Notes from the 2026-06-04 pass

**C7 — `import openai` is sanctioned, not banned.** Two files import the `openai` package:

1. **`v2/src/backend/app.py:24`** — `import openai` exists solely to register a global FastAPI exception handler for `openai.APIError` (lines 257 / 288 / 293 / 364: `app.add_exception_handler(openai.APIError, _openai_api_error_handler)` sanitizes upstream model failures to a 502 response).
2. **`v2/src/backend/core/providers/llm/foundry_iq.py:27`** — `import openai` is used only for the `openai.APIError` exception type that wraps OpenAI-compatible SDK calls (the client itself comes from `AIProjectClient.get_openai_client()` and is shape-narrowed locally via the `_OpenAIClient(Protocol)` defined at line 150). The module docstring explicitly carries the rationale: *"Why we don't `from openai import …`: hard rule #7 bans direct openai stubs (Q14a)."*

Hard Rule #14 (SDK boundary resilience) explicitly lists `openai.APIError` as one of the SDK exception umbrellas providers must wrap. Identifying that exception class requires importing `openai` as a module — the rule that's banned is direct **client construction** (`AzureOpenAI(...)`, `OpenAI(...)`, `from openai import AsyncOpenAI`), not module-level exception-type identification. The `openai==2.32.0` pin in `pyproject.toml` exists for (a) the exception class identity stability and (b) `AsyncOpenAI` shape compatibility for Foundry's returned client.

**Non-compliance handling**: any future failing spot-check is recorded as a new `U-QA-CN-*` row in dev_plan §0.1 with the AST gate name + reproduction command. The QA review does **not** patch the violation inline.

---

## Phase D — Library hygiene audit

Verify every dependency surface against ADR 0017 (Agent Framework pins), ADR 0011–0014 (frontend pins), Hard Rule #7 (banned packages), and ADR 0002 (no Key Vault for app secrets).

**Reviewed 2026-06-04** — every surface below is **compliant**.

| Unit | Surface | Spot-check | Outcome (2026-06-04) |
|---|---|---|---|
| D1 | Backend deps | `cat v2/pyproject.toml` + `grep -E '^\s*"(agent[-_]framework\|openai\|streamlit\|promptflow\|semantic-kernel)' v2/pyproject.toml` | ✅ `agent-framework==1.7.0` + `agent-framework-foundry==1.7.0` match ADR 0017 exactly; `openai==2.32.0` pinned per Hard Rule #14 SDK-boundary allowed-list (exception-class identifier only — see Phase C7 finding); zero `streamlit / promptflow / semantic-kernel` hits |
| D2 | Frontend deps | `cat v2/src/frontend/package.json` | ✅ React `^19.0.0`, Fluent v9 `@fluentui/react-components ^9.73.8`, Vitest `^2.1.0`, ESLint `^9.39.4` flat config with `typescript-eslint ^8.60.1`, Vite `^7.0.0`, TypeScript `^5.7.0` — pins match ADR 0011 (model extraction), ADR 0012 (test-folder mirror), ADR 0013 (strict TS + `.tsx` everywhere), ADR 0014 (CI workflow); no Jest, no CRA, no Webpack |
| D3 | Functions deps | `grep -RnE '^from\s+(backend\.core\|functions\.core)' v2/src/functions/` + `grep -RnE 'azure[-_]ai[-_]formrecognizer' v2/` | ✅ All 4 blueprints (`add_url`, `batch_push`, `batch_start`, `search_skill`) import from `backend.core.providers.*` + `functions.core.*`; zero `azure-ai-formrecognizer` regression (v1 used it; v2 uses `azure-ai-documentintelligence>=1.0,<2.0` per pyproject) |
| D4 | Infra deps | `grep -n 'allowProjectManagement\|kind:.*AIServices' v2/infra/main.bicep` + `grep -RnE 'keyVault\|Microsoft\.KeyVault' v2/infra/` + `grep -RnE 'azure\.keyvault\|SecretClient' v2/src/backend/` | ✅ Unified AI Services account at `main.bicep:443-464` with `kind: 'AIServices'` + `allowProjectManagement: true` (exposes Document Intelligence + OpenAI + Speech on one resource); **zero `keyVault` / `Microsoft.KeyVault` hits in `v2/infra/`**; **zero `azure.keyvault` / `SecretClient` imports in `v2/src/backend/`** — per ADR 0002 (no Key Vault for app secrets; UAMI + RBAC) |

### Notes from the 2026-06-04 pass

- **ADR 0017** confirmed live: pyproject pins (`agent-framework==1.7.0`, `agent-framework-foundry==1.7.0`) match ADR exact-pin policy. CWYD's intentional divergence from TAS27 is preserved per ADR 0017 "Continued intentional divergence from TAS27 exact package versions where CWYD has selected newer runtime surfaces."
- **ADR 0002** confirmed live: zero Key Vault dependency in any v2 surface (infra Bicep, backend Python, frontend TS). All Azure data-plane access flows through `azure-identity` `DefaultAzureCredential` + RBAC role assignments emitted by `v2/infra/main.bicep`.
- **ADR 0013** confirmed live: `typescript-eslint ^8.60.1` wired into ESLint 9 flat config; FE strict TS + `.tsx` everywhere policy intact (visible in B3c tsc clean exit).
- **No banned package additions discovered.** Frontend `package.json` carries only React 19, Fluent v9, Speech SDK; no React Router (single-page admin merge per `#35d`), no axios (uses generated typed client + `fetch`), no Redux (Context + `useReducer`).

**Evidence file pointers**

- ADR 0017 — [v2/docs/adr/0017-agent-framework-foundry-pinned-dependency-policy.md](adr/0017-agent-framework-foundry-pinned-dependency-policy.md).
- ADR 0011–0014 — frontend stack ADRs under [v2/docs/adr/](adr/).
- ADR 0002 — [v2/docs/adr/0002-no-key-vault-uami-rbac.md](adr/0002-no-key-vault-uami-rbac.md).

---

## Phase E — Modularity audit

Verify the registry surface, the plug-and-play profile boots, and the AST gates that enforce structural discipline.

**Reviewed 2026-06-04** — E1 and E3 fully compliant; E2 partial (YAML static contract verified; live `docker compose config` execution carried forward on `DV1`).

| Unit | Target | Spot-check | Outcome (2026-06-04) |
|---|---|---|---|
| E1 | Registry surface (8 domains) | `grep -E 'registry\s*=\s*Registry|load_entry_points\(' v2/src/backend/core/providers/*/registry.py` + `grep -E 'Registry\(' v2/src/backend/core/providers/*/_instance.py` | ✅ All 8 domains expose `registry: Registry[T]` + `load_entry_points("cwyd.providers.<domain>")`. 7 domains use the canonical `_instance.py` split (agents/credentials/databases/embedders/llm/orchestrators/search hold the `Registry(...)` instance there; `registry.py` re-exports + fires `@registry.register(...)` via eager side-effect imports). `parsers` inlines the instance in `registry.py` (legitimate variation). Caller shape — `from backend.core.providers.<domain> import registry as <domain>_registry; <domain>_registry.registry.get(key)(**kwargs)` — documented in every facade module docstring. |
| E2 | Plug-and-play profiles | `docker compose -f v2/docker/docker-compose.dev.yml --profile backend-only config ; docker compose -f v2/docker/docker-compose.dev.yml --profile frontend-only config` + static YAML check | ⏸ **Partial — live exec blocked on `DV1`** (`docker ps` exits 1: "failed to connect to the docker API at npipe://./pipe/dockerDesktopLinuxEngine"). **YAML static contract ✅** — backend + postgres + pgvector tagged `profiles: ["", "backend-only"]`; frontend tagged `profiles: ["", "frontend-only"]`; functions on default profile only; cosmos on opt-in `cosmos` profile. Plug-and-play surface (backend headless / frontend pointing at `VITE_BACKEND_URL`) is intact at the configuration layer. **Action**: re-run live `docker compose config` once Docker Desktop is available; `DV1` debt row stays open in §0.1. |
| E3 | AST gate state | `cd v2 ; uv run pytest tests/shared tests/test_no_silent_excepts.py -q` + `grep -RnE '_EXEMPTIONS\s*[:=]\s*frozenset' v2/tests/shared/` | ✅ 9 gates green (B4 close: 981 passed / 1 skipped). **5 gates carry `_EXEMPTIONS: frozenset[Path] = frozenset()` (zero growable exemptions)**: `test_imports_at_top_only.py` (Hard Rule #17), `test_init_files_are_marker_only.py` (Hard Rule #13), `test_no_legacy_shared_imports.py`, `test_no_type_checking_or_future_annotations.py` (Hard Rule #11), `test_pillar_phase_header.py` (Hard Rule #3). **2 gates carry typed positive allow-lists** (per Hard Rule #15/#11 carve-outs, not escape hatches): `test_no_anonymous_dict_returns.py` has 4 ALLOWED tuples (`backend.app._request_extras`, `backend.dependencies._decode_easy_auth_principal`, `CosmosDBClient._read_item`, `FoundryIQ._to_openai_messages` — all justified at SDK boundaries); `test_routers_contain_only_routes.py` defines the router protocol (`logger`/`router`/`__all__` + decorator verbs). **1 gate has no allow-list at all**: `test_no_process_narrative_in_src.py` (Hard Rule #16 — "Fix the comment; do not exempt the file"). **1 gate at `v2/tests/test_no_silent_excepts.py`** (Hard Rule #14). |

### Notes from the 2026-06-04 pass

- **Hard Rule #4 (Registry dispatch) holds across all 8 domains.** No `if/elif` provider dispatch survives in caller code; the `_instance.py` split decouples the facade (eager imports + entry-points) from the Registry instance, which is the cleaner Hard Rule #13 (`__init__.py` is a package marker) shape — `registry.py` carries the import side-effects, `_instance.py` carries only the typed `Registry[T]` binding.
- **No new debt rows opened from E1 or E3.** The `parsers` in-file Registry binding is acceptable variation — the EXTENSION-DISCOVERY-PIPELINE contract requires `registry.py` to be the import facade, not that the instance must live in a sibling file. Re-aligning `parsers` to the `_instance.py` split would be cosmetic.
- **E2 carry-forward**: `DV1` remains the single open debt row blocking live container validation. The YAML static check passes the plug-and-play contract review, so Phase E does not open a new debt row — the existing `DV1` row in dev_plan §0.1 already tracks the live-exec gap.

**Evidence file pointers**

- EXTENSION-DISCOVERY-PIPELINE contract — [extending.md](extending.md).
- 8 provider registries — [v2/src/backend/core/providers/](../src/backend/core/providers/).
- Docker compose profiles — [v2/docker/docker-compose.dev.yml](../docker/docker-compose.dev.yml).
- AST gates — [v2/tests/shared/](../tests/shared/) + [v2/tests/test_no_silent_excepts.py](../tests/test_no_silent_excepts.py).

---

## Phase F — Admin config + save flow audit

Walk the admin surface end to end: backend routes, RuntimeConfig lifecycle, audit log, frontend route closure, sensitive-field allow-list.

**Reviewed 2026-06-04** — F1/F2/F3/F5 fully compliant; F4 ⏳ partial (`#35d` FE admin merge open and tracked).

| Unit | Target | Spot-check | Outcome (2026-06-04) |
|---|---|---|---|
| F1 | Backend route surface | `grep -E '@router\.(get|patch|post|delete)' v2/src/backend/routers/admin.py` | ✅ **9 admin routes shipped** at `v2/src/backend/routers/admin.py`: (1) `GET /status:100`, (2) `GET /config:125`, (3) `GET /config/effective:147`, (4) `PATCH /config:219`, (5) `GET /documents:332`, (6) `DELETE /documents/{source:path}:378`, (7) `POST /documents/url:435`, (8) `POST /documents:487` (multipart upload), (9) `POST /documents/reprocess:569`. **Doc drift caught + fixed**: project_status.md previously claimed "7 admin routes" and was missing the `GET /documents` row — both corrected this pass. Router-only AST gate (`test_routers_contain_only_routes.py`) green per B4. |
| F2 | RuntimeConfig lifecycle | `grep -n 'class RuntimeConfig' v2/src/backend/core/types.py` + read admin.py:260-320 + `grep -RnE 'runtime_overrides' v2/src/backend/` | ✅ `RuntimeConfig` at `v2/src/backend/core/types.py:256` (Pydantic BaseModel; every override field typed `T \| None = None` so RFC 7396 merge is field-precise). PATCH handler (`admin.py:219`) flow: (a) `before = await db.get_runtime_config()`; (b) `current = before or RuntimeConfig()` (preserves None ≠ empty distinction); (c) `model_dump()` + per-key merge; (d) server-set `updated_at` / `updated_by` (frozen via `WRITABLE_FIELDS = frozenset(RuntimeConfig.model_fields) - {"updated_at", "updated_by"}`); (e) `model_validate` → 422 on type errors; (f) `db.upsert_runtime_config(merged)`; (g) **live-reload** via `request.app.state.runtime_overrides = merged` (atomic GIL-protected rebind, no lock per inline docstring). `requires_role("admin")` Easy Auth gate via `AdminUserIdDep` on every route. |
| F3 | Audit log | `grep -RnE 'AdminAuditEntry\|write_admin_audit' v2/src/backend/` | ✅ `AdminAuditEntry` at `types.py:303`; `write_admin_audit` abstract on `BaseDatabaseClient:168`; Cosmos impl at `cosmosdb.py:583` (writes `type=ADMIN_AUDIT` item in `_system` partition); Postgres impl at `postgres.py:673` (one row in `admin_audit` table with `idx_admin_audit_created` index on `created_at DESC`). PATCH handler (`admin.py:305-322`) writes the audit row **after** the persist + live-reload steps, wrapped in a `try/except Exception` that **logs but never rolls back** the successful PATCH — best-effort policy documented inline at `admin.py:297-304`. Coverage: `test_write_admin_audit_logs_and_reraises_on_sdk_error` (Cosmos) + `test_write_admin_audit_logs_and_reraises_on_postgres_error` (Postgres). |
| F4 | FE admin route closure | `Get-ChildItem v2/src/frontend/src/pages/admin/` + `Select-String /api/admin/ v2/src/frontend/src/api/admin.tsx` | ⏳ **Partial** — 4 FE admin pages shipped (`Configuration.tsx` with `configurationReducer:186` + `Configuration:372`; `DeleteData.tsx` with `deleteDataReducer:104` + `DeleteData:197`; `IngestData.tsx` with `ingestDataReducer:145` + `IngestData:266`; `PromptEditor.tsx` route shell at `PromptEditor:30`). API client at `v2/src/frontend/src/api/admin.tsx` mounts 5 admin URL constants. `#35d` remains ⏳ — `PromptEditor` persistence wiring open (decision pending on local-draft vs. backend-persist). Carry-forward in dev_plan §0.2; **non-blocking** for Phase 6 per copilot-instructions Phase 6 status note. |
| F5 | Sensitive-field allow-list | `grep -Rn 'test_(status\|config)_does_not_leak_sensitive_settings' v2/tests/` + read `v2/src/backend/models/admin.py` | ✅ `AdminConfig.model_fields` is a closed explicit allow-list (`orchestrator_name`, `openai_temperature`, `openai_max_tokens`, `search_use_semantic_search`, `search_top_k`, `log_level`, `content_safety_enabled` — `models/admin.py:65-72`). `AdminStatus.model_fields` likewise explicit (`orchestrator_name`, `db_type`, `index_store`, `environment`, `foundry_project_endpoint_host`, `gpt_deployment`, `embedding_deployment`, ... — `models/admin.py:92+`). Sensitive fields (UAMI ids, tenant id, connection strings, OpenAI API version) **deliberately omitted**. Tests `test_status_does_not_leak_sensitive_settings` (`tests/backend/test_admin.py:320`) + `test_config_does_not_leak_sensitive_settings` (`tests/backend/test_admin.py:545`) lock the allow-list in (both green per B2). |

### Notes from the 2026-06-04 pass

- **Doc drift in project_status.md caught and fixed inline.** Previous count claimed "7 admin routes" and the route table was missing the `GET /documents` row (which feeds the Delete Data grid). Both corrected as part of this audit since project_status.md is itself an output of the QA review pass, not source-of-truth code. No dev_plan §0.1 debt row needed — this is doc-doc drift, not source-code debt.
- **Audit log is best-effort by design** — F3 confirms PATCH success is **not** gated on audit-row success. Operator semantics: a 200 on PATCH always means the override is persisted AND live-reloaded; a failed audit write surfaces only in App Insights logs, not in the HTTP response. Test coverage exists for both DB providers.
- **Sensitive-field discipline is enforced by closed-set Pydantic models, not by regex / redaction.** Every new field surfaced via `/status` or `/config` requires a model edit that the leak tests will catch on next CI — the allow-list cannot be widened by accident, only by deliberate code change.
- **`#35d` is the only open admin item** and remains explicitly non-blocking for Phase 6 per copilot-instructions header note. Backend admin surface is fully closed.

**Evidence file pointers**

- Admin surface contract — [admin_runtime_config.md](admin_runtime_config.md).
- Backend router — [v2/src/backend/routers/admin.py](../src/backend/routers/admin.py).
- Models — [v2/src/backend/models/admin.py](../src/backend/models/admin.py).
- Types — [v2/src/backend/core/types.py](../src/backend/core/types.py).
- Audit-log impls — [v2/src/backend/core/providers/databases/cosmosdb.py](../src/backend/core/providers/databases/cosmosdb.py) + [postgres.py](../src/backend/core/providers/databases/postgres.py).
- FE admin pages — [v2/src/frontend/src/pages/admin/](../src/frontend/src/pages/admin/).

---

## Phase G — Chat history flow audit

Verify backend routes, both database backends, continuation contract, and frontend history panel.

**Reviewed 2026-06-04** — all 4 units fully compliant.

| Unit | Target | Spot-check | Outcome (2026-06-04) |
|---|---|---|---|
| G1 | Backend route surface | `grep -E '@router\.(get\|post\|patch\|delete)' v2/src/backend/routers/history.py` | ✅ **8 history routes shipped** at `routers/history.py`: (1) `GET /status:52`, (2) `GET /conversations:57`, (3) `POST /conversations:64` (201), (4) `GET /conversations/{id}:77` (returns `ConversationDetail` = conversation + full message list), (5) `PATCH /conversations/{id}:95` (rename), (6) `DELETE /conversations/{id}:115` (idempotent, 204), (7) `POST /conversations/{id}/messages:129` (201), (8) `POST /messages/{message_id}/feedback:153` (204). All routes carry `UserIdDep` + `DatabaseClientDep`; 404 raised on `KeyError` from per-user ownership check. Router-only AST gate green per B4. **Doc drift caught + fixed**: project_status.md table previously listed 6 routes — missing `DELETE /conversations/{id}` and `POST /conversations/{id}/messages` rows. Both added inline. |
| G2 | Both backends | `grep -RnE 'async def (list_conversations\|get_conversation\|create_conversation\|rename_conversation\|delete_conversation\|list_messages\|add_message\|set_feedback)' v2/src/backend/core/providers/databases/` | ✅ `BaseDatabaseClient` ABC (`base.py:51-99`) defines all 8 history methods; both concretes implement the full surface. **Cosmos** (`cosmosdb.py:214-575`): user-partitioned (`/userId`), parent-bump on `add_message` (lines 423-437 keep `conversation.updated_at` fresh for sort), feedback on per-message item type. **Postgres** (`postgres.py:365-441`): `conversations` + `messages` tables with FK cascade, per-conversation index, `asyncpg`-narrow exception wraps with structured `extra={"operation": ...}` per Hard Rule #14. Both registered under `providers/databases/registry.py` via `cosmosdb` + `postgres` keys; selector lives on `settings.database.db_type`. |
| G3 | Continuation contract | `grep -RnE 'continuation_token\|next_page' v2/src/backend/` + read `routers/conversation.py` POST handler | ✅ **No pagination by design** — zero `continuation_token` / `next_page` / `cursor` hits in `v2/src/backend/`. List endpoints return the full per-user sequence (`Sequence[Conversation]`, `Sequence[MessageRecord]`); operating volume is bounded by per-user conversation count and per-conversation message count. **Conversation continuation = client-driven**: `POST /api/conversation` (`routers/conversation.py:47`) takes the chat-turn body which carries `conversation_id` on the request; the chat router does **not** auto-load prior turns (no `list_messages` call) — the orchestrator receives only the messages the FE explicitly sends, so resumption is the FE's responsibility (HistoryPanel selects → ChatPage seeds prior turns). `DELETE` is idempotent (Cosmos silent on 404, Postgres `DELETE 0` returns silently — route always 204). IDs are server-assigned UUID4 strings at `create_conversation`. |
| G4 | FE history panel | `Get-ChildItem v2/src/frontend/src/pages/chat/components/HistoryPanel.tsx` + dev_plan §0.2 row for `#24` | ✅ **Backend-agnostic** — `HistoryPanel.tsx:82` consumes `/api/history/status` + `/api/history/conversations` via `fetchJson<T>` typed client (`Promise.all` parallel load, `AbortController` cleanup, error-state UI). Module docstring at line 13: *"Backend agnostic: the router behind `/api/history` dispatches to Cosmos or Postgres; the panel reads the discriminator from `/api/history/status` only to render the badge."* Composed by `ChatPage.tsx:44`. Companion typed surface: `models/chat.tsx` `HistoryConversation` interface mirrors `Conversation`; `api/feedback.tsx` mounts `POST /api/history/messages/{id}/feedback`. `#24` SSE FE wiring (citation cards / abort / reconnect) is **not** a history-panel concern — it is the chat-turn SSE pipe and lives in dev_plan §0.2 separately. |

### Notes from the 2026-06-04 pass

- **Doc drift in project_status.md caught and fixed inline.** Previous history table listed 6 routes — missing `DELETE /conversations/{id}` and `POST /conversations/{id}/messages` rows. Both added (consistent with the F1 fix earlier this pass). No dev_plan §0.1 debt row needed — doc-doc drift, not source-code debt.
- **No pagination is a deliberate Stable-Core choice** — not a debt item. The history surface is bounded by per-user conversation count; adding pagination would be a breaking contract change requiring an ADR. If a scale ceiling is ever hit, the path is to add `?limit=&before_id=` cursor params on `list_conversations` + `list_messages`, not a continuation token.
- **Continuation contract = client-driven** — the chat router never auto-loads prior turns. This keeps `POST /api/conversation` stateless and SSE-clean, and makes the orchestrator's input fully visible at the request boundary (one of the Phase 3 contract decisions).
- **Per-user ownership is enforced in every method** — `KeyError` from the DB layer maps to 404 in the router, so a user requesting another user's conversation gets the same response as a non-existent one (no enumeration oracle).

**Evidence file pointers**

- Backend router — [v2/src/backend/routers/history.py](../src/backend/routers/history.py).
- ABC + impls — [v2/src/backend/core/providers/databases/base.py](../src/backend/core/providers/databases/base.py) → [cosmosdb.py](../src/backend/core/providers/databases/cosmosdb.py) + [postgres.py](../src/backend/core/providers/databases/postgres.py).
- Models — [v2/src/backend/models/history.py](../src/backend/models/history.py).
- FE panel — [v2/src/frontend/src/pages/chat/components/HistoryPanel.tsx](../src/frontend/src/pages/chat/components/HistoryPanel.tsx).

**Evidence file pointers**

- Chat history flow — [chat_history.md](chat_history.md).
- Backend router — [v2/src/backend/routers/history.py](../src/backend/routers/history.py).

---

## Phase H — Per-phase closure verification

Walk every closed phase from dev_plan §0 status table. One phase per turn. Verify the phase-end green signal is reproducible.

**Reviewed 2026-06-04** — H1–H6 all ✅ closed; H7 ⏳ partial (FE tier in progress as expected).

| Unit | Phase | Spot-check | Outcome (2026-06-04) |
|---|---|---|---|
| H1 | Phase 1 — infra + project skeleton | `Test-Path v2/infra/main.bicep` + `grep services: v2/azure.yaml` + `Get-ChildItem v2/scripts/post-provision.*` | ✅ **Closed.** `v2/infra/main.bicep` present. `azure.yaml` `services:` populated at line 102 (was empty in Phase 1 per the inline note at line 16; populated by Phase 5 — see line 100 comment "blocker that `azure.yaml` `services:` was empty"); `hooks.postprovision` wired at line 137. Provision scripts: `v2/scripts/post-provision.sh` + `post-provision.ps1` + `post_provision.py` (Python entry-point invoked from both shells). **Doc-text drift caught in template**: H1 template said `post_provision.sh` (underscore); actual repo uses **hyphenated** `post-provision.{sh,ps1}` + underscored Python helper. Real spot-check command updated in this row. |
| H2 | Phase 2 — settings + LLM | `grep -E '@router\.' v2/src/backend/routers/health.py` + read response codes | ✅ **Closed.** Two routes at `routers/health.py` (lines 34, 43): `GET /api/health` always returns **200** with `HealthResponse` snapshot (per module docstring line 8: *"diagnostic. Always returns HTTP 200"*); `GET /api/health/ready` returns **503** when `result.status is OverallStatus.FAIL` (line 51) — readiness probe for ACA/AKS. Settings + LLM provider injection lives via `SettingsDep` + lifespan-constructed `app.state` per Phase 5.5 `backend.core` consolidation. |
| H3 | Phase 3 — RAG core chat | `grep -E 'class.*Orchestrator' v2/src/backend/core/providers/orchestrators/*.py` + read registry self-registration | ✅ **Closed.** Two orchestrators ship: `AgentFrameworkOrchestrator` (`agent_framework.py:61`) + `LangGraphOrchestrator` (`langgraph.py:73`), both extending `OrchestratorBase(ABC)`. `providers/orchestrators/registry.py:28-35` does the canonical `_instance.py` split + eager side-effect imports of both concretes + `load_entry_points("cwyd.providers.orchestrators")` for third-party plugins (Hard Rule #4 dispatch contract). SSE channels `reasoning/tool/answer/citation/error` are emitted on the typed `OrchestratorEvent` channel per Phase 3 contract (verified by E1 in Phase E + 2047 backend tests). |
| H4 | Phase 4 — chat history + both DBs | `grep -nE 'lifespan|ensure_schema' v2/src/backend/app.py` + G2 evidence | ✅ **Closed.** Lifespan at `app.py:70` (`_lifespan(app: FastAPI) -> AsyncGenerator[None, None]`); `app.py:179` calls `await search_provider.ensure_schema()` with a comment noting it's a no-op on AzureSearch and `pgvector` uses the injected pool. Both Cosmos + Postgres `BaseDatabaseClient` implementations confirmed under G2 (8 history methods each, narrow SDK exception wraps). Settings-driven dispatch via `settings.database.db_type` + `settings.search.index_store` (both registry-key-typed). |
| H5 | Phase 5 — admin + FE merge | dev_plan §0 row 5 + project_status.md Phases table + F1 evidence | ✅ **Backend closed; FE in progress.** 9 admin routes confirmed at F1; RBAC `AdminUserIdDep` on every route; audit log persisted in both Cosmos + Postgres (F3). FE `#35d` Streamlit-to-React admin merge ⏳ in progress on FE tier per project_status.md Phases row 5 — prompt-editor route shell + Section-based dispatch refactor shipped 2026-06-04. **Backend admin surface is fully closed**; only FE wiring remains. Non-blocking for Phase 6 per copilot-instructions header note. |
| H6 | Phase 6 — RAG indexing pipeline | `Get-ChildItem v2/src/functions/*/blueprint.py` + `Test-Path .github/workflows/v2-backend-only-smoke.yml` | ✅ **Closed.** All 4 blueprints present: `v2/src/functions/{batch_start,batch_push,add_url,search_skill}/blueprint.py`. Standalone-backend smoke CI workflow `.github/workflows/v2-backend-only-smoke.yml` exists with `--profile backend-only` boot + healthcheck wait + smoke-test step + log dump on failure (lines 60-104). The dev_plan §0 status snapshot pins Phase 6 as the **active phase** — closure here means the Phase 6 baseline (4 blueprints + smoke CI) is shipped, not that all Phase 6 work is done. Active Phase 6 work appends to dev_plan §0.1 within phase per Hard Rule #12. |
| H7 | Phase 7 — testing + docs | B1–B4 baseline + dev_plan §0 row 7 + project_status.md Phases row 7 | ⏳ **Partial as expected.** Backend tier ✅ drained 2026-06-02 (B1: pyright 0/0/0; B2: pytest 2047 pass / 1 skip / 3 deselect / 6 warn; B3: vitest 361/32 pass + lint 0/7 warn + tsc clean; B4: AST gates 981/1). FE tier ⏳ in progress: `#50` thumbs ✅ + `#53` Ingest Data backend ✅ + `#54` Delete Data backend ✅ (FE multi-select half open) + `#35d` FE admin merge ⏳ + `#24` SSE FE polish ⏳. Phase 7 closure is staged: backend-tier-drained is a real green signal; FE-tier-drained is the remaining gate. |

### Notes from the 2026-06-04 pass

- **One template wording fix** in H1: `post_provision.sh` → `post-provision.{sh,ps1}` + `post_provision.py`. The repo uses hyphenated shell wrappers and an underscored Python helper. The spot-check command in this row was rewritten to match the on-disk names so the next reviewer doesn't hit the same mismatch.
- **Phase 6 "closure" is structural, not exhaustive.** The 4 blueprints + smoke CI shipped — that is the Phase 6 baseline that lets Phase 6 work continue. Active Phase 6 development (debt rows, blueprint hardening) appends to dev_plan §0.1 within phase per Hard Rule #12; the closure check here only verifies the structural baseline is intact, not that every Phase 6 task is finished.
- **Phase 7 staging is by design.** The backend tier hit green on 2026-06-02 because every backend §0.1 row originating in Phases 1–7 is drained except externally-blocked items (FE-owned, upstream OSS, `#39`-gated). The FE tier is its own gate per project_status.md Executive Status — explicitly carry-forward.
- **No new dev_plan §0.1 debt rows opened.** All discrepancies were doc-text in the QA review plan template itself, fixed inline.

**Evidence file pointers**

- Phases status table — [project_status.md](project_status.md) (lines 126-140).
- Lifespan — [v2/src/backend/app.py](../src/backend/app.py).
- Health routes — [v2/src/backend/routers/health.py](../src/backend/routers/health.py).
- Orchestrator registry — [v2/src/backend/core/providers/orchestrators/registry.py](../src/backend/core/providers/orchestrators/registry.py).
- Smoke CI — [.github/workflows/v2-backend-only-smoke.yml](../../.github/workflows/v2-backend-only-smoke.yml).
- `azure.yaml` — [v2/azure.yaml](../azure.yaml).

---

## Phase I — Open debt drain plan

Mirror dev_plan §0.1 (backend) + §0.2 (frontend) open rows exactly. **No new debt invented here.** One row per open item.

**Reviewed 2026-06-04** — 7 rows mirrored verbatim from dev_plan; statuses + drain actions cross-checked against `development_plan.md` §0.1 + §0.2 + project_status.md Open Debt by Dimension. No new rows added or invented.

| Unit | Debt row | Origin | Status | Drain action |
|---|---|---|---|---|
| I1 | `#35d` FE admin merge | dev_plan §0.2 | ⏳ partial | Prompt-editor backend persistence decision (local-draft vs. `PATCH /api/admin/config` wiring) + FE acceptance test coverage |
| I2 | `#35g` per-tenant overrides | dev_plan §0.1 | — withdrawn (out of scope) | Withdrawn for the single-tenant deployment model; tenant-keyed config is a no-op over the singleton. See [ADR 0024](adr/0024-withdraw-per-tenant-runtime-config-single-tenant.md) (supersedes ADR 0023) |
| I3 | `#24` SSE FE remaining | dev_plan §0.2 | ⏳ partial | Citation cards, reconnect, cancel button, abort, multi-turn UX polish (FE backlog) |
| I4 | `B-IMPL-FACTORY-CACHE` | dev_plan §0.1 | ☐ open | Cache `FoundryAgent` per `(project_endpoint, agent_name, credential_identity)` at orchestrator-registry layer with lifespan shutdown hook |
| I5 | `B-IMPL-EXTRAS` | dev_plan §0.1 | ☐ deferred | Optional Agent Framework extras (`a2a`, `copilotstudio`, `microsoft`, `redis`); add only if a Scenario Pack needs them |
| I6 | `B-IMPL-FOUNDRY-STUBS-DEBT` | dev_plan §0.1 | ☐ upstream | Track upstream OSS SDK `py.typed` shipment; remove suppression when fixed. Not actionable on our side |
| I7 | `DV1` docker compose | dev_plan §0.2 | ⏸ blocked | Re-run `docker compose --profile {backend,frontend}-only config` once Docker daemon is restored |

**Discipline**: Each open row stays exactly as it appears in dev_plan. The QA review does NOT shorten, edit, or close debt rows — only mirrors them.

### Notes from the 2026-06-04 pass

- **Backend debt is structurally drained.** Per dev_plan §0 row 7 + `U-P7-AUDIT-3` (2026-06-02), every backend §0.1 row originating in Phases 1–7 is ✅ cleared except the listed rows: I4, I5, I6 are externally blocked (FE-owned, upstream OSS, or post-Phase-7 hardening), I2 (`#35g`) is withdrawn as out of scope (single-tenant — ADR 0024), plus I1 which is the FE half of an admin merge whose backend surface is complete. No new actionable backend debt was opened during the 2026-06-04 QA review.
- **`#39` is ✅ cleared; `#35g` is withdrawn (out of scope).** `#39` `requires_role("admin")` RBAC narrowing shipped 2026-05-06 (per §0 row 5). `#35g` (per-tenant overrides) is **no longer a debt row** — it was withdrawn for the single-tenant deployment model (tenant-keyed config is a no-op over the singleton; see [ADR 0024](adr/0024-withdraw-per-tenant-runtime-config-single-tenant.md), which supersedes ADR 0023). The tenant-claim seam shipped for it has been removed.
- **`#54` FE multi-select half is a Phase 7 task residue, not a §0.1 debt row.** It is tracked in dev_plan §4.7.1 task table (backend route + `BaseSearch.delete_by_source` ABC + 2 impls shipped `U-P7-54-BE` 2026-05-31). It is intentionally **not** mirrored as an I-row here because Phase I mirrors §0.1 + §0.2 only. It is correctly surfaced under H7 + project_status.md Executive Status.
- **`AST-GATE-NODE_MODULES-BACKFILL` is ✅ done.** The `node_modules/` carve-out added 2026-06-03 during `U-P7-53-AUDIT` back-fill across all 8 tree-walking AST gates is closed (confirmed under B4 — 981 passed / 1 skipped). Not a Phase I row.
- **`B1-MAF-MISLABEL` is ✅ done.** Agent Framework orchestrator rebuilt on OSS `agent_framework_foundry.FoundryAgent` 2026-06-02 per §0 row 3 `B-IMPL` notation. Not a Phase I row.
- **`DV1` is the only blocker that affects this QA review pass.** Live `docker compose config` exec was substituted with static YAML profile validation under E2. The drain action stays as-written — re-run when daemon returns.

**Evidence file pointers**

- Backend debt — [v2/docs/development_plan.md §0.1](../docs/development_plan.md).
- Frontend debt — [v2/docs/development_plan.md §0.2](../docs/development_plan.md).
- Open Debt by Dimension — [project_status.md](project_status.md) (lines 142-165).

---

## Phase J — QA acceptance pack

Final three units: smoke contract, manual QA matrix, sign-off ceremony.

**Reviewed 2026-06-04** — 3 CI workflows confirmed on disk; smoke contract anchored to actual gate semantics; manual QA matrix validated against `v2/tests/smoke/test_backend_only.py` route expectations; sign-off grid left blank for QA reviewer.

### J1 — Smoke contract: "ready for QA" gate

**Three CI workflows together form the gate.** All three must be green on `main` (or on the PR head) for the deliverable to be considered ready for QA. Path-scoped triggers — unrelated edits do not pay CI cost.

| # | Workflow | Path | Gate semantic |
|---|---|---|---|
| 1 | `v2 typecheck (pyright)` | `.github/workflows/v2-typecheck.yml` | `uv run pyright` (strict, scoped to `v2/src/backend/**` + `v2/src/functions/core/**` per `[tool.pyright]`) — `errors=0 warnings=0 informations=0`. Hard gate (no `continue-on-error`) since Q14e |
| 2 | `v2 frontend checks (lint + typecheck + vitest)` | `.github/workflows/v2-frontend-checks.yml` | Three sequential checks against `v2/src/frontend`: `npm run lint` (ESLint flat, strict-type-checked) → `npx tsc -p .` (strict + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes`) → `npm test` (vitest run). Hard gate per ADR 0014 |
| 3 | `v2 backend-only smoke` | `.github/workflows/v2-backend-only-smoke.yml` | Boots `backend + azurite + postgres` from clean room via `docker compose -f docker-compose.dev.yml -f docker-compose.smoke.yml --profile backend-only up -d --build`; waits ≤120s for `cwyd-v2-backend` healthcheck; runs `uv run pytest -m smoke tests/smoke/ -v` against `CWYD_SMOKE_BACKEND_URL=http://localhost:8000`; dumps logs on failure; tears down on `always()` |

**"Ready for QA" gate = all four green:**

1. ✅ `v2 typecheck (pyright)` — `0 errors / 0 warnings / 0 informations`.
2. ✅ `v2 frontend checks` — lint + tsc + vitest all pass.
3. ✅ `v2 backend-only smoke` — backend boots in clean room + smoke tests pass.
4. ✅ Local **9 AST gates green** (`v2/tests/shared/` × 8 + `v2/tests/test_no_silent_excepts.py` × 1) — currently rolled into `pytest` default run; B4 baseline `981 passed / 1 skipped` (2026-06-04).

**Local baseline numbers to compare against (2026-06-04, B-phase):**

- pyright: `0 errors / 0 warnings / 0 informations` (scoped).
- pytest default: `2047 passed / 1 skipped / 3 deselected / 6 warnings` (smoke marker excluded).
- vitest: `361 tests / 32 suites passed`.
- ESLint: `0 errors / 7 advisory` (HMR-only warnings).
- AST gates: `981 passed / 1 skipped`.

**Smoke marker discipline:** smoke tests live under `v2/tests/smoke/` and are gated by the `smoke` pytest marker (registered in `v2/pyproject.toml`). Default `pytest` excludes them via `addopts = "-m 'not smoke'"`, so the main suite count is unaffected and only the dedicated workflow runs them.

### J2 — Manual QA matrix

Run on a fresh subscription after the J1 gate is green. Pass = every row green.

| Scenario | Steps | Pass condition |
|---|---|---|
| Cold deploy | `azd up` from a clean azure subscription | Exit 0; all Bicep modules deploy; backend + frontend reachable via App URLs |
| Health probe | `GET /api/health` and `GET /api/health/ready` | `/api/health` returns 200 with `{status, version: "v2", checks: [...]}`; `/api/health/ready` returns 200 (or 503 if `OverallStatus.FAIL` — must be intentional) |
| OpenAPI surface | `GET /openapi.json` | Schema includes `/api/conversation`, all 9 `/api/admin/*` routes, all 8 `/api/history/*` routes, `/api/speech/*` |
| Chat round-trip | Open chat UI → ask a grounded question → observe SSE | `reasoning` panel renders; `answer` streams; ≥ 1 `citation` event fires; no `error` event |
| Admin PATCH live-reload | Admin UI → change a setting → save → ask a new question | New value visible in next request without backend restart; `GET /api/admin/config/effective` reflects override; audit row written |
| History persist + resume | Send 3 messages → reload page → reopen conversation | Conversation visible in history panel; messages render in order; resume continues with full context |
| Delete by source | Admin → Delete Data → pick source → confirm | All chunks with that `source` removed from index; subsequent chat does not cite that source. (FE multi-select half = `#54`, in progress) |
| Backend-agnostic DB | Repeat history scenario against Cosmos backend AND Postgres backend | Both backends pass identically; switching backend requires no FE change (see `HistoryPanel.tsx` backend-agnostic contract) |

### J3 — QA sign-off grid

Each row owned by a named reviewer with a dated evidence link. Phase rows mirror H1–H7; dimension rows mirror the per-dimension blocks in `project_status.md`.

| Row | Owner | Date | Evidence link |
|---|---|---|---|
| Phase 1 (H1) — infra + azd |  |  |  |
| Phase 2 (H2) — health probes |  |  |  |
| Phase 3 (H3) — orchestrator registry |  |  |  |
| Phase 4 (H4) — search + ingestion |  |  |  |
| Phase 5 (H5) — admin config + save |  |  |  |
| Phase 6 (H6) — Functions blueprints |  |  |  |
| Phase 7 (H7) — strict typing + AST gates |  |  |  |
| Dimension — Hard Rules (Phase C) |  |  |  |
| Dimension — Libraries (Phase D) |  |  |  |
| Dimension — Modularity (Phase E) |  |  |  |
| Dimension — Admin Config + Save (Phase F) |  |  |  |
| Dimension — Chat History (Phase G) |  |  |  |

### Notes from the 2026-06-04 pass

- **Three CI workflows on disk, not one.** The original A3 template framed the gate as "extend `.github/workflows/v2-backend-only-smoke.yml`" — but typecheck + frontend checks are already separate hard gates with their own path-scoped triggers. J1 reflects all three; the "ready for QA" criterion is the four-green combination above.
- **B2 baseline updated.** The original template said `1986/1/0`. Current baseline per Phase B (2026-06-04) is `2047 passed / 1 skipped / 3 deselected / 6 warnings` — 61-test growth captured in J1.
- **Smoke marker discipline survives.** `smoke` is the only `pytest` marker that gates a separate CI workflow. The default `pytest` invocation stays at the B2 number because `addopts = "-m 'not smoke'"` is configured in `pyproject.toml`. Do not collapse them.
- **Pyright bare invocation footgun.** Per repo memory `cwyd-tech-stack.md` + Further Considerations #2: bare `uv run --project v2 pyright` can stall; the scoped form (`v2/src/backend v2/src/functions/core`) is the contract. CI uses the configured scope via `[tool.pyright]` — QA team must do the same locally.
- **DV1 carry-forward affects J1 manual rerun.** J1 row 3 (backend-only smoke) cannot be re-validated locally while Docker daemon is down. CI on `main` is the source of truth; do not gate QA acceptance on local Docker availability.
- **J3 sign-off grid is intentionally empty.** This is the deliverable surface — QA reviewer fills it as they complete each row. The grid covers every Phase H row + every dimension reviewed (C through G). No row is optional.

**Evidence file pointers**

- CI workflows — [.github/workflows/v2-typecheck.yml](../../.github/workflows/v2-typecheck.yml), [.github/workflows/v2-frontend-checks.yml](../../.github/workflows/v2-frontend-checks.yml), [.github/workflows/v2-backend-only-smoke.yml](../../.github/workflows/v2-backend-only-smoke.yml).
- Smoke test suite — [v2/tests/smoke/test_backend_only.py](../tests/smoke/test_backend_only.py).
- Smoke compose overlay — `v2/docker/docker-compose.smoke.yml` (referenced by workflow 3).
- B-phase baseline metrics — [project_status.md](project_status.md) Verified Metrics 2026-06-04 (line 27).
- Per-dimension closure — [project_status.md](project_status.md) Per-Dimension Status (line 44 onward).
- ADR coverage — [v2/docs/adr/0014-frontend-ci-workflow.md](adr/0014-frontend-ci-workflow.md) for J1 row 2; [v2/docs/adr/0017-agent-framework-foundry-pinned-dependency-policy.md](adr/0017-agent-framework-foundry-pinned-dependency-policy.md) for D1 alignment.

---

## Cross-reference

- [project_status.md](project_status.md) — per-dimension snapshot.
- [development_plan.md](development_plan.md) — canonical ledger (§0, §0.1, §0.2, §4).
- [pillars_of_development.md](pillars_of_development.md) — read-only pillar policy.
- [.github/copilot-instructions.md](../../.github/copilot-instructions.md) — Hard Rules 1–17.
- [qa_report_v2.archived.md](qa_report_v2.archived.md) — historical narrative (archived 2026-06-04).
