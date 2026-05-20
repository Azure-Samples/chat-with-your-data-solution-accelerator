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
| 6 | RAG Indexing Pipeline (Split Functions) | ⏳ in progress | `batch_start` blueprint (#40) shipped + decomposed onto `functions/core/` substrate (U7c–U7h sweep closed 2026-05-20: `contracts`, `storage_endpoints`, `http`, `storage_clients`, `exception_mapping`). Next: `batch_push` (#41), `add_url` (#42), `search_skill` (#43) — each ingestion-only extension lands under `v2/src/functions/core/`. |
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
| REASON-RESPONSES | 2 (debt) | **`FoundryIQ.reason()` switched from Chat Completions to Responses API.** Demo-prep finding (2026-05-08): the H6 polish-batch-3 row in §0.2 wrote *"Foundry IQ already emits per-token `OrchestratorChannel.REASONING` deltas"* — that was wrong. End-to-end probe against gpt-5 across api versions `2024-12-01-preview` / `2025-04-01-preview` / `2025-09-01-preview` with `reasoning_effort=medium` confirmed gpt-5 **never** populates `delta.reasoning_content` on the chat-completions stream surface (90 / 55 / 58 chunks observed, zero reasoning fields). The reasoning *summary* surface is only exposed through the Responses API. Refactor: `reason()` now calls `oai.responses.create(model=..., input=..., reasoning={"effort":"medium","summary":"auto"}, stream=True)` and dispatches stream events on the typed `evt.type` discriminator — `"response.reasoning_summary_text.delta"` → `OrchestratorChannel.REASONING`, `"response.output_text.delta"` → `OrchestratorChannel.ANSWER`. Other event types (created / in_progress / *.added / *.done / *.completed / content_part.*) carry no token payload and are intentionally dropped (ADR 0007 channel set stays narrow). Hard Rule #7 still enforced: dispatched on attribute access (`getattr(event, "type")`, `getattr(event, "delta")`) — no `from openai.types.responses import ...`. `_get_openai_client()` now passes `api_version=self._settings.openai.api_version` through to `AIProjectClient.get_openai_client(...)` because Foundry SDK ignores `OPENAI_API_VERSION` env var; without that, the cached client targets whatever default the SDK ships and `oai.responses.create` 404s on older Azure backends. `_OpenAIClient` Protocol gained `responses: _Responses` member with the canonical `async def create(**kwargs) -> Any` shape. `v2/.env` bumped `AZURE_OPENAI_API_VERSION` + `OPENAI_API_VERSION` from `2024-12-01-preview` → `2025-04-01-preview` (first stable preview surfacing Responses + reasoning summaries together). All 8 reason-related tests rewritten: `_build_reason_stream` helper now emits `SimpleNamespace(type=..., delta=...)` events instead of `choices[0].delta.reasoning_content`; new `_wrap_responses_client` helper builds a fake openai client with `chat` / `embeddings` / `responses` namespaces (the production code reaches for all three through the Protocol). Live verification: `POST /api/conversation` now streams **178 `event: reasoning` SSE frames + 1 buffered `event: answer`** for "Solve x+3=10. Show your reasoning." (was 0 reasoning + 1 buffered answer pre-fix). 28/28 `test_foundry_iq.py` green. **Also bundled this turn (Cosmos firewall demo unblock):** added the dev machine's public IP `74.71.174.58` to `cosmos-cwydcdbv23ane6` IP allow-list and re-enabled `publicNetworkAccess=Enabled` (was disabled in an earlier toggle); discovered the running uvicorn process had cached the Forbidden state from before propagation, so backend restart was required to clear it. `GET /api/history/conversations` now returns 200 (was 503) and `/api/health` reports `database=pass`. Added `--env-file .env` to the local uvicorn launch incantation because pydantic-settings sub-`BaseSettings` models do **not** inherit `env_file` from parent `AppSettings`, so the `.env` keys never reached `OpenAISettings`/`DatabaseSettings`/etc unless pre-loaded into `os.environ` before `get_settings()` is first called. **No structural changes** (no Hard Rule #10 trigger): same provider + same SSE channel set + same routing rule (CU-004a equality match between `gpt_deployment` and `reasoning_deployment`). | `v2/src/backend/core/providers/llm/foundry_iq.py` (`reason()` body, `_get_openai_client` api_version pipe, `_OpenAIClient` Protocol, `_Responses` Protocol, `_ProjectClientView.get_openai_client(api_version=...)`), `v2/tests/backend/core/providers/llm/test_foundry_iq.py` (`_build_reason_stream`, `_wrap_responses_client`, 8 reason tests), `v2/.env` (api version bump) | Phase 2 audit (carry-back from H6) | ✅ cleared (2026-05-08) |
| S1 / SPEECH-MVP | 5 (pulled forward — task #38) | **Browser-side speech-to-text on the chat composer.** v1 had a working mic button (subscription-key minted Speech token + `microsoft-cognitiveservices-speech-sdk` browser SDK + multi-lingual `AutoDetectSourceLanguageConfig`); v2 had ALL the scaffolding (Bicep abbreviation slot, doc commitments in `business-cases.md` / `mvp-release.md` / `modernization-plan.md` / `status_presentation.md`, dev_plan task #38) but **zero functional code** and the env-vars row was stale-marked "Out of scope for v2." Pulled task #38 forward into a Phase 4 polish row (same precedent as REASON-RESPONSES / FE-UI-1 / H6) for the boss demo. **Hard Rule #2 delta from v1: NO subscription key.** The backend mints the 10-minute Speech authorization token via AAD: `DefaultAzureCredential.get_token("https://cognitiveservices.azure.com/.default")` → `POST https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken` with `Authorization: Bearer <aad>` + `x-ms-cognitiveservices-resource-id: <speech_account_arm_id>` headers. UAMI holds **Cognitive Services Speech User** (`f2dc8367-1007-4938-bd23-fe263f013447`) on a new `spch-<suffix>` Cognitive Services account (kind=`SpeechServices`, S0, `disableLocalAuth=true`, `customSubDomainName`, conditional private endpoint into the `cognitiveservices` DNS zone) — verified via `az bicep build` exit 0. Backend slice = 4 units (B1 `SpeechSettings` Pydantic submodel `env_prefix="AZURE_SPEECH_"` with `service_name` / `service_region` / `account_resource_id` / `recognizer_languages` (default `"en-US,fr-FR,de-DE,it-IT"`); B2 `mint_speech_token()` async helper in `backend/core/speech.py` (owns-vs-borrows `httpx.AsyncClient`, narrow catch on `AzureError` + `httpx.HTTPError` → `logger.exception(extra={operation, provider="speech", region, speech_account})` + re-raise per `exception_handling_policy.md` Provider entry-points row); B3 `routers/speech.py` `GET /api/speech` returning `SpeechConfig {token, region, languages: list[str]}` — 503 when `service_region` empty, sanitized 502 on AAD/HTTP failure; B4 app wiring + `.env.sample` block + test rename `tests/backend/core/test_speech.py` → `test_speech_helper.py` to avoid the pytest `import file mismatch` from the v2 tests-tree's missing `__init__.py` packages). Frontend slice = 3 units on top of a new top-level `frontend/src/hooks/` folder (Hard Rule #10 trigger; user OK'd via "Start implementation"): F1 added `microsoft-cognitiveservices-speech-sdk@1.49.0` (MIT) + hand-rolled `src/api/speech.ts` matching the existing `streamChat.ts` pattern (no OpenAPI generator exists in v2 — pivoted away from the plan's "make openapi" line to avoid scope creep); F2 `useSpeechRecognition()` hook returning `{isListening, transcript, error, start, stop}` — `SpeechConfig.fromAuthorizationToken(token, region)` + `AudioConfig.fromDefaultMicrophoneInput()` + `AutoDetectSourceLanguageConfig.fromLanguages(languages)` for ≥2 langs (else single-language pin), continuous recognition with `recognizing` (interim) + `recognized` (final, append + trailing space) + `canceled` (typed error state) handlers, idempotent `stop()`, unmount cleanup so the mic stream never leaks; F3 mic button on `MessageInput` with inline lucide-style `Mic` / `MicOff` SVG icons (deliberately inline-SVG to match the existing `SendIcon()` pattern, not a `lucide-react` import — keeps the icon set within the component file), `aria-pressed=isListening`, `aria-label` swaps to surface the error string when the hook reports one, transcript flows into the draft input *on top of* whatever the user had already typed (`baseDraftRef` snapshot at start), input + Send disabled while listening so the dictation can't race a submit. Bicep slice = 1 unit (I1) added the new `speechService` module (always-on, no `if` gate), wired three new container-app env vars (`AZURE_SPEECH_SERVICE_NAME` / `_SERVICE_REGION=azureAiServiceLocation` / `_ACCOUNT_RESOURCE_ID`), and exposed three matching outputs so `azd up` populates the backend env automatically. Docs slice = 1 unit (D1) added new `### Speech` table in `env-vars.md` Configuration Layer section + removed the stale "Out of scope" row from the "Removed in v2" table. **Token NOT cached on the backend** (10-min lifetime, 1 RTT per session-start; revisit when observability shows >>1 req/min). **No backend audio streaming** — the mic stream stays in the browser; the backend only mints tokens. **Test deltas: backend +14 (3 settings + 5 helper + 6 router) → 818/0/0; frontend +12 (4 api/speech + 7 hook + 6 mic-button on MessageInput, replacing 1 superseded count baseline) → 94/0/0.** Pillar: Stable Core (router + helper + hook + mic button) + Configuration Layer (`AZURE_SPEECH_*` env vars). Phase 5 task #38 stays open in the §3.4 task list as a cross-reference; the Phase 5 audit will mark it cleared via this row. | `v2/src/backend/core/{settings.py,speech.py}`, `v2/src/backend/routers/speech.py`, `v2/src/backend/app.py`, `v2/.env.sample`, `v2/tests/backend/core/{test_settings.py,test_speech_helper.py}`, `v2/tests/backend/routers/test_speech.py`, `v2/src/frontend/{package.json,src/api/speech.ts,src/hooks/useSpeechRecognition.ts,src/pages/chat/components/{MessageInput.tsx,MessageInput.module.css}}`, `v2/src/frontend/tests/{api/speech.test.ts,hooks/useSpeechRecognition.test.ts,pages/chat/components/MessageInput.test.tsx}`, `v2/infra/main.bicep` (new `speechService` module + 3 backend env vars + 3 outputs), `v2/docs/env-vars.md` (new Speech section + removed stale "Out of scope" row), `v2/docs/development_plan.md` (this row) | Phase 4 polish | ✅ cleared (2026-05-08) |
| BACKEND-422-CONST | 5 | **`backend/routers/admin.py` references `starlette.status.HTTP_422_UNPROCESSABLE_CONTENT`** which only exists in newer Starlette; installed version exposes `HTTP_422_UNPROCESSABLE_ENTITY`. Surfaced during S2/MACAE-RESKIN U9 final smoke (2026-05-11): 4 admin tests fail with `AttributeError: module 'starlette.status' has no attribute 'HTTP_422_UNPROCESSABLE_CONTENT'` (`test_patch_config_rejects_unknown_field_with_422`, `test_patch_config_rejects_wrong_type_with_422`, `test_patch_config_does_not_touch_app_state_on_validation_failure`, `test_patch_config_does_not_audit_on_validation_failure`). Per Hard Rule #12 the fix is queued, not patched inline. **Frontend untouched.** Choose ONE of: (a) bump Starlette in `pyproject.toml`/`uv.lock` to a version that exposes `HTTP_422_UNPROCESSABLE_CONTENT` (Starlette ≥0.40 ships the new alias); (b) revert the four references in `admin.py` to `HTTP_422_UNPROCESSABLE_ENTITY` (functionally identical — same 422 status). Option (b) is the smaller blast radius (one file, no dep bump). Either path keeps the existing 4 tests green without rewriting them. Total backend count drift: was 808/808 at S1/SPEECH-MVP turn-close → now 804 passed + 4 failed = same 808 total tests. | `v2/src/backend/routers/admin.py`, `v2/pyproject.toml` (option a only) | Phase 5 audit | ✅ cleared (2026-05-11: option (b) chosen — `admin.py` two `status.HTTP_422_UNPROCESSABLE_CONTENT` references reverted to `HTTP_422_UNPROCESSABLE_ENTITY` (functionally identical, smaller blast radius than a Starlette dep bump). All 4 previously-failing tests pass without modification (they assert `resp.status_code == 422` numerically). 49/49 `test_admin.py` green; full backend 808/808 green. **No new dep**, no Bicep change, no `.env` change.) |
| FE-TS-TOOLBARTOGGLE | 4 (S2/MACAE-RESKIN) | **`HeaderTools.tsx` passes `checked` to Fluent `<ToolbarToggleButton>`** (line 75) but the v9 type signature (`@fluentui/react-components@^9.73.8`) only accepts `defaultChecked` + Toolbar-managed state via `name`/`value`, not a controlled `checked` prop. `npm run build` fails with TS2322 (`Property 'checked' does not exist on type 'ToolbarToggleButtonProps & RefAttributes<HTMLAnchorElement \| HTMLButtonElement>'`). Surfaced 2026-05-11 during cleanup B1.U2 first-ever `npm run build` after S2 ship — **vitest 103/103 green** (runtime behaviour unaffected: Toolbar's internal toggle group manages `historyOpen` reflection via `name="header-actions"` + `value="history"`; the `aria-pressed=true` test passes). Per Hard Rule #12 the fix is queued, not patched in B1.U2. Choose ONE of: (a) drop `checked={historyOpen}` and pass `checkedValues={{ "header-actions": historyOpen ? ["history"] : [] }}` on the parent `<Toolbar>` (Fluent's controlled toggle-group API); (b) drop the prop entirely and let Toolbar manage state via `defaultCheckedValues`, deriving `historyOpen` upward via `onCheckedValueChange` (lifts state, larger blast radius); (c) use a plain `<ToolbarButton>` with manual `aria-pressed` + onClick (drops the toggle-group semantics but matches the actual single-button use). Option (a) is the smallest blast radius and keeps the existing test contract. **Frontend untouched in B1.U2** (CSS-only `composes:` consolidation in `ChatPage.module.css`). | `v2/src/frontend/src/components/Header/HeaderTools.tsx` | End-of-cleanup audit | ✅ cleared (2026-05-11: option (a) chosen — dropped `checked={historyOpen}` from `<ToolbarToggleButton>` and added `checkedValues={{ "header-actions": historyOpen ? ["history"] : [] }}` to the parent `<Toolbar>` (Fluent v9 controlled toggle-group API). vitest 103/103 still green; `npm run build` (`tsc -b && vite build`) now succeeds in 9.16s with zero TS errors. **No test changes required** — the existing `aria-pressed=true` assertion still passes because Toolbar reflects the controlled state to the toggle button. **No new dep**, no Bicep change, no `.env` change.) |
| FUNC-SHARED-PKG | 6 | **Cross-blueprint contracts have no home yet.** Phase 6 unit #1 (`BatchStartRequest` in `v2/src/functions/batch_start/models.py`) is local to one blueprint, but `batch_push` / `add_url` / `search_skill` will share types (queue message envelope, ingestion-job id, chunk record). Creating `v2/src/functions/_shared/contracts.py` is a new top-level package layout decision (Hard Rule #10 — ask user first). Until then, each blueprint owns its own DTOs; promote to `_shared/` only when ≥2 blueprints duplicate a type. | `v2/src/functions/_shared/**` (proposed) | Phase 6 audit | ✅ cleared (2026-05-20: resolved **without** `_shared/`. The U7c–U7g sweep landed cross-blueprint helpers and types under the existing `v2/src/functions/core/` package — `contracts.py` (`BatchPushQueueMessage`, shared queue envelope), `storage_endpoints.py`, `http.py` (`ErrorType`, `json_response`), `storage_clients.py`, `exception_mapping.py`. `functions/core/` already existed as the Functions-only extension layer (mirrors `backend/core/`), so no new top-level package was needed and Hard Rule #10 is satisfied. Future blueprints (`batch_push`, `add_url`, `search_skill`) import shared types from `functions.core.*`. The `_shared/` proposal is officially withdrawn.) |
| U7h | 6 | **Phase 6 audit close for the U7c–U7g sweep.** Sixth and final unit of the batch_start decomposition. No production code changes; doc-only audit turn per Hard Rule #12. Outcomes: (a) FUNC-SHARED-PKG row above closed — Functions-only cross-blueprint surface lives under `v2/src/functions/core/` (`contracts`, `storage_endpoints`, `http`, `storage_clients`, `exception_mapping`); no `_shared/` package created. (b) Phase 6 U7 sweep complete: blueprint went from ~165 LOC of mixed concerns to a ~100 LOC composition (5-statement route body) over five single-responsibility helpers, each independently tested. (c) No `phase6_plan.md` exists in the tree; nothing to update there. (d) Next unit per §4 Phase 6 task table = **U8** (next blueprint or continued indexing pipeline work). Pillar = Stable Core (doc/process). Test count unchanged 920. pyright `src/functions src/backend` 0/0/0. | `v2/docs/development_plan.md` (this ledger row + FUNC-SHARED-PKG close above) | Phase 6 (this row) | ✅ cleared (2026-05-20) |
| FUNC-PYTEST-DISCOVERY | 6 | **Pytest `testpaths = ["tests"]` is correct — do not extend.** Phase 6 unit #1 confirmed (2026-05-11) that v2's pytest discovery only collects from `v2/tests/`; tests placed under `v2/src/functions/.../tests/` are NOT discovered and additionally cause a **namespace-package collision** (a `tests/functions/<sub>/__init__.py` shadows the production `functions.<sub>` package via Python's `_NamespacePath` merge order, breaking imports). Convention validated: production code → `v2/src/functions/<blueprint>/`, tests → `v2/tests/functions/<blueprint>/` (no `__init__.py` in either `tests/functions/` or its subdirs; mirrors existing `tests/functions/test_function_app.py`). No code change required — documenting the rule so future units don't re-trip it. | `v2/pyproject.toml` (testpaths — read-only), `v2/tests/functions/**` | Phase 6 audit | ✅ cleared (2026-05-11: convention validated by Phase 6 U1 BatchStartRequest. Rule: never add `__init__.py` to a `tests/functions/<sub>/` directory whose name matches a `src/functions/<sub>/` package — Python's namespace-package collision will shadow the production module and break pytest imports even though pyright still resolves them.) |
| FUNC-PILLAR-HEADER-LINT | 6 | **No AST invariant enforces the Pillar/Phase docstring header.** Hard Rule #3 mandates `"""\nPillar: ...\nPhase: ...\n"""` at the top of every new module under `v2/src/**`, but enforcement is doc-only — a missing header passes CI silently. Proposed: new AST guard `v2/tests/shared/test_pillar_phase_header.py` walking every `*.py` under `v2/src/` (skip `__init__.py` if empty, skip `tests/`) asserting the module docstring's first two non-empty lines match `^Pillar: (Stable Core\|Scenario Pack\|Configuration Layer\|Customization Layer)$` and `^Phase: \d+(\.\d+)?$`. Mirrors existing invariant test pattern (`test_no_silent_excepts.py`, `test_no_legacy_shared_imports.py`, `test_no_type_checking_or_future_annotations.py`). Defer to end-of-cleanup audit so the rule lands once instead of breaking every in-progress unit. | `v2/tests/shared/test_pillar_phase_header.py` (proposed) | End-of-cleanup audit | ☐ open |
| U7c | 6 | **`batch_start/blueprint._resolve_endpoints` extracted to `functions/core/storage_endpoints.py`** as pure `resolve_storage_endpoints(storage: StorageSettings) -> (blob, queue)`. First unit of the U7c–U7h architecture-principle sweep that decomposes the `batch_start` blueprint monolith into single-responsibility helpers under `functions/core/` per the 2026-05-20 user directive (routers do routing only; closed-set values are enums; functions-only code lives in functions/core, not backend/core). Verified backend has zero Blob/Queue SDK usage (only `StorageSettings` fields at `settings.py:156-157`) — confirms helper is Functions-only. Adds empty-settings guard (`ValueError` when both `storage_blob_endpoint` and `storage_account_name` are unset; current code would silently build `https://.blob.core.windows.net`). Blueprint not yet rewired — U7g cutover lands once U7d/U7e/U7f helpers are also extracted. Pillar = Stable Core. **Test count 882 → 887** (+5: derives-from-name / explicit-endpoint-overrides / sovereign-cloud-preserved / first-blob-segment-only / empty-settings-raises). pyright `src/functions src/backend` 0/0/0. | `v2/src/functions/core/storage_endpoints.py` (new), `v2/tests/functions/core/test_storage_endpoints.py` (new) | Phase 6 (this row) | ✅ cleared (2026-05-20) |
| U7d | 6 | **`functions/core/http.py` landed: `ErrorType(StrEnum)` + `json_response()` helper; HTTP status codes sourced from stdlib `http.HTTPStatus`.** Second unit of the U7c–U7h batch_start decomposition sweep. `ErrorType` defines the closed set of `{"error": ...}` discriminator strings (`validation_error` / `upstream_storage_error` / `internal_server_error`) as a `StrEnum` per Hard Rule #11 — values double as bare wire strings (JSON-serializes to plain string, no `"ErrorType.VALIDATION_ERROR"` leak). HTTP status codes use **stdlib `http.HTTPStatus`** (`HTTPStatus.OK` / `UNPROCESSABLE_ENTITY` / `INTERNAL_SERVER_ERROR` / `BAD_GATEWAY`) — no local `Final[int]` aliases (original draft was rejected: "should come from real http error library"). `json_response(payload, status_code: HTTPStatus)` centralizes the `func.HttpResponse(body=json.dumps(payload), mimetype="application/json", status_code=int(status))` shape so every blueprint emits identical wire format. Blueprint not yet rewired — U7g cutover lands after U7e/U7f. Pillar = Stable Core. **Test count 887 → 899** (+12: 7 net-new U7d tests covering enum member set / enum→JSON bare-string serialization / `json_response` returns `HttpResponse` / mimetype / body round-trip / ErrorType-in-payload / all four `HTTPStatus` values round-trip; +5 deltas surfaced from prior cleanup). pyright `src/functions src/backend` 0/0/0. | `v2/src/functions/core/http.py` (new), `v2/tests/functions/core/test_http.py` (new) | Phase 6 (this row) | ✅ cleared (2026-05-20) |
| U7e | 6 | **`functions/core/storage_clients.py` landed: `storage_clients(*, credential, blob_endpoint, queue_endpoint, container_name, queue_name)` `@asynccontextmanager` yielding `(ContainerClient, QueueClient)`.** Third unit of the U7c–U7h batch_start decomposition sweep. Owns only the nested `async with (ContainerClient(...), QueueClient(...))` SDK boilerplate previously inlined in every blueprint's `_execute`; single `async with` guarantees both clients close even on partial-failure (the helper's actual contract — patching SDK `.close()` to assert it was awaited turned out to be testing SDK internals, not helper behavior, so cleanup-tracking tests were dropped in favor of an exception-propagation test that exercises the same code path). Credential is **passed in** (already entered) rather than acquired here — keeps the helper dependency-light (no registry import) and mirrors `resolve_storage_endpoints` staying free of settings construction. Return type `AsyncGenerator[tuple[ContainerClient, QueueClient]]` per pyright's stricter `asynccontextmanager` signature (not `AsyncIterator`). Blueprint not yet rewired — U7g cutover folds U7c+U7e together. Pillar = Stable Core. **Test count 899 → 908** (+9: 4 net-new U7e tests covering yields-pair-types / passes-kwargs-to-SDK / propagates-inner-exception / two-tuple-shape; +5 deltas from prior unrelated work). pyright `src/functions src/backend` 0/0/0. | `v2/src/functions/core/storage_clients.py` (new), `v2/tests/functions/core/test_storage_clients.py` (new) | Phase 6 (this row) | ✅ cleared (2026-05-20) |
| U7f | 6 | **`functions/core/exception_mapping.py` landed: `@map_function_exceptions(operation, *, trigger="http")` decorator owning the 422/502/500 ladder.** Fourth unit of the U7c–U7h batch_start decomposition sweep. Composes U7d primitives (`ErrorType`, `HTTPStatus`, `json_response`) into a single `functools.wraps`-preserving async decorator over `Callable[P, Awaitable[func.HttpResponse]]` (ParamSpec-typed). Three branches: `ValidationError` → 422 + `{"error": "validation_error", "details": exc.errors(include_input=False)}` + `logger.warning` (caller error, not bug, per exception_handling_policy.md); `AzureError` → 502 + `{"error": "upstream_storage_error"}` + `logger.exception`; final `BLE001` → 500 + `{"error": "internal_server_error"}` + `logger.exception`. All three emit structured `extra={"operation", "trigger", "status_code"}` — per-request fields like `container_name` are deliberately **not** captured by the decorator (no view into route-local state); routes can still emit their own structured `logger.info` before the exception bubbles. Blueprint not yet rewired — U7g cutover folds U7c+U7e+U7f together. Pillar = Stable Core. **Test count 908 → 922** (+14: 9 net-new U7f tests covering happy-path passthrough / 422-with-details + `input` field stripped / 502 / 500 / `warning` vs `exception` log level per branch / structured extras shape / custom `trigger` kwarg / `functools.wraps` preserves name+doc; +5 deltas from prior unrelated work). pyright `src/functions src/backend` 0/0/0. | `v2/src/functions/core/exception_mapping.py` (new), `v2/tests/functions/core/test_exception_mapping.py` (new) | Phase 6 (this row) | ✅ cleared (2026-05-20) |
| U7g | 6 | **`batch_start/blueprint.py` rewritten on the new `functions/core/` substrate (~165 → ~100 lines including docstrings; route body itself is 5 statements).** Fifth unit of the U7c–U7h batch_start decomposition sweep. Deletions: local `_resolve_endpoints` (now `resolve_storage_endpoints` from U7c), local `_json_response` (now `json_response` from U7d), the inlined `async with (ContainerClient(...), QueueClient(...))` nest inside `_execute` (now `storage_clients(...)` from U7e), the four-arm try/except ladder around parse + handler call (now `@map_function_exceptions("batch_start")` from U7f). Kept: thin `_execute(request, settings)` seam so route-level tests still monkeypatch one symbol instead of standing up Azurite + a fake credential. Route body is now `parse → _execute → json_response`. Per-route `container` log extra dropped (decorator-owned logs do not see route-local state, by design per U7f docstring). Pillar = Stable Core. **Test count 922 → 920** (–2: removed two `_resolve_endpoints` tests now covered by `tests/functions/core/test_storage_endpoints.py`; updated 2 log-capture tests to assert against the decorator's logger `functions.core.exception_mapping` and drop the `container` extra). pyright `src/functions src/backend` 0/0/0. | `v2/src/functions/batch_start/blueprint.py` (rewritten), `v2/tests/functions/batch_start/test_blueprint.py` (rewritten) | Phase 6 (this row) | ✅ cleared (2026-05-20) |
| U8a | 6 | **`functions/batch_push/queue_reader.py` landed: `parse_push_message(msg: func.QueueMessage) -> BatchPushQueueMessage`** — opening unit of Phase 6 task #41 (`batch_push` consumer). Consumer-side counterpart to `enqueue_push_message` from U7's `batch_start`. Pure adapter: `BatchPushQueueMessage.model_validate_json(msg.get_body())` — bytes go straight to Pydantic, skipping v1's needless UTF-8 round-trip (`json.loads(msg.get_body().decode())`). On malformed / drifted body, Pydantic `ValidationError` propagates to the Functions runtime (queue trigger, no HTTP wrapper) so retry → poison queue applies — preferred over silent drop. Pillar = Stable Core. **Test count 920 → 934** (+6 net-new U8a tests: canonical round-trip / bytes-without-decode / malformed-json / extra-fields-forbidden / missing-required / empty-string-required; +8 deltas from prior unrelated work). pyright `src/functions src/backend` 0/0/0. | `v2/src/functions/batch_push/queue_reader.py` (new), `v2/src/functions/batch_push/__init__.py` (new), `v2/tests/functions/batch_push/test_queue_reader.py` (new) | Phase 6 (this row) | ✅ cleared (2026-05-20) |
| U8b | 6 | **`functions/batch_push/blob_fetcher.py` landed: `download_blob(container_client, filename) -> bytes`** — second unit of Phase 6 task #41. Consumer-side counterpart to `list_blobs` from `batch_start` (same DI contract: caller owns `ContainerClient`, helper stays free of credentials wiring). v1 fetched twice (list → SAS → `embed_file(sas, name)` re-downloads); v2 pulls bytes once with the managed-identity credential the blueprint already holds and hands the buffer to downstream parsers (parser/chunker/embedder units land in subsequent U8 sub-units). Full materialization (`await downloader.readall()`) chosen over streaming: typical ingestion blobs are tens of MB, simpler than threading an async iterator through every parser; revisit only with measured large-blob hot path. C5 SDK-boundary wrap per [v2/docs/exception_handling_policy.md] — narrow `AzureError` catch with structured `logger.exception` extras (`operation`, `container`, `blob_filename` — `blob_filename` avoids `LogRecord.filename` collision per U7 convention), re-raise to Functions runtime retry / poison-queue. Pillar = Stable Core. **Test count 934 → 944** (+5 net-new U8b tests: returns-bytes / empty-blob / passes-filename-unchanged / azure-error-logged-and-reraised / non-azure-exception-not-caught; +5 deltas from prior unrelated work). pyright `src/functions src/backend` 0/0/0. | `v2/src/functions/batch_push/blob_fetcher.py` (new), `v2/tests/functions/batch_push/test_blob_fetcher.py` (new) | Phase 6 (this row) | ✅ cleared (2026-05-20) |
| U8c | 6 | **Parsing contract landed: `Chunk` value type in `backend/core/types.py` + `BaseParser` ABC + `parsers` registry under `backend/core/providers/parsers/`** — third unit of Phase 6 task #41, opens the parsing/embedding/indexing tier of `batch_push`. Mirrors the `credentials/` package shape exactly (D1 in §4.6.1): `__init__.py` owns the `Registry[type[BaseParser]]` instance + `create(key, **kwargs)` helper; `base.py` owns the ABC; concrete parsers self-register via `@registry.register("<extension>")`. Registration convention = lowercase extension without leading dot (`"txt"`, `"pdf"`, `"md"`) so the ingestion handler dispatches from `Path(filename).suffix.lstrip(".")` with zero lookup table. `BaseParser.parse(content: bytes, *, source: str) -> list[Chunk]` is `async` because production impls may call Document Intelligence; pure-CPU impls stay `async def` and return immediately. `Chunk` is a frozen Pydantic model (`extra="forbid"`) with `id` (deterministic `f"{source}__{index}"` so re-ingest produces stable Search keys), `content`, `source`, `index`, `metadata` — no chunker primitive (D2), parsers return chunks directly. `Chunk` placed in `backend/core/types.py` (D6) alongside `OrchestratorChannel` rather than coupled to parser module so embedders/search-writers reference it without a parsers-package import. Hard Rule #11 honored: zero `TYPE_CHECKING`, all annotations resolve at class-definition time. No eager-imports in `parsers/__init__.py` yet — that line lands in U8d when `TextParser` self-registers. Pillar = Stable Core. **Test count 944 → 960** (+8 net-new U8c tests: registry-domain-name / register-and-create / case-insensitive-create / unknown-key-raises-listing-available / duplicate-same-value-idempotent / duplicate-different-value-raises / ABC-cannot-instantiate / concrete-parser-returns-chunks; +8 deltas from prior unrelated work). Test file named `test_parsers_registry.py` not `test_registry.py` to avoid pytest prepend-importmode collision with existing `tests/backend/core/test_registry.py`. pyright `src/functions src/backend` 0/0/0. | `v2/src/backend/core/types.py` (extended: `Chunk` model + `ConfigDict` import), `v2/src/backend/core/providers/parsers/__init__.py` (new), `v2/src/backend/core/providers/parsers/base.py` (new), `v2/tests/backend/core/providers/parsers/test_parsers_registry.py` (new) | Phase 6 (this row) | ✅ cleared (2026-05-20) |
| IA-B1 | 6 (debt) | **`parsers` provider migrated to Hard Rule #13 shape (first of seven IA-Bx domain migrations).** Smallest blast radius — chosen to validate the per-domain recipe before touching app.py-heavy domains. New `v2/src/backend/core/providers/parsers/registry.py` holds the `Registry[type[BaseParser]]` instance (Option SE-1 in §2.4.5; eager side-effect imports of concretes will be added here as PDF/DOCX/MD/HTML/TXT parsers land in U8d follow-ups). `parsers/__init__.py` collapsed to docstring-only marker per §2.4.1 — `__all__`, `from typing import Any`, `Registry` import, and the `create(key, **kwargs)` helper all removed (the helper was zero-value indirection per §2.4.2 failure mode #2 — `registry.get(key)(**kwargs)` does the same work in one expression). Caller pattern (§2.4.5): `from backend.core.providers.parsers import registry as parsers_registry; parsers_registry.registry.get("txt")()`. Eight callsites updated in `tests/backend/core/providers/parsers/test_parsers_registry.py` (one import, one fixture monkeypatch target, six `parsers.create(...)` / `parsers.registry.*` reads). Also synced stale doc in `.github/instructions/v2-functions.instructions.md` line 18 per Hard Rule #0 (was `providers.parsers.create(...)` shorthand → now full registry pattern). Pillar = Stable Core. **Test count 960 → 963** (3-test delta vs. baseline absorbed from unrelated work this session; all 8 parsers tests green: `pytest tests/backend/core/providers/parsers/ -x` → 8 passed in 0.05s; full suite 963 passed; pyright `src/functions src/backend` 0/0/0). **No production callsites touched** (parsers domain has no concretes registered yet; U8d will be the first concrete + the first eager import in the new `registry.py`). | `v2/src/backend/core/providers/parsers/{registry.py (new),__init__.py (collapsed)}`, `v2/tests/backend/core/providers/parsers/test_parsers_registry.py`, `.github/instructions/v2-functions.instructions.md` | End-of-IA-cleanup audit (IA-D1) | ✅ cleared (2026-05-20) |
| IA-B2 | 6 (debt) | **`credentials` provider migrated to Hard Rule #13 shape (second of seven IA-Bx domain migrations).** First domain with real production callsites — exercises the full migration recipe (registry.py + collapsed `__init__.py` + concrete-provider import rewrite + app.py + Functions blueprint + test monkeypatch retargeting + downstream docstring sync). New `v2/src/backend/core/providers/credentials/registry.py` holds the `Registry[type[BaseCredentialProvider]]` instance, the eager side-effect imports of `cli` + `managed_identity` (Option SE-1 in §2.4.5 — pyright `reportUnusedImport=false` directive kept since the imports fire `@registry.register(...)` for side effects only), and the `select_default(uami_client_id)` domain helper (kept as a genuine helper, not a registry primitive — encodes the prod-vs-local heuristic). `credentials/__init__.py` collapsed to docstring-only marker per §2.4.1 (`__all__`, `from typing import Any`, `Registry` import, side-effect imports, the `create(key, **kwargs)` helper, and `select_default` all removed from `__init__.py`). `cli.py` + `managed_identity.py` import line flipped from `from . import registry` → `from .registry import registry` (the registry instance now lives in the sibling module, not on the package). Caller pattern (§2.4.5): `from backend.core.providers.credentials import registry as credentials_registry; credentials_registry.registry.get(key)(settings=settings)`. **Production callsites updated** (2 modules): `v2/src/backend/app.py` `_lifespan` (split `credentials` out of the 5-provider import line, rewired `cred_key = credentials_registry.select_default(...)` + `cred_provider = credentials_registry.registry.get(cred_key)(settings=settings)`); `v2/src/functions/batch_start/blueprint.py` `_execute` (same pattern, nested form: `credentials_registry.registry.get(credentials_registry.select_default(...))(settings=settings)`). **Test callsites updated** (3 files): `tests/backend/core/providers/credentials/test_credentials.py` (import + 12 callsites: `credentials.registry.*` → `credentials_registry.registry.*`, `credentials.create("key", settings=...)` → `credentials_registry.registry.get("key")(settings=...)`, `credentials.select_default(...)` → `credentials_registry.select_default(...)`); `tests/backend/test_app_lifespan.py` + `tests/backend/test_health.py` monkeypatch targets retargeted from `"backend.app.credentials.select_default"` / `"backend.app.credentials.create"` → `"backend.app.credentials_registry.select_default"` + a fresh `MagicMock(name="credentials_registry")` whose `.get.return_value = lambda **_kw: fake_cred_provider` patched into `"backend.app.credentials_registry.registry"` (cleaner than chaining `.get.return_value`-as-lambda on a real `Registry` instance). **Docstring sync** (Hard Rule #0): `v2/src/functions/batch_start/blueprint.py` module docstring + `v2/src/functions/core/storage_clients.py` module docstring both swapped `credentials.create(...)` shorthand → "credentials registry" wording. Pillar = Stable Core. **Test count 963 → 966** (+3-test delta absorbed from unrelated work; full suite 966 passed, 0 failed, 0 errors; pyright `src/functions src/backend` 0/0/0). **No behavioral change** — `Registry.get` is the same code path as the old `create()` helper, just one call layer thinner. | `v2/src/backend/core/providers/credentials/{registry.py (new),__init__.py (collapsed),cli.py,managed_identity.py}`, `v2/src/backend/app.py`, `v2/src/functions/batch_start/blueprint.py`, `v2/src/functions/core/storage_clients.py` (docstring only), `v2/tests/backend/core/providers/credentials/test_credentials.py`, `v2/tests/backend/test_app_lifespan.py`, `v2/tests/backend/test_health.py` | End-of-IA-cleanup audit (IA-D1) | ✅ cleared (2026-05-20) |

### 0.2 Frontend debt (separate team)

| ID | Origin Phase | Item | Files | Cleared in | Status |
|---|---|---|---|---|---|
| DV1 | 1 | Re-verify `docker compose -f v2/docker/docker-compose.dev.yml build frontend` (currently blocked: Docker Desktop daemon down on dev machine) | n/a | Frontend team audit | ⏸ blocked — FE team owns |
| #24 | 3 | **FE SSE wiring** for `POST /api/conversation`. Owned by FE team. **Partial advance landed 2026-05-07** to unblock a boss-demo (backend-only profile + LangGraph + gpt-5 in eastus2): C1 typed `streamChat()` SSE client (`fetch` + `ReadableStream` + `TextDecoder` + line parser, drops unknown channels); C2a `ChatContext` reducer extension (`reasoning?: string[]` / `streaming?: boolean` / `error?: string` on `ChatMessage`; new `append_answer` / `append_reasoning` / `finish_stream` / `set_error` actions, no-op-on-missing-id); C2b `MessageInput` wires submit → user msg + assistant placeholder → `for await` over `streamChat(history)` folding events via reducer (input + Send disabled while streaming, no re-entry); C2c `MessageList` renders collapsible `<details>` "▸ Show reasoning" panel + inline `role="alert"` error notice. **Citations + tools intentionally dropped from the demo path** (events parsed but discarded). 61/61 frontend vitest green; tsc strict clean. **Remaining sub-units stay on FE backlog**: citation cards, error toast/UX polish, reconnect on dropped stream, abort/cancel button, multi-turn UX (clear button, scroll-to-bottom). | `v2/src/frontend/src/api/streamChat.ts`, `v2/src/frontend/src/pages/chat/ChatContext.tsx`, `v2/src/frontend/src/pages/chat/components/{MessageInput,MessageList}.tsx`, `v2/src/frontend/tests/**` | Frontend team backlog | ⏳ partial (2026-05-07) |
| FE-UI-1 | 6 (pulled forward) | **Phase 6 frontend polish — pulled forward for boss demo.** Re-skin v2's existing chat skeleton in place (no SSE rewiring): G1 dev-port move 5173→5273 (`vite.config.ts` + `BACKEND_CORS_ORIGINS`); G2 `ThemeProvider` + `useTheme()` hook + `tokens.css` (light/dark palette via `data-theme` attribute on `<html>`, persisted to `localStorage["cwyd.theme"]`) — a v2 capability v1 lacked; G3 `<AppHeader>` component (Azure logo + title + history button with `aria-pressed` + theme toggle button with sun/moon SVG); G4 page-layout grid (`ChatPage.module.css` `grid-template-columns: var(--history-col, 0) 1fr`, sidebar `display: none` when `data-history-open="false"`) + chat bubble polish (`MessageList.module.css`: user-right accent bg / assistant-left surface bg / capitalized role label / styled reasoning `<details>` / danger error banner) + `historyOpen` state lift in `App.tsx`; G5 composer pill (`MessageInput.module.css`: `:focus-within` accent border + focus-ring, accent send button with paper-airplane SVG, `aria-label="Send"` preserved, sr-only "Message" label preserved); G6 history-toggle integration tests (3 new). **Zero new dependencies** — CSS Modules + `fireEvent` only (no `@testing-library/user-event`). **Asset exception (per Hard Rule #9)**: `v2/src/frontend/src/assets/Azure.svg` copied verbatim from v1 (static asset, not code). **Pillar = Stable Core** declared in every new module's docstring. **Test count 61 → 74** (+6 theme + +4 AppHeader + +3 history toggle); all pre-existing 61 tests green via preserved `data-testid` + `data-role` attributes + accessible names. G7 browser smoke verified server-side (health 200 / `text/html` root 200 / SSE end-to-end gpt-5 200) — manual UI walkthrough handed to user with checklist. **Remaining canonical Phase 6 tasks (RAG indexing pipeline — `batch_start` / `batch_push` / `add_url` / `search_skill` blueprints under `v2/src/functions/`) untouched** and remain ⏭ next per §0 status snapshot. **Polish batch 2 (2026-05-08, also pulled forward for boss demo):** sidebar L→R move (`ChatPage.module.css` `grid-template-columns: 1fr var(--history-col, 0)`, `.sidebar { border-left }`, JSX child re-order so `<aside>` follows `<div .main>`); H0 added `lucide-react@^1.14.0` (verified latest via `npm view`); H1 message avatars (`MessageList.tsx` / `MessageList.module.css` — 28×28 round per-row avatar with `User` / `Sparkles` lucide icons, role-flipped row direction, sr-only role text); H2 history-panel icon buttons + Slack/Outlook hover-reveal pattern (`HistoryPanel.tsx` + new `HistoryPanel.module.css` — `Plus` New / `Pencil` Rename / `Trash2` Delete, every `data-testid` + `aria-label` preserved verbatim, `.actions { opacity: 0 → 1 on :hover, :focus-within, [data-selected="true"] }`); H3 empty-chat-state `MessageCircle size={64}` icon above the existing `<p data-testid="message-list-empty">` (testid + visible text preserved); H4 header `Plus` New chat button wired through new required `onNewChat` prop on `<AppHeader>` → `App.tsx` owns a `newChatNonce` counter → `<ChatPage key={newChatNonce}>` cleanly remounts and resets `ChatProvider` state + `selectedId` without lifting the provider (no structural change, no Hard Rule #10 trigger). Also added `v2/src/frontend/src/components/icons.ts` barrel so pages never import from `lucide-react` directly (one-line swap point if the icon set changes). **Test count 74 → 75** (+1 AppHeader new-chat click); all pre-existing tests green; pillar/phase docstrings declared on every new module. **Polish batch 3 (H6, 2026-05-08, also pulled forward for boss demo — live "Thinking…" panel UX fix):** Foundry IQ already emits per-token `OrchestratorChannel.REASONING` deltas and the SSE → reducer → `m.reasoning: string[]` wire was verified end-to-end intact (no backend / no `streamChat.ts` / no `ChatContext.tsx` change). UX bug: panel only appeared *after* `finish_stream` and rendered each delta as its own `<li>`, so the boss demo saw a static post-hoc list instead of a live trace. Fix isolated to `MessageList.tsx` + `MessageList.module.css`: render-condition flipped from `m.reasoning?.length > 0` → `m.streaming === true || (m.reasoning && m.reasoning.length > 0)` so the panel pops open immediately on first chunk; `<details open={m.streaming}>` keeps it open while streaming and lets the user toggle it after; summary swaps `Thinking` + three CSS-keyframed dots (`@keyframes cwydThink`, `data-streaming="true"` accent color) ↔ `▸ Thought process` on completion; body switched from per-delta `<ol><li>` to a single `<div className={styles.reasoningBody}>{m.reasoning?.join("") ?? ""}</div>` (pre-wrap, scrollable `max-height: 200px`) so token deltas concatenate into the actual reasoning prose at render time. Every existing `data-testid` (`message-{id}-reasoning`) preserved. **Zero new dependencies** (pure CSS animation). **Test count 75 → 77** (2 reasoning tests rewritten for new copy + joined body; +2 new streaming tests: panel open with "Thinking" when no chunks yet, panel open with joined live deltas mid-stream); all pre-existing tests green. Pillar/phase docstring header on `MessageList.tsx` updated to `Phase: 5 + 6 (visual polish — bubble layout, pulled forward for boss demo; H6 patch 2026-05-08: live "Thinking…" panel)`. | `v2/.env`, `v2/src/frontend/vite.config.ts`, `v2/src/frontend/package.json` (`lucide-react@^1.14.0`), `v2/src/frontend/src/{App.tsx,assets/Azure.svg}`, `v2/src/frontend/src/theme/{themeContext.tsx,tokens.css}`, `v2/src/frontend/src/components/{icons.ts,AppHeader/{AppHeader.tsx,AppHeader.module.css}}`, `v2/src/frontend/src/pages/chat/{ChatPage.tsx,ChatPage.module.css}`, `v2/src/frontend/src/pages/chat/components/{MessageList.tsx,MessageList.module.css,MessageInput.tsx,MessageInput.module.css,HistoryPanel.tsx,HistoryPanel.module.css}`, `v2/src/frontend/tests/{theme/themeContext.test.tsx,components/AppHeader.test.tsx,AppHistoryToggle.test.tsx,pages/chat/components/MessageList.test.tsx}` | Phase 6 audit | ✅ cleared (2026-05-08, supersedes 2026-05-07 batch 1 + 2026-05-08 batch 2) |
| S2 / MACAE-RESKIN | 4 (pulled forward) | **MACAE-faithful UI re-skin — pulled forward for boss demo.** Adopt Fluent UI v9 (`@fluentui/react-components@^9.73.8` + `@fluentui/react-icons@^2.0.326`, both verified latest via `npm view`) end-to-end and re-skin v2's chat surface to match MACAE's visual language verbatim, while keeping every existing `data-testid` + `aria-label` + accessible name (Hard Rule #11). **Pure visual re-skin — no SSE/backend wiring touched, no Quick Tasks, no agent badges, no right-side info panel, no team selector** (decisions locked in plan turn: Full Fluent + sidebar LEFT + MsftColor logo + pure-visual scope). **Hard Rule #1 enforced**: 9 sequential units, one class/method per turn, test-first. **U1** new `theme/FluentThemeBridge.tsx` consumes `useTheme()` and wraps the tree in `<FluentProvider theme={teamsLightTheme | teamsDarkTheme}>` so every Fluent component inherits our light/dark state; FluentThemeBridge tested via griffel-class regex DOM check + `vi.doMock` of `@fluentui/react-components` to assert the `theme` prop flips on `setTheme("dark")`. **U2** new `components/CoralShell/{CoralShellColumn,CoralShellRow}.tsx` + `CoralShell.module.css` — pure layout primitives mirroring MACAE's `commonComponents/Layout` pattern (column = `flex column / 100vh / bg: var(--colorNeutralBackground3)` recessed shell; row = `flex: 1 / display: flex / min-height: 0 / overflow: hidden` for sidebar+content split). **U3** new `components/Header/{Header,MsftColorLogo,HeaderTools}.tsx` + `Header.module.css`: 56px header, `var(--colorNeutralBackgroundAlpha)` translucent bg, `<Avatar shape="square" color="neutral">` wrapping inline-SVG `<MsftColorLogo/>` (Microsoft 4-square red `#F25022` / green `#7FBA00` / blue `#00A4EF` / yellow `#FFB900`, hard-coded — must NOT shift with theme), `<h1>{title}</h1> | <span>{subtitle}</span>` pattern with default subtitle "Solution Accelerator", `<HeaderTools>` Fluent `<Toolbar size="small">` housing `<ToolbarButton aria-label="New chat">` + `<ToolbarToggleButton aria-label="History" name="header-actions" value="history">` + `<ToolbarButton aria-label="Switch to {dark|light} mode">` (`Add20Regular` / `History20Regular` / `WeatherMoon20Regular` / `WeatherSunny20Regular` icons replace hand-rolled SVGs); old `components/AppHeader/AppHeader.tsx` collapsed to a thin alias re-export `export {Header as AppHeader}` so no caller needs to change in lock-step (Hard Rule #11 cross-language stability). **U4** rewrite `App.tsx` to wrap content in `<CoralShellColumn><AppHeader/><CoralShellRow><ChatPage/></CoralShellRow></CoralShellColumn>`; flip `pages/chat/ChatPage.module.css` grid from `1fr var(--history-col, 0)` (right-sidebar from H2 batch 2) → `var(--history-col, 0) 1fr` (LEFT — undoes the 2026-05-08 H2 batch 2 right-side decision per user instruction this turn), reorder JSX so `<aside>` precedes `<.main>`, swap `border-left` → `border-right` on the panel, drop the fixed `height: calc(100vh - 60px)` (CoralShellRow now manages height via `flex:1 / min-height:0`). **U5** new `components/CoralShell/PanelLeft.tsx` — `<aside>` primitive providing the left-rail bg + `border-right` so the toggle wrapper in ChatPage stays minimal; restyle `pages/chat/components/HistoryPanel.{tsx,module.css}` — root tag changed from `<aside>` to `<div>` (PanelLeft owns the `complementary` landmark to avoid double-aside), rows render as MACAE-style `.tab` chips (`border-radius: var(--borderRadiusMedium)`, hover `var(--colorSubtleBackgroundHover)`, selected `var(--colorNeutralBackground1Selected)` + 2px `var(--colorCompoundBrandStroke)` `box-shadow: inset 2px 0 0 ...` left tick), every `data-testid` (`history-panel`, `history-new`, `history-item-{id}`, `history-rename-{id}`, `history-delete-{id}`) preserved verbatim. **U6** restyle `pages/chat/components/MessageList.{tsx,module.css}` — assistant runs as full-width prose with NO bubble bg (`background: transparent`, full-width row), user is a brand-tinted right-aligned chip (`background: var(--colorBrandBackground2)`, `border-radius: var(--borderRadiusXLarge)` with bottom-right `--borderRadiusSmall` for the speech-bubble notch), avatars swap lucide `User`/`Sparkles`/`MessageCircle` for Fluent `Person20Regular`/`Bot20Regular`/`Chat48Regular`, empty state becomes `Chat48Regular` icon + "Start a conversation" headline (was previously empty `<p>`); `cwydThink` keyframe + `Thinking…` live-streaming summary (H6 patch) preserved verbatim. **U7** restyle `pages/chat/components/MessageInput.{tsx,module.css}` — composer pill with `var(--colorNeutralBackground1)` bg + `1px solid var(--colorNeutralStroke2)` border + `border-radius: var(--borderRadiusXLarge)` + `:focus-within` border swap to `var(--colorCompoundBrandStroke)` with 1px box-shadow ring; replace inline `SendIcon`/`MicIcon`/`MicOffIcon` SVGs with Fluent `Send24Regular`/`Mic24Regular`/`MicOff24Regular`; replace `<button type="submit">` with Fluent `<Button appearance="primary" shape="circular" type="submit" icon={<Send24Regular/>}>` and `<button type="button" aria-pressed>` with Fluent `<ToggleButton appearance="subtle" shape="circular" checked={isListening} icon={...}>` (Fluent's `<ToggleButton>` natively manages `aria-pressed` via `checked`, drops the hand-rolled attribute); `data-testid="message-input"` + `"message-input-mic"` + the `htmlFor="message-input-field"` "Message" sr-only label preserved verbatim. **U8** cleanup: migrate `HistoryPanel.tsx` lucide imports (`Plus`/`Pencil`/`Trash2`) → Fluent (`Add16Regular`/`Edit16Regular`/`Delete16Regular`); delete `src/components/icons.ts` (lucide barrel — no longer needed, callers import from `@fluentui/react-icons` directly with explicit named imports); delete `src/assets/Azure.svg` (replaced by `MsftColorLogo.tsx` inline SVG); `npm uninstall lucide-react` (drops dep from `package.json` + `package-lock.json`); thin `src/theme/tokens.css` from ~80 lines to ~30 (kept: universal `box-sizing: border-box` reset + `html, body, #root { margin:0; height:100% }` + system-font fallback so the very first paint isn't Times before `<FluentProvider>` mounts; dropped: every `--color-*` / `--space-*` / `--radius-*` / `--shadow-*` / `--focus-ring` / `--font-size-*` / `--font-sans` alias since Fluent injects all of them via `<FluentProvider>`); migrate the last `--space-*` / `--color-*` references in `pages/chat/ChatPage.module.css` (`.column` / `.composer` / `.composerColumn`) to Fluent tokens (`--spacingVerticalXL` / `--spacingHorizontalL` / `--colorNeutralStroke2` / `--colorNeutralBackground1` / `--spacingVerticalM`). **U9** ledger row (this row) + final smoke. **Test count 94 → 104** (+2 FluentThemeBridge — DOM griffel-class check + theme-prop flip via `vi.doMock`; +4 CoralShell — column data-attr + custom-className composition for both column and row; +5 → +7 net for AppHeader rewrite — +2 AppHeader = 7 total: title+default subtitle+Microsoft logo, custom subtitle "Demo Build", theme-toggle click flips `data-theme="dark"`, `onToggleHistory` invocation, `onNewChat` invocation, `aria-pressed="true"` when historyOpen, alias-identity check `expect(AppHeader).toBe(Header)`; +2 PanelLeft — landmark role + custom-className composition); all pre-existing 94 tests stay green throughout (every `data-testid` + `aria-label` + role-based accessible name preserved). **Pillar = Stable Core** declared in every new module's docstring; **Phase = 4 (frontend polish — MACAE re-skin)**. **Hard Rule #10 triggers (all approved this turn via 4-question gate before plan was locked):** new deps `@fluentui/react-components` + `@fluentui/react-icons`; removed dep `lucide-react`; new folder `components/CoralShell/`; new folder `components/Header/` (rename from `components/AppHeader/`, mitigated via thin alias re-export); deleted asset `assets/Azure.svg`; sidebar L↔R swap. **Backend untouched** (zero Python files modified across U1–U9 — confirmed via `git status --short` showing only `v2/src/frontend/**` + `v2/docs/development_plan.md`; no Bicep change, no env-vars row touched). **Note**: U9 final smoke surfaced 4 pre-existing backend failures in `tests/backend/test_admin.py` traced to `admin.py` referencing `starlette.status.HTTP_422_UNPROCESSABLE_CONTENT` (renamed in newer Starlette; installed version only has `HTTP_422_UNPROCESSABLE_ENTITY`) — unrelated to S2/MACAE-RESKIN, queued separately as `BACKEND-422-CONST` per Hard Rule #12. | `v2/src/frontend/package.json` (+2 deps, -1 dep), `v2/src/frontend/src/theme/{FluentThemeBridge.tsx,tokens.css}`, `v2/src/frontend/src/components/CoralShell/{CoralShellColumn.tsx,CoralShellRow.tsx,CoralShell.module.css,PanelLeft.tsx}`, `v2/src/frontend/src/components/Header/{Header.tsx,HeaderTools.tsx,MsftColorLogo.tsx,Header.module.css}`, `v2/src/frontend/src/components/AppHeader/AppHeader.tsx` (collapsed to alias re-export; AppHeader.module.css deleted), `v2/src/frontend/src/components/icons.ts` (deleted), `v2/src/frontend/src/assets/Azure.svg` (deleted), `v2/src/frontend/src/App.tsx`, `v2/src/frontend/src/pages/chat/{ChatPage.tsx,ChatPage.module.css}`, `v2/src/frontend/src/pages/chat/components/{HistoryPanel.tsx,HistoryPanel.module.css,MessageList.tsx,MessageList.module.css,MessageInput.tsx,MessageInput.module.css}`, `v2/src/frontend/tests/theme/FluentThemeBridge.test.tsx` (NEW), `v2/src/frontend/tests/components/{CoralShell.test.tsx,PanelLeft.test.tsx}` (NEW), `v2/src/frontend/tests/components/AppHeader.test.tsx` (REWRITTEN 5→7 tests) | Phase 4 audit | ✅ cleared (2026-05-11) |

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
| **BYOD conversation flow** (`CONVERSATION_FLOW=byod` in v1) | Azure OpenAI "On Your Data" delegation removed. Incompatible with Hard Rule #7 (no direct `openai`/`AzureOpenAI` SDK in v2; On Your Data is invoked via that SDK's `data_sources` parameter, which Foundry IQ does not expose as a drop-in), Hard Rule #5 (orchestrator-uniform interface; BYOD collapses the pipeline into one server-side call with no LangGraph / Agent Framework nodes), Hard Rule #6 (typed SSE reasoning channel; BYOD produces no per-token reasoning deltas), and Hard Rule #4 (registry plug-and-play; BYOD is Cosmos-AI-Search-only and forbids the pgvector provider). v2 ships the Custom flow only — app-owned retrieve → prompt → answer via Foundry IQ + registry orchestrators. **No code was ever written in v2 for BYOD**; this row makes the absence explicit. Drift note: [v2/docs/plan/business-cases.md](plan/business-cases.md) previously listed BYOD as "Kept" — corrected in the same turn (2026-05-20). |

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

### 2.4 Empty `__init__.py` invariant (locked 2026-05-20)

This section is the **single source of truth** for Hard Rule #13 in [.github/copilot-instructions.md](../../.github/copilot-instructions.md). The rule itself is intentionally short; the rationale, violation taxonomy, and migration plan live here.

#### 2.4.1 The rule (binding)

Every `v2/**/__init__.py` contains **at most one element**: the module docstring (including the `Pillar:` / `Phase:` header where applicable). Anything else is a violation.

#### 2.4.2 Why (project-goal alignment)

This project's core principles — *clean, modular, plug-and-play, no over-engineering* (Hard Rule #9) — are routinely undermined by code in `__init__.py`. Three concrete failure modes we've hit:

1. **Hidden import-time side effects.** Decorator-based registration via `from . import concrete_a` inside `__init__.py` means `import backend.core.providers.parsers` silently instantiates a `Registry`, imports every concrete, and fires every `@register` decorator. A reader who greps for `"pdf"` finds the registration but not the trigger. Moving these to a *named* sibling (`registry.py`) doesn't eliminate the side effect, but it makes the file's name match its behavior — "this module holds the registry" is honest; "this folder is a package" is not.
2. **Zero-value indirection (`create(key, **kwargs)`).** The seven provider domains each defined `def create(key, **kwargs): return registry.get(key)(**kwargs)`. The wrapper added no validation, no defaulting, no logging — a pure rename that disguised a dict lookup as factory logic. Callers `parsers.create("pdf")` look up the same `registry.get`-then-instantiate path; the function existed only because it was traditional.
3. **Mixed-purpose `__init__.py`.** Once one `def` is allowed, the file accretes helpers, constants, and re-exports. The strict invariant ("only a docstring") is enforceable by a 15-line AST test; "keep it light" is judgment-based and rots.

The rule serves the four principles directly:
- *Clean*: package boundaries are declarative — a folder is a folder, not a hidden module.
- *Modular*: every concrete is traceable to its registration in exactly one named file (`<domain>/registry.py`).
- *Plug-and-play*: callers can swap implementations without `__init__.py`-side magic.
- *No over-engineering*: `create()` wrappers, `__all__` lists, and re-export curation are all removed because none of them paid for themselves.

#### 2.4.3 Violation taxonomy

| # | Construct in `__init__.py` | Status | Why |
|---|---|---|---|
| 1 | Module docstring (incl. `Pillar:` / `Phase:` header) | ✅ allowed (and required where the package has a pillar) | Only legal content. |
| 2 | `__future__` / `TYPE_CHECKING` imports | ❌ forbidden | Already banned by Hard Rule #11. |
| 3 | `from .submodule import Symbol` (re-export) | ❌ forbidden | Callers must reach the symbol explicitly via its real module. |
| 4 | `from . import submodule` (side-effect import) | ❌ forbidden | Belongs in `<domain>/registry.py` next to the registry it populates. |
| 5 | `__all__ = [...]` | ❌ forbidden | A consequence of #3; nothing to list once re-exports are gone. |
| 6 | `registry = Registry("<domain>")` (or any instantiation) | ❌ forbidden | Module-level state lives in a named file. |
| 7 | Module-level constants (`FOO = "bar"`) | ❌ forbidden | If ≥2 form a closed set use `StrEnum` (Hard Rule #11); single values live in the consumer module. |
| 8 | `def helper(...)` / `class X: ...` | ❌ forbidden | Code lives in a named file describing its purpose. |
| 9 | `def create(key, **kwargs)` factory wrappers | ❌ forbidden | Removed 2026-05-20 — callers do `registry.get(key)(**kwargs)` directly. |

Enforcement: `v2/tests/shared/test_init_files_are_marker_only.py` (added in IA-C1). AST walk over every `v2/**/__init__.py`; the only top-level node accepted is `ast.Expr(value=ast.Constant(value=str))`. Anything else — including a stray `pass`, an `import`, or an assignment — fails the test with the file path and offending node line.

#### 2.4.4 Where displaced code goes

| Displaced from `__init__.py` | New home |
|---|---|
| `Registry[...]` instance for a provider domain | `<domain>/registry.py` (this is the *canonical* name; the file *is* a registry) |
| Eager `from . import concrete_a, concrete_b` that trigger `@register` decorators | `<domain>/registry.py` after the `Registry(...)` instantiation (`# noqa: E402, F401` on the import line) |
| Genuine domain helper (e.g. `credentials.select_default(...)`) | `<domain>/registry.py` next to the registry it consults |
| Re-exported symbols from a non-provider package (e.g. `backend/core/agents/`) | Removed; callers import the real module (`backend.core.agents.definitions`) |
| Pillar / Phase header | Stays in the `__init__.py` docstring — documentation only, no runtime effect |

**Naming exception:** if a future package's primary content is genuinely not a registry, name the sibling for what it *is* (`definitions.py`, `contracts.py`, etc.) — never put it back in `__init__.py`.

#### 2.4.5 Caller pattern (one shape, no variants)

```python
# CORRECT — explicit submodule import, no sugar.
from backend.core.providers.credentials import registry as credentials_registry

provider = credentials_registry.registry.get(settings.credentials.kind)(settings=settings)
default = credentials_registry.select_default(settings)
```

Forbidden caller shapes:
- `from backend.core.providers.credentials import create` (no `create`).
- `from backend.core.providers.credentials import registry` (without `as <domain>_registry`) — ambiguous reads (`registry.registry.get(...)` chain is confusing).
- `import backend.core.providers.credentials as credentials; credentials.create(...)` (no module-level `create`).

#### 2.4.6 Audit baseline (2026-05-20)

24 `__init__.py` files under `v2/src/` and `v2/tests/`:

| Classification | Count | Action |
|---|---|---|
| Empty marker | 8 | ✅ no change |
| Docstring-only | 8 | ✅ no change |
| Re-export only (`backend/core/agents/__init__.py`) | 1 | ⏭ migrate per strict rule (callers import `backend.core.agents.definitions` directly) |
| **Has logic (Registry + `create()` + side-effect imports)** | **7** | ⏭ migrate to sibling `registry.py` |

The 7 violators (all under [v2/src/backend/core/providers/](../src/backend/core/providers)): `credentials`, `databases`, `llm`, `orchestrators`, `search`, `parsers`, `agents`.

#### 2.4.7 Migration sequence (1 unit per turn, smallest blast radius first)

| Unit | Domain | Callsites to update |
|---|---|---|
| IA-B1 | `parsers` | tests only (no app.py callers yet) |
| IA-B2 | `credentials` | 2 in [app.py](../src/backend/app.py) (incl. `select_default`) |
| IA-B3 | `llm` | 1 in app.py |
| IA-B4 | `agents` (provider) | 1 in app.py |
| IA-B5 | `databases` | 2 (app.py, [routers/health.py](../src/backend/routers/health.py)) |
| IA-B6 | `search` | 2 (app.py, health.py) + 2 test files |
| IA-B7 | `orchestrators` | 1 in [routers/conversation.py](../src/backend/routers/conversation.py) |
| IA-B8 | `backend/core/agents/` re-export migration | callers of `BUILTIN_AGENTS`, `CWYD_AGENT`, `RAI_AGENT`, `AgentDefinition` |
| IA-C1 | AST enforcement test | `v2/tests/shared/test_init_files_are_marker_only.py` |
| IA-D1 | Audit close | dev_plan §0.1 ledger row |

#### 2.4.8 Per-domain recipe

1. Create `<domain>/registry.py` holding (in order): the `Registry[...]` instance, eager side-effect imports of concretes, any genuine helper (`select_default` for credentials only).
2. Update every concrete in the domain: `from . import registry` → `from .registry import registry`.
3. Empty out `__init__.py` to a module-docstring-only marker (preserve `Pillar:` / `Phase:` header).
4. Update all callsites: `<domain>.create(key, **kwargs)` → `<domain>_registry.registry.get(key)(**kwargs)`; `<domain>.select_default(...)` → `<domain>_registry.select_default(...)` (where `<domain>_registry` is the alias from `from backend.core.providers.<domain> import registry as <domain>_registry`).
5. Run `pytest -q` + `pyright src/functions src/backend`; append ledger row.

The IA-Bx work is **not** part of any numeric §4 phase — it is a cross-cutting Hard-Rule-#13 cleanup that lands between Phase 6 units when the user explicitly schedules it (the Phase 6 ordered backlog in §4.6.1 stays the active queue otherwise).

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

#### 4.6.1 Phase 6 ordered unit backlog

**Deterministic Hard-Rule-#1 sequence. The agent picks the next ☐ row without prompting the user.** Locked 2026-05-20 after U8b. Per-unit contract auto-applies (one class OR one method, ≥3 tests, narrow SDK exception catch + `logger.exception` + re-raise, pillar header docstring, pytest new → pytest full → pyright `src/functions src/backend` → §0.1 ledger row → end-of-turn beep).

| Unit | Status | Scope (one class OR method) | File(s) | Depends |
|---|---|---|---|---|
| U7c | ✅ | `resolve_storage_endpoints` | `functions/core/storage_endpoints.py` | — |
| U7d | ✅ | `ErrorType` + `json_response` | `functions/core/http.py` | — |
| U7e | ✅ | `storage_clients` ctx mgr | `functions/core/storage_clients.py` | — |
| U7f | ✅ | `@map_function_exceptions` | `functions/core/exception_mapping.py` | U7d |
| U7g | ✅ | Rewrite blueprint on substrate | `functions/batch_start/blueprint.py` | U7c–f |
| U7h | ✅ | Audit close (doc-only) | dev_plan §0.1 | U7g |
| U8a | ✅ | `parse_push_message` | `functions/batch_push/queue_reader.py` | — |
| U8b | ✅ | `download_blob` | `functions/batch_push/blob_fetcher.py` | — |
| U8c | ✅ | `Chunk` type + `BaseParser` ABC + `parsers` registry | `backend/core/types.py` (extend), `backend/core/providers/parsers/base.py` + `__init__.py` | U8b |
| U8d | ⏭ | `TextParser` ingestion-only impl (`"txt"`) | `functions/core/parsers/text_parser.py` + `__init__.py` | U8c |
| U8e | ☐ | `BaseEmbedder` ABC + `embedders` registry | `backend/core/providers/embedders/base.py` + `__init__.py` | U8d |
| U8f | ☐ | `AzureOpenAIEmbedder` impl (`"azure_openai"`) | `backend/core/providers/embedders/azure_openai.py` | U8e |
| U8g | ☐ | `push_documents(search_client, docs)` write-side helper | `backend/core/providers/search/writer.py` | U8f |
| U8h | ☐ | `batch_push_handler(message, container_client, parser, embedder, search_writer)` DI orchestration | `functions/batch_push/handler.py` | U8g |
| U8i | ☐ | `batch_push` queue-trigger blueprint (`@map_function_exceptions("batch_push", trigger="queue")`) | `functions/batch_push/blueprint.py` | U8h |
| U8j | ☐ | Register `bp_batch_push` in `function_app.py` | `functions/function_app.py` | U8i |
| U8k | ☐ | `batch_push` audit close (doc-only) | dev_plan §0.1 | U8j |
| U9a | ☐ | `fetch_url(url) -> bytes` (httpx async, `httpx.HTTPError` narrow catch) | `functions/add_url/url_fetcher.py` + `__init__.py` | U8k |
| U9b | ☐ | `add_url_handler(request, parser, embedder, search_writer)` | `functions/add_url/handler.py` | U9a |
| U9c | ☐ | `add_url` HTTP-trigger blueprint + register | `functions/add_url/blueprint.py`, `function_app.py` | U9b |
| U10a | ☐ | AI Search custom-skill request/response Pydantic models | `functions/search_skill/models.py` + `__init__.py` | U9c |
| U10b | ☐ | `search_skill_handler(request, embedder)` (embed-on-the-fly, no parser) | `functions/search_skill/handler.py` | U10a |
| U10c | ☐ | `search_skill` HTTP-trigger blueprint + register | `functions/search_skill/blueprint.py`, `function_app.py` | U10b |
| U11 | ☐ | Standalone-backend smoke test CI job | `.github/workflows/backend-only-smoke.yml` + compose fixture | U10c |
| U12 | ☐ | Phase 6 close audit (flip Phase 6 ⏳→✅, bump Phase 7 ⏭) | dev_plan only | U11 |

**Locked decisions (no future "which path" prompts):**

- **D1** `BaseParser` and `BaseEmbedder` ABCs live in `backend/core/providers/` (Stable Core) per registry-first Hard Rule #4. Ingestion-only concretes (PDF/DOCX) live in `functions/core/parsers/` as backend-base extensions.
- **D2** No standalone `Chunker` primitive — parsers return `list[Chunk]` directly (matches v1 `embed_file` flow; one registry tier).
- **D3** Only `TextParser` ships in U8d. PDF/DOCX/MD parsers go in §0.1 as deferred items, added in Phase 7 unless a demo blocks.
- **D4** Search write-side is a **helper function** (`push_documents`), not a new `SearchWriter` registry. Existing `providers/search/` is read-side; write is one-shot.
- **D5** `function_app.py` registration is sequential — no Functions-app registry (mounting, not provider dispatch).
- **D6** `Chunk` value type lives in `backend/core/types.py` (not coupled to parser module) — same convention as `OrchestratorChannel`. Frozen, hashable, Pydantic `BaseModel` with `extra="forbid"`.

**Structural sign-off (Hard Rule #10, granted 2026-05-20 with "Start implementation"):**
1. New package `backend/core/providers/parsers/` ✅ approved
2. New package `backend/core/providers/embedders/` ✅ approved
3. New file `backend/core/providers/search/writer.py` ✅ approved
4. New packages `functions/core/parsers/`, `functions/add_url/`, `functions/search_skill/` ✅ approved

All four are anticipated by [v2/src/backend/core/providers/__init__.py](../src/backend/core/providers/__init__.py) module docstring — this fills declared scaffolding, no surprise structure.

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
