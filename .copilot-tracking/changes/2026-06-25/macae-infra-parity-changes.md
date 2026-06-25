<!-- markdownlint-disable-file -->
# Release Changes: MACAE infra parity — one-shot `azd up` for CWYD v2

**Related Plan**: macae-infra-parity-plan.instructions.md
**Implementation Date**: 2026-06-25

## Summary

Make CWYD v2 deploy end-to-end with a single `azd up` by adopting MACAE's patterns: frontend on App Service build-from-source, backend image by name+tag, post-deploy sample-data upload, and durable back-port of the A1–A11 manual-change debt. Implemented unit-by-unit (test-first) per the CWYD one-unit-per-turn contract.

## Changes

### Added

* v2/scripts/package-frontend.sh / .ps1 - Step 1.3: prepackage wrappers (npm ci && npm run build, then stage the deploy artifact); no VITE_BACKEND_URL bake (runtime /config).
* v2/scripts/package_frontend.py - Step 1.6: assembles the App Service deploy artifact (server + requirements.txt + static dist/) at src/frontend/build-output.
* v2/tests/scripts/test_package_frontend.py - Step 1.3/1.6: wrapper textual contract + build_artifact assembly tests.
* v2/src/frontend/src/api/runtimeConfig.tsx - Step 1.5b: shared runtime-config seam that fetches /config once at boot (Phase Implementor) + its vitest test.
* v2/infra/modules/ai-project-kb-mcp-connection.bicep - Phase 4 (A4): new Foundry Project `RemoteTool` connection `cwyd-kb-mcp` (`ProjectManagedIdentity` + `useWorkspaceManagedIdentity` + `audience: https://search.azure.com`, `properties` wrapped in `any(...)`), cosmosdb-gated. The KB MCP path's auth connection (the CognitiveSearch one 401s — BUG-0025/0059).
* v2/scripts/upload_sample_data.py - Phase 7: post-deploy sample-data uploader. Seeds by **assistant scenario** (keyed on the existing `AssistantType` enum): `default`/`employee assistant` → benefits/HR docs, `contract assistant` → `data/contract_data/*`, plus an **All** scope (35 docs). MACAE-style interactive menu picks the scope (with `--set` / `AZURE_ENV_SAMPLE_DATA` override for unattended; non-interactive + no override → skip). Reads from repo-root `data/` (no committed binaries); idempotent; trigger-aware; raw-JSON enqueue reusing `BatchPushQueueMessage`.
* v2/scripts/upload-sample-data.sh / .ps1 - Phase 7: postdeploy wrappers (→ `uv run python upload_sample_data.py "$@"`).
* v2/tests/scripts/test_upload_sample_data.py - Phase 7: tests for the manifest, scope selection (cli/env/menu/skip), menu, idempotency, dry-run, and event-grid suppression.
* v2/azure.yaml - Phase 7: project-level `hooks.postdeploy` (interactive) runs the scenario-menu uploader after services deploy.
* v2/infra/main.bicep - Phase 4 (A4): instantiate `aiProjectKbMcpConnection` (cosmosdb-gated) next to `aiProjectSearchConnection`; re-point backend `AZURE_AI_SEARCH_CONNECTION_NAME` from the CognitiveSearch connection to the new `cwyd-kb-mcp` connection. `az bicep build` clean.

### Modified

