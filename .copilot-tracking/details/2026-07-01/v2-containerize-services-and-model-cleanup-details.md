<!-- markdownlint-disable-file -->
# Implementation Details: CWYD v2 — Containerize All Three Services + Model Cleanup

## Context Reference

Sources:
* .copilot-tracking/research/2026-07-01/v2-acr-build-rbac-models-research.md (primary — confirmed decisions, selected approach, per-service change table)
* .copilot-tracking/research/subagents/2026-07-01/v2-containerize-frontend-function-research.md (frontend + function containerization edit sites, hosting-option comparison)
* .copilot-tracking/research/subagents/2026-07-01/v2-reasoning-drop-gpt4-scrub-research.md (reasoning-removal edit sites, gpt-4 inventory)
* .copilot-tracking/research/subagents/2026-07-01/v2-residual-gaps-research.md (image-tag swap, model edit sites, KB connection)
* .copilot-tracking/research/subagents/2026-07-01/v2-rbac-auth-readiness-research.md (RBAC complete; anonymous auth confirmed)

CWYD Hard Rules that gate every step below:
* One unit per turn (one class OR one method); test-first; `Pillar:`/`Phase:` docstring header on new modules.
* Hard Rule #10 — every structural change (new/removed bicep resource, `host:` change, removed settings field, narrowed type) needs explicit user confirmation before the implementer touches the file.
* Hard Rule #18 — no environment-specific IDs in any tracked file; placeholders only.
* Every phase ends green (`az bicep build` + what-if, pytest, vitest, pyright --strict, ruff, AST gates).

All line numbers below are from the research docs and MUST be re-verified against the live file at implementation time (the tree moves).

## Implementation Phase 1: Frontend → Container App

<!-- parallelizable: false -->

Shared-file note: Phases 1-3 all edit `v2/infra/main.bicep` and `v2/azure.yaml`; they are strictly sequential (shared file + bicep build order). No phase-level parallelism.

### Step 1.1: Confirm/adjust `Dockerfile.frontend` prod stage for Container Apps

Verify the existing `prod` stage serves on the port Container Apps ingress will target and needs no build-arg baking. The frontend resolves the backend URL at RUNTIME via `/config` → `BACKEND_API_URL`, so no `VITE_BACKEND_URL` build-arg is needed.

Files:
* v2/docker/Dockerfile.frontend - confirm `prod` stage: `EXPOSE 80`, uvicorn static server, `/config` endpoint reads `BACKEND_API_URL`. Adjust only if the port/CMD differs from what the Container App ingress expects.

Discrepancy references:
* Addresses DR-01 (Dockerfile.frontend prod stage assumed correct — must verify).

Success criteria:
* `docker build -f v2/docker/Dockerfile.frontend --target prod ..` succeeds locally.
* The prod image exposes a single HTTP port and serves `/config` returning `BACKEND_API_URL`.

Context references:
* v2-containerize-frontend-function-research.md — Part A (Dockerfile.frontend prod stage, uvicorn :80, `/config`).

Dependencies:
* None.

### Step 1.2: Point `v2/azure.yaml` frontend service at `host: containerapp`

Change the frontend service host and docker block to mirror the backend; remove App-Service-specific config and the `VITE_BACKEND_URL` build-arg.

Files:
* v2/azure.yaml - frontend service block: set `host: containerapp`; `docker:` `path: ../../docker/Dockerfile.frontend`, `target: prod`, `context: ../..`; drop `buildArgs: VITE_BACKEND_URL=...`.

Discrepancy references:
* Addresses the confirmed decision #1 (frontend as a container image).

Success criteria:
* `azd` schema accepts the frontend service (no `docker:`-under-`appservice` warning).
* The frontend service tag resolves to `azd-service-name: frontend` on the new bicep resource.

Context references:
* v2-containerize-frontend-function-research.md — Part A step 2 (azure.yaml frontend edit).
* v2/azure.yaml backend service block (the mirror template).

Dependencies:
* Step 1.1.

