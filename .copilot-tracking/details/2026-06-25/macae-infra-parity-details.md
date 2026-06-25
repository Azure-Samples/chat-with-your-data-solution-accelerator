<!-- markdownlint-disable-file -->
# Implementation Details: MACAE infra parity — one-shot `azd up` for CWYD v2

## Context Reference

Sources: research `.copilot-tracking/research/2026-06-25/macae-infra-parity-research.md`; subagent docs `v2-bicep-line-numbers-aitems.md`, `v2-frontend-appservice-scope.md`, `macae-container-build-pattern.md` (all under `.copilot-tracking/research/.../2026-06-25/`); manual-debt catalogue `.../2026-06-24/manual-change-debt-deployment-iac.md`.

All line numbers below are the CURRENT positions found during research (2026-06-25). Re-read each anchor before editing — line numbers drift as earlier steps land.

## Implementation Phase 1: Frontend → App Service build-from-source (BUG-0081)

<!-- parallelizable: false -->

### Step 1.1: Make `frontend_app.py` serve from a wwwroot-relative dist

Today `_DIST_DIR` defaults to the Docker path `/usr/src/app/dist`. On App Service the deploy root is `/home/site/wwwroot`, so resolve the default relative to the app file instead, keeping the `DIST_DIR` env override for tests.

Files:
* v2/src/frontend/frontend_app.py - change `_DIST_DIR` default from `/usr/src/app/dist` to `Path(__file__).resolve().parent / "dist"`; keep the `DIST_DIR` env override and the catch-all SPA fallback.
* v2/tests/frontend/ (or v2/src/frontend/tests/) - add/extend a test asserting the server serves `index.html` for a deep link and a real file when present, using a `DIST_DIR` fixture.

Discrepancy references:
* Addresses subagent finding: `frontend_app.py` hard-codes the Docker dist path (v2-frontend-appservice-scope.md §3).

Success criteria:
* Server resolves `dist/` next to `frontend_app.py` when `DIST_DIR` is unset.
* Test passes with a fixture dist dir.

Context references:
* v2-frontend-appservice-scope.md §3 (frontend_app.py full source).

Dependencies:
* None.

### Step 1.2: Replace the frontend `docker:` block with `dist:` + a `prepackage` hook in azure.yaml

Files:
* v2/azure.yaml - in `services.frontend` (lines ~107-126): remove the `docker:` block (path/context/target/buildArgs); add `dist: ./dist`; add `hooks.prepackage` (posix `sh` → `../scripts/package-frontend.sh`, windows `pwsh` → `../scripts/package-frontend.ps1`), mirroring `services.function.hooks.prepackage` (lines ~127-152). Keep `host: appservice`, `project: ./src/frontend`, `language: js`.

Discrepancy references:
* Addresses BUG-0081 (appservice + docker unsupported).

Success criteria:
* `services.frontend` has `host: appservice`, `dist: ./dist`, a service-scoped `prepackage` hook, and NO `docker:` block.

Context references:
* v2-frontend-appservice-scope.md §1 (frontend + function blocks verbatim).

Dependencies:
* Step 1.3 supplies the referenced scripts (land 1.3 in the same or prior turn so the hook resolves).

### Step 1.3: Add `v2/scripts/package-frontend.{sh,ps1}` build hook

A thin OS wrapper that builds the SPA so azd uploads a fresh `dist/`. Per ID-02 (runtime `/config`), the build does NOT bake a backend URL — the SPA fetches it at runtime; the hook just runs `npm ci && npm run build`.

Files:
* v2/scripts/package-frontend.sh - `set -euo pipefail`; `cd` to `src/frontend` relative to the script dir; `npm ci`; `npm run build`. Pillar/Phase header comment.
* v2/scripts/package-frontend.ps1 - PowerShell equivalent (`$ErrorActionPreference='Stop'`, `npm ci`, `npm run build`).
* v2/scripts/tests/ - optional pester/pytest smoke that the wrapper exists and exits non-zero on a missing `src/frontend` (match existing `v2/scripts/tests/` style).

Discrepancy references:
* DD-01 (PD-01): build-time bake vs runtime `/config`.

Success criteria:
* Running the wrapper from a clean tree regenerates `v2/src/frontend/dist/`.

