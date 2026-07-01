---
applyTo: '.copilot-tracking/changes/2026-07-01/v2-containerize-services-and-model-cleanup-changes.md'
---
<!-- markdownlint-disable-file -->
# Implementation Plan: CWYD v2 — Containerize All Three Services + Model Cleanup

## Overview

Convert the CWYD v2 frontend and function into ACR-built container images (backend already is), removing the dedicated `o4-mini` reasoning deployment and scrubbing all live `gpt-4` references, so a fresh cosmosdb-mode `azd up` builds + pushes + rolls fresh code for all three services on the shared Container Apps environment.

## Objectives

### User Requirements

* Infra provisions an ACR used to build + push Docker images for frontend, backend, AND function, rebuilt (code updated) every deploy — `cwydcontainerreg`-style. — Source: user request 2026-07-01 + decision #1 ("1 yes")
* Accept anonymous end-user auth with NO code change and NO manual frontend identity. — Source: decision #2
* Use cosmosdb as the default database for this environment. — Source: decision #3
* Drop the dedicated reasoning model; no `gpt-5-mini`, no separate reasoning deployment. — Source: decision #4
* Remove every `gpt-4` reference; use no model on the Foundry retirement schedule. — Source: decision #5 + user request

### Derived Objectives

* Move the frontend `host: appservice` → `host: containerapp` and the function off Flex Consumption to Azure Functions on Azure Container Apps (the only azd-supported containerized-Functions path). — Derived from: decision #1 requires all three as images; Flex cannot run custom containers.
* Preserve reasoning streaming from `gpt-5.1` after removing `o4-mini`. — Derived from: `FoundryIQ` probes the chat model's `supports_reasoning()`, not the reasoning deployment.
* Leave dated historical records (`bugs.md`, `worklog/**`) unscrubbed. — Derived from: Hard Rule #16/#19 (process records are not rewritten).

## Context Summary

### Project Files

