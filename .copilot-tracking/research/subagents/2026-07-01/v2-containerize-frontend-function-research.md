<!-- markdownlint-disable-file -->
# Research — Containerize all three CWYD v2 services (backend already done; move frontend + function to container images pushed to the provisioned ACR)

Status: Complete (read-only; no source/infra edited)

Scope: Move the FRONTEND onto a container on Azure Container Apps, and move the FUNCTION off Flex Consumption onto a container-capable Functions host, so all three services build a Docker image from source, push to the infra-provisioned ACR `cr<suffix>`, and rebuild on every `azd deploy` — mirroring the backend, which already does this.

Files inspected (all under `c:\workstation\Microsoft\github\cwyd-cdb\v2`):
- `azure.yaml`
- `infra/main.bicep` (compute + registry + env + storage + event grid + outputs)
- `docker/Dockerfile.backend`, `docker/Dockerfile.frontend`, `docker/Dockerfile.functions`
- `docker/docker-compose.dev.yml`
- `scripts/prepackage_function.py`
- `src/functions/function_app.py` + every blueprint under `src/functions/**`
- `src/functions/host.json`
- `src/frontend/frontend_app.py`, `src/frontend/src/api/runtimeConfig.tsx`

---

## Executive decision (answers the two hard questions up front)

1. Frontend → **`host: containerapp` on the shared Container Apps Environment** (`cae-<suffix>`), a `Microsoft.App/containerApps` resource tagged `azd-service-name: frontend`, mirroring the backend one-for-one. The `Dockerfile.frontend` already has a production `prod` stage that serves the SPA via uvicorn on port 80 and exposes a runtime `/config` endpoint. **Do NOT bake the backend URL as a `VITE_BACKEND_URL` build-arg** — the current frontend resolves the backend origin at RUNTIME from `/config` fed by the `BACKEND_API_URL` env var (build-arg is only a fallback). So the container needs `BACKEND_API_URL` as a runtime env var, exactly like the App Service does today.

2. Function → **`host: containerapp` with a `Microsoft.App/containerApps` resource whose `kind` = `functionapp` (Azure Functions on Azure Container Apps)**. This is the ONLY azd-supported path to run a containerized Functions app, because azd's `host: function` target is **zip-deploy-only** — the azure.yaml schema explicitly forbids `docker:`/`image:` under `host: function` (see Part B.2). Functions-on-ACA supports custom container images, KEDA event-driven scaling for the queue + HTTP triggers CWYD uses, managed-identity ACR pull + AzureWebJobsStorage, and azd deploys it exactly like any other container app. Flex Consumption cannot host a custom container at all.

Net effect: all three services become `host: containerapp`, all three push an image to the same `cr<suffix>` ACR, all three share the single `cae-<suffix>` Container Apps Environment, and all three pull with the shared UAMI's existing AcrPull grant. This is the maximally uniform, minimal-surface end state.

---

## PART A — Frontend → container on Azure Container Apps

### A.1 Current frontend host (App Service build-from-source, NOT a container)

CONFIRMED: the frontend is currently a **Python App Service build-from-source** app, not a container. The earlier survey note is accurate.

`azure.yaml` — frontend service block, lines 114–142 (`host: appservice` at line 117):

```yaml
  frontend:
    project: ./src/frontend
    language: js
    host: appservice
    # Build-from-source on App Service (reference-architecture pattern). host: appservice
    # does not support a `docker:` block -- pairing them is the root
    # cause of BUG-0081. The service-scoped prepackage hook runs
    # `npm ci && npm run build`, then stages a self-contained deploy
    # artifact at ./build-output (the App Service start command
    # `uvicorn frontend_app:app` needs the server + requirements.txt
    # beside the static dist/ ...)
    dist: ./build-output
    hooks:
      prepackage:
        posix:
          shell: sh
          run: ../../scripts/package-frontend.sh
        windows:
          shell: pwsh
          run: ../../scripts/package-frontend.ps1
```

`infra/main.bicep` — frontend compute resource is `frontendWebApp` (AVM `avm/res/web/site:0.22.0`), a **Linux App Service Web App on an App Service Plan**, lines 2020–2130 (excerpt with the App-Service-specific bits):

```bicep
module frontendWebApp 'br/public:avm/res/web/site:0.22.0' = {          // L2020
  name: take('avm.res.web.site.frontend.${solutionSuffix}', 64)
  params: {
    name: frontendAppName
    tags: union(allTags, { 'azd-service-name': 'frontend' })            // L2025
    kind: 'app,linux'
    serverFarmResourceId: appServicePlan.outputs.resourceId
    managedIdentities: { userAssignedResourceIds: [ userAssignedIdentity.outputs.resourceId ] }
    ...
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'                                     // build-from-source
      appCommandLine: 'uvicorn frontend_app:app --host 0.0.0.0 --port 8000'
      appSettings: union([
        { name: 'BACKEND_API_URL', value: 'https://${backendContainerApp.outputs.fqdn}' }
        { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false' }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'WEBSITES_PORT', value: '8000' }
        { name: 'ENABLE_ORYX_BUILD', value: 'true' }
      ], enableMonitoring ? [ APPLICATIONINSIGHTS_CONNECTION_STRING ] : [])
    }
  }
}
```

Supporting resource: `appServicePlan` (AVM `avm/res/web/serverfarm:0.7.0`) at line 2005 (`asp-<suffix>`, SKU `B1` default / `P1v3` when scaled or redundant). Frontend name var `frontendAppName = 'app-frontend-${solutionSuffix}'` at line 1993; plan name var `appServicePlanName = 'asp-${solutionSuffix}'` at line 1992.

Outputs affected: `AZURE_FRONTEND_URL` at line 2671 (`'https://${frontendWebApp.outputs.defaultHostname}'`).

