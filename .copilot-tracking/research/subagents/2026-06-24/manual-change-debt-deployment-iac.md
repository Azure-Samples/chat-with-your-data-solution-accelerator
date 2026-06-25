<!-- markdownlint-disable-file -->
# Subagent Research — Manual-change debt (live cloud overrides needing durable IaC back-port + open deployment defects)

## Research topics / questions

1. Which CWYD v2 deployment fixes were applied as **live, manual cloud changes** (`az ...` / portal) that are **not yet durable in Bicep/azd**, so they revert on the next `azd up` / `azd provision` / `azd deploy`?
2. For each, what is the exact manual command applied, the durable fix direction, and the source-of-truth file/line to edit?
3. Which deployment-related **defects remain open** (cloud-not-verified, deferred deploy, or unresolved)?
4. Where are these tracked (bugs.md vs development_plan.md §0.1/§0.2) and what is the canonical record per item?

## Sources consulted (workspace-relative)

- v2/docs/bugs.md — canonical defect registry (BUG-0001 … BUG-0084). Registry table + Details sections.
- v2/docs/development_plan.md §0.1 (backend debt) + §0.2 (frontend debt) — phase debt/task queues; infra debt rows.
- v2/docs/development_plan.md §0.0a–§0.0e — session receipts.

Tracking split (Hard Rule #12 + #19): **defects** (broken/wrong runtime behavior) live in bugs.md; **phase debt/tasks** live in development_plan.md §0.1/§0.2. A bicep back-port that is "pending" is recorded in the bug's Details tail AND/OR a §0.1 debt row.

---

## A. Manual cloud overrides applied live but NOT yet durable in Bicep/azd

These are the core "manual change debt" items. Each was applied live to unblock, and each **reverts on the next reconcile** unless back-ported. Status values are verbatim from bugs.md.

### A1. BUG-0052 — `AZURE_AI_SERVICES_ENDPOINT` env var + UAMI `Cognitive Services User` role (backend + function)
- Area: infra. Severity: high. Bug status: **fixed (live)**; durable back-port **pending**.
- Manual applied:
  - `az containerapp update --set-env-vars AZURE_AI_SERVICES_ENDPOINT=https://aisa-<SUFFIX>.cognitiveservices.azure.com/` (backend)
  - `az functionapp config appsettings set ... AZURE_AI_SERVICES_ENDPOINT=...` (function)
  - `az role assignment create` granting UAMI **Cognitive Services User** scoped to the AI Services account.
- Durable fix: add the env var to BOTH the backend Container App `env` and the function `env` in main.bicep (today emitted only as a stack output), and add the RBAC role assignment to `infra/`. Quote from Details: "both the env var (backend + function `env`) and the RBAC role assignment should be added to `main.bicep` ... not applied this turn (further bicep edits paused by the operator)."

### A2. BUG-0053 — Function App `alwaysReady = {function:batch_push: 1}` (Flex scale-from-zero)
- Area: functions. Severity: high. Bug status: **fixed (live)**; durable back-port **pending (bicep paused)**.
- Manual applied: `az functionapp scale config always-ready set -g <RESOURCE_GROUP> -n func-<SUFFIX> --settings function:batch_push=1`.
- Durable fix: add `alwaysReady` to the function app bicep `functionAppConfig.scaleAndConcurrency`. Note: any future queue trigger (e.g. `blob_event`, BUG-0054/BUG-0077) carries the same scale-from-zero risk and needs its own always-ready entry.

### A3. BUG-0056 — Host queue `messageEncoding=none` (raw-JSON producer/consumer match)
- Area: functions. Severity: high. Bug status: **fixed (live)**; durable back-port **pending (bicep paused)**.
- Manual applied: `az functionapp config appsettings set ... "AzureFunctionsJobHost__extensions__queues__messageEncoding=none"` + restart.
- Durable fix: add `extensions.queues.messageEncoding=none` to `host.json` OR the bicep function-app app settings so every deploy carries it (today it lives only in `functions/local.settings.json`).

### A4. BUG-0059 — backend `AZURE_AI_SEARCH_CONNECTION_NAME=cwyd-kb-mcp` (KB MCP connection)
- Area: infra. Severity: high. Bug status: **fixed (live)**; durable back-port **pending (bicep paused)**.
- Manual applied: `az containerapp update ... --set-env-vars "AZURE_AI_SEARCH_CONNECTION_NAME=cwyd-kb-mcp"`.
- Cloud recurrence of BUG-0025. Durable fix: main.bicep must resolve `AZURE_AI_SEARCH_CONNECTION_NAME` to the KB MCP `RemoteTool`/`ProjectManagedIdentity` connection (`cwyd-kb-mcp`, audience `https://search.azure.com`) — NOT the general `CognitiveSearch` connection (`search-srch-<DATA_SUFFIX>`) — and create that connection + the project-MI `Search Service Contributor` assignment durably in `infra/`. "Until that lands, every `azd up` re-introduces this 401 and the env var must be re-flipped post-deploy."

### A5. BUG-0061 — Event Grid topic MI `Storage Queue Data Message Sender` role (deploy-time chicken-and-egg)
- Area: infra. Severity: blocker. Bug status: **fixed (live)**; durable back-port **pending (bicep paused)**.
- Manual applied: `az role assignment create --assignee-object-id <EG_TOPIC_MI> --role "Storage Queue Data Message Sender" --scope <storage account>`, then re-ran `azd up`.
- Caveat captured: hand-granting a role bicep also manages under a random GUID name causes a follow-on `RoleAssignmentExists` on the next provision; delete the manual grant and let bicep own it (the subscription is permanently created so the chicken-and-egg does not recur).
- Durable fix: restructure Event Grid wiring so the role precedes the subscription preflight — either (a) lift `blob-created-to-doc-processing` out of the AVM `event-grid/system-topic` module into a standalone `Microsoft.EventGrid/systemTopics/eventSubscriptions` resource that `dependsOn` `eventGridQueueSenderRole`, or (b) provision topic+MI+role first, then add the subscription in a later pass. The `useExistingEventGridTopic` branch already uses a standalone subscription resource (pattern present in the file).

### A6. BUG-0062 — Function storage account `--default-action Allow` (Flex storage firewall)
- Area: infra. Severity: blocker. Bug status: **fixed (live)**; durable back-port **pending**.
- Manual applied: `az storage account update -n st<SUFFIX> -g <RESOURCE_GROUP> --default-action Allow`.
- Durable fix: for the no-private-networking profile (`enablePrivateNetworking=false`), either set the function storage `networkRuleSet.defaultAction=Allow`, OR add a resource-instance rule granting the `Microsoft.Web/sites` Function App access while keeping `defaultAction=Deny`. (When `enablePrivateNetworking=true` the private endpoint covers this and Deny stays correct.)

### A7. BUG-0063 — backend `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME=id-<SUFFIX>` (UAMI, not deployer)
- Area: infra. Severity: blocker. Bug status: **fixed (live)**; durable back-port **pending**.
- Manual applied: `az containerapp update -n ca-backend-<SUFFIX> ... --set-env-vars AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME=id-<SUFFIX>`.
- Durable fix: main.bicep runtime `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` for backend (~L1760) and function (~L2066) must be `'id-${solutionSuffix}'` (the UAMI's postgres principal), not `postgresAdminPrincipalName` (the human deployer UPN). Note: `--set-env-vars` is reverted by the next `azd deploy`, so durable fix required before next deploy.

### A8. BUG-0064 — backend `CWYD_ORCHESTRATOR_NAME=langgraph` (orchestrator env-var rename + pgvector value)
- Area: infra. Severity: high. Bug status: **fixed (live)**; durable back-port **pending**.
- Manual applied: `az containerapp update -n ca-backend-<SUFFIX> ... --set-env-vars CWYD_ORCHESTRATOR_NAME=langgraph`.
- Two faults: (a) main.bicep L1776 emits env var `ORCHESTRATOR` but backend reads `CWYD_ORCHESTRATOR_NAME` (`OrchestratorSettings` env_prefix `CWYD_ORCHESTRATOR_`); (b) value hardcoded `agent_framework` for every db type.
- Durable fix: rename L1776 env var `ORCHESTRATOR` → `CWYD_ORCHESTRATOR_NAME`, value mode-conditional `databaseType == 'postgresql' ? 'langgraph' : 'agent_framework'`.

### A9. BUG-0069 — backend `AZURE_ENVIRONMENT=production` (status reports `local` in cloud)
- Area: infra. Severity: high. Bug status: **open** (Bicep wired 2026-06-22, NOT yet cloud-verified).
- Final fix (operator-directed): keep `AppSettings.environment` default = `local` (dev-friendly); wire `{ name: 'AZURE_ENVIRONMENT', value: 'production' }` onto BOTH deployed runtimes in main.bicep (backend Container App + Function App) so prod flips config to `production` and the admin local-dev auth bypass fails closed. An earlier secure-by-default code default-flip (`local`→`production` in settings.py) was **reverted** per operator directive (see user memory `config-defaults-dev-first.md`). `az bicep build` clean; **status stays open pending cloud deploy + live verification.** Security tie-in: the admin gate local-dev bypass (BUG-0047) keys on `environment == "local"`.

### A10. ACR-AAD-AS-ARM-BICEP-DEBT (development_plan.md §0.2)
- Area: infra. Phase 7 debt. Status: **☐ open**.
- Manual applied (by hand, reverts on provision): `az acr config authentication-as-arm update -r cr<SUFFIX> --status enabled`.
- Symptom: Basic-SKU ACR ships `azureAdAuthenticationAsArmPolicy = disabled` by default; App Service MI→ACR token exchange returns 401 even with correct `AcrPull` RBAC.
- Durable fix (structural, Hard Rule #10 ask): add `policies: { azureADAuthenticationAsArmPolicy: { status: 'enabled' } }` to the `Microsoft.ContainerRegistry/registries` resource in `v2/infra/modules/container_registry.bicep` (or its AVM module call).

### A11. BACKEND-CA-ACR-REGISTRIES-BICEP-DEBT (development_plan.md §0.1)
- Area: infra. Phase 7 debt. Status: **☐ open**.
- Manual applied (by hand, reverts on provision): `az containerapp registry set -g <RESOURCE_GROUP> -n ca-backend-<SUFFIX> --server cr<SUFFIX>.azurecr.io --identity <UAMI_RESOURCE_ID>`.
- Symptom: `backendContainerApp` AVM module attaches the UAMI + grants `AcrPull` but ships NO `registries:` block, so the revision update fails `UNAUTHORIZED: authentication required` (anonymous pull fallback) after a fresh `azd provision`.
- Durable fix (structural, Hard Rule #10 ask): add `registries: [ { server: '${containerRegistryName}.azurecr.io', identity: userAssignedIdentity.outputs.resourceId } ]` to the `backendContainerApp` AVM module call in main.bicep. Pair with A10 in the same infra-hardening turn.

### A12. FRONTEND-APPSERVICE-AZD-CONTAINER-DEPLOY-DEBT (development_plan.md §0.1) + BUG-0081
- Area: infra. Severity: high (BUG-0081 = **open**); §0.1 row **☐ open**.
- Symptom: `azd deploy frontend` performs a **zip/code push deployment** to the container-kind App Service (leaving it on `mcr.microsoft.com/appsvc/staticsite:latest` placeholder) — the `appservice` azd host does NOT support the `docker:` block declared in `v2/azure.yaml`, so the Dockerfile is silently ignored. ACR never receives an `azd-deploy-*` frontend image.
- Manual applied (by hand, reverts on next provision): `az acr build ... -f docker/Dockerfile.frontend --target prod --build-arg VITE_BACKEND_URL=<backend-fqdn>`; `az webapp config container set ...`; `az resource update ... --set properties.acrUseManagedIdentityCreds=true properties.acrUserManagedIdentityID=<UAMI-client-id>`; `WEBSITES_PORT=80` + restart.
- Durable fix (structural design decision, Hard Rule #10): EITHER move the frontend to a **Container App** (like the backend — fully azd-supported container build/push) OR switch the App Service to an azd **code/static deploy** model. Today's `az webapp config container set` is reverted by the next `azd provision`.

---

## B. Open / not-cloud-verified deployment defects (no durable fix yet, or deferred deploy)

### B1. BUG-0054 — Event Grid `blob_event` translator (schema-mismatch poison)
- Area: infra. Severity: medium. Status: **open** — fix implemented + proven locally; **cloud deploy of the `blob_event` translator deferred**.
- ADR 0028. Locally validated end-to-end; cloud `azd deploy function` exceeded azd's 20-min wait (Flex remote-build slowness). To resume: deploy `blob_event`, add `alwaysReady` for `function:blob_event` (BUG-0053 class), then `azd env set AZURE_ENV_INGESTION_TRIGGER event_grid` + `azd provision` to flip off backend double-enqueue, re-validate.
- Note: BUG-0080 (deploy hang) is now fixed, which unblocks this cloud verification.

### B2. BUG-0055 — App Insights receives zero telemetry (backend + function)
- Area: infra. Severity: medium. Status: **open** — both halves code/config-complete but **not yet cloud-verified** (was blocked by Flex build outage / BUG-0080).
- Backend half durable in Bicep (rename backend container env var to `AZURE_APP_INSIGHTS_CONNECTION_STRING`; ADR 0018 Amendment 1). Function half wired (`configure_telemetry()` worker OTel). Keep open until App Insights shows backend + function telemetry post-deploy. Possible follow-up: host-level `requests` telemetry needs `host.json` `telemetryMode` (separate).

### B3. BUG-0058 — `azd deploy function` ships a stale build-functions artifact
- Area: functions. Severity: medium. Status: **open** — root-caused + fixed in azure.yaml (moved `prepackage` hook from project-scope to `services.function.hooks.prepackage`); drift-guard test added. **Stays open only until a live `azd deploy function` confirms `build-functions/` regenerates** (gated on the previously-blocked Flex deploy, now unblocked by BUG-0080).

### B4. BUG-0077 — auto-remove index chunks on blob delete (Event Grid `BlobDeleted`)
- Area: functions. Severity: low (enhancement). Status: **open**. Phase 1 implemented + committed (`a214182`); main.bicep adds `Microsoft.Storage.BlobDeleted` to both Event Grid subscriptions. **Phase 2 (deploy) deferred** behind BUG-0058 (prepackage) + BUG-0053 (always-ready for the queue trigger). Open until function deploys and a live blob-delete drops its chunks.

### B5. BUG-0082 — backend crash-loop when PostgreSQL unreachable (no connect timeout)
- Area: backend. Severity: medium. Status: **open**. FastAPI lifespan's first DB calls (`get_runtime_config` → `ensure_pool` → `ensure_schema`) have no connect timeout, so an unreachable/auto-stopped Burstable server hangs the lifespan forever → permanent crash-loop. Observed 2026-06-24 (psql auto-stopped after 7-day idle). Fix direction (pending): bounded asyncpg connect timeout + fail-fast or degrade the `database` check; add `PYTHONUNBUFFERED=1` to the backend image so startup logs flush.

---

## C. Already-durable Bicep fixes (NOT manual debt — recorded so they are not re-flagged)

These deployment defects were fixed **in Bicep/code** (durable), so they are NOT manual-override debt:

- BUG-0051 — storage env vars (`AZURE_STORAGE_ACCOUNT_NAME` / `AZURE_DOCUMENTS_CONTAINER` / `AZURE_DOC_PROCESSING_QUEUE`) added to `backendContainerApp` env in main.bicep (live hotfix applied too, but the bicep edit landed — "makes the wiring durable across re-provision").
- BUG-0060 — search-PE DNS-zone index made mode-conditional in main.bicep (`avmPrivateDnsZones[databaseType == 'cosmosdb' ? dnsZoneIndex.search : dnsZoneIndex.postgres]`); `az bicep build` clean.
- BUG-0080 — repinned `agent-framework==1.7.0` umbrella → `agent-framework-core==1.7.0` in pyproject.toml (kept `agent-framework-foundry==1.7.0`); guard test added. Unblocks cloud verification of BUG-0054 / BUG-0055 / BUG-0058 / BUG-0077.
- BUG-0078 — prepackage allow-list `_FUNCTION_SUBPACKAGES` gained `blob_event` + set-equality guard test.
- BICEP-COSMOS-PUBLIC-ACCESS-INCONSISTENCY (§0.1) — ✅ cleared 2026-06-08 (C1).
- DOCKERFILE-BACKEND-RELOAD-DEV-FLAG (§0.1) — ✅ cleared 2026-06-08 (C2, MACAE single-image pattern).

---

## D. Consolidated durable-back-port checklist (the "manual change debt" set)

Grouped by source-of-truth file. Each item below reverts on reconcile until landed in IaC.

`v2/infra/main.bicep`:
- A1 — add `AZURE_AI_SERVICES_ENDPOINT` to backend + function `env`; add UAMI `Cognitive Services User` role assignment (BUG-0052).
- A4 — resolve `AZURE_AI_SEARCH_CONNECTION_NAME` → `cwyd-kb-mcp` RemoteTool connection; create that connection + project-MI `Search Service Contributor` (BUG-0059).
- A5 — restructure Event Grid wiring so `eventGridQueueSenderRole` precedes the `blob-created-to-doc-processing` subscription preflight (BUG-0061).
- A6 — function storage `networkRuleSet` for no-private-networking profile (defaultAction=Allow OR resource-instance rule) (BUG-0062).
- A7 — backend (~L1760) + function (~L2066) `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` = `'id-${solutionSuffix}'` not `postgresAdminPrincipalName` (BUG-0063).
- A8 — rename L1776 env var `ORCHESTRATOR` → `CWYD_ORCHESTRATOR_NAME`, value `databaseType == 'postgresql' ? 'langgraph' : 'agent_framework'` (BUG-0064).
- A9 — `{ name: 'AZURE_ENVIRONMENT', value: 'production' }` on backend + function (BUG-0069) — **already wired 2026-06-22, awaiting cloud verify**.
- A11 — `registries:` block on `backendContainerApp` AVM module (BACKEND-CA-ACR-REGISTRIES-BICEP-DEBT).

`v2/infra/modules/container_registry.bicep`:
- A10 — `policies.azureADAuthenticationAsArmPolicy.status = 'enabled'` (ACR-AAD-AS-ARM-BICEP-DEBT).

Function host config (`host.json` or bicep function-app app settings):
- A3 — `extensions.queues.messageEncoding=none` (BUG-0056).

Function app bicep `functionAppConfig.scaleAndConcurrency`:
- A2 — `alwaysReady = { function:batch_push: 1 }` (BUG-0053); add `function:blob_event` when B1/B4 deploy.

`v2/azure.yaml` + frontend host topology (structural decision, Hard Rule #10):
- A12 — frontend → Container App OR azd code/static deploy (FRONTEND-APPSERVICE-AZD-CONTAINER-DEPLOY-DEBT / BUG-0081).

Backend code/image:
- B5 — asyncpg connect timeout + fail-fast/degrade + `PYTHONUNBUFFERED=1` (BUG-0082).

---

## Key findings

1. **Eight live `az`-override fixes are not yet in Bicep** (A1–A8), all flagged "durable bicep fix pending (bicep edits paused by the operator)". Every one reverts on the next `azd provision` / `azd deploy`, re-breaking the deployment. This is the core "manual change debt."
2. **Three more structural Bicep/azd gaps** (A10 ACR ARM policy, A11 ACA registries block, A12 frontend container deploy) are tracked as §0.1/§0.2 debt rows and also require by-hand re-application after each provision.
3. **A9 (BUG-0069 `AZURE_ENVIRONMENT`)** is the only one already wired into Bicep (2026-06-22) but still **open pending cloud verification**; the correct fix kept the code default `local` and wired the prod env var (operator reverted an earlier secure-by-default code flip — matches user memory `config-defaults-dev-first.md`).
4. **Deploy-pipeline unblock:** BUG-0080 (Agent Framework umbrella hyperlight conflict on Python 3.11) is now fixed, which unblocks the deferred cloud verification of BUG-0054 / 0055 / 0058 / 0077.
5. **One non-IaC open backend deploy defect:** BUG-0082 (DB-unreachable crash-loop, no connect timeout).
6. **Caveat for A5/A10/A11:** hand-granting a role/registry that Bicep also manages causes a follow-on conflict (`RoleAssignmentExists`) or is wiped on reconcile — the only clean path is the durable IaC edit, or matching Bicep's deterministic `guid(...)` name.

## Clarifying questions (need user input)

- None blocking for research. For implementation: A12 (frontend host) and A5 (Event Grid restructure) are structural (Hard Rule #10) and need an explicit user pick before editing. "Bicep edits paused by the operator" was the standing reason A1–A8 were not back-ported — confirm whether that pause is lifted before opening a Bicep back-port turn.

## Recommended next research (not done this session)

- [ ] Open `v2/infra/main.bicep` and confirm the exact current line numbers for: `ORCHESTRATOR` env (≈L1776), `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` (backend ≈L1760 / function ≈L2066), backend container `env` block (for A1/A9/A11), the AVM `event-grid/system-topic` module + `eventGridQueueSenderRole` (A5), and the function storage `networkRuleSet` (A6).
- [ ] Confirm `v2/infra/modules/container_registry.bicep` exposes a `policies`/AVM param for the ARM-auth policy (A10).
- [ ] Inspect `v2/azure.yaml` `services.frontend` block + `v2/docker/Dockerfile.frontend` to scope the A12 host decision (Container App vs static deploy).
- [ ] Check whether a function-app bicep module already exposes `functionAppConfig.scaleAndConcurrency` (A2) and `extensions.queues.messageEncoding` app-setting plumbing (A3).
- [ ] Verify the post-BUG-0080 deploy actually landed A9 (`AZURE_ENVIRONMENT=production`) live and whether any A1–A8 overrides were re-applied or back-ported in the 2026-06-24 deploy.