### Step 1.3: Replace the frontend App Service resource with a Container App in `main.bicep`

Replace the frontend `Microsoft.Web/sites` (`kind: 'app,linux'`, `PYTHON|3.11`) with a `Microsoft.App/containerApps` resource (mirror the backend Container App; same AVM `container-app` module or raw resource), tagged `azd-service-name: frontend`, external ingress `targetPort: 80`, the shared UAMI identity, the ACR registry, placeholder image, and a `BACKEND_API_URL` env = backend Container App FQDN. Because the frontend is the App Service Plan's ONLY consumer (main.bicep:2028), DEFINITIVELY remove the `appServicePlan` module (~2005) + its three now-orphaned vars `appServicePlanName` (~1992), `appServicePlanSkuName` (~2002), `appServicePlanSkuCapacity` (~2003) in this same step — no "if dedicated" hedge. This is a structural change (Hard Rule #10 — confirm before editing).

Files:
* v2/infra/main.bicep - remove the frontend App Service resource (~line 2074) + its Easy Auth `authConfig` (~2050-2069, stays disabled/anonymous — decision #2) + the `appServicePlan` module (~2005) + its 3 orphaned vars (`appServicePlanName` ~1992, `appServicePlanSkuName` ~2002, `appServicePlanSkuCapacity` ~2003); add the frontend Container App resource mirroring the backend block; keep `azd-service-name: frontend`.

Discrepancy references:
* Addresses confirmed decision #1; preserves decision #2 (anonymous — no authConfig added); addresses DR-09 (App Service Plan + orphaned vars removal owned here).

Success criteria:
* `az bicep build` succeeds with zero unused-var warnings for the 3 App-Service-Plan vars.
* `what-if` shows the frontend App Service + the `appServicePlan` removed and a frontend Container App added on the existing `cae-<suffix>` environment.
* No new role assignment required (shared UAMI already holds AcrPull, registry-scoped).

Context references:
* v2-containerize-frontend-function-research.md — Part A steps 1-2 (App Service current shape; Container App target properties: ingress targetPort, external, env, identity, registry).
* v2/infra/main.bicep backend Container App block (mirror template).

Dependencies:
* Step 1.2.

### Step 1.4: Repoint frontend URL output + backend CORS to the Container App FQDN

Update any bicep output that exposed the frontend App Service FQDN and any backend CORS/frontend-origin env that referenced it, so both point at the new frontend Container App FQDN.

Files:
* v2/infra/main.bicep - frontend URL output; any backend `env` CORS allow-list / frontend-origin value that referenced the old App Service FQDN.

Discrepancy references:
* Addresses DR-02 (CORS/origin repointing after host change).

Success criteria:
* `what-if` shows the frontend URL output resolving to the Container App FQDN.
* Backend CORS env (if any) references the frontend Container App FQDN.

Context references:
* v2-containerize-frontend-function-research.md — Part A step 4 (outputs/DNS/CORS wiring).

Dependencies:
* Step 1.3.

### Step 1.5: Retire frontend packaging scripts + `build-output` staging

Mirror the function's Step 2.6 for the frontend: once `host: containerapp` builds the image, the App-Service source-build packaging is dead. Remove the packaging scripts and the `dist: ./build-output` staging reference (the `azure.yaml` frontend `hooks.prepackage` + `dist:` line is removed in Step 1.2; this step deletes the now-orphaned script files).

Files:
* v2/scripts/package-frontend.sh, v2/scripts/package-frontend.ps1, v2/scripts/package_frontend.py - remove.
* v2/.gitignore - remove any dead `build-output/` entry.

Discrepancy references:
* Addresses DR-10 (frontend packaging-script retirement parity with function Step 2.6).

Success criteria:
* `grep -ri "package.frontend\|build-output" v2/scripts v2/azure.yaml` returns only historical (docs/worklog) hits, no live references.
* CI (`Dockerfile.ci-validate` flow) does not call the removed scripts.

Context references:
* v2-containerize-frontend-function-research.md — Part A.2 (package-frontend scripts + `package_frontend.py` become dead).
* User memory: clean up + reduce code debt as you go.

Dependencies:
* Step 1.4.

### Step 1.6: Validate Phase 1

Files:
* (validation only)

Validation commands:
* `cd v2/infra; az bicep build --file main.bicep` — bicep compiles.
* `az deployment sub what-if ... -p main.parameters.json` (or the repo's what-if wrapper) — confirm frontend delta.
* frontend build/test: `cd v2/src/frontend; npm run build` — SPA still builds.

Success criteria:
* Bicep green; frontend build green; no new lint/type errors.

Dependencies:
* Steps 1.1-1.5.

## Implementation Phase 2: Function → Azure Functions on Azure Container Apps

<!-- parallelizable: false -->

Selected target: **Azure Functions on Azure Container Apps** (`Microsoft.App/containerApps` `kind: functionapp`, azd `host: containerapp`) — the only azd-supported containerized-Functions path. Net infra reduction (removes Flex plan, App Service Plan, deployment-package container, `flexDeploymentRole`). Decision defaults baked in: `minReplicas: 1` (warm, mirrors Flex `alwaysReady`); self-contained prod Dockerfile (retire `prepackage_function.py` + `build-functions/`); bump the shared `container-app` AVM module version.

### Step 2.1: Author a production `Dockerfile.functions`

Write a prod Functions image (base `mcr.microsoft.com/azure-functions/python:4-python3.11`) that reproduces the deploy layout `prepackage_function.py` builds: `function_app.py` + `host.json` at the app root, the function subpackages nested under `functions/<sub>/` (with marker `__init__.py`), and `backend/` copied so `from backend.core...` resolves. Do NOT flatten `src/functions → wwwroot` (that breaks `from functions.<sub>` imports — the compose-only Dockerfile's bug).

Files:
* v2/docker/Dockerfile.functions - rewrite from compose-only to a prod azd deploy image with the correct `functions/`-subpackage nesting + `backend/` copy. Deps SINGLE SOURCE = `v2/pyproject.toml [project.dependencies]`: the image installs from `pyproject.toml` at build (e.g. `pip install .` / `uv export`), NOT from a committed `requirements.functions.txt` — because Step 2.6 deletes `prepackage_function.py`, the current requirements generator. Do not strand deps on the retired generator.

Discrepancy references:
* Addresses DR-03 (High risk — function import layout must match prepackage nesting); DR-17 (requirements source pinned to `pyproject.toml`, not the retired generator).

Success criteria:
* `docker build -f v2/docker/Dockerfile.functions ..` succeeds.
* Inside the image, `python -c "import function_app"` and `from functions.batch_push import ...` and `from backend.core... import ...` all resolve (smoke).

Context references:
* v2/scripts/prepackage_function.py (the authoritative layout to reproduce: subpackages `add_url`, `batch_push`, `batch_start`, `blob_event`, `search_skill`, `core`; backend copy; requirements generation).
* v2-containerize-frontend-function-research.md — Part B step 4c (Dockerfile.functions assessment).

Dependencies:
* Phase 1 complete.

### Step 2.2: Point `v2/azure.yaml` function service at `host: containerapp`

Change the function service host to `containerapp` with a `docker:` block; remove the `prepackage` hook and the `project: ./build-functions` staging pointer (project points at `./src/functions` build context now via the Dockerfile).

Files:
* v2/azure.yaml - function service block: `host: containerapp`; `docker:` `path: ../../docker/Dockerfile.functions`, `context: ../..`; remove the `services.function.hooks.prepackage` block.

Discrepancy references:
* Addresses confirmed decision #1 (function as a container image).

Success criteria:
* `azd` schema accepts the function service under `host: containerapp` with `docker:`.
* Tag resolves to `azd-service-name: function`.

Context references:
* v2-containerize-frontend-function-research.md — Part B step 4a.
* v2/azure.yaml current function block (~lines 126-159).

Dependencies:
* Step 2.1.

### Step 2.3: Replace the Flex Function App with a Functions-on-ACA resource in `main.bicep`

Replace the Flex Consumption Function App + its App Service Plan (`functionPlan`, FC1) + the deployment-package storage container with a `Microsoft.App/containerApps` `kind: functionapp` on the shared `cae-<suffix>` environment, tagged `azd-service-name: function`, using the shared UAMI, the ACR registry, a placeholder image, and the existing function app settings (`AzureWebJobsStorage__accountName`/`__credential`/`__clientId`, `FUNCTIONS_EXTENSION_VERSION`, plus all the AZURE_* settings already wired). Bump the shared `container-app` AVM module version to one supporting `kind: functionapp` (re-validate the backend). Structural change (Hard Rule #10 — confirm).

**DO NOT literally mirror the backend block — three host-specific deltas are load-bearing (DR-11):**
* Add `FUNCTIONS_WORKER_RUNTIME=python` — a NEW app setting REQUIRED on ACA (Flex forbids it; the current bicep comment at ~2257 notes "Flex Consumption rejects FUNCTIONS_WORKER_RUNTIME"). Missing it → worker fails to start.
* Set `ingressTargetPort: 80` — the Functions Python base image listens on 80, NOT the backend's 8000. Wrong port → `search_skill`/`health`/HTTP triggers unreachable.
* Set `minReplicas: 1` (warm, mirrors Flex `alwaysReady`) and map `maxReplicas` from Flex `maximumInstanceCount` (~2231 `enableScalability ? 100 : 40`) → ACA `maxReplicas: enableScalability ? 100 : 40`, NOT the backend's 3/10 (that is an ingestion-throughput regression).

Files:
* v2/infra/main.bicep - remove the Flex Function App resource + its `functionPlan` (FC1) + the deployment-package blob container; add the Functions-on-ACA Container App with the 3 deltas above; bump the `container-app` AVM module version at the module reference(s).

Discrepancy references:
* Addresses DR-04 (AVM module version bump affects backend — re-validate); DR-11 (3 host-specific deltas enumerated: `FUNCTIONS_WORKER_RUNTIME`, `ingressTargetPort: 80`, `maxReplicas` 40/100).

Success criteria:
* `az bicep build` succeeds (backend Container App still compiles under the bumped module version).
* `what-if` shows the Flex Function App + `functionPlan` + deployment container removed and a Functions-on-ACA Container App added.
* All existing function app settings present on the new resource PLUS `FUNCTIONS_WORKER_RUNTIME=python`; `ingressTargetPort: 80`; `maxReplicas` = `enableScalability ? 100 : 40`; `minReplicas: 1`.

Context references:
* v2-containerize-frontend-function-research.md — Part B steps 2-4 (hosting-option comparison, recommended target, bicep edit).
* v2/infra/main.bicep function app settings block (~lines 2078-2130 in the older survey; re-verify).

Dependencies:
* Step 2.2.

### Step 2.4: Remove `flexDeploymentRole` + deployment-package container

Remove the `flexDeploymentRole` (Storage Blob Data Owner, ~line 2155) and the deployment-package blob container now that the image comes from ACR. Confirm nothing else references them.

Files:
* v2/infra/main.bicep - remove `flexDeploymentRole` role assignment + the deployment-package container resource.

Discrepancy references:
* Addresses DR-05 (drop Flex deployment RBAC).

Success criteria:
* `grep` shows zero remaining references to the removed symbols.
* `what-if` shows the role assignment + container removed; the function still pulls from ACR via UAMI AcrPull.

Context references:
* v2-rbac-auth-readiness-research.md (RBAC table — `flexDeploymentRole` is Flex-deploy-only).

Dependencies:
* Step 2.3.

### Step 2.5: Repoint any consumer of the function FQDN

Repoint any AI Search skillset or backend env that referenced the Flex Function App URL (`AZURE_FUNCTION_APP_URL` or similar) to the new function Container App FQDN.

Files:
* v2/infra/main.bicep - function URL output + any skillset/backend env referencing it.
* v2/scripts/post_provision.py - if the search skillset registration uses the function URL, verify it reads the new FQDN env/output.

Discrepancy references:
* Addresses DR-06 (skillset/URL repointing after function host change).

Success criteria:
* `what-if` + `grep` confirm every function-URL consumer resolves to the Container App FQDN.

Context references:
* v2-containerize-frontend-function-research.md — Part B step 5 (skillset repointing risk).

Dependencies:
* Step 2.4.

### Step 2.6: Retire `prepackage_function.py` + `build-functions/` staging

Remove the now-unused prepackage tooling (the self-contained Dockerfile replaces it). Delete `prepackage_function.py`, the `prepackage-function.sh`/`.ps1` shells, and any `build-functions/` gitignore entry that is now dead; confirm no azure.yaml hook or CI step still calls them.

Files:
* v2/scripts/prepackage_function.py - remove.
* v2/scripts/prepackage-function.sh, v2/scripts/prepackage-function.ps1 - remove.
* v2/.gitignore / v2/azure.yaml - remove dead `build-functions/` references (azure.yaml hook already removed in Step 2.2).

Discrepancy references:
* Deviates from DD-01 (keep-prepackage alternative) — self-contained Dockerfile chosen for a clean container end-state.

Success criteria:
* `grep` for `prepackage` and `build-functions` returns only historical (docs/worklog) hits, no live references.
* CI (`Dockerfile.ci-validate` flow) does not call the removed scripts.

Context references:
* v2-containerize-frontend-function-research.md — clarifying Q2 (self-contained Dockerfile end-state).
* User memory: clean up + reduce code debt as you go.

Dependencies:
* Step 2.5.

### Step 2.7: Validate Phase 2

Files:
* (validation only)

Validation commands:
* `docker build -f v2/docker/Dockerfile.functions ..` + import smoke (Step 2.1 criteria).
* `cd v2/infra; az bicep build --file main.bicep` + what-if.
* `cd v2; uv run pytest tests/functions -q` (or the repo's function test scope) — function tests green.

Success criteria:
* Image builds + imports resolve; bicep green; function tests green; poison-queue behavior unchanged (KEDA queue trigger preserved).

Dependencies:
* Steps 2.1-2.6.

## Implementation Phase 3: Remove the dedicated reasoning deployment (o4-mini)

<!-- parallelizable: false -->

Confirmed SAFE — `o4-mini` reasoning deployment is dead in the prod path; `gpt-5.1` carries the reasoning stream. Strategy: **Option (b) full removal**. Each step is test-first and one-unit.

### Step 3.1: Remove the `o4-mini` model deployment + reasoning params from `main.bicep`

Files:
* v2/infra/main.bicep - remove the `o4-mini` entry from the model deployments array (~551, ~571-584, reused-OpenAI children ~681-699), the `reasoningModel*` params (~160-175), and the `usageName` quota hint (~69) + any `~122`/`~654`/`~708` reasoning references.

Discrepancy references:
* Addresses confirmed decision #4 (drop dedicated reasoning; remove retiring o4-mini).

Success criteria:
* `az bicep build` succeeds; `what-if` shows the `o4-mini` deployment removed and no dangling param reference.

Context references:
* v2-reasoning-drop-gpt4-scrub-research.md — Part 1 step 3 (bicep edit sites).

Dependencies:
* Phase 2 complete.

### Step 3.2: Remove `AZURE_OPENAI_REASONING_DEPLOYMENT` from runtime env in `main.bicep`

Files:
* v2/infra/main.bicep - remove the `AZURE_OPENAI_REASONING_DEPLOYMENT` backend Container App env entry (~1881) and the function app setting if present; remove the `~2563`/`~2581-2582` reasoning output(s).

Success criteria:
* `grep` shows no `REASONING_DEPLOYMENT` in main.bicep; `what-if` clean.

Context references:
* v2-reasoning-drop-gpt4-scrub-research.md — Part 1 step 3.

Dependencies:
* Step 3.1.

### Step 3.3: Remove `reasoningModelName` from both parameter files

Files:
* v2/infra/main.parameters.json - remove `reasoningModelName` + version/sku/capacity (lines ~35-46).
* v2/infra/main.waf.parameters.json - same (byte-identical map).

Success criteria:
* Both param files parse; `az bicep build` with each param file resolves with no missing/extra param.

Context references:
* v2-reasoning-drop-gpt4-scrub-research.md — Part 1 step 3 (params lines 35-46).

Dependencies:
* Step 3.2.

### Step 3.4: Remove the `reasoning_deployment` field from `OpenAISettings`

Test-first: update `test_settings.py` to drop the reasoning field expectation, then remove the field.

Files:
* v2/src/backend/core/settings.py - remove the `reasoning_deployment` field + its env (`AZURE_OPENAI_REASONING_DEPLOYMENT`).
* v2/tests/**/test_settings.py - drop the reasoning-field assertion/fixture.

Success criteria:
* `uv run pytest -k settings` green; pyright --strict green on settings.py.

Context references:
* v2-reasoning-drop-gpt4-scrub-research.md — Part 1 step 2 (settings field), step 4 (fixture refs).

Dependencies:
* Step 3.3.

### Step 3.5: Retarget `reason()` to the chat deployment; remove dead routing + narrow `DeploymentAttr`

Test-first: update `test_foundry_iq.py:338` + `agents/test_base.py:318` to assert `gpt-5.1` (chat) instead of `o4-mini`/`reasoning_deployment`, then change the code. Narrowing/removing `DeploymentAttr` is structural (Hard Rule #10 — confirm).

Files:
* v2/src/backend/core/providers/llm/base.py - retarget `reason()` default deployment resolution to the chat deployment; remove the reasoning branch.
* v2/src/backend/core/providers/llm/foundry_iq.py - remove any `reasoning_deployment` read.
* v2/src/backend/core/**/definitions.py (agent definitions) - remove `deployment_attr="reasoning_deployment"`; narrow `DeploymentAttr` to `Literal["gpt_deployment"]` or remove the field (confirm depth).
* v2/tests/**/test_foundry_iq.py, v2/tests/**/agents/test_base.py - update the 2 routing assertions.

Discrepancy references:
* Deviates from DD-02 (Option (a) point-at-gpt-5.1) — full removal chosen per decision #4 + "reduce code debt."

Success criteria:
* `uv run pytest -k "foundry_iq or test_base" ` green; reasoning still streams from `gpt-5.1` (supports_reasoning() path intact); pyright --strict green.

Context references:
* v2-reasoning-drop-gpt4-scrub-research.md — Part 1 steps 1, 3, 4 (runtime consumers; `reason()` raise site; breaking tests).

Dependencies:
* Step 3.4.

### Step 3.6: Remove `reasoning_deployment` from admin config + frontend admin model + post_provision + live docs

Test-first: update `test_admin.py:245/391/400` to drop `reasoning_deployment` from `AdminConfig`, then remove it across admin surface + frontend model + post_provision + the live reference doc.

Files:
* v2/src/backend/**/admin (AdminConfig model + admin router) - remove `reasoning_deployment`.
* v2/src/frontend/src/models/admin.tsx (~line 77) - remove the reasoning field from the admin model/type.
* v2/scripts/post_provision.py - remove any reasoning-deployment reference.
* v2/docs/admin_runtime_config.md (~line 45) - remove the `reasoning_deployment` AdminConfig field-table row (LIVE reference doc, NOT a dated record — must be updated so the doc stays factual).
* v2/tests/**/test_admin.py - update assertions (245/391/400).
* v2/src/frontend/**/admin.test.tsx (~line 49), v2/src/frontend/**/AppNavigation.test.tsx (~line 35) - update FE vitest fixtures that carry the reasoning field (required for the "vitest admin tests green" criterion).

Discrepancy references:
* Addresses DR-13 (live `admin_runtime_config.md:45` row owned here); DR-16 (FE vitest fixtures enumerated so Step 3.6's success criterion is met).

Success criteria:
* `uv run pytest -k admin` green; `cd v2/src/frontend; npx vitest run` admin tests green; pyright --strict + tsc green.
* `grep -ri "reasoning_deployment" v2/docs` returns zero live hits (only dated `bugs.md`/`worklog/**` may mention it).

Context references:
* v2-reasoning-drop-gpt4-scrub-research.md — Part 1 step 3 (admin/frontend/post_provision + `admin_runtime_config.md:45` sites), step 4 (test_admin + FE fixtures).

Dependencies:
* Step 3.5.

### Step 3.7: Validate Phase 3

Validation commands:
* `cd v2; uv run pytest -q` (backend + functions).
* `cd v2/src/frontend; npx vitest run`.
* `cd v2/infra; az bicep build --file main.bicep` (both param files).
* `uv run pyright` (strict scope) + `uv run ruff check`.
* Local-hygiene sweep (DR-12): remove the stale `AZURE_OPENAI_REASONING_DEPLOYMENT=o4-mini` line + reasoning comments from `v2/.env` (gitignored — local-dev only, not a tracked-file/Hard Rule #18 concern, but keeps the "full removal" claim consistent).
* Optional debt sweep (DR-16, non-breaking): the ~8 harmless `AZURE_OPENAI_REASONING_DEPLOYMENT` env fixtures (`test_azure_openai.py:30`, the five `functions/**/test_blueprint.py`, `test_post_provision.py:219`, `test_foundry_iq.py:40`), stale `o4-mini` docstrings (`test_foundry_iq.py:567-665`), the `_make_settings` helper (`agents/test_base.py:194`), and `content_safety.py:24,159` `deployment_attr` comments — clean up if touched, do not block on.

Success criteria:
* All green; no `reasoning_deployment` / `o4-mini` symbol remains except historical `bugs.md`/`worklog/**` records.

Dependencies:
* Steps 3.1-3.6.

## Implementation Phase 4: Scrub all `gpt-4` references

<!-- parallelizable: false -->

58 first-party lines: src 2 (docstrings), scripts 2 (comments), tests 43 (19 routing-tied `[R]`), docs 11 (all historical `[H]`). Infra already clean. **PD-01 = B (user override 2026-07-01):** scrub `gpt-4` EVERYWHERE, INCLUDING dated `bugs.md` / `worklog/**` / `docs/plan/**` records — the user explicitly overrode the Hard Rule #16/#19 leave-historical default. Replace live references with `gpt-5.1`; for historical records, neutralize the literal `gpt-4` token while keeping each dated statement truthful (rephrase rather than falsify, e.g. "the model deployment" where a swap would misstate history).

### Step 4.1: Scrub production `src` + `scripts` literals

Files:
* v2/src/** (2 docstring examples) - replace `gpt-4*` literal with `gpt-5.1`.
* v2/scripts/** (2 comment literals) - replace/remove `gpt-4*` literal.

Success criteria:
* `grep -ri "gpt-4" v2/src v2/scripts` returns zero hits; pytest + pyright green.

Context references:
* v2-reasoning-drop-gpt4-scrub-research.md — Part 2 (categories A + E).

Dependencies:
* Phase 3 complete.

### Step 4.2: Scrub test-fixture literals (preserve routing-assertion intent)

Replace the 43 test `gpt-4*` fixture literals with `gpt-5.1`. For the 19 routing-tied `[R]` cases, preserve each assertion's meaning (a "cheaper model" case → `gpt-5.1-mini`; a chat-vs-reasoning routing case that Phase 3 already touched → align with the post-removal behavior). One test file per turn.

Files:
* v2/tests/** + v2/src/**/tests/** - replace `gpt-4*` literals; keep assertions meaningful.

Success criteria:
* `uv run pytest -q` green; no assertion silently weakened (the 19 `[R]` cases still assert real routing behavior).

Context references:
* v2-reasoning-drop-gpt4-scrub-research.md — Part 2 (category C, the 19 `[R]` flags).

Dependencies:
* Step 4.1.

### Step 4.3: Scrub live docs; leave dated historical records

Replace `gpt-4*` in live/reference docs; explicitly LEAVE `v2/docs/bugs.md` + `v2/docs/worklog/**` dated records unchanged. `v2/docs/development_plan.md` / `docs/plan/**` snapshots (INCLUDING `business-cases.md` `GPT-4 Vision`) are a USER DECISION per PD-01 — default: LEAVE (do not annotate or rewrite unless the user opts in). Do not self-contradict: if the user keeps the default, `docs/plan/**` is untouched.

Files:
* v2/docs/** (live/reference, non-historical, NOT under `docs/plan/**`) - replace `gpt-4*` with `gpt-5.1`.

Discrepancy references:
* Addresses DR-18 (removes the annotate-vs-leave contradiction; `docs/plan/**` incl. business-cases.md deferred to PD-01).

Success criteria:
* `grep -ri "gpt-4" v2/docs` returns only intentional hits (`bugs.md`, `worklog/**`, and `docs/plan/**` unless the user opted to scrub it).
* markdownlint green on edited docs.

Context references:
* v2-reasoning-drop-gpt4-scrub-research.md — Part 2 (category D, all `[H]`; `docs/plan/**` = "user decision required").

Dependencies:
* Step 4.2.

### Step 4.4: Validate Phase 4

Validation commands:
* `grep -ri "gpt-4" v2/src v2/scripts v2/infra v2/tests v2/docs` — zero hits anywhere (PD-01 = B, docs included).
* `cd v2; uv run pytest -q`.
* markdownlint on edited docs.

Success criteria:
* All green; ZERO `gpt-4` mentions remain anywhere under `v2/`.

Dependencies:
* Steps 4.1-4.3.

## Implementation Phase 5: Final Validation

<!-- parallelizable: false -->

### Step 5.1: Run full project validation

Execute the full v2 gate:
* `cd v2; uv sync`
* `cd v2; uv run pytest -q` (backend + functions + shared AST gates: no-process-narrative, init-marker-only, imports-at-top, no-silent-excepts, no-anonymous-dict-returns, no-type-checking)
* `cd v2/src/frontend; npm ci && npm run build && npx vitest run`
* `cd v2/infra; az bicep build --file main.bicep` then what-if with `main.parameters.json` AND `main.waf.parameters.json`
* `cd v2; uv run pyright` (strict scope: backend + functions/core) + `uv run ruff check`
* `docker build` all three images: `Dockerfile.backend`, `Dockerfile.frontend --target prod`, `Dockerfile.functions` (import smoke on the function image)
* markdownlint on all edited `.md`

### Step 5.2: Fix minor validation issues

Iterate on lint/type/build/test failures that are straightforward and isolated (one unit per turn).

### Step 5.3: Report blocking issues

Document any failure needing more than a minor fix (e.g. AVM module bump cascading into the backend, KEDA scale-rule mismatch, a routing test that cannot preserve intent) and recommend a follow-up research/planning turn rather than a large inline fix.

## Dependencies

* `azd` (repo-pinned `>= 1.18.0 != 1.23.9`), Azure CLI + bicep, Docker, `uv`, Node 20.
* Deployer identity holds Owner or User-Access-Administrator (fresh-tenant RBAC prerequisite).
* `gpt-5.1` + `text-embedding-3-large` GlobalStandard quota in the target region (`eastus2` default) — verify before `azd up`.

## Success Criteria

* All three services (backend, frontend, function) build as container images, push to the provisioned ACR (`cr<suffix>`), and roll fresh code on each `azd deploy`.
* Frontend + function run on the shared Container Apps Environment (`cae-<suffix>`) under the shared UAMI; no new RBAC required.
* No `o4-mini` / dedicated reasoning deployment remains; reasoning still streams from `gpt-5.1`.
* Zero live `gpt-4` references (only dated historical records remain).
* `azd up` provisions + deploys clean on a fresh cosmosdb-mode tenant, anonymous auth, ending green.