### A.1.1 CRITICAL nuance — how the SPA finds the backend (runtime `/config`, not a build-arg)

The user's Part A spec assumed `buildArgs: VITE_BACKEND_URL=${AZURE_BACKEND_URL}`. That is NOT how the current frontend works, and baking it is the inferior choice. Evidence:

`src/frontend/src/api/runtimeConfig.tsx` — `getBackendUrl()` fallback order:

```ts
export function getBackendUrl(): string {
  if (cachedBackendUrl !== null) {          // 1. value fetched from /config (authoritative)
    return cachedBackendUrl;
  }
  return (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "";  // 2. build-time fallback
}
```

`src/frontend/frontend_app.py` serves `/config` from the `BACKEND_API_URL` env var at runtime:

```python
@app.get("/config")
def get_config() -> FrontendConfig:
    return FrontendConfig(backend_url=os.environ.get("BACKEND_API_URL", ""))
```

Implication: the deployed SPA calls `/config` on boot and uses whatever `BACKEND_API_URL` the host sets — the built bundle is backend-URL-agnostic. Baking `VITE_BACKEND_URL` at build would reintroduce the chicken-and-egg problem the App-Service design already solved (the backend Container App FQDN is not knowable on a clean first `azd up`, before the backend exists). Therefore the frontend container should set `BACKEND_API_URL` as a **runtime env var on the container app** (an `env` entry), NOT a Docker `buildArgs`. This exactly matches how the backend container app injects its config.

### A.2 Exact changes to make the frontend a container on Container Apps

Template to mirror — the backend Container App block (`backendContainerApp`, AVM `avm/res/app/container-app:0.22.1`), `infra/main.bicep` lines 1776–~1900. Every property the frontend equivalent needs is listed against the backend's usage:

| Property | Backend value (template) | Frontend value |
| --- | --- | --- |
| module | `br/public:avm/res/app/container-app:0.22.1` | same |
| `name` | `backendAppName` (`ca-backend-<suffix>`) | new `frontendContainerAppName` e.g. `ca-frontend-<suffix>` |
| `tags` | `union(allTags, { 'azd-service-name': 'backend' })` | `union(allTags, { 'azd-service-name': 'frontend' })` |
| `environmentResourceId` | `containerAppsEnv.outputs.resourceId` | same (shared env) |
| `managedIdentities.userAssignedResourceIds` | `[ userAssignedIdentity.outputs.resourceId ]` | same (shared UAMI) |
| `registries` | `[{ server: containerRegistry.outputs.loginServer, identity: userAssignedIdentity.outputs.resourceId }]` | same (AcrPull already on UAMI) |
| `workloadProfileName` | `acaWorkloadProfileName` (`Consumption`) | same |
| `ingressTargetPort` | `8000` | **`80`** (the `prod` stage `EXPOSE 80` / uvicorn `--port 80`) |
| `ingressExternal` | `!enablePrivateNetworking` | same (SPA must be publicly reachable in the non-private profile) |
| `ingressAllowInsecure` | `false` | same |
| `ingressTransport` | `'auto'` | same |
| `scaleSettings` | `min 0/1`, `max 3/10` | same shape (SPA can scale to zero) |
| `containers[0].image` | placeholder `mcr.microsoft.com/k8se/quickstart:latest` when hostname empty, else `<hostname>/<name>:<tag>` | same placeholder pattern with new `frontendContainerImageName` (e.g. `cwyd-frontend`) + reuse `backendContainerRegistryHostname` param + a `frontendContainerImageTag` param |
| `containers[0].resources` | `cpu 0.5/1.0`, `memory 1.0/2.0Gi` | can be smaller (static server); `0.25`/`0.5Gi` is enough |
| `containers[0].env` | large backend env block | **just `BACKEND_API_URL` = `'https://${backendContainerApp.outputs.fqdn}'`** + optional `APPLICATIONINSIGHTS_CONNECTION_STRING` when `enableMonitoring` |

`azure.yaml` — replace the frontend service block (lines 114–142) with the backend-style container block:

```yaml
  frontend:
    project: ./src/frontend
    language: js
    host: containerapp
    docker:
      path: ../../docker/Dockerfile.frontend
      context: ../..
      target: prod
      remoteBuild: true
      # NOTE: do NOT add buildArgs: VITE_BACKEND_URL here. The SPA reads the
      # backend origin at runtime from /config (BACKEND_API_URL env on the
      # container app), so nothing is baked at build time.
```

Removals from the frontend service block: the `dist: ./build-output` line, the whole `hooks.prepackage` block, and the two package-frontend scripts become dead (`scripts/package-frontend.sh` / `.ps1` and their `package_frontend.py`) — they exist only to stage the App-Service self-contained deploy artifact. Container build stages the SPA inside the image, so the hook is unnecessary.

Bicep — delete `frontendWebApp` (L2020) and replace with a `frontendContainerApp` module cloned from `backendContainerApp`, with the property values in the table above. Add name/image vars near the backend vars (L1618–1622): `var frontendContainerAppName = 'ca-frontend-${solutionSuffix}'`, `param frontendContainerImageName string = 'cwyd-frontend'`, `param frontendContainerImageTag string = 'latest'`. The `appServicePlan` module (L2005) becomes orphaned ONLY IF the function also leaves App Service (it does — see Part B); after both moves, delete `appServicePlan` and its `appServicePlanName`/`appServicePlanSkuName`/`appServicePlanSkuCapacity` vars.

Runtime env: the frontend container needs exactly ONE runtime env var — `BACKEND_API_URL` — plus `APPLICATIONINSIGHTS_CONNECTION_STRING` when monitoring is on. No build-arg bake. No `AZURE_CLIENT_ID` (the SPA never calls Azure directly).

