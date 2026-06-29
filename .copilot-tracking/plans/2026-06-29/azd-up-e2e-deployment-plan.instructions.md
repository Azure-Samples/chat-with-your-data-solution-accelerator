---
applyTo: '.copilot-tracking/changes/2026-06-29/azd-up-e2e-deployment-changes.md'
---
<!-- markdownlint-disable-file -->
# Implementation Plan: MACAE-parity end-to-end `azd up`

## Overview

Make a default `azd up` plus the post-deploy seed yield a fully usable CWYD v2 — frontend loads with no auth wall, chat works, admin/upload works, and the functions ingest the seeded documents — by closing four MACAE-parity gaps across Bicep, backend settings/dependencies, and the seed script, validated live on Azure.

## Objectives

### User Requirements

* `azd up` provisions all infra + config and builds/deploys frontend, backend, and functions into an immediately-usable site. — Source: conversation ("we should deploy all the infrastructure and the configuration, ... we should be able to go to the frontend and start to use the system").
* Find and fix the root cause of frontend↔backend non-communication and the broken end-to-end flow. — Source: conversation ("we need to find the root cause fix it").
* Mirror MACAE's DEFAULT `azd up` configuration (public profile). — Source: conversation ("we should do the same that MACAE does when azd up, default configuration").
* Admin/ingest surface OPEN by default (MACAE-faithful). — Source: conversation (selected "Open by default (MACAE-faithful, fastest path to a usable deploy)").
* Validate against a real cloud deployment only. — Source: conversation ("we deploy our new cwyd v2 code to the cloud and we test. Any other approach it is not valid").

### Derived Objectives

* Clear the stale Easy Auth on the frontend App Service via declarative Bicep. — Derived from: research C1/BUG-0090 (the error page is an Easy Auth misconfig `azd up` never reconciles).
* Inject a deterministic, cycle-free `BACKEND_CORS_ORIGINS` and relax the admin fail-closed gate behind a default-off flag. — Derived from: research C3 (only `BACKEND_CORS_ORIGINS` is functionally missing; admin gate is the certain `/api/admin/*` blocker).
* Make the seed run unattended and verify the index is populated. — Derived from: research C2 RC-1 (seed silently skipped, no TTY) + RC-async (async index can be silently empty).
* Preserve all binding repo conventions (one-unit-per-turn + test-first, no inverted `Environment.LOCAL` default, no banned tech / no Key Vault, no env-specific content, no process narrative). — Derived from: .github/copilot-instructions.md Hard Rules.

## Context Summary

### Project Files

* v2/infra/main.bicep - Central fix target: backend Container App env array (~L1808-1916), `AZURE_ENVIRONMENT` pin + comment (~L1814-1825), backend ingress (~L1770-1779), `frontendWebApp` AVM site module (~L1962-2025) + its `appSettings` (~L2005-2021).
* v2/src/backend/core/settings.py - `AppSettings` (L506-548), `NetworkSettings.cors_origins` (L291-352), `SearchSettings` (L245-268), `Environment` enum + default (L41-52, 533) — do NOT change the default.
* v2/src/backend/dependencies.py - `requires_role._checker` admin fail-closed gate (L437-485), `REQUIRE_ADMIN_USER` / `AdminUserIdDep` (L494-496).
* v2/src/backend/app.py - CORS middleware wiring (L241-263).
* v2/scripts/upload_sample_data.py - `resolve_selection` seed-scope resolution (L185-210), token map + menu (L81-99).
* v2/scripts/post_provision.py - postprovision substrate (pgvector / Search index / Foundry-IQ KB); reused-resource self-heal target (conditional).
* v2/azure.yaml - service + hook wiring; `postdeploy` seed hook (`continueOnError: true`, ~L217-228).

### References

* .copilot-tracking/research/2026-06-28/azd-up-e2e-deployment-research.md - Primary research: C1/C2/C3 failure map, MACAE parity table, selected approach, considered alternatives.
* .copilot-tracking/research/subagents/2026-06-28/cwyd-v2-frontend-deploy.md - C1 (BUG-0090) Easy Auth misconfig.
* .copilot-tracking/research/subagents/2026-06-28/cwyd-v2-functions-ingestion.md - C2 seed-skip + reused-resource drift.
* .copilot-tracking/research/subagents/2026-06-28/cwyd-v2-azd-flow-seeding.md - azd-up lifecycle + hooks.
* .copilot-tracking/research/subagents/2026-06-28/cwyd-v2-backend-env-diff.md - C3 reads-vs-sets env diff.

### Standards References

