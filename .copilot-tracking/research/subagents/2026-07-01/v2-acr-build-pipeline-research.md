<!-- markdownlint-disable-file -->
# Research: CWYD v2 — ACR provisioning + build→push→deploy loop for backend / frontend / function

Status: Complete
Date: 2026-07-01
Scope: READ-ONLY. Does the v2 infra provision its own ACR and wire an explicit, repeatable build→push→deploy loop that ships UPDATED code every build for backend, frontend, AND function? Compare against CGSA + MACAE. Decisive recommendation.
Baseline read first: .copilot-tracking/research/subagents/2026-06-25/v2-infra-current-state.md

---

## TL;DR (read this first)

1. **The ACR is already provisioned by infra** — module `containerRegistry` (AVM `container-registry/registry:0.12.1`), name `cr<suffix>`, Basic SKU, admin OFF, AcrPull to the shared UAMI, login server exported as `AZURE_CONTAINER_REGISTRY_ENDPOINT`. Q1 answer: **confirmed, done.**
2. **The 2026-06-25 baseline is partly STALE.** Since then the frontend was moved OFF containers. The premise "three images (backend, frontend, function)" **no longer matches the codebase**: today **only the backend is a container image**. The frontend is a **Python App Service build-from-source** (BUG-0081 fix) and the function is a **Flex Consumption ZIP deploy** — by design, neither is an image.
3. **A repeatable loop already exists and ships fresh code every deploy for all three services** — it is `azd deploy` / `azd up`. Backend: `azd` builds the image in ACR (`remoteBuild: true`), pushes, and swaps the revision (fresh `azd-deploy-<timestamp>` tag every run). Frontend: prepackage runs `npm ci && npm run build`, azd zip-deploys. Function: prepackage regenerates `build-functions/` from source, azd zip-deploys to the Flex deployment blob container. **There is no per-image staleness** — every `azd deploy` rebuilds from the working tree.
4. **The function CANNOT be a container** on its current hosting plan. Flex Consumption has a single deploy path (build → zip → blob container); custom Docker containers are **not** a Flex Consumption capability (Microsoft Learn, cited below). Containerizing the function is a hosting-model change (→ Functions on Azure Container Apps, or Premium/Dedicated with a custom image), i.e. Hard Rule #10 (ask first).
5. **v2 already uses the most robust image-reference contract for a clean tenant**: a *hybrid* of parameterized name+tag WITH a public placeholder fallback. First `azd up` boots a pullable placeholder (no image exists yet), then `azd deploy` builds/pushes/swaps; re-provisions compose the real `cr<suffix>/cwyd-backend:<tag>` reference. This is the same chicken-and-egg guard MACAE and CGSA use in their build-from-source modes.

---

## Evidence log — CWYD v2 (exact file:line)

### Q1 — ACR provisioning in v2/infra/main.bicep — CONFIRMED

ACR name variable — v2/infra/main.bicep:1622
```bicep
// ACR name must be globally unique, 5-50 alphanumeric (no dashes).
var containerRegistryName = take('cr${replace(solutionSuffix, '-', '')}', 50)
```

ACR module — v2/infra/main.bicep:1751-1785
```bicep
module containerRegistry 'br/public:avm/res/container-registry/registry:0.12.1' = {
  name: take('avm.res.container-registry.registry.${solutionSuffix}', 64)
  params: {
    name: containerRegistryName
    location: location
    tags: allTags
    enableTelemetry: false
    acrSku: 'Basic'
    acrAdminUserEnabled: false
    publicNetworkAccess: 'Enabled'
    networkRuleSetDefaultAction: 'Allow'
    // Basic-SKU ACR ships this policy disabled, which 401s the
    // App Service / Container App managed-identity -> ACR token exchange
    // even with correct AcrPull RBAC. Enable it durably.
    azureADAuthenticationAsArmPolicyStatus: 'enabled'
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        roleDefinitionIdOrName: '7f951dda-4ed3-4680-a7ca-43fe172d538d'  // AcrPull
        principalType: 'ServicePrincipal'
      }
    ]
  }
}
```