### A.3 `Dockerfile.frontend` already has a Container-Apps-suitable `prod` stage

`docker/Dockerfile.frontend` — the `prod` stage (quoted):

```dockerfile
# ---- prod stage: Python + uvicorn (matches v1 hosting model) ----
FROM python:3.11-slim AS prod
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /usr/src/app
RUN pip install --no-cache-dir uvicorn fastapi
COPY --from=build /app/dist /usr/src/app/dist
COPY src/frontend/frontend_app.py /usr/src/app/frontend_app.py
EXPOSE 80
CMD ["uvicorn", "frontend_app:app", "--host", "0.0.0.0", "--port", "80"]
```

Assessment: ready as-is. Server = uvicorn/FastAPI (`frontend_app.py`), port = **80**, serves `dist/` + `/config`. So `ingressTargetPort: 80`. The `build` stage takes an `ARG VITE_BACKEND_URL=""` (defaults empty) — leave it empty; the runtime `/config` path supersedes it. `azure.yaml` must set `docker.target: prod` (the default target is the last stage, which is already `prod`, but pinning is safer).

### A.4 Outputs / DNS / CORS wiring to change when frontend moves App Service → Container Apps FQDN

- `AZURE_FRONTEND_URL` output (L2671) changes from `frontendWebApp.outputs.defaultHostname` to `frontendContainerApp.outputs.fqdn` (i.e. `'https://${frontendContainerApp.outputs.fqdn}'`). Check the postprovision summary script (`scripts/post-provision.*`) and any test asserting on this output name — the output NAME stays the same, only the expression changes, so downstream consumers are unaffected.
- `AZURE_BACKEND_URL` (L2668) is unchanged (backend stays put). The frontend's `BACKEND_API_URL` env still binds to `backendContainerApp.outputs.fqdn`.
- CORS: search the backend for a CORS allow-list env that references the frontend FQDN. The backend env block (L1826+) does not appear to bind a frontend-origin CORS var, and the App-Service design relied on same-origin `/config` + the SPA calling the backend cross-origin already. Verify `backend.core.settings` / the FastAPI CORS middleware: if a `CWYD_*`/`AZURE_FRONTEND_URL`-style CORS origin is wired into the backend container env, it must be repointed to the new frontend FQDN. (Not found in the inspected bicep env block — flag for confirmation during implementation.)
- Private-networking profile: the frontend App Service used regional VNet integration into the `web` subnet to reach the backend on the CAE internal IP. On ACA, the frontend joins the SAME internal CAE and reaches the backend via `<app>.<defaultDomain>` through the existing `caeDnsZone` wildcard A-record (L1719) — the `web` subnet + `webSubnetResourceId` wiring for the frontend becomes unused. This simplifies the private-networking path (one fewer subnet consumer) but is a VNet/subnet change to validate.

---

## PART B — Function → container-capable Functions host

### B.1 Every trigger the function app uses

Enumerated by reading `src/functions/function_app.py` + each blueprint. **Only two trigger classes: HTTP and Storage Queue. No blob trigger, no timer, no direct Event Grid trigger.**

| Function | Blueprint | Trigger type | Binding detail |
| --- | --- | --- | --- |
| `health` | `function_app.py` | HTTP (GET) | anonymous liveness probe |
| `batch_start` | `batch_start/blueprint.py` | HTTP (POST `/api/batch_start`) | fans blobs under a prefix onto the doc-processing queue |
| `batch_push` | `batch_push/blueprint.py` | **Storage Queue** | `QueueMessage` on `%AZURE_DOC_PROCESSING_QUEUE%` (`doc-processing`); AAD-identity `AzureWebJobsStorage__*` connection; re-raises → poison queue |
| `add_url` | `add_url/blueprint.py` | HTTP (POST `/api/add_url`) | one-off URL ingestion |
| `blob_event` | `blob_event/blueprint.py` | **Storage Queue** | `QueueMessage` on the fixed `blob-events` queue; Event Grid system topic delivers `BlobCreated`/`BlobDeleted` INTO this queue (queue destination, not an EventGrid function trigger — ADR 0028); re-raises → poison queue |
| `search_skill` | `search_skill/blueprint.py` | HTTP (POST `/api/search_skill`) | AI Search custom WebApiSkill called by the indexer per record batch |

`host.json` (`src/functions/host.json`): extension bundle `[4.*, 5.0.0)`, `extensions.queues.messageEncoding = "none"`. No blob-trigger config, no scale-controller-specific config.

Key consequence for the host decision: because ingestion from blob writes flows through **Event Grid → queue → Queue trigger** (not a native Blob trigger), the well-known "Blob Storage Trigger auto-scaling only works with Event Grid source" limitation on Functions-on-ACA does NOT bite CWYD — the CWYD design already uses the Event-Grid-fed queue pattern that ACA recommends.

### B.2 Azure options to run a Functions app as a CUSTOM CONTAINER image — comparison