* v2/src/frontend/frontend_app.py - Step 1.1: `_DIST_DIR` default now resolves relative to the module file (`Path(__file__).parent / "dist"`) so it works on App Service (wwwroot) and in the Docker prod stage (`/usr/src/app/dist`) unchanged. Step 1.5a: added a `GET /config` route (before the catch-all) returning the `BACKEND_API_URL` env value.
* v2/tests/frontend_app/test_frontend_app.py - Step 1.1/1.5a: module-relative-default test + /config route test.
* v2/azure.yaml - Step 1.2/1.6: frontend service now `host: appservice` + `dist: ./build-output` + service-scoped `prepackage` hook (no `docker:` block); fixes BUG-0081.
* v2/infra/main.bicep - Step 1.4: frontend App Service `linuxFxVersion` → `PYTHON|3.11` + uvicorn `appCommandLine`; appSettings swap `VITE_BACKEND_URL` → `BACKEND_API_URL` (runtime /config). (Phase Implementor; `az bicep build` clean.)
* v2/src/frontend/src/App.tsx + src/api/{admin,conversationHistory,streamChat,speech}.tsx - Step 1.5c–1.5g: converged the 5 build-time `VITE_BACKEND_URL` reads onto the runtime-config seam (Phase Implementor) + tests.
* v2/.gitignore - Step 1.6: ignore `src/frontend/build-output/` (the assembled deploy artifact).
* v2/infra/main.bicep - Phase 2: A10 `azureADAuthenticationAsArmPolicyStatus: 'enabled'` on the ACR module; A11 `registries:` block on `backendContainerApp` (UAMI pull); backend image params (`backendContainerRegistryHostname`/`ImageName`/`ImageTag`) + first-provision-safe conditional image (`empty(hostname) ? MCR placeholder : '${hostname}/${name}:${tag}'`, DD-03). `az bicep build` clean.
* v2/azure.yaml - Phase 2 (Step 2.3a): `docker.remoteBuild: true` on `services.backend`.
* v2/infra/main.parameters.json - Phase 2 (Step 2.3c): `backendContainerRegistryHostname` = `${AZURE_CONTAINER_REGISTRY_ENDPOINT=}`, `backendContainerImageTag` = `${AZURE_ENV_IMAGE_TAG=latest}`.
* v2/infra/main.bicep - Phase 3: A1 `AZURE_AI_SERVICES_ENDPOINT` env on backend + function; A1 UAMI `Cognitive Services User` role on the AI Services account; A7 `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` runtime value → `id-${solutionSuffix}` (backend + function); A8 `ORCHESTRATOR` → `CWYD_ORCHESTRATOR_NAME` with `databaseType == 'postgresql' ? 'langgraph' : 'agent_framework'`; A4 Project MI `Search Service Contributor` on the Search service. `az bicep build` clean.
* v2/infra/main.bicep - Phase 5 (A2): `alwaysReady: [{ name: 'function:batch_push', instanceCount: 1 }]` on `functionAppConfig.scaleAndConcurrency`. `az bicep build` clean.
* v2/src/functions/host.json - Phase 5 (A3): `extensions.queues.messageEncoding = "none"` (raw-JSON producer/consumer match; durable BUG-0056 back-port).
* v2/infra/main.bicep - Phase 6: A6 storage `networkAcls: { defaultAction: enablePrivateNetworking ? 'Deny' : 'Allow', bypass: 'AzureServices' }` (BUG-0062); A5 lifted the `blob-created-to-doc-processing` subscription out of the `event-grid/system-topic` AVM module into a standalone `blobCreatedSubscription` resource (parent = `newEventGridTopic` `existing` ref) that `dependsOn` `eventGridQueueSenderRole` (BUG-0061 role-ordering fix). `az bicep build` clean.
* v2/azure.yaml - Phase 7: project-level `hooks.postdeploy` (sh + pwsh) running the sample-data uploader after services deploy (`continueOnError: true` so a seed hiccup does not fail the deploy).

### Removed

* (none yet)

## Additional or Deviating Changes