* v2/azure.yaml - service host + docker blocks for backend/frontend/function; hooks.
* v2/infra/main.bicep - ACR, Container Apps env, backend Container App (mirror template), frontend App Service, Flex Function App + plan + deployment container, model deployments, reasoning params/env, `flexDeploymentRole`.
* v2/infra/main.parameters.json, v2/infra/main.waf.parameters.json - model + reasoning params.
* v2/docker/Dockerfile.frontend - prod stage (uvicorn :80, `/config` → `BACKEND_API_URL`).
* v2/docker/Dockerfile.functions - currently compose-only; needs prod rewrite.
* v2/scripts/prepackage_function.py - authoritative function deploy layout (to reproduce in the prod Dockerfile, then retire).
* v2/src/backend/core/settings.py + providers/llm/{base,foundry_iq}.py + admin surface - reasoning-deployment consumers.
* v2/src/frontend/src/models/admin.tsx - admin reasoning field.
* v2/tests/** - reasoning-routing + gpt-4 fixtures.

### References

* .copilot-tracking/research/2026-07-01/v2-acr-build-rbac-models-research.md - primary research, confirmed decisions, per-service change table.
* .copilot-tracking/research/subagents/2026-07-01/v2-containerize-frontend-function-research.md - containerization edit sites + hosting-option comparison.
* .copilot-tracking/research/subagents/2026-07-01/v2-reasoning-drop-gpt4-scrub-research.md - reasoning removal + gpt-4 inventory.
* .copilot-tracking/research/subagents/2026-07-01/v2-residual-gaps-research.md - image-tag swap, model edit sites.
* .copilot-tracking/research/subagents/2026-07-01/v2-rbac-auth-readiness-research.md - RBAC complete; anonymous auth.

### Standards References

* .github/copilot-instructions.md - Hard Rules #1 (one unit/turn), #2 (test-first), #3 (pillar), #7 (no banned tech / azd-only), #10 (structural change confirmation), #16/#19 (no process narrative / durable tracking), #18 (no env IDs).
* .github/instructions/v2-infra.instructions.md - Bicep + azd conventions.
* .github/instructions/v2-functions.instructions.md - Functions blueprint + trigger conventions.
* .github/instructions/v2-frontend.instructions.md - frontend conventions.
* .github/instructions/v2-tests.instructions.md - test-first contract.

## Implementation Checklist

### [x] Implementation Phase 1: Frontend → Container App

<!-- parallelizable: false -->

* [x] Step 1.1: Confirm/adjust `Dockerfile.frontend` prod stage for Container Apps
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 27-46)
* [x] Step 1.2: Point `v2/azure.yaml` frontend service at `host: containerapp`
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 47-67)
* [x] Step 1.3: Replace the frontend App Service + `appServicePlan` with a Container App in `main.bicep` (structural — Hard Rule #10 confirm)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 68-89)
* [x] Step 1.4: Repoint frontend URL output + backend CORS to the Container App FQDN
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 90-109)
* [x] Step 1.5: Retire frontend packaging scripts + `build-output` staging
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 110-131)
* [x] Step 1.6: Validate Phase 1 (bicep build + what-if; frontend build)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 132-147)

### [x] Implementation Phase 2: Function → Azure Functions on Azure Container Apps

<!-- parallelizable: false -->

* [x] Step 2.1: Author a production `Dockerfile.functions` (reproduce prepackage nesting)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 154-174)
* [x] Step 2.2: Point `v2/azure.yaml` function service at `host: containerapp`; drop prepackage hook
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 175-195)
* [x] Step 2.3: Replace the Flex Function App with a Functions-on-ACA resource in `main.bicep` (structural — Hard Rule #10 confirm)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 196-222)
* [x] Step 2.4: Remove `flexDeploymentRole` + deployment-package container
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 223-242)
* [x] Step 2.5: Repoint any consumer of the function FQDN
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 243-262)
* [x] Step 2.6: Retire `prepackage_function.py` + `build-functions/` staging
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 263-285)
* [x] Step 2.7: Validate Phase 2 (function image build + import smoke; bicep; function tests)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 286-301)

### [x] Implementation Phase 3: Remove the dedicated reasoning deployment (o4-mini)

<!-- parallelizable: false -->

* [x] Step 3.1: Remove the `o4-mini` model deployment + reasoning params from `main.bicep`
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 308-324)
* [x] Step 3.2: Remove `AZURE_OPENAI_REASONING_DEPLOYMENT` from runtime env in `main.bicep`
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 325-338)
* [x] Step 3.3: Remove `reasoningModelName` from both parameter files
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 339-353)
* [x] Step 3.4: Remove the `reasoning_deployment` field from `OpenAISettings` (test-first)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 354-370)
* [x] Step 3.5: Retarget `reason()` to the chat deployment; remove dead routing + narrow `DeploymentAttr` (test-first; structural confirm)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 371-392)
* [x] Step 3.6: Remove `reasoning_deployment` from admin config + frontend admin model + post_provision + live docs (test-first)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 393-417)
* [x] Step 3.7: Validate Phase 3 (pytest; vitest; bicep; pyright + ruff; `.env` sweep)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 418-433)

### [x] Implementation Phase 4: Scrub all `gpt-4` references

<!-- parallelizable: false -->

* [x] Step 4.1: Scrub production `src` + `scripts` literals
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 440-454)
* [x] Step 4.2: Scrub test-fixture literals (preserve routing-assertion intent)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 455-470)
* [x] Step 4.3: Scrub live docs; leave dated historical records
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 471-490)
* [x] Step 4.4: Validate Phase 4 (grep zero live hits; pytest; markdownlint)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 491-503)

### [x] Implementation Phase 5: Final Validation

<!-- parallelizable: false -->

* [x] Step 5.1: Run full project validation (uv sync; pytest + AST gates; frontend build+vitest; bicep both param files; pyright + ruff; docker build all three; markdownlint)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 508-518)
* [x] Step 5.2: Fix minor validation issues (one unit per turn)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 519-522)
* [x] Step 5.3: Report blocking issues (recommend follow-up research rather than large inline fixes)
  * Details: .copilot-tracking/details/2026-07-01/v2-containerize-services-and-model-cleanup-details.md (Lines 523-527)

## Planning Log

See .copilot-tracking/plans/logs/2026-07-01/v2-containerize-services-and-model-cleanup-log.md for discrepancy tracking, implementation paths considered, and suggested follow-on work.

## Dependencies

* `azd` (repo-pinned `>= 1.18.0 != 1.23.9`), Azure CLI + bicep, Docker, `uv`, Node 20.
* Deployer holds Owner or User-Access-Administrator (fresh-tenant RBAC prerequisite).
* `gpt-5.1` + `text-embedding-3-large` GlobalStandard quota in the target region (`eastus2` default).
* Shared `container-app` AVM module version that supports `kind: functionapp` (Phase 2 bump).

## Success Criteria

* All three services build as container images, push to the provisioned ACR (`cr<suffix>`), and roll fresh code on each `azd deploy`. — Traces to: user request + decision #1.
* Frontend + function run on the shared Container Apps Environment under the shared UAMI with no new RBAC. — Traces to: v2-rbac-auth-readiness-research.md (UAMI complete).
* No `o4-mini` / dedicated reasoning deployment remains; reasoning still streams from `gpt-5.1`. — Traces to: decision #4 + FoundryIQ `supports_reasoning()`.
* Zero live `gpt-4` references (only dated historical records remain). — Traces to: decision #5 + Hard Rule #16/#19.
* `azd up` provisions + deploys clean on a fresh cosmosdb-mode tenant, anonymous auth, ending green. — Traces to: decisions #2 + #3.