Authoritative deployment-technology matrix (Microsoft Learn, "Deployment technologies in Azure Functions", <https://learn.microsoft.com/en-us/azure/azure-functions/functions-deployment-technologies>):

| Deployment technology | Flex Consumption | Consumption | Elastic Premium | Dedicated (App Service) | Container Apps |
| --- | --- | --- | --- | --- | --- |
| One deploy (zip) | ✔ | | | | |
| Zip deploy | | ✔ | ✔ | ✔ | |
| **Docker container** | ❌ | Linux-only | Linux-only | Linux-only | ✔ |

So **Flex Consumption cannot host a custom container at all** (confirmed by Microsoft: Functions-on-ACA overview lists Flex "Custom container support: ❌ Limited (no bring your own container)"). Custom containers are supported only on Container Apps, Elastic Premium, and Dedicated (all Linux-only).

Per-option evaluation for the CWYD trigger set (HTTP + Queue, no blob/timer):

| Host option | Custom container image? | KEDA / event-driven scale for queue+HTTP? | azd deploy support | Modern recommended path? |
| --- | --- | --- | --- | --- |
| **Azure Functions on Azure Container Apps** (`Microsoft.App/containerApps`, `kind=functionapp`) | ✅ Yes — bring-your-own image | ✅ Yes — KEDA auto-configured from trigger config; Queue Storage is a supported pull scaler (scale-to-zero → 1000); HTTP scaler needs ingress enabled | ✅ Yes — via `host: containerapp` (azd builds+pushes image, updates the `Microsoft.App/containerApps` revision regardless of `kind`) | ✅ **Yes** — Microsoft's explicitly recommended approach for new containerized-Functions workloads |
| Functions Premium (Elastic Premium `EP1`) with container | ✅ Yes (Linux) | ✅ Event-driven scale (Functions scale controller, not KEDA) | ⚠️ Partial — azd `host: function` is zip-deploy-only (see below); a container Premium app is NOT deployable through the azd function target. Would require `az functionapp config container set` outside azd | ⚠️ Legacy relative to ACA; webhook CD unsupported on Elastic Premium containers |
| Functions Dedicated (App Service plan) with container | ✅ Yes (Linux) | ❌ No auto/event-driven scale — you manage scale-out manually | ⚠️ Same azd gap as Premium (zip-only function target) | ❌ Not recommended for event-driven RAG ingestion (no scale-to-zero, manual scale) |

**azd support is the decisive constraint.** The azure.yaml schema (`https://raw.githubusercontent.com/Azure/azure-dev/main/schemas/v1.0/azure.yaml.json`) groups `function` with "Traditional hosts (non-container only)" and explicitly disables container properties:

```json
{ "comment": "Traditional hosts (non-container only) - require project, disable container-specific properties",
  "if": { "properties": { "host": { "enum": ["function", "springapp", "staticwebapp"] } } },
  "then": { "required": ["project"], "properties": { "image": false, "docker": false, "k8s": false, "apiVersion": false, "env": false } } }
```

azd's function target source (`Azure/azure-dev` `cli/azd/pkg/project/service_target_functionapp.go`) only ever does zip deploy — `DeployFunctionAppUsingZipFileFlexConsumption` (Flex) or `DeployFunctionAppUsingZipFileRegular` (Consumption/Premium/Dedicated). There is **no container path** in the function target. Container deployment through azd lives entirely in the `containerapp` target (`service_target_containerapp.go`), which builds the image, pushes to ACR, and updates a `Microsoft.App/containerApps` revision. A `kind=functionapp` container app is still a `Microsoft.App/containerApps` resource (azd's `isHostResource` includes `Microsoft.App/containerApps`), so `host: containerapp` deploys it natively.

Cited Learn URLs:
- Functions on Container Apps overview: <https://learn.microsoft.com/en-us/azure/container-apps/functions-overview> (custom container ✅, KEDA scale-to-zero→1000, ACR managed-identity pull, AzureWebJobsStorage managed identity, `kind=functionapp`, "recommended for most new workloads").
- Work with Functions in containers (Container Apps pivot): <https://learn.microsoft.com/en-us/azure/azure-functions/functions-how-to-custom-container> (the "Native Azure Functions Support in Azure Container Apps" banner recommending the ACA approach).
- Deployment technologies matrix (Flex = no Docker container): <https://learn.microsoft.com/en-us/azure/azure-functions/functions-deployment-technologies>
- ACA `kind=functionapp` Bicep/ARM sample: <https://github.com/Azure/azure-functions-on-container-apps/tree/main/samples/ACAKindfunctionapp>
- azd azure.yaml schema (host enum + host-specific `allOf` rules): <https://raw.githubusercontent.com/Azure/azure-dev/main/schemas/v1.0/azure.yaml.json>

### B.3 Recommendation — Azure Functions on Azure Container Apps (`kind=functionapp`)