* Phase 4 (KB MCP project connection) is DEFERRED — blocked on WI-01 (the `cwyd-kb-mcp` RemoteTool connection schema is unconfirmed; planning log DR-01).
* Phases 2–6 (and Step 1.4) edit `v2/infra/main.bicep`; the operator previously paused bicep edits (planning log PD-05). Confirmation requested before the infra back-port proceeds — see the turn's Implementation Decisions.
* Execution is unit-by-unit (one method/class + its test per turn) per CWYD Hard Rule #1, rather than whole-phase batches.
* Step 1.6 (deploy-artifact assembly) was ADDED during implementation: `dist: ./dist` would upload only the built SPA, but the App Service start command `uvicorn frontend_app:app` needs the server + requirements.txt at the deploy root. Resolved by staging a self-contained artifact at `src/frontend/build-output` (server + requirements.txt + static dist/) and pointing `services.frontend.dist` at it — the MACAE-aligned pattern. `project` stays `./src/frontend` (a real dir) so the azd schema linter is satisfied.
* ID-02 (PD-01) = runtime `/config` (MACAE-exact): the frontend build does NOT bake `VITE_BACKEND_URL`; the SPA fetches the backend URL once at boot from `/config` fed by the `BACKEND_API_URL` app setting. Reverses the planning-log DD-01 default.
* AUTO-COMMIT (rule deviation): a Phase Implementor subagent committed Phases 1-3 as local commit `2428a0b0` ("v2: App Service frontend + infra parity changes") against the no-auto-commit rule. It is LOCAL ONLY (origin still at `257103b9`). Operator chose to LEAVE it as-is (2026-06-25). Phases 5/6/7 + `main.json` remain uncommitted in the working tree.
* `v2/infra/main.json` (compiled ARM) was regenerated by the Phase 8 `az bicep build`; operator chose to KEEP it (reflects the final bicep).
* A10 schema correction: the AVM `container-registry/registry:0.12.1` module exposes a FLAT scalar param `azureADAuthenticationAsArmPolicyStatus: 'enabled'`, not the nested `policies: { azureADAuthenticationAsArmPolicy: { status } }` the plan/research assumed (BCP037 on the nested shape). Applied the verified flat param.

## Release Summary

All 7 implementation phases landed (Phase 8 cloud smoke deferred to the operator). The change makes `azd up` deploy CWYD v2 end-to-end with no manual `az` follow-ups:

* **Phase 1 — Frontend → App Service build-from-source** (fixes BUG-0081). `azure.yaml` drops the unsupported `docker:` block; `package-frontend.{sh,ps1}` + `package_frontend.py` assemble a self-contained deploy artifact (server + `requirements.txt` + static `dist/`) at `src/frontend/build-output`; `main.bicep` frontend → `PYTHON|3.11` + uvicorn `appCommandLine`; runtime `/config` seam replaces the 5 build-time `VITE_BACKEND_URL` reads.
* **Phase 2 — Backend image + ACR MI pull.** A10 ACR AAD-as-ARM policy, A11 ACA `registries:` block, first-provision-safe name+tag image params + `docker.remoteBuild: true`.
* **Phase 3 — env + RBAC.** A1 `AZURE_AI_SERVICES_ENDPOINT` + `Cognitive Services User`; A7 postgres principal = UAMI; A8 `CWYD_ORCHESTRATOR_NAME` (db-conditional); A4 Project-MI `Search Service Contributor`.
* **Phase 4 — KB MCP connection** (A4). New `ai-project-kb-mcp-connection.bicep` `RemoteTool` connection `cwyd-kb-mcp` (`ProjectManagedIdentity` + `audience`, `any(...)`-wrapped); backend `AZURE_AI_SEARCH_CONNECTION_NAME` re-pointed to it (closes BUG-0025/0059's pending back-port). Unblocked by the WI-01 spike.
* **Phase 5 — function host.** A2 `alwaysReady` for `batch_push`; A3 `messageEncoding=none` in `host.json`.
* **Phase 6 — storage + Event Grid.** A6 storage `networkAcls` (Allow when no private net); A5 standalone blob-created subscription `dependsOn` the queue-sender role.
* **Phase 7 — post-deploy seed.** `upload_sample_data.py` + interactive `postdeploy` hook: per-assistant-scenario (default / contract / employee) + All, keyed on the `AssistantType` enum (MACAE content-pack parity); `--set`/`AZURE_ENV_SAMPLE_DATA` override.

**Files:** ~10 added / ~17 modified across `v2/azure.yaml`, `v2/infra/main.bicep` (+`main.json`) + `modules/ai-project-kb-mcp-connection.bicep`, `v2/infra/main.parameters.json`, `v2/.gitignore`, `v2/src/functions/host.json`, `v2/src/frontend/**`, `v2/scripts/**`, `v2/tests/**`.

**Validation:** `az bicep build` clean; 2651 pytest passed (1 skipped); 607 vitest passed (46 files); convention gates pass.

**Deferred / operator follow-up:** Phase 8.3 `azd up` smoke on both database types (closes the BUG cloud-verifications); WI-02 (confirm live A3/A5/A6 override commands); WI-06 (`queue_writer.py` docstring); flip the BUG rows + worklog post-deploy (Hard Rule #19).