Context references:
* v2-frontend-appservice-scope.md §6 (wrapper convention `*-name.{sh,ps1}` → `uv run python`; here npm directly).

Dependencies:
* None (Node 20 + npm available).

### Step 1.4: Repoint the frontend App Service `linuxFxVersion` in main.bicep

Files:
* v2/infra/main.bicep - `frontendWebApp` AVM module (`web/site:0.22.0`, module start line ~1892): change `kind` from `'app,linux,container'` (line ~1898) to `'app,linux'`; change `linuxFxVersion` (line ~1925) from `'DOCKER|mcr.microsoft.com/appsvc/staticsite:latest'` to `'PYTHON|3.11'`; add `appCommandLine: 'uvicorn frontend_app:app --host 0.0.0.0 --port 8000'`; in `appSettings` (open ~1935) remove `VITE_BACKEND_URL` (build-time only now) and keep `WEBSITES_ENABLE_APP_SERVICE_STORAGE='false'`; if PD-01 = runtime `/config`, instead add `{ name: 'BACKEND_API_URL', value: <backend FQDN output> }` and keep no build-time URL.

Discrepancy references:
* Addresses BUG-0081 durable half (host config).

Success criteria:
* `az bicep build` clean; frontend site renders as a `PYTHON|3.11` App Service with a uvicorn appCommandLine.

Context references:
* v2-bicep-line-numbers-aitems.md "Frontend Microsoft.Web/sites" section (lines 1892/1898/1925/1935).

Dependencies:
* Step 1.1 (server entrypoint), Step 1.2 (dist deploy).

### Step 1.5 (conditional — only if PD-01 = runtime `/config`): `/config` endpoint + SPA seam