Recommend **Azure Functions on Azure Container Apps**. Justification against the CWYD constraints:
- **Trigger set fit:** HTTP + Queue Storage triggers are both first-class KEDA scalers on ACA; scale-to-zero works for the queue consumers and the HTTP endpoints. The Event-Grid-fed-queue design sidesteps the only relevant ACA trigger caveat (blob-trigger auto-scale).
- **KEDA scaling:** auto-configured from trigger config — no manual scale rules. Premium uses a different (non-KEDA) scaler; Dedicated has no auto-scale at all.
- **azd support:** the ONLY container option azd can deploy end-to-end, via the same `host: containerapp` target the backend already uses. Premium/Dedicated containers are not deployable through azd's function target.
- **Hard Rule #10 (minimal change):** collapses onto the SAME primitive as the backend (`Microsoft.App/containerApps`), the SAME environment (`cae-<suffix>`), the SAME registry + UAMI + AcrPull grant. No new resource type, no new deployment mechanism, no new IaC pattern — a net reduction (kills the App Service Plan, the Flex plan, the Flex deployment-container config, and the deployment-package RBAC).
- **Managed identity posture preserved:** ACR pull + `AzureWebJobsStorage__*` identity connection are both supported with the shared UAMI, keeping the no-keys / no-Key-Vault posture (Hard Rule #7).

### B.4 Exact changes for Functions-on-ACA

#### B.4a `azure.yaml` — function service `host:` + docker vs prepackage

Replace the `function` service block (lines 143–180) with a container block. The `host: containerapp` target builds the image and updates the revision; the prepackage zip hook is no longer needed for deployment BUT the staging logic it performs (nesting blueprints under a `functions/` package + copying `backend/`) still has to happen — either inside the Dockerfile or via the retained hook feeding the Dockerfile. Two options:

Option 1 (minimal diff — keep `prepackage_function.py`, thin Dockerfile copies its output):

```yaml
  function:
    project: ./src/functions       # or keep ./build-functions; context must reach the staged tree
    language: py
    host: containerapp
    docker:
      path: ../../docker/Dockerfile.functions
      context: ../..
      target: prod                 # new prod stage that COPYs build-functions/ -> /home/site/wwwroot
      remoteBuild: true
    hooks:
      prepackage:                   # retained: stages build-functions/ before the image build
        posix: { shell: sh,   run: ../scripts/prepackage-function.sh }
        windows: { shell: pwsh, run: ../scripts/prepackage-function.ps1 }
```

Option 2 (cleaner end-state — self-contained Dockerfile does the staging, drop `prepackage_function.py` + `build-functions/` + the hook). Preferred for a clean modular end-state matching the backend's self-contained Dockerfile. The Dockerfile's build stage rearranges `src/functions/*` into the `functions/` subpackage layout and copies `src/backend`.

What happens to `build-functions/` + `prepackage_function.py`: under Option 1 they stay (the zip-layout staging still runs, feeding the container build). Under Option 2 both are deleted along with the prepackage hook and the `prepackage-function.{sh,ps1}` wrappers — a net simplification. Either way, the `services.function.project` no longer needs to point at `build-functions/` for a zip; with a self-contained Dockerfile it can point back at `./src/functions` with `docker.context: ../..`.

#### B.4b Bicep resource change

Delete: `functionApp` (AVM web/site, L2183), `functionPlan` (AVM serverfarm, L2164, `FC1`), and the Flex-specific `functionAppConfig` block inside `functionApp` (`deployment.storage` → deployment-package container + `runtime` + `scaleAndConcurrency.alwaysReady`). Also delete `flexDeploymentRole` (L2331, Storage Blob Data Owner for the Flex package upload) — a container pulls its image from ACR, so the deployment-package blob container + its Owner grant are no longer part of function deploy. The `deployment-package` container itself (`deploymentContainerName`, storage module L1145) can be removed too, unless kept for other reasons.

Add: a `functionContainerApp` module cloned from `backendContainerApp`, with `kind: 'functionapp'` and the function's app settings as `env`. The AVM module `avm/res/app/container-app` DOES expose a `kind` param (allowed values include `'functionapp'`; there is a dedicated `function-optimized` e2e test that sets `kind: 'functionapp'`). BUT the `kind` param was added in a version NEWER than the backend's pinned `0.22.1` (the `kind`-supporting revision uses container-app API `2025-02-02-preview`/`2026-01-01`). So either (a) bump BOTH backend and function to the newer AVM container-app version that supports `kind`, or (b) author the function as a raw `Microsoft.App/containerApps@2025-02-02-preview` resource with `kind: 'functionapp'` (mirroring the official ACAKindfunctionapp sample). Recommendation: (a) bump the shared AVM version so both apps use the same module (keeps the "clone the backend block" symmetry); flag the version bump as a change to validate.

Function container app properties (clone backend + these deltas):
- `kind: 'functionapp'`
- `name`: `ca-func-<suffix>` (new var; replaces `functionAppName = 'func-<suffix>'`)
- `tags`: `union(allTags, { 'azd-service-name': 'function' })`
- `environmentResourceId`: shared `containerAppsEnv.outputs.resourceId`
- `managedIdentities`: shared UAMI
- `registries`: shared ACR + UAMI (AcrPull already granted)
- `ingressTargetPort: 80` (the Functions Python base image listens on **80**; the Learn doc confirms containerized function apps monitor port 80 by default, overridable via `WEBSITES_PORT`)
- `ingressExternal: !enablePrivateNetworking` (HTTP triggers `batch_start`/`add_url`/`search_skill` must be reachable — `search_skill` is called by the AI Search indexer; ingress is ALSO required for KEDA auto-scaling per the ACA docs)
- `scaleSettings`: `minReplicas` ≥ 1 for the queue consumers to mirror the current Flex `alwaysReady: [batch_push:1, blob_event:1]` (avoids scale-from-zero latency on the first queued message); `maxReplicas` 40/100 to match the Flex `maximumInstanceCount`. Setting `minReplicas: 0` would restore true scale-to-zero at the cost of queue cold-start latency — a deliberate trade-off to decide.
- `containers[0].env`: carry over the SAME app settings the Flex `functionApp.siteConfig.appSettings` binds (identity, Foundry endpoints, DB routing, storage wiring), EXCEPT the Flex-only knobs — see B.4d.

#### B.4c `Dockerfile.functions` — currently compose-only; needs a prod path

`docker/Dockerfile.functions` (quoted in full):

```dockerfile
# Azure Functions dev image — Python 3.11 + uv
FROM mcr.microsoft.com/azure-functions/python:4-python3.11
ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    PYTHONPATH="/home/site/wwwroot" \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv
RUN pip install --no-cache-dir uv
WORKDIR /home/site/wwwroot
COPY src/functions/pyproject.toml src/functions/uv.lock* ./
RUN uv sync --frozen --no-install-project || uv sync --no-install-project || true
COPY src/functions /home/site/wwwroot
COPY src/backend   /home/site/wwwroot/backend
ENV PATH="/opt/venv/bin:$PATH"
```

Assessment — NOT reusable as-is for azd deploy. Two problems:
1. **Import-layout mismatch.** The blueprints import `from functions.<sub>.<mod> import ...` (e.g. `from functions.add_url.blueprint import bp`). That requires a `functions/` PACKAGE directory at the deploy root (`/home/site/wwwroot/functions/add_url/...`). This Dockerfile does `COPY src/functions /home/site/wwwroot`, which flattens the blueprint subpackages to the wwwroot ROOT (`/home/site/wwwroot/add_url/...`) with `function_app.py` at root — so `from functions.add_url` would NOT resolve. This is exactly the layout problem `prepackage_function.py` exists to solve (it stages `function_app.py` + `host.json` at root, blueprint subpackages nested under `wwwroot/functions/`, and `backend/` at `wwwroot/backend/`). The dev compose only "works" because of how it is mounted; it is not a correct deploy layout.
2. **Deps via `uv sync` into `/opt/venv`** rather than the Functions-host-expected site path. For a deploy image the Functions host resolves the worker's packages; the Flex path used a generated `requirements.txt`. A prod image should `pip install -r requirements.txt` (generated from `pyproject.toml [project.dependencies]`, same source `prepackage_function.py` uses) into the image's Python so the Functions Python worker imports them.

Fix — add a `prod` stage (or replace the file) that reproduces the `prepackage_function.py` layout. Cleanest self-contained form (Option 2 from B.4a):

```dockerfile
FROM mcr.microsoft.com/azure-functions/python:4-python3.11 AS prod
ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true
WORKDIR /home/site/wwwroot
# entry + host config at the deploy root
COPY src/functions/function_app.py src/functions/host.json ./
# blueprint subpackages nested under functions/ so `from functions.<sub>` resolves
COPY src/functions/add_url      ./functions/add_url
COPY src/functions/batch_push   ./functions/batch_push
COPY src/functions/batch_start  ./functions/batch_start
COPY src/functions/blob_event   ./functions/blob_event
COPY src/functions/search_skill ./functions/search_skill
COPY src/functions/core         ./functions/core
RUN printf '"""Pillar: Stable Core\nPhase: 6\n"""\n' > ./functions/__init__.py
# shared backend tree
COPY src/backend ./backend
# deps (single source: v2/pyproject.toml [project.dependencies])
COPY requirements.functions.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
```

(If Option 1 is chosen instead, the prod stage is simply `COPY build-functions /home/site/wwwroot` after the retained prepackage hook stages `build-functions/`.) Either way the base image `mcr.microsoft.com/azure-functions/python:4-python3.11` is correct for Functions-on-ACA and already listens on port 80.

#### B.4d App settings — Flex-specific vs container-host differences

Current Flex `functionApp` app settings (L2253+) and their disposition on a `kind=functionapp` container:

| Setting (Flex) | On Functions-on-ACA container |
| --- | --- |
| `AzureWebJobsStorage__accountName` / `__credential=managedidentity` / `__clientId` | **KEEP unchanged** — identity-based host storage is still mandatory (every Functions-on-ACA app must be linked to a storage account for triggers/state); managed-identity connection is supported |
| `FUNCTIONS_EXTENSION_VERSION = ~4` | KEEP (or rely on the base image's `4-python3.11`) |
| Flex `functionAppConfig.runtime { name: python, version: 3.11 }` | **DROP** — runtime comes from the container base image, not `functionAppConfig` |
| Flex `functionAppConfig.deployment.storage` (deployment-package blobContainer + UAMI auth) | **DROP** — the image is pulled from ACR, not a deployment blob |
| Flex `functionAppConfig.scaleAndConcurrency.alwaysReady` | **REPLACE** with ACA `scaleSettings.minReplicas` ≥ 1 for the queue consumers |
| `FUNCTIONS_WORKER_RUNTIME` | On ACA set explicitly (`python`) — the ACA sample sets `FUNCTIONS_WORKER_RUNTIME`; Flex forbade it, ACA/other plans require/accept it |
| All the CWYD env (`AZURE_CLIENT_ID`, `AZURE_UAMI_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_ENVIRONMENT=production`, Foundry endpoints, `AZURE_DB_TYPE`, `AZURE_INDEX_STORE`, `AZURE_COSMOS_ENDPOINT`, `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_POSTGRES_ENDPOINT`, `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME`, `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_DOCUMENTS_CONTAINER`, `AZURE_DOC_PROCESSING_QUEUE`, `APPLICATIONINSIGHTS_CONNECTION_STRING`) | **KEEP unchanged** — these are the app's own settings, moved verbatim into the container app `env` array |
| `WEBSITE_*` (Flex/App-Service platform knobs) | none are currently set beyond the above; the container host does not need `WEBSITE_RUN_FROM_PACKAGE`, `WEBSITES_ENABLE_APP_SERVICE_STORAGE`, etc. Set `WEBSITES_PORT` only if the container listens on a non-80 port (it listens on 80, so not needed) |

### B.5 Risks / blockers for the function move

- **Storage/queue trigger wiring: PRESERVED.** The `doc-processing` and `blob-events` queues live on the same storage account and are addressed by the same identity-based `AzureWebJobsStorage__*` app settings. Moving the compute from Flex to an ACA `kind=functionapp` container does not change the queue triggers or their bindings. KEDA on ACA polls the same queues.
- **Poison-queue behavior: PRESERVED.** `batch_push` and `blob_event` re-raise on failure (via `log_queue_errors`); the Functions host retry → poison-queue policy is a runtime behavior of the Functions host, which is the same host inside the container. The `*-poison` queues already exist in bicep. No change.
- **Event Grid subscription: UNCHANGED and independent of the function host.** `blobCreatedSubscription` (L2406) delivers `BlobCreated`/`BlobDeleted` to the `blob-events` QUEUE (a StorageQueue destination with the system topic's MI), NOT to a function. It has zero coupling to how the function compute is hosted. No change needed; the `blob_event` queue trigger consumes as before.
- **Deployment-container RBAC (`flexDeploymentRole`, Storage Blob Data Owner): REMOVED.** This grant + the `deployment-package` container existed only for the Flex package upload. On ACA the image comes from ACR. Removing them is correct, not a regression — but confirm no other resource references the deployment-package container. AcrPull on the UAMI (already granted via the `containerRegistry` role assignment, L1751+) now covers the function image pull.
- **KEDA scale rules vs alwaysReady:** Functions-on-ACA auto-generates KEDA rules; to keep the queue consumers warm (current Flex `alwaysReady: 1`), set `minReplicas: 1`. That forgoes scale-to-zero for the function app. If scale-to-zero is desired, accept queue cold-start latency. Ingress MUST be enabled for auto-scaling (it is, for the HTTP triggers).
- **AVM module version bump:** `kind: 'functionapp'` requires an `avm/res/app/container-app` version newer than the backend's `0.22.1`. Bumping the shared module version affects the backend too — re-validate the backend container app after the bump (API version moves to `2025-02-02-preview`/`2026-01-01`).
- **Import-layout correctness:** the deploy image MUST reproduce the `functions/`-subpackage nesting (B.4c) or the app fails at import time. This is the single most likely implementation bug.
- **`search_skill` reachability:** the AI Search indexer calls `POST /api/search_skill` over the network — external ingress (or the private CAE path) must expose it, exactly as the Flex Function App FQDN did. Confirm any AI Search skillset config that references `AZURE_FUNCTION_APP_URL` (output L2674) is repointed to the new container app FQDN.

---

## PART C — Cross-cutting

### C.1 All three services push to the SAME provisioned ACR; Basic SKU + shared AcrPull are sufficient

After the change, backend + frontend + function all build+push to `cr<suffix>` (`containerRegistryName = take('cr${replace(solutionSuffix, '-', '')}', 50)`, L1622). Three repos: `cwyd-backend`, `cwyd-frontend`, `cwyd-functions`.

- **ACR SKU (Basic) supports 3 repos:** yes — repository count is not limited by SKU (Basic/Standard/Premium differ on included storage, throughput, geo-replication, private link, not repo count). Three small images fit comfortably in Basic's 10 GB included storage. No SKU change needed. Only concern to watch: Basic throughput/concurrent-build limits under heavy CI, irrelevant for `azd deploy`.
- **AcrPull covers all three:** the `containerRegistry` module grants AcrPull (`7f951dda-4ed3-4680-a7ca-43fe172d538d`) to the shared UAMI at the REGISTRY scope (L1751+), so it applies to every repo in the registry. The frontend and function container apps reuse the same UAMI, so no new role assignment is required. (Functions-on-ACA supports managed-identity ACR pull.)

### C.2 The Container Apps Environment already exists and is shareable by all three

`containerAppsEnv` (AVM `avm/res/app/managed-environment:0.13.2`) is created once, L1653–1690 (`containerAppsEnvName = 'cae-${solutionSuffix}'`, L1618). Excerpt:

```bicep
module containerAppsEnv 'br/public:avm/res/app/managed-environment:0.13.2' = {   // L1653
  name: take('avm.res.app.managed-environment.${solutionSuffix}', 64)
  params: {
    name: containerAppsEnvName
    zoneRedundant: enableRedundancy
    internal: enablePrivateNetworking
    workloadProfiles: [ { name: 'Consumption', workloadProfileType: 'Consumption' } ]
    appLogsConfiguration: { destination: 'azure-monitor' }
  }
}
resource containerAppsEnvResource 'Microsoft.App/managedEnvironments@2024-03-01' existing = {  // L1692
  name: containerAppsEnvName
  dependsOn: [ containerAppsEnv ]
}
```

Both the frontend container app AND the function container app join it via `environmentResourceId: containerAppsEnv.outputs.resourceId` — the same value the backend uses. The wildcard private DNS zone (`caeDnsZone`, L1719) already covers "any app in this env" for the internal/private profile, so frontend + function get in-VNet reachability for free. No new environment resource.

### C.3 Per-service change table

| Service | Current host | Target host | `azure.yaml` edit | Bicep edit | Dockerfile status | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| backend | Container App (`Microsoft.App/containerApps`, ACR remote build) — DONE | unchanged | none (only re-validate after AVM container-app version bump) | none, except possible AVM `container-app` version bump shared with function | `Dockerfile.backend` — ready, unchanged | Low |
| frontend | App Service build-from-source (`avm/res/web/site`, `PYTHON|3.11`, Oryx) | Container App (`Microsoft.App/containerApps`) | `host: appservice`→`containerapp`; add `docker` block (`Dockerfile.frontend`, `target: prod`, `remoteBuild: true`, NO `VITE_BACKEND_URL` buildArg); drop `dist:` + prepackage hook | delete `frontendWebApp` (L2020) → add `frontendContainerApp` cloned from backend (`ingressTargetPort: 80`, env `BACKEND_API_URL`); after function move, delete `appServicePlan` (L2005) + its vars; update `AZURE_FRONTEND_URL` output (L2671) | `Dockerfile.frontend` `prod` stage — READY as-is (uvicorn, port 80, `/config`) | Low–Med (CORS/frontend-origin backend setting to verify; VNet `web` subnet becomes unused) |
| function | Function App on Flex Consumption (`avm/res/web/site`, `kind functionapp,linux`, `FC1`, `functionAppConfig`) | Azure Functions on Azure Container Apps (`Microsoft.App/containerApps`, `kind: functionapp`) | `host: function`→`containerapp`; add `docker` block (`Dockerfile.functions`, `target: prod`, `remoteBuild: true`); drop/keep prepackage hook per Option 1/2 | delete `functionApp` (L2183) + `functionPlan` (L2164) + `flexDeploymentRole` (L2331) + deployment-package container; add `functionContainerApp` (`kind: functionapp`, `ingressTargetPort: 80`, `minReplicas`≥1, carry app settings minus Flex-only knobs); update `AZURE_FUNCTION_APP_URL`/`AZURE_FUNCTION_APP_NAME` outputs (L2674/L2677); requires AVM container-app version supporting `kind` | `Dockerfile.functions` — NOT ready; needs a `prod` stage reproducing the `functions/`-subpackage layout (or a thin stage over `build-functions/`); base image already listens on 80 | **High** (import-layout correctness; AVM version bump; alwaysReady→minReplicas; drop Flex deployment RBAC) |

---

## Key discoveries (with evidence)

- Frontend is currently App Service build-from-source, not a container (`azure.yaml` L114–142 `host: appservice`; `main.bicep` L2020 `frontendWebApp` `kind: 'app,linux'` + `linuxFxVersion: 'PYTHON|3.11'`). `Dockerfile.frontend` already ships a `prod` stage (uvicorn, `EXPOSE 80`) suitable for ACA.
- The SPA resolves the backend origin at RUNTIME from `/config`→`BACKEND_API_URL` (`runtimeConfig.tsx`, `frontend_app.py`); `VITE_BACKEND_URL` is only a build-time fallback. → set `BACKEND_API_URL` as a container env var, do NOT bake a build-arg.
- Function triggers are HTTP + Storage Queue only (no blob/timer/direct-EventGrid). Event Grid delivers to the `blob-events` QUEUE, consumed by the `blob_event` queue trigger (ADR 0028). → the "ACA blob-trigger auto-scale only with Event Grid" caveat does not apply.
- Flex Consumption cannot host a custom container (Learn deployment-tech matrix + Functions-on-ACA overview). Custom containers = Container Apps / Elastic Premium / Dedicated (Linux) only.
- azd's `host: function` is zip-deploy-only; the azure.yaml schema disables `docker`/`image`/`env` for `host: function`. → containerized Functions via azd MUST use `host: containerapp` against a `Microsoft.App/containerApps` `kind: functionapp` resource. This is Microsoft's recommended modern path AND the minimal-change path (collapses onto the backend's primitive/env/registry/UAMI).
- AVM `avm/res/app/container-app` supports a `kind` param (incl. `'functionapp'`, with a `function-optimized` e2e test), but in a version newer than the backend's pinned `0.22.1` (kind-supporting revision → container-app API `2025-02-02-preview`/`2026-01-01`). → bump the shared module version, or author the function as a raw `Microsoft.App/containerApps` resource.
- ACR Basic supports 3 repos; AcrPull is granted to the shared UAMI at registry scope (L1751+), covering all three images. The `cae-<suffix>` environment (L1653) is shared by all three apps.
- `Dockerfile.functions` is dev/compose-only and its `COPY src/functions /home/site/wwwroot` does NOT reproduce the `functions/`-subpackage nesting the blueprints' `from functions.<sub>` imports require — a prod image must replicate `prepackage_function.py`'s staging.

---

## Recommended next research (not done this session)

- [ ] Confirm the exact AVM `avm/res/app/container-app` version that first exposes `kind` (and whether `0.22.1` in-repo already does) — determines version-bump vs raw-resource for the function.
- [ ] Grep the backend for any CORS allow-list / frontend-origin env binding (`backend.core.settings`, FastAPI CORS middleware) that must repoint from the App Service FQDN to the frontend Container App FQDN.
- [ ] Locate any AI Search skillset config that references `AZURE_FUNCTION_APP_URL` and confirm it repoints to the new function container app FQDN.
- [ ] Confirm whether `v2/src/functions/backend/` (seen in `list_dir`) is a gitignored build artifact vs tracked source, to avoid double-copying `backend/` in the prod Dockerfile.
- [ ] Verify azd hook ordering for `host: containerapp` (prepackage → docker build) if Option 1 (retain prepackage_function.py feeding the Dockerfile) is chosen.
- [ ] Confirm `scripts/post-provision.*` summary + any pytest asserting on `AZURE_FRONTEND_URL` / `AZURE_FUNCTION_APP_URL` output expressions after the host swaps.

## Clarifying questions for the user

- Scale-to-zero vs warm queue consumers for the function: keep `minReplicas: 1` (mirror Flex `alwaysReady`, no cold-start) or `minReplicas: 0` (true scale-to-zero, accept queue cold-start latency)?
- Function Dockerfile strategy: Option 1 (retain `prepackage_function.py` + `build-functions/` + hook, thin Dockerfile copies the staged tree — minimal diff) or Option 2 (self-contained prod Dockerfile does the staging, delete `prepackage_function.py` + `build-functions/` + hook — cleaner end-state)?
- AVM approach for the function: bump the shared `avm/res/app/container-app` version so both backend + function get `kind` support, or author the function as a raw `Microsoft.App/containerApps` `kind: functionapp` resource and leave the backend module version pinned?

## References (external, cited)

- Azure Functions on Azure Container Apps overview — <https://learn.microsoft.com/en-us/azure/container-apps/functions-overview>
- Work with Azure Functions in containers (Container Apps pivot) — <https://learn.microsoft.com/en-us/azure/azure-functions/functions-how-to-custom-container>
- Deployment technologies in Azure Functions (host × deployment-tech matrix) — <https://learn.microsoft.com/en-us/azure/azure-functions/functions-deployment-technologies>
- ACA `kind=functionapp` Bicep/ARM sample — <https://github.com/Azure/azure-functions-on-container-apps/tree/main/samples/ACAKindfunctionapp>
- azd `azure.yaml` schema (host enum + per-host `allOf` container rules) — <https://raw.githubusercontent.com/Azure/azure-dev/main/schemas/v1.0/azure.yaml.json>
- azd function target (zip-deploy-only) — `Azure/azure-dev` `cli/azd/pkg/project/service_target_functionapp.go`
- AVM container-app `kind` param — `Azure/bicep-registry-modules` `avm/res/app/container-app/main.bicep` + `tests/e2e/function-optimized/main.test.bicep`
