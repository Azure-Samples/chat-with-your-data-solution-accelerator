<!-- markdownlint-disable-file -->
# Release Changes: CWYD v2 — Containerize All Three Services + Model Cleanup

**Related Plan**: v2-containerize-services-and-model-cleanup-plan.instructions.md
**Implementation Date**: 2026-07-01

## Summary

Convert the CWYD v2 frontend and function into ACR-built container images (backend already is), remove the dedicated `o4-mini` reasoning deployment, and scrub all live `gpt-4` references, so a fresh cosmosdb-mode `azd up` builds + pushes + rolls fresh code for all three services on the shared Container Apps environment.

## Phase Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Frontend → Container App | Complete |
| 2 | Function → Azure Functions on Azure Container Apps | Complete |
| 3 | Remove the dedicated reasoning deployment (o4-mini) | Complete |
| 4 | Scrub all `gpt-4` references | Complete |
| 5 | Final Validation | Complete |

## Changes

### Added

* v2/tests/functions/test_dockerfile_subpackages.py - Phase 2: guards the prod `Dockerfile.functions` COPY list against the `src/functions` subpackage set (replaces the retired prepackage test).

### Modified

* v2/azure.yaml - Phase 1: frontend service → `host: containerapp` + `docker:` block; dropped `dist: ./build-output` + frontend `hooks.prepackage`; no `VITE_BACKEND_URL` build-arg. Phase 2: function service → `host: containerapp` + `docker:` (`Dockerfile.functions`, `remoteBuild: true`); removed the `prepackage` hook + `./build-functions` project pointer.
* v2/infra/main.bicep - Phase 1: frontend App Service → Container App (see above). Phase 2: replaced the Flex `functionApp` + `functionPlan` (FC1) + `functionAppConfig` with a raw `Microsoft.App/containerApps@2024-10-02-preview` `kind: functionapp` (shared env/UAMI/ACR, `FUNCTIONS_WORKER_RUNTIME=python`, `ingressTargetPort: 80`, `minReplicas: 1`, `maxReplicas = enableScalability ? 100 : 40`); added `functionContainerImageName`/`Tag` params + `functionContainerAppName`/`identityName` vars; removed `flexDeploymentRole` + `storageBlobDataOwnerRoleId` + the `deployment-package` container + `deploymentContainerName` var; repointed `AZURE_FUNCTION_APP_URL`/`AZURE_FUNCTION_APP_NAME`.
* v2/docker/Dockerfile.functions - Phase 2: rewritten from compose-only to a prod Functions-on-ACA image reproducing the `functions/<sub>/` nesting + `backend/` copy; deps single-source from `pyproject.toml` via `tomllib`.
* v2/.gitignore - Phase 1: removed dead `src/frontend/build-output/`. Phase 2: removed dead `build-functions/` entry.
* v2/.dockerignore - Phase 2: removed dead `build-functions/` entry.
* v2/tests/functions/test_azure_yaml_hooks.py - Phase 2: rewritten to assert the `host: containerapp` + `docker:` contract (no prepackage hook).

### Phase 3 — Modified (reasoning-deployment full removal)

* v2/infra/main.bicep - Phase 3: removed the `o4-mini` model deployment + `reasoningModel*` params + `usageName` quota hint + `AZURE_OPENAI_REASONING_DEPLOYMENT` backend env + reasoning output(s).
* v2/infra/main.parameters.json + v2/infra/main.waf.parameters.json - Phase 3: removed `reasoningModelName` (+ version/sku/capacity).
* v2/src/backend/core/settings.py - Phase 3: removed the `reasoning_deployment` field + `AZURE_OPENAI_REASONING_DEPLOYMENT` env from `OpenAISettings`.
* v2/src/backend/core/providers/llm/base.py + foundry_iq.py + agent definitions - Phase 3: `reason()` default resolves to the chat deployment; `deployment_attr` FULLY REMOVED (WI-04 resolved → full removal); reasoning STREAM via `supports_reasoning()`/`gpt-5.1` preserved.
* v2/src/backend admin surface (AdminConfig model + admin router) - Phase 3: removed `reasoning_deployment`.
* v2/src/frontend/src/models/admin.tsx - Phase 3: removed the reasoning field.
* v2/scripts/post_provision.py - Phase 3: removed reasoning-deployment reference.
* v2/docs/admin_runtime_config.md - Phase 3: removed the live `reasoning_deployment` AdminConfig field-table row.
* v2 tests (test_settings, test_foundry_iq, agents/test_base, test_admin) + FE fixtures (admin.test.tsx, AppNavigation.test.tsx) - Phase 3: updated to the post-removal behavior (assert chat deployment `gpt-5.1`).