* .github/copilot-instructions.md - Hard Rules #1/#2 (one-unit + test-first), #3 (pillar header), #7 (no banned tech / no Key Vault), #10 (ask before structure), #11 (StrEnum / no `__future__`/`TYPE_CHECKING`), #16 (no process narrative), #18 (no env-specific content), #19 (worklog + bugs.md).
* .github/instructions/v2-infra.instructions.md - Bicep + azd conventions (module wiring, RBAC, outputs, naming).
* .github/instructions/v2-backend.instructions.md - FastAPI/router/DI conventions.
* .github/instructions/v2-backend-core.instructions.md - settings + registry conventions.
* .github/instructions/v2-functions.instructions.md - ingestion pipeline conventions.
* .github/instructions/v2-tests.instructions.md - test-first contract.
* User memory config-defaults-dev-first - do NOT invert `Environment.LOCAL`; flip via IaC env var.
* User memory azure-env-ids-never-commit / cleanup-before-next-step - placeholders only; clean test artifacts.

## Implementation Checklist

### [x] Implementation Phase 1: C3 backend env — CORS origin + defensive index pin (Bicep)

<!-- parallelizable: false -->

* [x] Step 1.1: Add `BACKEND_CORS_ORIGINS` deterministic literal to backend env
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 29-53)
* [x] Step 1.2: Pin `AZURE_AI_SEARCH_INDEX='cwyd-index'` defensively
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 54-76)
* [~] Step 1.3: (OPTIONAL) Add the cosmetic admin-display env cluster — SKIPPED (deferred)
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 77-96)
* [x] Step 1.4: Validate phase changes (`az bicep build`)
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 97-102)

### [x] Implementation Phase 2: C3/A1 backend admin open-by-default flag (settings + dependencies)

<!-- parallelizable: false -->

* [x] Step 2.1: Add `require_admin_auth: bool = False` to `AppSettings` + test
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 109-133)
* [x] Step 2.2: Gate the admin fail-closed branch on the flag in `requires_role._checker` + test
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 134-161)
* [x] Step 2.3: Wire `AZURE_REQUIRE_ADMIN_AUTH='false'` in backend Bicep env + reconcile the comment
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 162-181)

### [x] Implementation Phase 3: C1 frontend auth disabled + build hardening (Bicep)

<!-- parallelizable: false -->

* [x] Step 3.1: Declare frontend Easy Auth DISABLED on the App Service (PD-01 = declarative)
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 189-213)
* [x] Step 3.2: Add `WEBSITES_PORT=8000` + `ENABLE_ORYX_BUILD=True` frontend app settings
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 214-234)
* [~] Step 3.3: (MANUAL) BUG-0081 container-kind guard (executed in Phase 5)
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 235-251)
* [x] Step 3.4: Validate phase changes (`az bicep build`)
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 252-256)

### [x] Implementation Phase 4: C2 functions ingestion — unattended seed + completion check

<!-- parallelizable: false -->

* [x] Step 4.1: Make the seed run unattended by default (non-TTY → PDF persona) + test
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 263-289)
* [x] Step 4.2: Add a post-seed index-completion check (loud FAIL banner) + test
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 290-311)
* [~] Step 4.3: (CONDITIONAL — PD-02 = reuse mandatory) Reused-resource self-heal + test
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 312-331)
* [x] Step 4.4: Validate phase changes (`uv run pytest` seed/post-provision tests)
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 332-342)

### [ ] Implementation Phase 5: Validation — local gates + live `azd up` to Azure

<!-- parallelizable: false -->

* [x] Step 5.1: Run local gates (pytest, bicep build, frontend build, AST gates)
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 343-350)
* [~] Step 5.2: Live `azd up` to Azure (fresh resources via cleared EXISTING_* pins) — provision succeeded for the whole v2 stack EXCEPT AI Search (eastus2 capacity); remediation moved to Phase 6. API-level e2e now PROVEN (Phase 6): `/api/health` = pass (foundry_iq + cosmosdb + AzureSearch), `POST /api/conversation` returns a grounded answer + 5 citations to the seeded PDFs. Remaining: browser/frontend check (no auth wall + chat + admin upload).
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 351-360)
* [ ] Step 5.3: Clean up test artifacts; update bugs.md + worklog
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 361-366)
* [ ] Step 5.4: Report blocking issues requiring follow-on planning
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 367-372)

### [ ] Implementation Phase 6: AI Search regional-capacity remediation + RG cleanup (discovered in Step 5.2)

<!-- parallelizable: false -->