- Module name: `containerRegistry` (AVM `container-registry/registry:0.12.1`).
- Resource name pattern: `cr<suffix-without-dashes>` (matches `cr<suffix>`), capped at 50 chars.
- SKU: **Basic**.
- Admin user: **disabled** (`acrAdminUserEnabled: false`).
- Anonymous pull: **not enabled** (AVM default is off; no `anonymousPullEnabled` param set).
- `azureADAuthenticationAsArmPolicyStatus: 'enabled'` — durable fix for the Basic-SKU managed-identity token-exchange 401 (this is the `ACR-AAD-AS-ARM-BICEP-DEBT` from worklog 2026-06-16, now back-ported into bicep).
- AcrPull (`7f951dda-4ed3-4680-a7ca-43fe172d538d`) granted to the shared UAMI **on the registry** via the module's `roleAssignments`.

Login-server output + name output — v2/infra/main.bicep:2680, 2683
```bicep
@description('Container Registry login server (e.g. cr<SUFFIX>.azurecr.io). `azd deploy` reads this to discover the push target for backend + function images.')
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer

@description('Container Registry resource name. Diagnostic surface only — azd uses the login server above.')
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.name
```

Env var that exposes it: **`AZURE_CONTAINER_REGISTRY_ENDPOINT`** (the login server), plus `AZURE_CONTAINER_REGISTRY_NAME`.

> Note: the output comment says "backend + function images", but the function does NOT actually build an image (see Q2/Q6). The registry is used only by the backend Container App today.

### Q2 — How each service gets its image today

**azure.yaml services** (v2/azure.yaml:104-190):

- **backend** (v2/azure.yaml:105-118): `host: containerapp` + `docker:` block, `path: ../../docker/Dockerfile.backend`, `context: ../..`, **`remoteBuild: true`** (build in ACR, not local Docker). No `target`.
- **frontend** (v2/azure.yaml:119-142): `host: appservice`, **NO `docker:` block**, `dist: ./build-output`, service-scoped `prepackage` hook → `package-frontend.{sh,ps1}`. The inline comment states: *"host: appservice does not support a `docker:` block -- pairing them is the root cause of BUG-0081."*
- **function** (v2/azure.yaml:143-190): `host: function`, **NO `docker:` block**, `project: ./build-functions`, service-scoped `prepackage` hook → `prepackage-function.{sh,ps1}`.

**Backend image reference — parameterized name+tag WITH placeholder fallback (hybrid):**

Params — v2/infra/main.bicep:1634-1642
```bicep
@description('Optional. Login server of the registry hosting the backend image ... Empty until the first provision publishes AZURE_CONTAINER_REGISTRY_ENDPOINT; empty selects a public placeholder image so the first provision can pull.')
param backendContainerRegistryHostname string = ''
@description('Optional. Repository (image) name of the backend container image within the registry.')
param backendContainerImageName string = 'cwyd-backend'
@description('Optional. Tag of the backend container image to deploy.')
param backendContainerImageTag string = 'latest'
```

Image expression — v2/infra/main.bicep:1826-1831
```bicep
image: empty(backendContainerRegistryHostname)
  ? 'mcr.microsoft.com/k8se/quickstart:latest'
  : '${backendContainerRegistryHostname}/${backendContainerImageName}:${backendContainerImageTag}'
```

Managed-identity registry pull — v2/infra/main.bicep:1795-1800
```bicep
registries: [
  {
    server: containerRegistry.outputs.loginServer
    identity: userAssignedIdentity.outputs.resourceId
  }
]
```

azd tag swap — the backend Container App carries `azd-service-name: backend` (v2/infra/main.bicep:1781); `azd deploy` builds + pushes the real image and patches the live revision.

Param binding — v2/infra/main.parameters.json:
```jsonc
"backendContainerRegistryHostname": { "value": "${AZURE_CONTAINER_REGISTRY_ENDPOINT=}" },
"backendContainerImageTag":         { "value": "${AZURE_ENV_IMAGE_TAG=latest}" }
```
(`backendContainerImageName` is NOT bound — it keeps the bicep default `cwyd-backend`.) On a clean first `azd up`, `AZURE_CONTAINER_REGISTRY_ENDPOINT` does not exist yet → hostname empty → placeholder `mcr.microsoft.com/k8se/quickstart:latest`. After the first `azd deploy`, later provisions compose `cr<suffix>.azurecr.io/cwyd-backend:latest`.

**Frontend — Python App Service source-build (NO image):**

