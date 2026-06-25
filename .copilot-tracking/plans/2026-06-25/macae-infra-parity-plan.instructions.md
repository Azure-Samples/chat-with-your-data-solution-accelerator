---
applyTo: '.copilot-tracking/changes/2026-06-25/macae-infra-parity-changes.md'
---
<!-- markdownlint-disable-file -->
# Implementation Plan: MACAE infra parity — one-shot `azd up` for CWYD v2

## Overview

Make CWYD v2 deploy end-to-end with a single `azd up` (provision + build + deploy frontend/backend/function, no manual `az` follow-ups) by adopting MACAE's deployment patterns: frontend on App Service build-from-source, backend image referenced by name+tag, sample-data upload after deploy, and durable back-port of every live `az`-override fix.

## Objectives

### User Requirements

* `azd up` provisions infra AND builds+deploys all three code services in one shot — Source: user request 2026-06-25 ("when the user azd up the user can deploy the infrastructure and deploy the code from the frontend, backend and function").
* Operator selects cosmosdb (also deploy Azure AI Search) or postgresql (no Search) — Source: user request 2026-06-25. (Already correct in v2 — verification only.)
* A post-deploy step uploads the sample/data files automatically — Source: user request 2026-06-25 ("after deploy script to upload the files").
* Build the container from current source during `azd up`; bicep references the built image by container name + tag only, no resource "search"/lookup — Source: user request 2026-06-25.
* Frontend takes the MACAE approach (App Service, not a container) — Source: user follow-up 2026-06-25 ("take the same approach of macae").
* Close every place v2/infra needs a manual change — Source: user request 2026-06-25 ("see what is missing or what is wrong from a well known working version as macae").

### Derived Objectives

* Fix BUG-0081 (frontend `appservice` + `docker:` is unsupported by azd) — Derived from: the frontend deploy is the only outright-broken `azd up` step (research Scenario 1).
* Make the backend ACR pull work under managed identity on first provision (A10 ACR ARM-auth policy + A11 ACA `registries:` block) — Derived from: without these the backend revision falls back to anonymous/MCR pull and the named image never runs.
* Back-port A1–A8 env/RBAC/network fixes so no `az ... update` is needed after `azd up` — Derived from: the 8 live overrides revert on every reconcile (research Scenario 4).

## Context Summary

### Project Files