This expands into SEVEN one-unit-per-turn sub-steps (Hard Rule #1) — each lands with its test. Skip the whole step if PD-01 = build-time bake (the default).

* Step 1.5a: `frontend_app.py` — register `GET /config` returning `{ "backendUrl": os.environ.get("BACKEND_API_URL", "") }` BEFORE the catch-all route (FastAPI ordering) + its test.
* Step 1.5b: new `v2/src/frontend/src/api/runtimeConfig.tsx` seam that fetches `/config` once at boot and caches the backend URL + its vitest test.
* Step 1.5c–1.5g: converge the 5 `import.meta.env.VITE_BACKEND_URL` read sites onto the seam, ONE FILE PER TURN, each updating its own test: `App.tsx` (1.5c), `api/admin.tsx` (1.5d), `api/conversationHistory.tsx` (1.5e), `api/streamChat.tsx` (1.5f), `api/speech.tsx` (1.5g).

Files:
* v2/src/frontend/frontend_app.py; v2/src/frontend/src/api/runtimeConfig.tsx (new); v2/src/frontend/src/App.tsx; v2/src/frontend/src/api/{admin,conversationHistory,streamChat,speech}.tsx (+ each file's test).

Discrepancy references:
* DD-01 (PD-01): only executed if the user picks runtime `/config`. Step 1.4's frontend appSetting becomes `BACKEND_API_URL` instead of removing the URL.

Success criteria:
* SPA fetches `/config` once and all API calls use the runtime value; vitest green at each sub-step.

Context references:
* v2-frontend-appservice-scope.md §3 + §4 (the 5 read sites; route-ordering caveat).

Dependencies:
* Step 1.1, Step 1.4.

## Implementation Phase 2: Backend image + ACR managed-identity pull

<!-- parallelizable: false -->

### Step 2.1: A10 — enable ACR `azureADAuthenticationAsArmPolicy`

Files:
* v2/infra/main.bicep - `containerRegistry` AVM module (`container-registry/registry:0.12.1`, module start line ~1674): add `policies: { azureADAuthenticationAsArmPolicy: { status: 'enabled' } }` inside `params` (alongside `acrSku`/`publicNetworkAccess` lines ~1681-1684). Verify the nested key against AVM v0.12.1 schema.

Discrepancy references:
* Addresses A10 (ACR-AAD-AS-ARM-BICEP-DEBT).

Success criteria:
* `az bicep build` clean with the `policies` param.

Context references:
* v2-bicep-line-numbers-aitems.md §A10 (module at 1674; no `policies` today).

Dependencies:
* None.

### Step 2.2: A11 — add `registries:` to `backendContainerApp`

Files:
* v2/infra/main.bicep - `backendContainerApp` AVM module (`app/container-app:0.22.1`, lines 1695-1847): add `registries: [{ server: containerRegistry.outputs.loginServer, identity: userAssignedIdentity.outputs.resourceId }]`. The UAMI already holds `AcrPull` (role at module 1685/1688) and is attached (1703-1707).

Discrepancy references:
* Addresses A11 (BACKEND-CA-ACR-REGISTRIES-BICEP-DEBT).

Success criteria:
* Container App declares the ACR registry with the UAMI identity; `az bicep build` clean.

Context references:
* v2-bicep-line-numbers-aitems.md §A11.

Dependencies:
* Step 2.1 (pair the ACR-auth fixes).

### Step 2.3: Backend image by name+tag — first-provision-safe (PD-02)

Name+tag in bicep WITHOUT breaking a clean first `azd up`. On a clean run the ACR is created during provision and the image is pushed during the later deploy, so `AZURE_CONTAINER_REGISTRY_ENDPOINT` (a provision OUTPUT) is empty at first provision. Therefore the composed image must fall back to a PULLABLE PUBLIC placeholder when the hostname param is empty (NOT the freshly-created empty ACR `loginServer`, which is unpullable). azd's deploy-time `azd-service-name` tag-swap patches the live image after build, so the named ACR image is what actually runs. There is NO `preprovision az acr build` bootstrap — it cannot run before the registry exists.

Files:
* v2/azure.yaml - add `docker.remoteBuild: true` to `services.backend` (today it is plain `docker: path/context`) so azd builds in ACR (the research's MACAE remote-build assumption).
* v2/infra/main.bicep - add params `backendContainerRegistryHostname string = ''` / `backendContainerImageName string = 'cwyd-backend'` / `backendContainerImageTag string = 'latest'`; change `containers[0].image` (line ~1729) to: `empty(backendContainerRegistryHostname) ? 'mcr.microsoft.com/k8se/quickstart:latest' : '${backendContainerRegistryHostname}/${backendContainerImageName}:${backendContainerImageTag}'`. This composes name+tag from params (no `reference()`, no `existing` ACR, no lookup) while staying first-provision-safe; the placeholder is only the initial value azd overwrites on deploy.
* v2/infra/main.parameters.json - add `backendContainerRegistryHostname = ${AZURE_CONTAINER_REGISTRY_ENDPOINT}` and `backendContainerImageTag = ${AZURE_ENV_IMAGE_TAG=latest}` (both resolve empty on first provision → placeholder; populated on re-provision after the ACR endpoint is in the azd env).

Discrepancy references:
* Addresses DD-03 (critical): the empty-`loginServer` fallback + `preprovision` bootstrap were unworkable on a clean first provision.
* DD-02 (PD-02): name+tag param-trio vs azd placeholder-swap.

Success criteria:
* `az bicep build` clean; first `azd up` on a clean env succeeds (placeholder pulls, azd swaps to the ACR image on deploy); a re-provision references `${acr}/cwyd-backend:latest` by name+tag.

Context references:
* v2-bicep-line-numbers-aitems.md "Backend image reference"; macae-container-build-pattern.md (param trio + `docker.remoteBuild: true` + deploy-time patch).

Dependencies:
* Steps 2.1, 2.2 (ACR pull must work first).

## Implementation Phase 3: Env-var + RBAC back-ports (A1, A7, A8, A4-roles)

<!-- parallelizable: false -->

### Step 3.1: A1 env — `AZURE_AI_SERVICES_ENDPOINT` on both runtimes

Files:
* v2/infra/main.bicep - add `{ name: 'AZURE_AI_SERVICES_ENDPOINT', value: aiServices.outputs.endpoint }` to the backend env array (1740-1827) and the function appSettings array (2090-2125). The output already exists at line 2359.

Discrepancy references:
* Addresses A1 env half (BUG-0052).

Success criteria:
* Both runtimes carry the env var; `az bicep build` clean.

Context references:
* v2-bicep-line-numbers-aitems.md §A1.

Dependencies:
* None.

### Step 3.2: A1 RBAC — `Cognitive Services User` on the Foundry account

Files:
* v2/infra/main.bicep - add a `Cognitive Services User` (`a97b65f3-24c7-4388-baec-2e87135dc908`) role assignment for the UAMI into the `aiServices` module `roleAssignments` array (line 582). Today it is granted only on Content Safety (line 847).

Discrepancy references:
* Addresses A1 RBAC half (BUG-0052) — DocumentIntelligence/Content Understanding need it on the AI Services account.

Success criteria:
* UAMI holds `Cognitive Services User` on the AI Services account; `az bicep build` clean.

Context references:
* v2-bicep-line-numbers-aitems.md §A1 (RBAC).

Dependencies:
* None.

### Step 3.3: A7 — postgres principal = UAMI on both runtimes

Files:
* v2/infra/main.bicep - change the backend (line 1794) and function (line 2120) `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` value from `postgresAdminPrincipalName` (deployer UPN) to `'id-${solutionSuffix}'` (the UAMI principal the runtime connects as; registered as a postgres admin at line 1497), keeping the `databaseType == 'postgresql' ? ... : ''` guard.

Discrepancy references:
* Addresses A7 (BUG-0063).

Success criteria:
* Runtime postgres login principal is the UAMI; `az bicep build` clean.

Context references:
* v2-bicep-line-numbers-aitems.md §A7.

Dependencies:
* None.

### Step 3.4: A8 — `ORCHESTRATOR` → `CWYD_ORCHESTRATOR_NAME`, databaseType-conditional value

First VERIFY the backend settings field reads `CWYD_ORCHESTRATOR_NAME` (env_prefix `CWYD_ORCHESTRATOR_`, field `name`) in `v2/src/backend/core/...settings`. Then edit.

Files:
* v2/infra/main.bicep - line 1810: rename env key `ORCHESTRATOR` → `CWYD_ORCHESTRATOR_NAME`; value `databaseType == 'postgresql' ? 'langgraph' : 'agent_framework'` (postgres has no Foundry IQ KB → app-side RAG via langgraph).

Discrepancy references:
* Addresses A8 (BUG-0064).

Success criteria:
* Backend reads the orchestrator from `CWYD_ORCHESTRATOR_NAME`; value is correct per db type.

Context references:
* v2-bicep-line-numbers-aitems.md §A8; research doc Scenario 2 (A8 note).

Dependencies:
* Settings-class verification (same turn).

### Step 3.5: A4 roles — Project MI `Search Service Contributor`

Files:
* v2/infra/main.bicep - add a `Search Service Contributor` (`7ca78c08-252a-4471-8644-bb5ff32d4ba0`) role assignment for `aiProject.outputs.projectPrincipalId` into the `aiSearch` `roleAssignments` array (line 904). Today the Project MI gets only `Search Index Data Reader` (line ~927).

Discrepancy references:
* Addresses A4 RBAC half (BUG-0059) — Foundry IQ / Project builds + manages the KB/index.

Success criteria:
* Project MI holds `Search Service Contributor`; `az bicep build` clean; cosmosdb-gated.

Context references:
* v2-bicep-line-numbers-aitems.md §A4.

Dependencies:
* None.

## Implementation Phase 4: KB MCP project connection (A4 connection)

<!-- parallelizable: false -->

### Step 4.1: Declare the `cwyd-kb-mcp` RemoteTool project connection

The `cwyd-kb-mcp` connection does NOT exist in bicep today — `AZURE_AI_SEARCH_CONNECTION_NAME` currently resolves to the `CognitiveSearch` connection (`search-<svc>`), which causes a 401 against the KB MCP. Declare the RemoteTool connection and repoint the env var. STRUCTURAL — confirm the connection shape against the live KB MCP before authoring.

Files:
* v2/infra/modules/ai-project-search-connection.bicep (or a new sibling module) - add a project connection resource named `cwyd-kb-mcp` (category RemoteTool / MCP, AAD auth, target audience `https://search.azure.com`), cosmosdb-gated like the existing `CognitiveSearch` connection (module called at main.bicep line 1037).
* v2/infra/main.bicep - change the backend env `AZURE_AI_SEARCH_CONNECTION_NAME` (line 1792) to resolve to the new `cwyd-kb-mcp` connection name (cosmosdb mode), not the `CognitiveSearch` connection.

Discrepancy references:
* DR-01 / A4 connection half (BUG-0059) — research catalogued this as "create that connection + project-MI Search Service Contributor"; the connection itself is a NEW resource not yet scoped to a concrete schema.

Success criteria:
* The `cwyd-kb-mcp` connection deploys (cosmosdb mode); `AZURE_AI_SEARCH_CONNECTION_NAME` resolves to it; `az bicep build` clean.

Context references:
* v2-bicep-line-numbers-aitems.md §A4 (connection NOT FOUND); ai-project-search-connection.bicep (existing connection shape).

Dependencies:
* Step 3.5 (Project MI Search Service Contributor) — the connection is useless without the role.
* RESEARCH GAP — see Planning Log DR-01: the exact RemoteTool/MCP connection schema needs confirmation against the live KB MCP before this step is implementable.

## Implementation Phase 5: Function host config (A2, A3)

<!-- parallelizable: false -->

### Step 5.1: A2 — `alwaysReady` for the queue trigger(s)

Files:
* v2/infra/main.bicep - `functionApp` module, `functionAppConfig.scaleAndConcurrency` (lines 2070-2073): add `alwaysReady: [{ name: 'function:batch_push', instanceCount: 1 }]` (add `function:blob_event` when that trigger deploys per BUG-0054/0077).

Discrepancy references:
* Addresses A2 (BUG-0053).

Success criteria:
* Flex function keeps one always-ready instance for the queue trigger; `az bicep build` clean.

Context references:
* v2-bicep-line-numbers-aitems.md §A2.

Dependencies:
* None.

### Step 5.2: A3 — queue `messageEncoding=none`

Confirm whether the manual fix used the app setting `AzureFunctionsJobHost__extensions__queues__messageEncoding=none` or a `host.json` extension block; prefer `host.json` (ships with the package) for durability, else the app setting.

Files:
* v2/src/functions/host.json - add `extensions.queues.messageEncoding = "none"` (preferred); OR
* v2/infra/main.bicep - add `{ name: 'AzureFunctionsJobHost__extensions__queues__messageEncoding', value: 'none' }` to the function appSettings array (2090-2125).

Discrepancy references:
* Addresses A3 (BUG-0056).

Success criteria:
* Producer/consumer raw-JSON encoding matches on every deploy.

Context references:
* v2-bicep-line-numbers-aitems.md §A3.

Dependencies:
* None.

## Implementation Phase 6: Storage firewall + Event Grid ordering (A6, A5)

<!-- parallelizable: false -->

### Step 6.1: A6 — storage `networkAcls` for the no-private-net profile

Files:
* v2/infra/main.bicep - `storageAccount` AVM module (`storage/storage-account:0.32.0`, module start line 1060): add `networkAcls: { defaultAction: enablePrivateNetworking ? 'Deny' : 'Allow', bypass: 'AzureServices' }` so the Flex function deploy is not blocked when private networking is off; private-networking keeps `Deny` (the private endpoint covers it).

Discrepancy references:
* Addresses A6 (BUG-0062).

Success criteria:
* `enablePrivateNetworking=false` → storage `defaultAction=Allow`; `az bicep build` clean.

Context references:
* v2-bicep-line-numbers-aitems.md §A6 (no `networkAcls` today; `publicNetworkAccess` gated on `enablePrivateNetworking` line 1072).

Dependencies:
* None.

### Step 6.2: A5 — Event Grid role-before-subscription ordering

Restructure so `eventGridQueueSenderRole` is created before the `blob-created-to-doc-processing` subscription's preflight. STRUCTURAL (Hard Rule #10).

Files:
* v2/infra/main.bicep - lift the `blob-created-to-doc-processing` subscription out of the AVM `event-grid/system-topic` `eventSubscriptions:` array (line 2192/2198) into a standalone `Microsoft.EventGrid/systemTopics/eventSubscriptions` resource that `dependsOn` `eventGridQueueSenderRole` (line 2234) — mirroring the existing `existingEventGridSubscription` standalone resource (line 2274) used on the reuse path.

Discrepancy references:
* Addresses A5 (BUG-0061) — PD-04 confirms the restructure approach.

Success criteria:
* Fresh `azd provision` no longer fails the subscription preflight on a missing queue-sender role; no `RoleAssignmentExists` on reconcile.

Context references:
* v2-bicep-line-numbers-aitems.md §A5 (subscription nested in AVM module; standalone reuse-path resource present as the template).

Dependencies:
* None (but high-risk — validate with `azd provision --preview`).

## Implementation Phase 7: Post-deploy sample-data upload (Scenario 3)

<!-- parallelizable: false -->

### Step 7.1: Choose + stage the curated sample-data set (PD-03)

Files:
* v2/data/sample/ (new) - copy the curated grounding subset from repo-root `data/` (default: the Northwind/Benefits set), OR keep a manifest pointing at repo-root `data/`. Decision PD-03.

Discrepancy references:
* DD-03 (PD-03): curated `v2/data/sample/` copy vs manifest over root `data/`.

Success criteria:
* A deterministic, small, curated doc set is resolvable from `v2/`.

Context references:
* v2-frontend-appservice-scope.md §7 (root `data/` corpus listing; no `v2/data/`).

Dependencies:
* None.

### Step 7.2: Add `v2/scripts/upload_sample_data.py`

Files:
* v2/scripts/upload_sample_data.py - `DefaultAzureCredential` Blob client to `AZURE_STORAGE_ACCOUNT_NAME` (already an azd output); upload the curated docs to the documents container (idempotent: skip blobs already present); then enqueue to `doc-processing` (the store→`batch_push` path the admin upload uses) so the deployed function ingests. `--dry-run`, `_require()`, Pillar/Phase header — match `post_provision.py` style.
* v2/scripts/tests/ - pytest covering: dry-run makes no SDK calls; idempotent skip-if-exists; required-env failure exits non-zero.

Discrepancy references:
* DD-04 (PD-05 in research): enqueue-via-pipeline (recommended) vs direct-index push.

Success criteria:
* Uploader is idempotent and exercises the real ingestion pipeline; tests pass.

Context references:
* v2-frontend-appservice-scope.md §6 (post_provision.py auth + style); research Scenario 3.

Dependencies:
* Step 7.1 (data set).

### Step 7.3: Wire the `postdeploy` hook in azure.yaml

Files:
* v2/azure.yaml - add a project-level `hooks.postdeploy` (posix `sh` → `./scripts/upload-sample-data.sh`, windows `pwsh` → `./scripts/upload-sample-data.ps1`), mirroring the `postprovision` block (lines ~168-180). `postdeploy` runs after all services deploy so the function is live to ingest.
* v2/scripts/upload-sample-data.sh + .ps1 - thin wrappers → `uv run python upload_sample_data.py` (match `post-provision.{sh,ps1}`).

Discrepancy references:
* Addresses Scenario 3 (no postdeploy hook today).

Success criteria:
* `azd up` runs the uploader after deploy; re-running is a no-op.

Context references:
* v2-frontend-appservice-scope.md §1 + §6 (hooks + wrapper convention).

Dependencies:
* Step 7.2.

## Implementation Phase 8: Validation

<!-- parallelizable: false -->

### Step 8.1: Bicep build + what-if (both db types)

Validation commands:
* `az bicep build --file v2/infra/main.bicep` - must be clean (0 errors/warnings).
* `azd provision --preview` with `databaseType=cosmosdb` then `=postgresql` - confirm Search deploys only for cosmosdb and the new role/env/connection changes appear.

### Step 8.2: Run the v2 test suites

Validation commands:
* `uv run pytest v2/` (scoped to changed scripts: `package_frontend`, `upload_sample_data`, `frontend_app`).
* `npm --prefix v2/src/frontend run test` (vitest) - covers `frontend_app` server + any runtime-config seam if PD-01 = `/config`.

### Step 8.3: End-to-end `azd up` smoke

Run `azd up` from a clean env for `databaseType=cosmosdb`, then a second env for `postgresql`. Confirm: all three services deploy; frontend reaches backend; index/KB has the sample docs; the deployed backend AND function report `environment=production` (closes BUG-0069 / A9 cloud-verify, DR-03); zero manual `az` follow-ups. Document results in the day's worklog (`v2/docs/worklog/2026-06-25.md`) and flip the corresponding BUG rows in `v2/docs/bugs.md`. Report any failure that needs more than a minor fix rather than fixing inline.

## Dependencies

* azd `>= 1.18.0 != 1.23.9`, Bicep CLI, `az` CLI, `uv`, Node 20 / npm.

## Success Criteria

* One `azd up` deploys infra + all three services with no manual `az` follow-up, for both database types; bicep clean; v2 tests pass; sample docs present post-deploy.