* [x] Step 6.1: Add a `searchServiceLocation` Bicep param (defaults to global `location` when empty) + wire the `aiSearch` module + `main.parameters.json` + `test_main_bicep.py` test + `az bicep build`
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 373-399)
* [x] Step 6.2: Set `AZURE_ENV_SEARCH_SERVICE_LOCATION` to a capacity region (uksouth); re-run `azd up`; verify AI Search provisions and the full v2 stack deploys green
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 400-412)
* [x] Step 6.3: Grant the deployer principal Storage Blob Data Contributor + Storage Queue Data Message Sender on the storage account (Bicep) so the post-deploy seed runs under the deployer identity (fixes the `AuthorizationPermissionMismatch` seed failure) + `test_main_bicep.py` test + `az bicep build`
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 413-439)
* [x] Step 6.4: Fix open-mode chat — `get_user_id` falls back to the synthetic user when auth is open (`not require_admin_auth`), not only when `environment is LOCAL`, so the deployed open backend (Easy Auth disabled) does not 401 the chat endpoint + `test_dependencies.py` test (CRITICAL blocker for "chat works, no auth wall"; mirrors the Phase 2 admin-open fix)
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 452-478)
* [x] Step 6.5: Grant the deployer principal Search Index Data Reader on the `aiSearch` module (Bicep) so the seed's index-population self-check works under the deployer identity (fixes the `Forbidden` count poll) + ensure `AZURE_AI_SEARCH_INDEX` reaches the postdeploy seed env + `test_main_bicep.py` test + `az bicep build` — 6.5a (deployer search-read grant) + 6.5b (single-source `searchIndexName` param + `AZURE_AI_SEARCH_INDEX` output) code landed + tested (33 infra pass, bicep EXIT 0); APPLIED via `azd provision` (SUCCESS 4m11s, no resources deleted); PROVEN on cloud — `AZURE_AI_SEARCH_INDEX="cwyd-index"` now in azd env + deployer reads index count 263 (no `Forbidden`). Manual diagnostic grants cleaned up (WI-10).
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 479-505)
* [ ] Step 6.6: Delete the leftover old `cwydcdbv23ane6` resource set (user-consented, destructive; old-suffix only) — executes LAST, after 6.4/6.5/6.7 are deployed green
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 506-517)

* [~] Step 6.7: Fix the frontend "Authentication Not Configured" wall — `run_health_checks` set `auth_enforced` from `environment is PRODUCTION`, so the open production backend reported `auth_enforced=true`; the SPA pairs that with an empty Easy Auth `/.auth/me` and renders `AuthBlocked`. Tie `auth_enforced` to `settings.require_admin_auth` (the actual wall) so an open deploy reports `false` + `test_health.py` tests + `azd deploy backend` (discovered during Step 5.2 frontend validation; the direct analog of Step 6.4 on the health/frontend-gating path; executes BEFORE Step 6.6). Code + tests landed (37 health tests pass); deploying.
  * Details: .copilot-tracking/details/2026-06-29/azd-up-e2e-deployment-details.md (Lines 506-517)

## Planning Log

See .copilot-tracking/plans/logs/2026-06-29/azd-up-e2e-deployment-log.md for discrepancy tracking (DR/DD), implementation paths considered (IP), planning decisions (PD), and suggested follow-on work (WI).

## Dependencies

* `azd >= 1.18.0 != 1.23.9`; Azure subscription with default-profile quota.
* `uv` (Python), Node/npm (frontend build), `az` CLI + Bicep. Docker not required (backend uses ACR remote build).
* AVM `br/public:avm/res/web/site:0.22.0` — confirm the frontend auth-settings param shape for Step 3.1.

## Success Criteria

* Default `azd up` (no WAF/private flags) + unattended seed → frontend loads with no auth wall, chat works, admin/upload returns no 401, functions ingest the seeded PDFs, all reachable from the frontend URL. — Traces to: user requirement "go to the frontend and start to use the system" + research selected approach.
* `BACKEND_CORS_ORIGINS` and the admin-open flag are present and deterministic (no FQDN cycle, no env-specific literals). — Traces to: research C3 + Hard Rule #18.
* Easy Auth is declaratively OFF on the frontend; a reprovision clears the stale provider. — Traces to: research C1/BUG-0090.
* The seed verifies the index is populated and fails loudly when empty. — Traces to: research C2 RC-async.
* Every new field/method lands with an executing test; `Environment.LOCAL` default unchanged; live azd-up validation passes. — Traces to: Hard Rules #1/#2 + user memory config-defaults-dev-first + user "validate on cloud only".