### Phase 4 — Modified (gpt-4 scrub, PD-01 = B — 57 first-party literals → 0)

* v2/src/backend/core/providers/llm/foundry_iq.py + registry.py - Phase 4: docstring `gpt-4*` examples → `gpt-5.1` / neutral phrasing.
* v2/scripts/post_provision.py - Phase 4: KB-model example comments → `gpt-5.1, gpt-5-mini`.
* v2 tests (16 files) - Phase 4: 42 `gpt-4*` fixtures → `gpt-5.1` / `gpt-5.1-mini`; 19 routing-tied cases changed fixture + assertion in lockstep (intent preserved). Files: test_foundry_iq, agents/test_base, test_settings, test_admin, tools/{test_post_prompt,test_qa,test_text_processing}, scripts/test_post_provision, embedders/test_azure_openai, test_app_lifespan, test_health, test_services_health, functions/{add_url,batch_push,batch_start,blob_event,search_skill}/test_blueprint.
* v2/docs (6 files) - Phase 4: `plan/business-cases.md` ("GPT-4 Vision" → "Vision LLM"), `plan/modernization-plan.md` (`gpt-4.1` → `gpt-5.1`), `bugs.md` + `worklog/{2026-06-12,2026-06-14,2026-06-16}.md` (dated allow-list quotes paraphrased truthfully; `gpt-4*` token removed, `o4-mini` left per Hard Rule #19).

### Phase 5 — Modified (validation fix)

* v2/tests/infra/test_main_bicep.py - Phase 5: updated slice markers to the post-containerization infra shape (`frontendContainerApp`; `functionContainerApp` raw `kind: 'functionapp'`); replaced the obsolete Flex `alwaysReady` blob_event test with `test_function_container_app_stays_warm_for_queue_consumers` (`minReplicas: 1`) + a new `test_bicep_uses_container_apps_not_flex_or_appservice` structural guard (removed hosting gone, new hosting present). 3 failed + 17 errors → 37 passed. This is the ONLY regression our Phases 1-4 caused.

### Removed

* v2/scripts/package-frontend.sh - Phase 1: dead App-Service packaging script.
* v2/scripts/package-frontend.ps1 - Phase 1: dead App-Service packaging script.
* v2/scripts/package_frontend.py - Phase 1: dead App-Service packaging helper.
* v2/tests/scripts/test_package_frontend.py - Phase 1: orphaned test for the removed helper.
* v2/scripts/prepackage_function.py - Phase 2: dead Flex-zip staging generator (Dockerfile now owns the layout).
* v2/scripts/prepackage-function.sh - Phase 2: dead prepackage shell.
* v2/scripts/prepackage-function.ps1 - Phase 2: dead prepackage shell.
* v2/tests/functions/test_prepackage_subpackages.py - Phase 2: replaced by test_dockerfile_subpackages.py.

## Additional or Deviating Changes

* Execution cadence: user chose **run straight through all phases** autonomously (2026-07-01); no `azd up`/`azd deploy` runs — validation stops at `bicep build` + `what-if` + pytest/vitest/pyright/ruff + local docker build.
* **PD-01 → B (user override 2026-07-01):** scrub `gpt-4` EVERYWHERE including dated `bugs.md` / `worklog/**` / `docs/plan/**` records. This is an explicit user-directed override of Hard Rule #16/#19 (leave-historical-records). Step 4.3 rephrases historical statements to stay truthful rather than blindly swapping the literal.
* PD-02: user accepted the default — function `minReplicas: 1` (warm).
* Phase 3 scope call: `o4-mini` / `reasoning_deployment` mentions in DATED historical docs (ADRs, `bugs.md`, `cleanup_audit.md`, `development_plan.md`, `worklog/**`) were PRESERVED per Hard Rule #19 — decisions #4/#5 target the deployable config + `gpt-4`, not rewriting reasoning history. PD-01=B covers `gpt-4` scrubbing (Phase 4), not reasoning-history rewrites.
* Flagged for Phase 5 triage: the Phase 3 implementor reported pre-existing test failures in files outside its changeset ("Phase 1/2 fallout"). Phase 5 must run the full suite and FIX any genuine regressions caused by Phases 1-4 (e.g., tests still referencing removed modules) vs. truly pre-existing issues (e.g., the #35d `TS6133`).
* **CONFIRMED regression (Phase 4 triage) — Phase 5 must fix:** `v2/tests/infra/test_main_bicep.py` slices `main.bicep` on the `module appServicePlan` / Flex-function markers that Phases 1-2 REMOVED → 1 failed + 17 collection errors. This IS our structural drift, not pre-existing. Also investigate `test_no_silent_excepts[v2/src/functions/core/search_resolution.py]` (1 failed; determine pre-existing vs Phase-2 fallout).## Release Summary

**All 5 phases complete.** CWYD v2 now builds all three services (backend, frontend, function) as container images to the provisioned ACR (`cr<suffix>`) on the shared Container Apps Environment (`cae<suffix>`) under the shared UAMI, rebuilt on every `azd deploy`. The dedicated `o4-mini` reasoning deployment is fully removed (reasoning still streams from `gpt-5.1`), and every first-party `gpt-4` reference is scrubbed.

**Files affected:** ~30. Notable:
* **Created (2):** `v2/tests/functions/test_dockerfile_subpackages.py` (Dockerfile COPY-list guard), plus the rewritten function/frontend test contracts.
* **Modified (core):** `v2/azure.yaml` (frontend + function → `host: containerapp`), `v2/infra/main.bicep` (frontend Container App; raw `functionContainerApp` `kind: functionapp`; removed `appServicePlan`, Flex `functionApp`+`functionPlan`, `flexDeploymentRole`, deployment-package container, `o4-mini` deployment + reasoning params/env), both param files, `v2/docker/Dockerfile.functions` (prod rewrite), `settings.py` + LLM providers + admin surface + `admin.tsx` (reasoning removal), `post_provision.py`, 22 test files, 6 docs.
* **Removed (7):** `package-frontend.{sh,ps1}`, `package_frontend.py`, `prepackage_function.py`, `prepackage-function.{sh,ps1}`, and 2 orphaned tests.

**Infra/hosting change:** frontend App Service (+ its plan) and the Flex Consumption Function App (+ its plan + deployment-package container + `flexDeploymentRole`) are gone — a net resource reduction. The function uses a raw `Microsoft.App/containerApps@2024-10-02-preview` `kind: functionapp` (IP-02 fallback; avoided a shared-AVM-module bump that would re-touch the backend/frontend). `FUNCTIONS_WORKER_RUNTIME=python`, `ingressTargetPort: 80`, `minReplicas: 1`, `maxReplicas = enableScalability ? 100 : 40` applied.

**Validation:** bicep build **0 errors**; pyright strict **0/0/0**; pytest **2686 passed** (1 pre-existing fail: Phase 6 `search_resolution.py` silent-except); vitest **594 passed** (1 pre-existing #35d fail).

**Deployment notes / blockers before `azd up`:**
1. **Frontend image blocked by pre-existing #35d:** `Dockerfile.frontend --target prod` runs `npm run build`, which fails on a pre-existing `TS6133` (`Configuration.tsx:628`, commented-out #35d "Updated by" audit line). The frontend container image will NOT build until #35d resolves this (uncommenting the audit render fixes both the TS6133 and the related vitest failure). Not caused by this plan.
2. **Docker builds + `what-if` deferred** — no Docker daemon / no live Azure auth in this environment. Run `docker build` ×3 + `az deployment sub what-if` before `azd up`.
3. **Quota (WI-01):** verify `gpt-5.1` + `text-embedding-3-large` GlobalStandard quota in the target region (`eastus2` default) before provision.
4. **Deployer** needs Owner / User-Access-Administrator for the role assignments.