* v2/azure.yaml - service host topology + hooks; frontend `docker:` block to remove, `postdeploy` hook to add.
* v2/infra/main.bicep - single ~2475-line template; all A-item edits + frontend site + backend image land here.
* v2/infra/modules/ai-project-search-connection.bicep - the existing `CognitiveSearch` project connection; sibling to the new `cwyd-kb-mcp` connection (A4).
* v2/infra/main.parameters.json - azd env → bicep param mapping; gains the backend image params.
* v2/src/frontend/frontend_app.py - the App Service static server; needs wwwroot-relative dist + optional `/config` route.
* v2/src/frontend/src/api/*.tsx + App.tsx - 5 build-time `VITE_BACKEND_URL` read sites.
* v2/scripts/ - hook convention (`*-name.{sh,ps1}` → `uv run python name.py`); home of the new `package-frontend` + `upload_sample_data` scripts.
* v2/scripts/post_provision.py - seeds the Search index + Foundry IQ KB schema; runs before ingestion.
* data/ (repo root) - the curated grounding corpus (Northwind/Woodgrove/Contoso PDFs+DOCXs); there is no `v2/data/`.

### References

* .copilot-tracking/research/2026-06-25/macae-infra-parity-research.md - primary research: selected approach + 4 scenarios + A1–A12.
* .copilot-tracking/research/subagents/2026-06-25/v2-bicep-line-numbers-aitems.md - exact main.bicep line numbers for every A-item.
* .copilot-tracking/research/subagents/2026-06-25/v2-frontend-appservice-scope.md - frontend serving + SPA backend-URL wiring + script conventions.
* .copilot-tracking/research/subagents/2026-06-25/macae-container-build-pattern.md - MACAE App Service python-zip + image param-trio.
* .copilot-tracking/research/subagents/2026-06-24/manual-change-debt-deployment-iac.md - A1–A12 catalogue mapped to BUG ids.

### Standards References

* .github/copilot-instructions.md - Hard Rule #1 (one unit/turn), #4 (registry / no lookup), #10 (ask before structural changes), #18 (no env-specific content in tracked files — use placeholders), test-first.
* .github/instructions/v2-infra.instructions.md - Bicep + azd conventions, naming, RBAC, AVM modules.
* .github/instructions/v2-frontend.instructions.md - React/Vite conventions, `.tsx` everywhere, closed-set enums.

## Implementation Checklist

### [ ] Implementation Phase 1: Frontend → App Service build-from-source (BUG-0081)

<!-- parallelizable: false -->

* [x] Step 1.1: Make `frontend_app.py` serve from a wwwroot-relative dist (App Service compatible)
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 12-40)
* [x] Step 1.2: Add `services.frontend.hooks.prepackage` + remove the `docker:` block in azure.yaml
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 42-66)
* [x] Step 1.3: Add `v2/scripts/package-frontend.{sh,ps1}` build hook (npm ci && npm run build → dist/)
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 68-92)
* [x] Step 1.4: Repoint the frontend App Service `linuxFxVersion` to `python|3.11` + uvicorn appCommandLine in main.bicep
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 94-120)
* [x] Step 1.5 (runtime `/config`, ID-02): `/config` endpoint + SPA runtime-config seam (sub-steps 1.5a–1.5g)
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 122-150)
* [x] Step 1.6: Assemble the App Service deploy artifact (server + requirements.txt + static dist/) at `./build-output` via `package_frontend.py`; point `services.frontend.dist` at it
  * Added during implementation — closes the packaging gap (`dist`-only upload lacked the uvicorn server + deps).

### [ ] Implementation Phase 2: Backend image + ACR managed-identity pull

<!-- parallelizable: false -->

* [x] Step 2.1: A10 — enable ACR `policies.azureADAuthenticationAsArmPolicy.status = 'enabled'`
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 152-176)
  * Note: AVM 0.12.1 exposes a FLAT param `azureADAuthenticationAsArmPolicyStatus: 'enabled'` (not the nested `policies` object).
* [x] Step 2.2: A11 — add `registries:` block to the `backendContainerApp` AVM module
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 178-202)
* [x] Step 2.3: Backend image by name+tag, first-provision-safe (PD-02) — params + placeholder fallback + `docker.remoteBuild: true` + parameters.json mapping
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 204-238)

### [ ] Implementation Phase 3: Env-var + RBAC back-ports (A1, A7, A8, A4-roles)

<!-- parallelizable: false -->

* [x] Step 3.1: A1 env — add `AZURE_AI_SERVICES_ENDPOINT` to backend env + function appSettings
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 240-262)
* [x] Step 3.2: A1 RBAC — grant UAMI `Cognitive Services User` on the AI Services / Foundry account
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 264-284)
* [x] Step 3.3: A7 — set `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` to `id-${solutionSuffix}` on both runtimes
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 286-306)
* [x] Step 3.4: A8 — rename `ORCHESTRATOR` → `CWYD_ORCHESTRATOR_NAME`, value databaseType-conditional
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 308-332)
  * Verified: backend `OrchestratorSettings` (settings.py) reads env_prefix `CWYD_ORCHESTRATOR_` field `name` (WI-05 closed).
* [x] Step 3.5: A4 roles — grant the Foundry Project MI `Search Service Contributor` on the Search service
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 334-354)

### [x] Implementation Phase 4: KB MCP project connection (A4 connection)

<!-- parallelizable: false -->

* [x] Step 4.1: Declare the `cwyd-kb-mcp` RemoteTool project connection + resolve `AZURE_AI_SEARCH_CONNECTION_NAME` to it
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 356-388)
  * Unblocked by the WI-01 spike (.copilot-tracking/research/2026-06-25/wi-01-kb-mcp-connection-schema.md). New module `v2/infra/modules/ai-project-kb-mcp-connection.bicep` (`RemoteTool` + `ProjectManagedIdentity` + `audience` via `any(...)`); env re-pointed; `az bicep build` clean.

### [ ] Implementation Phase 5: Function host config (A2, A3)

<!-- parallelizable: false -->

* [x] Step 5.1: A2 — add `alwaysReady` to `functionAppConfig.scaleAndConcurrency`
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 390-412)
* [x] Step 5.2: A3 — wire queue `messageEncoding=none` (app setting or host.json)
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 414-436)
  * Landed in `v2/src/functions/host.json` (`extensions.queues.messageEncoding = "none"`); 26 tests pass.

### [ ] Implementation Phase 6: Storage firewall + Event Grid ordering (A6, A5)

<!-- parallelizable: false -->

* [x] Step 6.1: A6 — storage `networkAcls.defaultAction='Allow'` + `bypass='AzureServices'` for the no-private-net profile
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 438-460)
* [x] Step 6.2: A5 — restructure Event Grid so the queue-sender role precedes the subscription preflight
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 462-490)
  * Standalone `blobCreatedSubscription` resource (parent = `newEventGridTopic` `existing` ref) `dependsOn` `eventGridQueueSenderRole`; mirrors the reuse-path pattern.

### [ ] Implementation Phase 7: Post-deploy sample-data upload (Scenario 3)

<!-- parallelizable: false -->

* [x] Step 7.1: Choose + stage the curated sample-data set (PD-03)
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 492-512)
  * Allow-list over repo-root `data/` (no `v2/data/` folder, no committed binaries) — DD-08.
* [x] Step 7.2: Add `v2/scripts/upload_sample_data.py` (blob upload + enqueue, idempotent) + test
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 514-544)
  * Reuses the real `BatchPushQueueMessage` contract; trigger-aware (suppresses enqueue under `event_grid`); 14 tests.
* [x] Step 7.3: Wire the `postdeploy` hook + `upload-sample-data.{sh,ps1}` wrappers in azure.yaml
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 546-566)

### [ ] Implementation Phase 8: Validation

<!-- parallelizable: false -->

* [x] Step 8.1: `az bicep build` clean + `azd provision --preview` (what-if) on both databaseType values
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 568-586)
  * `az bicep build` clean (exit 0). `azd provision --preview` DEFERRED to the operator (cloud op).
* [x] Step 8.2: Run the v2 pytest + vitest suites covering the changed scripts/code
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 588-602)
  * 2651 pytest passed (1 skipped); 607 vitest passed (46 files).
* [ ] Step 8.3: End-to-end `azd up` smoke (cosmosdb + postgresql) — zero manual `az` follow-ups
  * Details: .copilot-tracking/details/2026-06-25/macae-infra-parity-details.md (Lines 604-624)
  * DEFERRED to the operator (deploy op; closes BUG-0052/53/54/55/56/58/59/61/62/63/64/69/77/81 on cloud verify).

## Planning Log

See `.copilot-tracking/plans/logs/2026-06-25/macae-infra-parity-log.md` for discrepancy tracking, implementation paths considered, and suggested follow-on work.

## Dependencies

* azd `>= 1.18.0 != 1.23.9`, Bicep CLI, `az` CLI.
* `uv` (Python env) + `npm`/Node 20 for the frontend build.
* AVM modules already pinned in main.bicep: `container-registry/registry:0.12.1`, `app/container-app:0.22.1`, `web/site:0.22.0`, `cognitive-services/account:0.13.0`, `search/search-service:0.12.0`, `event-grid/system-topic:0.6.4`, `storage/storage-account:0.32.0`.
* Backend settings class confirmation that the orchestrator env field reads `CWYD_ORCHESTRATOR_NAME` (Step 3.4 verifies before editing).

## Success Criteria

* `azd up` from a clean checkout provisions + deploys all three services with no manual `az` follow-up, for `databaseType=cosmosdb` and `databaseType=postgresql` — Traces to: user requirement (one-shot azd up).
* Frontend App Service serves the built SPA and reaches the backend; no `docker:` block on `appservice` — Traces to: BUG-0081 + "same approach as macae".
* `cosmosdb` deploys Azure AI Search + KB; `postgresql` deploys neither — Traces to: user requirement (db-conditional Search). Verification only.
* The deployed index/KB contains the curated sample docs after `azd up` — Traces to: user requirement (after-deploy upload).
* Backend Container App runs the ACR image (not MCR placeholder) via managed-identity pull — Traces to: A10/A11 + image contract.
* `az bicep build` is clean; the v2 test suites pass — Traces to: every-phase-ends-green.