- Module `frontendWebApp` (AVM `web/site:0.22.0`) — v2/infra/main.bicep:2022; `frontendAppName = 'app-frontend-${solutionSuffix}'` (line 1993); `kind: 'app,linux'` (line 2027, **not** `app,linux,container`); tag `azd-service-name: frontend` (line 2025).
- Runtime — v2/infra/main.bicep:2074-2075
  ```bicep
  linuxFxVersion: 'PYTHON|3.11'
  appCommandLine: 'uvicorn frontend_app:app --host 0.0.0.0 --port 8000'
  ```
- App settings — v2/infra/main.bicep:2089-2108: `BACKEND_API_URL = 'https://${backendContainerApp.outputs.fqdn}'` (SPA reads it at runtime from `/config`, **no build-time bake**), `WEBSITES_ENABLE_APP_SERVICE_STORAGE=false`, `SCM_DO_BUILD_DURING_DEPLOYMENT=true`, `WEBSITES_PORT=8000`, `ENABLE_ORYX_BUILD=true`.
- No `linuxFxVersion: 'DOCKER|...'`, no placeholder container image. This is a build-from-source App Service — Oryx pip-installs `requirements.txt` then runs uvicorn.

**Function — Flex Consumption ZIP-to-blob (NO image):**

- Module `functionApp` (AVM `web/site:0.22.0`) — v2/infra/main.bicep:2185; `functionAppName = 'func-${solutionSuffix}'` (line 2147); `kind: 'functionapp,linux'` (line 2190); plan `functionsPlanSkuName = 'FC1'` (Flex Consumption); tag `azd-service-name: function`.
- Deployment source — v2/infra/main.bicep (functionAppConfig.deployment):
  ```bicep
  functionAppConfig: {
    deployment: {
      storage: {
        type: 'blobContainer'
        value: '${effectiveStorageBlobEndpoint}${deploymentContainerName}'
        authentication: { type: 'UserAssignedIdentity'; userAssignedIdentityResourceId: ... }
      }
    }
    runtime: { name: 'python'; version: '3.11' }
    scaleAndConcurrency: { ... alwaysReady: [batch_push, blob_event] }
  }
  ```
  The function package is pulled from a blob container using the UAMI. **No image, no `linuxFxVersion` image reference.**

Hosting endpoints outputs — v2/infra/main.bicep:2668-2678: `AZURE_BACKEND_URL`, `AZURE_FRONTEND_URL`, `AZURE_FUNCTION_APP_URL`, `AZURE_FUNCTION_APP_NAME`.

### Q3 — Explicit build/push tooling already present?

**No standalone `az acr build` / `docker build` / `docker push` scripts exist in v2.** The build/push is entirely `azd`-driven. Searched the whole `v2/` tree — the only `az acr build` / `docker build` occurrences are in worklogs (manual break-glass fixes) and `.gitignore`/`.dockerignore` comments.

- v2/Makefile — only `typecheck` (`uv run pyright`), `test` (`uv run pytest`), `lint` (`black` + `flake8`). **No deploy / build-image / push target.**
- v2/package.json scripts — `build` / `dev` / `test` / `lint` (frontend workspace only). No image build/push.
- v2/scripts/ — three packaging helpers, none of which build or push a container:
  - v2/scripts/package_frontend.py — stages the App Service deploy artifact at `src/frontend/build-output/` (copies `dist/` + `frontend_app.py` + a pinned `requirements.txt`). Wrappers `package-frontend.{sh,ps1}` run `npm ci && npm run build` first.
  - v2/scripts/prepackage_function.py — regenerates `v2/build-functions/` from `src/functions/` + `src/backend/` on every run (function_app.py + host.json + `functions/` subpackage + `backend/` subpackage + generated `requirements.txt` + `.funcignore`).
  - v2/scripts/upload_sample_data.py — postdeploy sample-data seed (NOT a build tool).
- v2/docker/Dockerfile.frontend + v2/docker/Dockerfile.functions — used **ONLY** by `docker-compose.dev.yml` / `docker-compose.smoke.yml` (v2/docker/docker-compose.dev.yml `build.dockerfile: docker/Dockerfile.frontend` / `Dockerfile.functions`). **azd never uses them** (the frontend + function services have no `docker:` block).
- v2/docker/Dockerfile.backend — used by BOTH `azd` (`services.backend.docker`) and compose.

