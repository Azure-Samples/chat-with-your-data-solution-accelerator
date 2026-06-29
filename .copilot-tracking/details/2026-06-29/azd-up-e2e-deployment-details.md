<!-- markdownlint-disable-file -->
# Implementation Details: MACAE-parity end-to-end `azd up`

## Context Reference

Sources:
* Primary research: .copilot-tracking/research/2026-06-28/azd-up-e2e-deployment-research.md
* Round-2 subagent reports: .copilot-tracking/research/subagents/2026-06-28/{cwyd-v2-frontend-deploy,cwyd-v2-functions-ingestion,cwyd-v2-azd-flow-seeding,cwyd-v2-backend-env-diff}.md
* Standards: .github/copilot-instructions.md (Hard Rules #3 pillar, #7 no-banned-tech/no-KeyVault, #10 ask-before-structure, #11 StrEnum, #16 no-process-narrative, #18 no-env-specific, #19 worklog/bugs)
* Instruction files: .github/instructions/v2-infra.instructions.md, v2-backend.instructions.md, v2-backend-core.instructions.md, v2-functions.instructions.md, v2-tests.instructions.md

User decisions locked in (research §"Confirmed scope + user decisions"):
* Mirror MACAE's DEFAULT `azd up` config — public profile, `enablePrivateNetworking=false`. RC-3 (private-networking reverse proxy) is OUT of scope.
* Admin/ingest surface OPEN by default (MACAE-faithful, `AUTH_ENABLED=false` equivalent). Selected RC-1 sub-option is A1.
* Validation is live-only: `azd up` to Azure → seed → exercise the frontend URL. "Any other approach it is not valid."

Binding repo constraints carried into every step:
* One unit per turn (one class OR one method) + a test that executes (Hard Rule #1/#2).
* Do NOT invert the `Environment.LOCAL` code default — prod is flipped only by the IaC-set `AZURE_ENVIRONMENT` env var (user memory config-defaults-dev-first). The bicep `AZURE_ENVIRONMENT='production'` pin is already correct and stays.
* No env-specific content in tracked files — CORS/origin literals are built from `${solutionSuffix}` only (Hard Rule #18).
* No process narrative in production-code comments (Hard Rule #16).

## Implementation Phase 1: C3 backend env — CORS origin + defensive index pin (Bicep)

<!-- parallelizable: false -->

Shares v2/infra/main.bicep with Phase 3; kept sequential so each Bicep edit lands as one reviewable unit.

### Step 1.1: Add `BACKEND_CORS_ORIGINS` to the backend Container App env

Add a deterministic, cycle-free CORS origin to the backend Container App `env` array so the backend allows the frontend origin (MACAE pattern A/B). The value is constructed from `solutionSuffix` — never a module-output reference — so there is no frontend↔backend dependency cycle (the original author left the frontend origin as an output-only with a "CORS must allow this origin" comment instead of injecting it).

Files:
* v2/infra/main.bicep — backend module `backendContainerApp`, `containers[0].env` first (unconditional) array. Insert after the storage/ingestion block (after `AZURE_INGESTION_TRIGGER`, end of the first array literal). Add:
  `{ name: 'BACKEND_CORS_ORIGINS', value: 'https://app-frontend-${solutionSuffix}.azurewebsites.net' }`
  * Backend reads this via `NetworkSettings.cors_origins` (settings.py L317-320, bare `BACKEND_CORS_ORIGINS` alias, comma-split). `app.py` L241-263 then sets `allow_origins=[origin]`, `allow_credentials=True` (because origins != ["*"]).
  * `.azurewebsites.net` is the public App Service suffix; valid for the default public profile only (private mode is out of scope).

Discrepancy references:
* Addresses RC-2 (research Key Discoveries §2) — the one true CORS gap.

Success criteria:
* `BACKEND_CORS_ORIGINS` present in the backend env array with a `${solutionSuffix}`-derived literal (no `${frontendWebApp.outputs...}` reference, no hard-coded suffix).
* `az bicep build` / mcp build of v2/infra/main.bicep succeeds with no new warnings.

Context references:
* v2/infra/main.bicep backend env array (identity block ~L1808 through `AZURE_INGESTION_TRIGGER` ~L1915).
* v2/src/backend/core/settings.py (Lines 291-352) — `NetworkSettings.cors_origins` alias + split validator.
* v2/src/backend/app.py (Lines 241-263) — CORS middleware wiring.

Dependencies:
* None (first step).

### Step 1.2: Pin `AZURE_AI_SEARCH_INDEX` defensively

Add an explicit index-name env var so a future infra rename cannot silently break retrieval (today it works only because the `SearchSettings` default happens to equal the provisioned index name).

Files:
* v2/infra/main.bicep — backend `containers[0].env` first array, near the existing Search vars (`AZURE_AI_SEARCH_ENDPOINT`, `AZURE_AI_SEARCH_KNOWLEDGE_*`). Add:
  `{ name: 'AZURE_AI_SEARCH_INDEX', value: 'cwyd-index' }`
  * IMPLEMENTER MUST verify the exact env-var name the `SearchSettings` field resolves to (env_prefix + field) before adding — the research states `AZURE_AI_SEARCH_INDEX` (settings.py ~L245-268). If the prefix differs, use the resolved name and the existing provisioned index name (the one `post_provision.py` creates: `cwyd-index`).

Discrepancy references:
* Addresses research Key Discoveries §C3 "MISSING & OPTIONAL, functional" (fragile default-coincidence).

Success criteria:
* Backend env carries the explicit index name matching the index `post_provision.py` provisions.
* Bicep build succeeds.

Context references:
* v2/src/backend/core/settings.py (Lines 245-268) — `SearchSettings`.
* v2/scripts/post_provision.py — provisions the `cwyd-index` Search index.

Dependencies:
* Step 1.1 (same file region; sequential).

### Step 1.3: (OPTIONAL, cosmetic) Add the admin-display env cluster

Add the cosmetic env cluster so `GET /api/admin/status` stops *looking* half-configured. No functional impact — defer unless the operator wants the status page complete. Every value is `${solutionSuffix}`-derived or an existing module output (deterministic, no new cycles).

Files:
* v2/infra/main.bicep — backend env first array. Candidates (each maps to an existing `AppSettings` top-level field, settings.py L512-516 + nested identity): `AZURE_SOLUTION_SUFFIX`, `AZURE_RESOURCE_GROUP`, `AZURE_LOCATION`, `AZURE_AI_SERVICE_LOCATION`, `AZURE_UAMI_PRINCIPAL_ID`, `AZURE_UAMI_RESOURCE_ID`, `AZURE_COSMOS_ACCOUNT_NAME`, `AZURE_FUNCTION_APP_NAME`, `AZURE_BACKEND_URL`, `AZURE_FRONTEND_URL`.
  * `AZURE_FRONTEND_URL` = `'https://app-frontend-${solutionSuffix}.azurewebsites.net'` (same literal as Step 1.1; no cycle).

Discrepancy references:
* Addresses research Key Discoveries §C3 "MISSING & OPTIONAL, cosmetic". Marked DR-03 in the log (optional).

Success criteria:
* If implemented: each added var reads green in `GET /api/admin/status`; bicep build succeeds.

Context references:
* v2/src/backend/core/settings.py (Lines 506-548) — `AppSettings` top-level fields + nested `IdentitySettings`.

Dependencies:
* Step 1.2 (same file region).

### Step 1.4: Validate Phase 1 Bicep

Validation commands:
* `az bicep build --file v2/infra/main.bicep` (or mcp build_bicep) — must compile clean.
* Do NOT run `azd provision` yet — live provision is deferred to Phase 5 (the binding validation).

## Implementation Phase 2: C3/A1 backend admin open-by-default flag (settings + dependencies)

<!-- parallelizable: false -->

Two one-unit code edits (settings field, then dependency-gate change) plus the Bicep env wiring. This is the decision that makes admin/upload usable without Easy Auth (MACAE `AUTH_ENABLED=false` equivalent) while keeping `AZURE_ENVIRONMENT='production'` intact.

### Step 2.1: Add `require_admin_auth` flag to `AppSettings`

Add a top-level boolean settings field that gates the admin fail-closed behavior. Default `False` (open) so a clean checkout and a default deploy are both usable; the IaC env var (Phase 2.3) is what an operator flips to re-enable the wall. This does NOT invert any existing default and does NOT touch `environment`.

Files:
* v2/src/backend/core/settings.py — `AppSettings` class (Lines 506-548). Add a field beside `environment`:
  `require_admin_auth: bool = False` (resolves to `AZURE_REQUIRE_ADMIN_AUTH` via the class `env_prefix="AZURE_"`).
  * Docstring/comment must describe WHAT the field is (the admin-auth gate switch), not process narrative (Hard Rule #16).
* v2/src/backend/core/tests/test_settings.py (or the existing settings test module) — assert default `False`; assert `AZURE_REQUIRE_ADMIN_AUTH=true` env → `True`.

Discrepancy references:
* Addresses RC-1 / A1 (research §"The four concrete gaps" #1 + selected approach C3/A1).

Success criteria:
* `AppSettings().require_admin_auth is False` by default; env override flips it.
* New/updated test executes and passes; no other settings test regresses.
* AST gates green (no-process-narrative, imports-at-top, no-`__future__`/`TYPE_CHECKING`).

Context references:
* v2/src/backend/core/settings.py (Lines 506-548) — `AppSettings`.
* v2/src/backend/core/settings.py (Lines 41-52, 533) — `Environment` enum + `environment` default (reference for placement; do NOT change it).

Dependencies:
* Phase 1 complete (sequential; clean working tree per unit).

### Step 2.2: Gate the admin fail-closed branch on `require_admin_auth`

Relax `requires_role._checker` so the missing-claims path fails closed ONLY when the gate is actually required. Currently it raises 401 whenever `claims_raw` is absent and `environment != LOCAL`. Change the condition so the synthetic admin id is returned when `environment is LOCAL` OR `not settings.require_admin_auth`; raise 401 only when `require_admin_auth` is true and claims are absent. Apply the same relaxation to the missing-principal-id branch.

Files:
* v2/src/backend/dependencies.py — `requires_role` inner `_checker` (Lines 437-485). The absent-claims branch (L448-457) and the missing-principal-id branch (L478-485) gain the `settings.require_admin_auth` condition. The `_checker` signature already receives `settings: SettingsDep`, so `settings.require_admin_auth` is in scope — no new parameter.
  * Update the function docstring + inline comments to describe the new gate WITHOUT process narrative or unit IDs (Hard Rule #16).
* v2/src/backend/tests/test_dependencies.py (or the existing dependencies test module) — cases:
  * `environment=production`, `require_admin_auth=False`, no claims → returns synthetic/principal id (no 401). (The new open-by-default path.)
  * `environment=production`, `require_admin_auth=True`, no claims → 401.
  * `environment=production`, valid claims with `admin` role → returns principal id (unchanged).
  * `environment=production`, valid claims WITHOUT `admin` role → 403 (unchanged).

Discrepancy references:
* Addresses RC-1 / A1 (the certain `/api/admin/*` 401 blocker).

Success criteria:
* Admin routes are reachable on a default deploy (production env, flag off) with the SPA's self-supplied principal-id; no 401.
* Flipping `AZURE_REQUIRE_ADMIN_AUTH=true` restores the fail-closed 401.
* Role enforcement (403 when claims present but role missing) is unchanged.
* Tests execute and pass.

Context references:
* v2/src/backend/dependencies.py (Lines 425-496) — `requires_role`, `REQUIRE_ADMIN_USER`, `AdminUserIdDep`.

Dependencies:
* Step 2.1 (the field must exist).

### Step 2.3: Wire `AZURE_REQUIRE_ADMIN_AUTH` in the backend Bicep env + reconcile the comment

Add the explicit flag to the backend Container App env (set to `'false'`) so the deployed default is open, and update the existing `AZURE_ENVIRONMENT='production'` comment block so it accurately describes the new two-flag model (production pins the runtime mode; `AZURE_REQUIRE_ADMIN_AUTH` independently gates the admin wall). No process narrative / unit IDs in the comment.

Files:
* v2/infra/main.bicep — backend env first array; the existing `AZURE_ENVIRONMENT` entry + its comment (~L1814-1825). Add `{ name: 'AZURE_REQUIRE_ADMIN_AUTH', value: 'false' }` and rewrite the comment to state: production is pinned so the runtime reports the real environment and the local-dev identity bypass cannot fire; the admin auth wall is governed separately by `AZURE_REQUIRE_ADMIN_AUTH` (default false = open, MACAE-faithful; set true to require Easy Auth claims).

Discrepancy references:
* Addresses RC-1 / A1.

Success criteria:
* Backend env carries `AZURE_REQUIRE_ADMIN_AUTH='false'`; comment reflects the new model with no process narrative.
* Bicep build succeeds.

Context references:
* v2/infra/main.bicep backend `AZURE_ENVIRONMENT` entry + comment (~L1814-1825).

Dependencies:
* Step 2.2 (code must read the flag before infra sets it).

## Implementation Phase 3: C1 frontend auth disabled + build hardening (Bicep)

<!-- parallelizable: false -->

Shares v2/infra/main.bicep. Closes the frontend "error page" (BUG-0090) by making Bicep declaratively own the frontend auth state as DISABLED so a reprovision clears the stale Entra provider `azd up` never reconciles.

### Step 3.1: Declare frontend Easy Auth DISABLED on the App Service (PD-01 = declarative)

Add an explicit, disabled auth configuration to the `frontendWebApp` AVM `web/site` module so every `azd up` reconciles Easy Auth OFF. This is the open-by-default, MACAE-faithful posture.

Files:
* v2/infra/main.bicep — `frontendWebApp` module (`br/public:avm/res/web/site:0.22.0`, ~L1962-2025). The AVM `web/site` 0.22.0 module exposes Easy Auth through its `configs` array — add a `configs` entry of `name: 'authsettingsV2'` (NOT a top-level `authSettingV2Configuration` param; validator-confirmed against the 0.22.0 schema) whose `properties` disable the wall:
  * `globalValidation.requireAuthentication: false`
  * `globalValidation.unauthenticatedClientAction: 'AllowAnonymous'`
  * `platform.enabled: false` (fully off) — or `platform.enabled: true` with empty `identityProviders` if the AVM module requires platform-enabled to emit a reconcilable config; pick whichever the AVM 0.22.0 `authsettingsV2` config shape supports for a deterministic "off".
  * No identity providers, no clientId/issuer (Hard Rule #18 — nothing env-specific).
  * IMPLEMENTER MUST confirm the exact `configs[].authsettingsV2` `properties` shape against the AVM 0.22.0 module before wiring (use the Bicep schema tools).

Discrepancy references:
* Addresses C1 PRIMARY (BUG-0090). Implements PD-01 (declarative bicep). Alternate IP recorded as DD-01.

Success criteria:
* `frontendWebApp` declares auth disabled; a reprovision over a stale-Easy-Auth site clears the redirect.
* Bicep build succeeds; the AVM param shape matches the 0.22.0 schema.

Context references:
* v2/infra/main.bicep `frontendWebApp` module (Lines ~1962-2025) — `kind: 'app,linux'`, `siteConfig`, `appSettings`.
* Research §C1 (BUG-0090) and §"Considered Alternatives" (A2 rejected).

Dependencies:
* Phase 2 complete (sequential; same file).

### Step 3.2: Add frontend build-from-source hardening app settings

Harden the App Service build-from-source path so the staged uvicorn server boots reliably.

Files:
* v2/infra/main.bicep — `frontendWebApp` `siteConfig.appSettings` union first array (alongside `BACKEND_API_URL`, `WEBSITES_ENABLE_APP_SERVICE_STORAGE`, `SCM_DO_BUILD_DURING_DEPLOYMENT`, ~L2005-2021). Add:
  * `{ name: 'WEBSITES_PORT', value: '8000' }`
  * `{ name: 'ENABLE_ORYX_BUILD', value: 'True' }`

Discrepancy references:
* Addresses C1 "Parity hardening (not the root cause)".

Success criteria:
* Both settings present; bicep build succeeds.

Context references:
* v2/infra/main.bicep frontend `appSettings` (Lines ~2005-2021).

Dependencies:
* Step 3.1 (same module).

### Step 3.3: (MANUAL pre-deploy check, not a code edit) BUG-0081 container-kind guard

Before/early in Phase 5, confirm the live frontend site `kind` is `app,linux` (not `app,linux,container`). Site `kind` is effectively immutable, so a container-kind leftover ignores the code deploy and serves the placeholder page (a *different* symptom than the Easy Auth redirect).

Operator command (placeholders per Hard Rule #18):
* `az webapp show -g <RESOURCE_GROUP> -n app-frontend-<SUFFIX> --query kind -o tsv`
* If it returns `app,linux,container`: delete the site so `azd up` recreates it as `app,linux` (the bicep `kind: 'app,linux'` cannot flip it in place). Prefer the Phase 5 fresh-resource deploy (PD-02) which avoids this entirely.

Discrepancy references:
* Addresses C1 SECONDARY (BUG-0081).

Success criteria:
* Live site `kind == 'app,linux'` before the code deploy lands.

Dependencies:
* None (operational check, executed in Phase 5).

### Step 3.4: Validate Phase 3 Bicep

Validation commands:
* `az bicep build --file v2/infra/main.bicep` — clean compile.

## Implementation Phase 4: C2 functions ingestion — unattended seed + completion check

<!-- parallelizable: false -->

Makes a bare `azd up` actually leave a populated, queryable site.

### Step 4.1: Make the seed run unattended by default (RC-1)

Change the seed scope resolution so a non-interactive `azd up` seeds the PDF happy-path corpus instead of silently skipping. Keep an explicit opt-out.

Files:
* v2/scripts/upload_sample_data.py — `resolve_selection` (Lines 185-210). Change the non-TTY fallback (currently `return SeedScope.SKIP` at L201-207) to return a default seed scope (recommend the `default` persona = PDF-only happy path, NOT `all` — `all` includes the `.docx` that poisons under BUG-0088). Keep the `--set`/`AZURE_ENV_SAMPLE_DATA` precedence intact so `AZURE_ENV_SAMPLE_DATA=none` is the explicit opt-out and any persona/`all` override still wins.
  * Rationale honors the user's "azd up → ready-to-use site" goal; this is a product-behavior default, not a dev-vs-prod mode flip, so config-defaults-dev-first is not violated.
* v2/scripts/tests/test_upload_sample_data.py (or the existing seed test module) — cases:
  * non-TTY + no token → returns the default seed scope (NOT `SeedScope.SKIP`).
  * non-TTY + `AZURE_ENV_SAMPLE_DATA=none` → `SeedScope.SKIP`.
  * `--set all` / env `all` → unchanged (`SeedScope.ALL`).
  * TTY path (menu) → unchanged.

Discrepancy references:
* Addresses C2 RC-1 (the dominant cause). Deviates from research's `all` suggestion → DD-02 (PDF-only default because of BUG-0088).

Success criteria:
* A non-interactive run with no override seeds the PDF corpus; `none` still skips.
* Tests execute and pass.

Context references:
* v2/scripts/upload_sample_data.py (Lines 81-99 token map + menu, 185-210 `resolve_selection`).
* Research §C2 RC-1 + §"Considered Alternatives".

Dependencies:
* Phase 3 complete (sequential).

### Step 4.2: Add a post-seed index-completion check (RC-async)

Because CWYD seeds asynchronously (upload + enqueue; `batch_push` does the indexing), add a bounded post-enqueue check that polls the index / `list_sources` until the seeded docs are indexed, then emits a loud PASS/FAIL banner so a poisoned/cold pipeline surfaces instead of reporting false success.

Files:
* v2/scripts/upload_sample_data.py — after the enqueue step, add a `wait_for_index_completion(...)`-style helper (one method) that polls with a bounded timeout + interval and logs a clear FAIL banner + remediation hint (check `doc-processing-poison`, function `/api/health`) when the index stays empty. The `postdeploy` hook stays `continueOnError: true` (a transient ingestion lag must not fail an otherwise-good deploy), so the value is the loud, unmistakable log — not a hard failure. Whether to also flip `continueOnError: false` is PD-03 (recommend keep `true` + loud log).
* v2/scripts/tests/test_upload_sample_data.py — test the poll helper: completes when the source-count predicate is met; emits the FAIL banner + returns the empty-signal when the timeout elapses with an empty index (use injected clock/poll fns, no real sleep).

Discrepancy references:
* Addresses C2 RC-async (silent empty index). Rejected alternative: keep async seed with no check (research §"Considered Alternatives").

Success criteria:
* A populated index logs PASS; an empty index after timeout logs a clear FAIL banner with the remediation hint.
* Tests execute and pass (no real sleeps/network).

Context references:
* v2/scripts/upload_sample_data.py — enqueue path + endpoint resolution (Lines 213-230).
* Research §C2 RC-async + the confirmation recipe (documents blob count / queue depth / poison depth).

Dependencies:
* Step 4.1.

### Step 4.3: (CONDITIONAL — only if PD-02 = reuse mandatory) Reused-resource self-heal

Only needed when the target env reuses pre-existing data resources. Preferred path is a fresh-resource deploy (PD-02 recommended), in which case SKIP this step.

Files:
* v2/scripts/post_provision.py — add a reconcile step that (a) sets reused storage `publicNetworkAccess` to allow the non-VNet Flex host (BUG-0086), and (b) prunes any stale v1 Event Grid subscription dumping raw `BlobCreated` onto `doc-processing` (BUG-0087). Idempotent; placeholders only (Hard Rule #18).
* v2/scripts/tests/test_post_provision.py — cover the reconcile branch (mock the storage/eventgrid SDK calls).

Discrepancy references:
* Addresses C2 RC-2 (BUG-0086/0087). De-prioritized → DR-04 (conditional).

Success criteria:
* If implemented: reused storage reachable by the Flex host; no stale EG subscription poisoning `doc-processing`.

Context references:
* Research §C2 RC-2; v2/scripts/post_provision.py.

Dependencies:
* Step 4.2; gated on PD-02 answer = "reuse mandatory".

### Step 4.4: Validate Phase 4

Validation commands:
* `uv run pytest v2/scripts/tests/test_upload_sample_data.py` (+ test_post_provision.py if 4.3 ran) — green.

## Implementation Phase 5: Final validation — local gates + live `azd up` to Azure

<!-- parallelizable: false -->

The binding validation per the user directive ("we deploy our new cwyd v2 code to the cloud and we test. Any other approach it is not valid").

### Step 5.1: Local gates

Validation commands:
* `uv run pytest` (v2 backend + scripts suites, incl. the new settings / dependencies / seed tests).
* `az bicep build --file v2/infra/main.bicep` — clean compile.
* `npm --prefix v2/src/frontend run build` — SPA builds (`tsc --noEmit` exit 0).
* The v2 shared AST gates: test_no_type_checking_or_future_annotations, test_imports_at_top_only, test_no_process_narrative_in_src, test_no_silent_excepts, test_no_anonymous_dict_returns, test_init_files_are_marker_only — all green.

### Step 5.2: Live `azd up` to Azure (prefer fresh resources, PD-02)

Execute:
* (PD-02 recommended) Provision against FRESH data resources so v2 Bicep owns the full network posture (no reuse drift). If reuse is mandatory, ensure Step 4.3 shipped first.
* `azd up` (default profile — no WAF/private flags) → confirm provision + deploy of all 3 services; confirm the real backend image replaced the `mcr.microsoft.com/k8se/quickstart:latest` placeholder.
* Step 3.3 container-kind guard executed before/at deploy.
* Confirm the unattended seed ran (Phase 4) — `documents` blob count > 0, `doc-processing` drained, `doc-processing-poison` empty.
* Exercise the frontend URL end-to-end: loads with NO auth wall → chat works → admin upload works (no 401) → a seeded doc answers a grounded question in chat.
* `GET <function>/api/health` → 200; `GET <backend>/api/health` → 200; `GET <frontend>/config` → backend FQDN.

### Step 5.3: Clean up + record

* Clean up every test artifact created during validation (test blobs, ingested test docs via the admin delete-by-source endpoint, poison-queue messages) BEFORE closing out — user memory cleanup-before-next-step.
* Update v2/docs/bugs.md: close/verify BUG-0090 (Easy Auth), BUG-0086 + BUG-0087 (only if reuse path exercised), note BUG-0081 guard outcome; BUG-0088 (.docx) stays OPEN.
* Update the day's worklog v2/docs/worklog/YYYY-MM-DD.md with the plan, results, and decisions (Hard Rule #19).

### Step 5.4: Report blocking issues

* If validation surfaces work beyond minor fixes (e.g. private-mode requested, `.docx` required in the corpus, reuse mandatory and self-heal insufficient), document it and recommend a follow-on planning pass rather than large inline changes. Map each to a WI in the log.

Validation commands:
* Live `azd up`, `az webapp show`, `az storage blob list`, `az storage queue` depth checks, browser exercise — all per Step 5.2.

### Step 6.1: `searchServiceLocation` Bicep param (AI Search region override)

Why: Step 5.2's `azd up` provisioned the entire v2 stack in `eastus2` EXCEPT `srch-cwyd2bh3kb` (Azure AI Search, standard SKU), which failed with `InsufficientResourcesAvailable` — `eastus2` is physically out of AI Search capacity (a capacity wall, not a raisable quota). User chose Option A: deploy AI Search in a capacity region (uksouth) while keeping the rest (incl. the proven OpenAI/AI-Services quota) in `eastus2`.

Change (Configuration Layer pillar — operator-tunable infra knob):
* `v2/infra/main.bicep`:
  * Add `param searchServiceLocation string = ''` alongside the other location-ish params (near `existingSearchName` ~L108-120).
  * Add `var effectiveSearchLocation = empty(searchServiceLocation) ? location : searchServiceLocation` next to `useExistingSearch` (~L122) — empty default ⇒ same region as today (backward compatible).
  * In `module aiSearch` (L887-891), change `location: location` → `location: effectiveSearchLocation`.
* `v2/infra/main.parameters.json`: add `"searchServiceLocation": { "value": "${AZURE_ENV_SEARCH_SERVICE_LOCATION=}" }` (mirrors the `${AZURE_ENV_EXISTING_SEARCH_NAME=}` empty-default pattern).
* `v2/tests/infra/test_main_bicep.py`: add a grep-style test asserting (a) `param searchServiceLocation` is declared, (b) the `effectiveSearchLocation` ternary exists, (c) the `aiSearch` module binds `location: effectiveSearchLocation` (not `location: location`). Pillar/Phase header consistent with the file.

Conventions: Hard Rule #11 (camelCase Bicep param), #16 (no process narrative in the bicep comment — describe the knob, not the incident), #18 (no env-specific region literal in tracked files — the region is supplied via the env var, default empty). Cross-region search is safe in the public profile (no private endpoints; `enablePrivateNetworking=false` gates the search PE out).

Validation:
* `az bicep build --file v2/infra/main.bicep` — EXIT 0.
* `uv run python -m pytest tests/infra/test_main_bicep.py -q` — green.

### Step 6.2: Set region env var + re-run `azd up`

Execute (Task Implementor ops):
* `azd env set AZURE_ENV_SEARCH_SERVICE_LOCATION uksouth` (uksouth = proven AI Search capacity; the old `srch-cwydcdbv23ane6` already runs there).
* `azd up` from `v2/` (Set-Location chained so it can't drift to the repo-root v1 `azure.yaml`).
* Confirm `srch-cwyd2bh3kb` provisions in uksouth and the full provision + 3-service deploy completes green.
* Then proceed to the Step 5.2 end-to-end verification (seed ran, queues drained, frontend no auth wall, chat + admin work, health 200s).

### Step 6.3: Grant the deployer principal storage data-plane roles (fix the seed `AuthorizationPermissionMismatch`)

Why: Step 6.2's `azd up` deployed the whole stack green, but the post-deploy seed hook (`upload-sample-data.ps1` → `upload_sample_data.py`) failed with `AuthorizationPermissionMismatch` on `stcwyd2bh3kb`. Root cause (confirmed by reading `main.bicep`): the storage account `roleAssignments` grant the three storage roles **only to the UAMI** (`userAssignedIdentity.outputs.principalId`); the seed runs locally under the **deployer identity** (`DefaultAzureCredential` → the human/CI principal running `azd up`), which has **no** storage data-plane RBAC. There is no `deployer()`-based role assignment on the storage module today (only `postgresAdminPrincipalId` uses that pattern, for Postgres). This is an IaC defect, not a propagation race (the error is an RBAC denial, not a transient 404). A fresh default `azd up` therefore cannot seed sample data.

Change (Configuration Layer pillar — deployer bootstrap RBAC; mirrors the existing UAMI grants + the `postgresAdminPrincipal*` deployer pattern already in the file):
* `v2/infra/main.bicep`:
  * Add, next to the existing `createdBy`/`deployer()` usage (~L239) or near the storage module, the deployer identity facts:
    * `var deployerPrincipalId = deployer().objectId`
    * `var deployerPrincipalType = contains(deployer(), 'userPrincipalName') ? 'User' : 'ServicePrincipal'` (same expression already used for `postgresAdminPrincipalType` at ~L1491 — keep it as a `var` so both can share or reuse it).
  * In `module storageAccount` `roleAssignments` array (L1144-1166), append two entries:
    * `{ principalId: deployerPrincipalId, principalType: deployerPrincipalType, roleDefinitionIdOrName: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' }` — Storage Blob Data Contributor (upload seed blobs).
    * `{ principalId: deployerPrincipalId, principalType: deployerPrincipalType, roleDefinitionIdOrName: 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a' }` — Storage Queue Data Message Sender (enqueue doc-processing messages from the seed). This GUID is already referenced for the Event Grid queue-sender grant, so it is not a new literal in the file.
  * Add unconditionally (the deployer always seeds via the public endpoint in the default profile; the assignment is harmless when no seed runs). No process-narrative comment — describe what the grant is for (deployer seed), per Hard Rule #16.
* `v2/tests/infra/test_main_bicep.py`: add a grep-style test asserting the `storageAccount` module slice contains a role assignment whose `principalId` is `deployerPrincipalId` for BOTH role GUIDs (Blob Data Contributor + Queue Data Message Sender), and that `deployerPrincipalId`/`deployerPrincipalType` vars are declared. Reuse the `_slice_module` helper (`module storageAccount ` → the next `module ` after it).

Conventions: Hard Rule #1 (one unit — the deployer-RBAC grant + its test), #2 (test-first), #11 (camelCase `var`), #16 (no incident narrative in the bicep comment), #18 (no env-specific principal id — `deployer()` resolves at deploy time; nothing written to a tracked file).

Validation:
* `az bicep build --file v2/infra/main.bicep` — EXIT 0.
* `uv run python -m pytest tests/infra/test_main_bicep.py -q` — green.
* Then re-run `azd up` (or just re-invoke the seed once RBAC propagates): seed succeeds, `documents` blob count > 0, `doc-processing` drains, `doc-processing-poison` empty, search index document count > 0.

Note (defect tracking): record this as a new `BUG-####` in `v2/docs/bugs.md` (deployer-identity storage RBAC seed failure) + a worklog entry in `v2/docs/worklog/2026-06-29.md` per Hard Rule #19. Task Implementor mode writes only under `.copilot-tracking/`, so the `bugs.md`/worklog updates are flagged here and performed by the implementer/user as an explicit out-of-scope step.

### Step 6.4: Fix open-mode chat (`get_user_id` open-auth fallback)

Discovered during Step 6.2/6.3 live validation: the deployed backend runs `environment=production` (correct, per config-defaults-dev-first — IaC flips it) AND has Easy Auth disabled (Step 3.1, "no auth wall"). `POST /api/conversation` consumes `UserIdDep` → `backend.dependencies.get_user_id`, which only falls back to the synthetic `_LOCAL_DEV_USER` when `settings.environment is Environment.LOCAL`. With no Easy Auth principal header in production it raises `401 "Missing client principal; Easy Auth header required."` — so open chat is broken. This is the exact analog of the Phase 2 admin-open fix (`requires_role` uses `allow_open = environment is LOCAL or not require_admin_auth`).

Files / change:
* `v2/src/backend/dependencies.py`: in `get_user_id`, widen the synthetic-user fallback to mirror `requires_role`. Replace the `if settings.environment is Environment.LOCAL:` guard with the open-auth condition `if settings.environment is Environment.LOCAL or not settings.require_admin_auth:` → `return _LOCAL_DEV_USER`. Keep the production-with-Easy-Auth path failing closed (401) only when auth is REQUIRED (`require_admin_auth=True`) and no/invalid principal is present. Update the docstring to describe the open-deployment fold (anonymous callers map to the synthetic partition when auth is open), per Hard Rule #16 (describe what the code is, no incident narrative). A forged/malformed principal id still 401s (the `_is_valid_principal_id` branch is unchanged).
* `v2/tests/backend/test_dependencies.py` (or the existing `get_user_id` test module): add a test asserting that with `environment=production` + `require_admin_auth=False` + no principal header, `get_user_id` returns `_LOCAL_DEV_USER` (does NOT raise); and that with `environment=production` + `require_admin_auth=True` + no header it still raises 401. Reuse the existing fixture/stub pattern for `Request` + `settings`.

Conventions: Hard Rule #1 (one unit — the `get_user_id` fallback widening + its test), #2 (test-first), #11 (`Environment` StrEnum comparison via `is`), #16 (docstring describes behavior, not the incident). Single back-fill allowed under Hard Rule #12 (the end-to-end "chat works" validation literally cannot proceed without it) — annotate in the planning log.

Validation:
* `uv run python -m pytest tests/backend/test_dependencies.py -q` — green.
* Full backend suite stays green: `uv run python -m pytest -q` (no regression).
* Redeploy backend: `azd deploy backend` (app-code-only change; no infra). Then `POST <backend>/api/conversation` with `{"messages":[{"role":"user","content":"<benefits question>"}]}` + `Accept: application/json` → 200 with a grounded answer + non-empty `citations` (proves index populated + open chat works).

Note (defect tracking): record as a new `BUG-####` in `v2/docs/bugs.md` (open-mode chat 401 when Easy Auth disabled in production) + worklog entry, per Hard Rule #19 (flagged, out-of-scope for Task Implementor file-write boundary).

### Step 6.5: Grant the deployer Search Index Data Reader + export AZURE_AI_SEARCH_INDEX to the seed

Two robustness gaps found while validating the seed's index self-check (the system itself works — ingestion confirmed via drained queues + no poison; these only affect the seed's *verification* path):
* Gap A — the `aiSearch` service has `disableLocalAuth: true` (RBAC-only data plane). The `aiSearch` module `roleAssignments` grant Search Index Data Contributor/Reader to the UAMI + AI Foundry project, but NOT to the deployer. The local seed (run under the deployer via `DefaultAzureCredential`) therefore gets `Forbidden` on every index-count poll and emits a false-negative FAIL banner even though ingestion succeeded.
* Gap B — `AZURE_AI_SEARCH_INDEX` is empty in `azd env get-values`, so the postdeploy seed hook (which only verifies when BOTH `AZURE_AI_SEARCH_ENDPOINT` and `AZURE_AI_SEARCH_INDEX` are set) skips the index verify entirely on a real `azd up`. Index name is `cwyd-index`.

Files / change:
* `v2/infra/main.bicep`: in `module aiSearch` `roleAssignments` (~L919-944), append `{ principalId: deployerPrincipalId, principalType: deployerPrincipalType, roleDefinitionIdOrName: '1407120a-92aa-4202-b7e9-c0e197c71c8f' }` — Search Index Data Reader (deployer reads index doc count during seed verify). Reuses the `deployerPrincipalId`/`deployerPrincipalType` vars added in Step 6.3 (no new literal).
* `v2/infra/main.bicep`: ensure the search index name reaches the seed env. Prefer adding/confirming an `output AZURE_AI_SEARCH_INDEX string = '<resolved index name>'` (the index name the backend uses, `cwyd-index`) so azd exports it to the postdeploy hook env. If the index name is a param/var already, surface it as an output; otherwise add a stable `param searchIndexName string = 'cwyd-index'` consumed by both the backend container env and the new output (confirm naming with the existing backend `AZURE_AI_SEARCH_INDEX` env wiring before adding — avoid duplicating a source of truth).
* `v2/tests/infra/test_main_bicep.py`: add a test asserting the `aiSearch` module slice grants `deployerPrincipalId` the Search Index Data Reader GUID, and that `AZURE_AI_SEARCH_INDEX` is exported as an output (or the index-name param is surfaced to the seed). Reuse `_slice_module`.

Conventions: Hard Rule #1 (one unit — the deployer search-read grant + index-name export + test; if the output wiring is non-trivial, split into two turns: 6.5a grant, 6.5b output), #2 (test-first), #11 (camelCase), #16, #18 (no env-specific principal; `deployer()` resolves at deploy time).

Validation:
* `az bicep build --file v2/infra/main.bicep` — EXIT 0.
* `uv run python -m pytest tests/infra/test_main_bicep.py -q` — green.
* `azd provision` to apply; then `azd env get-values` shows `AZURE_AI_SEARCH_INDEX=cwyd-index`; re-run the seed → index-count verify passes (no `Forbidden`), FAIL banner gone.

Note (defect tracking): record as new `BUG-####` rows in `v2/docs/bugs.md` (deployer search-read RBAC false-negative seed verify; `AZURE_AI_SEARCH_INDEX` not exported to seed) + worklog, per Hard Rule #19 (flagged, out-of-scope for the Task Implementor file-write boundary).

### Step 6.6: Delete the old `cwydcdbv23ane6` resource set

> Executes LAST — after Steps 6.4 and 6.5 are deployed green.


User-consented destructive cleanup (answered "Yes — delete the old set"). Delete ONLY the `cwydcdbv23ane6`-suffixed resources (old v1-style set: incl. Key Vault, `-docker` apps, uksouth search, AI Foundry + project, OpenAI, Cognitive Services, Doc Intelligence, Speech, Event Grid, Cosmos, Storage, App Service Plan, managed identity). NEVER touch any `cwyd2bh3kb`-suffixed (current v2) resource.

Execute:
* Enumerate old-suffix resources, delete child/dependent resources before parents where ordering matters (AI Foundry project before account; apps before plan).
* Do this AFTER Step 6.2 is green (working deploy first), per cleanup-before-next-step.
* Soft-delete shells (Key Vault / Cognitive Services / OpenAI / AI Foundry) are harmless — they carry the old suffix and cannot collide with the new `cwyd2bh3kb` names; purge is optional and out of scope.

Validation:
* `az resource list -g <RESOURCE_GROUP> --query "[?contains(name,'cwydcdbv23ane6')]"` returns empty (or only soft-deleted shells).
* `az resource list` confirms all `cwyd2bh3kb` resources remain intact.

## Dependencies

* `azd >= 1.18.0 != 1.23.9`, Azure subscription with quota for the default profile.
* `uv` (Python env), Node/npm (frontend build), `az` CLI + Bicep, Docker not required (backend uses ACR remote build).
* AVM modules: `br/public:avm/res/web/site:0.22.0` (frontend auth param shape).

## Success Criteria

* A default `azd up` + unattended seed yields: frontend loads (no auth wall), chat works, admin/upload works (no 401), functions ingest the seeded PDFs — all reachable from the frontend URL, validated live on Azure.
* No banned tech, no Key Vault, no inverted `Environment.LOCAL` default, no env-specific content in tracked files, every new method/field lands with an executing test.