**How the image actually gets built + pushed today:** `azd deploy backend` (or `azd up`) reads the `docker:` block, does a **remote build in ACR** (`remoteBuild: true`), pushes with a fresh `azd-deploy-<timestamp>` tag, and updates the `azd-service-name: backend` Container App revision. Confirmed live in v2/docs/worklog/2026-06-16.md:99 (`azd deploy --all → SUCCESS ... backend, frontend, and function all Done`) and the same worklog's post-mortem noting the backend `host: containerapp` "builds + pushes correctly" with `azd-deploy-*` tags, whereas the *then-current* frontend `host: appservice` + `docker:` combo silently did a zip push and never built its image — the defect that triggered the BUG-0081 refactor to the current source-build frontend.

**Repeatable "ships updated code every build" confirmation:**
| Service | Rebuild trigger each `azd deploy` | Fresh code guaranteed? |
|---|---|---|
| backend | ACR remote build of Dockerfile.backend from working tree; new `azd-deploy-<ts>` tag | YES |
| frontend | prepackage `npm ci && npm run build` → new `dist/` → zip-deploy | YES |
| function | prepackage regenerates `build-functions/` from `src/` → zip-deploy to blob | YES |

### Q4 — Placeholder-swap vs parameterized `SERVICE_<NAME>_IMAGE_NAME`, and clean-tenant one-shot behavior

v2 uses **neither pure pattern — it uses a hybrid** (parameterized ref + placeholder fallback), which is the most reliable clean-tenant contract. The two "pure" patterns and their chicken-and-egg behavior:

- **(a) Pure placeholder-swap (azd canonical for `host: containerapp`).** Bicep seeds a throwaway public image; the `azd-service-name` tag tells azd which resource maps to which service; `azd deploy` builds → pushes → patches the revision. First `azd up` always succeeds (placeholder is pullable before any image exists). This is what MACAE `main_custom.bicep` and the azd Container Apps reference do. Downside: bicep never *names* the real image, so a `provision`-only run leaves the placeholder in place until the next `deploy`.
- **(b) Pure parameterized `image: '${host}/${name}:${tag}'`.** Bicep references the built image directly (MACAE `main.bicep` + CGSA `main.bicep` do this against a **pre-built shared public ACR** where the image already exists). On a clean tenant where you build your OWN image, this has a hard chicken-and-egg: the image doesn't exist at first `provision`, so the container/App Service fails to pull. CGSA/MACAE solve it two ways: (i) point at a Microsoft-owned registry that ships the image (`biabcontainerreg.azurecr.io`, `contentgencontainerreg`), or (ii) guard the resource (`shouldDeployACI = !empty(imageTag) && imageTag != 'none'`) so it isn't deployed until a tag exists.
- **(c) v2 hybrid (current).** `empty(hostname) ? placeholder : '${host}/${name}:${tag}'`. First `azd up` → hostname empty → placeholder → provision succeeds → `azd deploy` builds/pushes/swaps → **re-provisions compose the real `cr<suffix>/cwyd-backend:<tag>` reference** because `backendContainerRegistryHostname` is now bound to the published `AZURE_CONTAINER_REGISTRY_ENDPOINT`. This gives BOTH first-run safety AND a bicep that references the built image by name+tag after the first cycle. **This is the most reliable for a clean-tenant one-shot** and is already implemented.

Standard azd guidance: for `host: containerapp` with a `docker:` block, azd owns build+push+tag-swap; the bicep placeholder must simply be *pullable* at provision time. You do NOT need a `SERVICE_*_IMAGE_NAME` parameter — the `azd-service-name` tag is the contract. (v2 layers the parameterized ref on top purely so a `provision`-only reconcile reproduces the real image reference instead of reverting to the placeholder.)

### Q5 — Frontend `host: appservice` + `docker:` (the flagged combo) — ALREADY REMOVED

The 2026-06-25 baseline described `host: appservice` + `docker:` with a `VITE_BACKEND_URL` build-arg bake. **That combination no longer exists** — it was BUG-0081 and is fixed. The frontend is now `host: appservice` build-from-source (v2/azure.yaml:119-142). Implications for the user's question:

- azd officially supports `host: appservice` **either** as build-from-source (Oryx, no Dockerfile — current v2) **or** as a container (`kind: app,linux,container` + `linuxFxVersion: DOCKER|...`). Mixing `host: appservice` with a `docker:` block in `azure.yaml` is the unsupported case that caused BUG-0081 (azd silently zip-pushed instead of building the image).
- **`host: containerapp` is the more reliable azd container target.** If the user genuinely wants the frontend as a rebuilt-every-deploy *image*, moving it to `host: containerapp` (like the backend, and like MACAE `main.bicep`'s frontend which uses `app,linux,container` + `DOCKER|...`) is the clean path. That entails:
  - azure.yaml: change frontend to `host: containerapp` + a `docker:` block (`Dockerfile.frontend`, `remoteBuild: true`), drop the `dist:` + `package-frontend` prepackage hook.
  - bicep: replace the `frontendWebApp` App Service + App Service Plan with a second `container-app` module in the existing `cae-<suffix>` environment (reuse the ACR + UAMI AcrPull), placeholder+parameterized image like the backend, `azd-service-name: frontend`.
  - **`VITE_BACKEND_URL` bake implication:** a container frontend bakes `VITE_BACKEND_URL` at image build (Dockerfile.frontend `build` stage `ARG VITE_BACKEND_URL`). But the backend FQDN isn't known until the backend is provisioned — a classic ordering problem. The current source-build frontend AVOIDS this by reading the backend URL at runtime from `/config` (fed by `BACKEND_API_URL`). If moving to a container, either keep the runtime `/config` approach (recommended — no rebuild-on-URL-change) or accept a two-phase deploy (provision backend → capture `AZURE_BACKEND_URL` → build frontend image with the bake).
- **Net:** the frontend is currently the *most reliable* it has been (source-build, runtime config, no image bake). Switching it back to a container is only warranted if "three images" is a hard product requirement; it is not necessary for "ships updated code every build" (source-build already does that).

### Q6 — Can/should the function be a container? Flex Consumption reality

**No — not on its current plan.** Microsoft Learn (https://learn.microsoft.com/azure/azure-functions/flex-consumption-plan, "Deployment"):

> "Deployments in the Flex Consumption plan follow a single path. There's no longer a need for app settings to influence deployment behavior. You build and zip your project code into an application package, and then deploy it to a blob storage container. On startup, your app gets the package and runs your function code from this package."

Custom Docker containers are **not** listed anywhere as a Flex Consumption capability, and "In-place migration of an existing function app from another hosting plan to the Flex Consumption plan isn't supported" (Considerations). The single deploy path = build → zip → blob. This exactly matches what v2 does (prepackage regenerates `build-functions/`, azd zip-deploys to the Flex deployment blob container using the UAMI). **ZIP is the correct and only azd pattern for a Python Function on Flex Consumption.**

If a *containerized* function is truly required, the function must leave Flex Consumption for one of:
- **Azure Functions on Azure Container Apps** (custom image, runs in a Container Apps environment — v2 already has `cae-<suffix>`), or
- **Elastic Premium (EP) / Dedicated (App Service) plan** with a custom container image (`kind: functionapp,linux,container`).

Both are hosting-model changes → **Hard Rule #10 (structural, ask the user first)**, and both lose Flex's scale-to-zero + sub-second cold start. `v2/docker/Dockerfile.functions` exists but is compose-only (local dev/smoke); it is NOT wired to any azd deploy path and is NOT a Flex artifact.

### Q7 — see Recommendation section below.

---

## Per-service summary table

| Service | `host:` (azure.yaml) | Image today? | Image reference in bicep | Build tool (repeatable loop) | Ships fresh code each deploy | Gap vs "three rebuilt images" |
|---|---|---|---|---|---|---|
| **backend** | `containerapp` | **YES** — own ACR image | `empty(host) ? mcr.../k8se/quickstart : cr<sfx>/cwyd-backend:<tag>` (main.bicep:1826) | `azd deploy` → ACR remote build (`remoteBuild: true`) → push → `azd-deploy-<ts>` tag swap | YES | none — this IS the target image loop |
| **frontend** | `appservice` (source) | **NO** (by design) | `linuxFxVersion: 'PYTHON\|3.11'` + Oryx build (main.bicep:2074) | `azd deploy` → prepackage `npm ci && npm run build` → zip-deploy | YES | not an image (BUG-0081 removed the container). Optional: move to `host: containerapp` |
| **function** | `function` (Flex FC1) | **NO** (impossible on Flex) | `functionAppConfig.deployment.storage.type: 'blobContainer'` — ZIP to blob | `azd deploy` → prepackage regenerates `build-functions/` → zip-deploy | YES | not an image; Flex Consumption has no custom-container path |

---

## CGSA + MACAE comparison — how the reference accelerators handle ACR + images

Both accelerators ship **two** deploy modes, and the split is the key insight: a *default* mode that pulls **pre-built images from a Microsoft-owned public ACR** (the v1 CWYD `cwydcontainerreg.azurecr.io` model — operator never rebuilds), and a *custom/advanced* mode that **provisions its own ACR and builds from source**. CWYD v2 has adopted the *custom* mode as its only mode.

### MACAE (the closest analogue — it is CWYD v2's direct pattern source)

- **`infra/main.bicep` (default "Quick Deploy"):** pre-built PUBLIC shared ACR.
  - `param backendContainerRegistryHostname string = 'biabcontainerreg.azurecr.io'`, `backendContainerImageName = 'macaebackend'`, `backendContainerImageTag = 'latest_v4'` (also `macaefrontend`, `macaemcp`) — main.bicep:139-161.
  - Backend Container App references the image directly (no placeholder): `image: '${backendContainerRegistryHostname}/${backendContainerImageName}:${backendContainerImageTag}'` — main.bicep:1246.
  - Frontend App Service is a **container**: `kind: 'app,linux,container'` + `linuxFxVersion: 'DOCKER|${frontendContainerRegistryHostname}/${frontendContainerImageName}:${frontendContainerImageTag}'` — main.bicep:1541-1547.
  - This is the **v1-CWYD-equivalent** pattern (images pre-built by Microsoft, pulled by name+tag).
- **`infra/main_custom.bicep` (the "Advanced: Deploy Local Changes" path):** own ACR + build-from-source — **identical to CWYD v2**.
  - Own ACR: `module containerRegistry 'br/public:avm/res/container-registry/registry:0.12.0'`, `name: 'cr${solutionSuffix}'`, `acrSku: 'Basic'`, `acrAdminUserEnabled: false`, `azureADAuthenticationAsArmPolicyStatus: 'enabled'`, AcrPull to UAMI — main_custom.bicep:1196-1216. (CWYD v2's ACR is the same module one minor version newer.)
  - Backend Container App: **placeholder** `image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'` (real ref commented out) + `registries: [{ server: containerRegistry.outputs.loginServer, identity: userAssignedIdentity.outputs.resourceId }]` + `azd-service-name: backend` — main_custom.bicep:1265-1290. (Same placeholder+MI-pull+tag-swap as CWYD v2.)
  - Frontend App Service: **build-from-source**, `kind: 'app,linux'` + `linuxFxVersion: 'python|3.11'` + `appCommandLine: 'python3 -m uvicorn frontend_server:app --host 0.0.0.0 --port 8000'` + `SCM_DO_BUILD_DURING_DEPLOYMENT: 'True'` + `ENABLE_ORYX_BUILD: 'True'` + `WEBSITES_PORT: '8000'` + `BACKEND_API_URL` — main_custom.bicep:1593-1618. **This is exactly CWYD v2's frontend.**
  - Mode switch (docs/DeploymentGuide.md "Advanced: Deploy Local Changes"): rename `azure_custom.yaml → azure.yaml` and `main_custom.bicep → main.bicep`, then `azd up`.
  - Explicit manual build/push is documented as the break-glass path: `az acr build --registry <acr> --image backendmacae:latest .` (docs/ManualAzureDeployment.md) and `docker build ... && docker push` (docs/ACRBuildAndPushGuide.md).
- **azd build-from-source confirmation:** next-steps.md — "Azure Container App to host the 'backend' service / 'frontend' service", "Build from source (no Dockerfile) ... Buildpacks using Oryx", `azd up` provisions + deploys.

**Takeaway:** CWYD v2 = MACAE's `main_custom` (own ACR + build-from-source) chosen as the *only* path. The pattern is proven upstream.

### CGSA (content-generation-solution-accelerator)

- **`infra/main.bicep` (default):** pre-built PUBLIC shared ACR — `param acrName string = 'contentgencontainerreg'` ("Must contain pre-built images: content-gen-app and content-gen-api"). App Service frontend `linuxFxVersion: 'DOCKER|${acrResourceName}.azurecr.io/content-gen-app:${imageTag}'` (main.bicep:969); ACI backend `containerImage: '${acrResourceName}.azurecr.io/content-gen-api:${imageTag}'` (main.bicep:1015). Again the **v1-CWYD pre-built** model.
- **`infra/main_custom.bicep` + `scripts/deploy.{sh,ps1}` (custom):** own ACR (`avm/res/container-registry/registry:0.9.0`, Standard SKU, admin off, `anonymousPullEnabled: false`) + `backendImageUrl = '${containerRegistry.outputs.loginServer}/${backendImageName}:${imageTag}'` + a chicken-and-egg guard `var shouldDeployACI = !empty(imageTag) && imageTag != 'none'` (main_custom.bicep) + explicit `az acr build --registry <acr> --image "contentgen-backend:$TAG" --file backend/ApiApp.Dockerfile backend` (scripts/deploy.sh:100). CGSA's custom path is the **explicit `az acr build` → update-resource** style rather than azd `services:` build-from-source.

**Takeaway:** CGSA demonstrates the two viable "guard the chicken-and-egg" techniques — a `shouldDeployACI` conditional, and an explicit `az acr build` script driving `imageTag`. Useful if v2 ever wants a scripted `az acr build` alternative to azd.

### Cross-accelerator pattern matrix

| Aspect | v1 CWYD | CGSA main.bicep | MACAE main.bicep | CGSA main_custom | MACAE main_custom | **CWYD v2 (current)** |
|---|---|---|---|---|---|---|
| ACR ownership | Microsoft public (`cwydcontainerreg`) | Microsoft public (`contentgencontainerreg`) | Microsoft public (`biabcontainerreg`) | own ACR (Standard) | own ACR (`cr<sfx>`, Basic) | **own ACR (`cr<sfx>`, Basic)** |
| Images rebuilt by operator | no (pre-built) | no (pre-built) | no (pre-built) | yes (`az acr build`) | yes (azd build-from-source) | **yes (azd build/push)** |
| Backend image ref | name+tag literal | name+tag literal | name+tag literal | `${acr}/${name}:${tag}` + `shouldDeployACI` guard | placeholder + tag-swap | **placeholder + parameterized (hybrid)** |
| Frontend | container (App Service) | container (App Service) | container (App Service) | source-build App Service | source-build App Service | **source-build App Service** |
| Chicken-and-egg handling | image pre-exists | image pre-exists | image pre-exists | `imageTag != 'none'` guard | placeholder fallback | **empty-hostname placeholder fallback** |

---

## Recommendation (decisive)

**Do NOT restructure the deploy loop. It already meets the intent, and the "three images" premise is based on the stale 2026-06-25 doc.** Concretely:

### (a) Infra provisions the ACR — CONFIRMED DONE.
`containerRegistry` module (v2/infra/main.bicep:1751), `cr<suffix>`, Basic, admin off, AcrPull to UAMI, `AZURE_CONTAINER_REGISTRY_ENDPOINT` output (line 2680). No change needed. This matches MACAE `main_custom` one-for-one.

### (b) A repeatable build→push→deploy loop already exists for all three services — it is `azd deploy` / `azd up`.
Every `azd deploy` ships fresh code:
- **backend** → ACR remote build (`remoteBuild: true`) → push → `azd-deploy-<ts>` tag swap (a NEW image every deploy — no `latest` staleness in practice; the `latest` tag param is only for `provision`-reconcile ref composition).
- **frontend** → `npm ci && npm run build` (fresh `dist/`) → zip-deploy.
- **function** → regenerate `build-functions/` from source → zip-deploy to the Flex blob container.

The one true gap vs the user's mental model: **only the backend is an image.** The frontend and function are intentionally NOT images (frontend source-build after BUG-0081; function ZIP because **Flex Consumption cannot host containers** — Microsoft Learn cited in Q6). This is correct, modern, and matches MACAE `main_custom`.

### (c) Compute correctly consumes the freshly-built images.
Backend Container App pulls `cr<sfx>/cwyd-backend:<tag>` via UAMI AcrPull (`registries:` block, main.bicep:1795). Frontend + function consume fresh zip packages. No change needed.

### Entry point: `azd up` (first run) / `azd deploy [--all]` (iterate). Optionally add a thin Makefile wrapper.
`azd` is the right entry point (not a hand-rolled `az acr build` script — that is the break-glass path CGSA/MACAE keep for their manual docs). If the user wants a single memorable command, add to v2/Makefile (developer-tooling Stable Core, no structural change):
```makefile
.PHONY: deploy provision up
provision:
	azd provision
deploy:
	azd deploy --all
up:
	azd up
```
This is a convenience wrapper only — it changes no contract and needs no user sign-off beyond adding Makefile targets.

### Keep the hybrid image-reference contract (placeholder + parameterized). Do NOT move to a pure `SERVICE_*_IMAGE_NAME` param.
The current `empty(hostname) ? placeholder : '${host}/${name}:${tag}'` is strictly better than either pure pattern for a clean-tenant one-shot: first `azd up` is safe (placeholder pullable), and after the first deploy the bicep references the real built image by name+tag (satisfying "bicep references the built image by name+tag"). This is the same guard MACAE/CGSA use.

### Only if the user makes "all three must be rebuilt container images" a hard requirement:
1. **Frontend → `host: containerapp`** (reliable azd container target; MACAE `main.bicep` frontend precedent). Changes: azure.yaml frontend to `containerapp` + `docker: { path: ../../docker/Dockerfile.frontend, remoteBuild: true }` (drop `dist:` + `package-frontend` hook); bicep swap `frontendWebApp` App Service for a second `container-app` module in `cae-<suffix>` (reuse ACR + UAMI), placeholder+parameterized image + `azd-service-name: frontend`. **Keep the runtime `/config` backend-URL read** to avoid the `VITE_BACKEND_URL` build-time-bake ordering problem (backend FQDN unknown until backend is provisioned). This is a structural change → Hard Rule #10 (ask first).
2. **Function → container is NOT possible on Flex Consumption.** Would require moving to Azure Functions on Azure Container Apps or Premium/Dedicated with a custom image (loses scale-to-zero + fast cold start). Strong recommendation: **do not do this** — ZIP is the correct azd pattern for Python on Flex, and it already ships fresh code every deploy. Hard Rule #10 if pursued anyway.

**Bottom line:** infra already provisions the ACR; `azd up`/`azd deploy` already is the explicit, repeatable, code-updating loop for all three services; the backend is the only legitimate image and it is wired correctly; the frontend and function are non-images by deliberate, well-precedented design. The likely real action item is documentation (correct the "three images" expectation) plus an optional `make deploy` convenience target — not an infra rework.

---

## Clarifying questions for the user

1. The "three images" requirement appears to come from the stale 2026-06-25 baseline. Given that (a) the frontend was intentionally moved to source-build (BUG-0081) and (b) Flex Consumption **cannot** host a containerized function, is the true requirement "**every deploy ships freshly-built code for all three services**" (already satisfied by `azd deploy`) — or is it literally "**all three must be Docker images in the ACR**" (which forces a frontend `host: containerapp` change AND a function hosting-plan change away from Flex)?
2. Is a `make deploy` / `make up` convenience wrapper around `azd` desired, or is invoking `azd up` / `azd deploy --all` directly sufficient?

## Recommended follow-on research (not done here)
- [ ] Confirm the current `AZURE_ENV_IMAGE_TAG` value in the live azd env and whether any workflow sets a unique per-build tag (vs relying on azd's `azd-deploy-<ts>` tag for the actual deployed digest).
- [ ] Read v2/scripts/upload_sample_data.py end-to-end to confirm the postdeploy seed is idempotent + non-blocking (continueOnError: true) — relevant to a clean one-shot but out of scope for the image pipeline.
- [ ] If frontend→containerapp is pursued: verify Dockerfile.frontend `prod` stage serves on port 8000 (or align ingressTargetPort) and that `/config` runtime read is preserved so no `VITE_BACKEND_URL` bake is needed.
- [ ] Check v2/docs/development_plan.md §0.1 for any open debt row tracking a frontend-containerization or function-container decision (to avoid re-litigating a closed ADR).
