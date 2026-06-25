<!-- markdownlint-disable-file -->
# MACAE — One-shot `azd up` container build + bicep image-reference pattern

Research date: 2026-06-25
Sample root: data/sample_code/macae
Status: Complete

All code paths below are workspace-relative plain text (no links) so the doc stays AI-consumable.

---

## TL;DR — the one critical insight

MACAE ships **two parallel deployment modes** and the repo selects between them by **swapping
files**, not by an azd flag:

| Mode | azure.yaml in effect | infra root entry | `isCustom` | What azd does |
|------|----------------------|------------------|-----------|----------------|
| **Default (prebuilt images)** | `azure.yaml` — **NO `services:` block, only `hooks:`** | `infra/main.bicep` (`isCustom=false`) | false | `azd up` only provisions infra. Bicep references **prebuilt public images** `biabcontainerreg.azurecr.io/<name>:latest_v5` by **name+tag only** — no build, no ACR, no resource lookup. |
| **Custom (build from source)** | `azure_custom.yaml` (renamed to `azure.yaml`) — full `services:` block | `infra/main_custom.bicep` (renamed to `main.bicep`, sets `isCustom: true`) | true | azd ACR-**remoteBuild**s backend + mcp, pushes to a per-deploy ACR, updates the container apps; frontend App Service gets a **Python zip-deploy** (no docker). |

The default `azd up` is "one-shot" precisely because it does **zero building** — the bicep
hard-codes prebuilt image name+tag and pulls from a public ACR. The "build from source" path is
the opt-in custom flow.

This directly answers the CWYD problem: MACAE's frontend is an **App Service**, and in the
build-from-source flow it is served via **`linuxFxVersion: 'python|3.11'` + zip-deploy of `dist/`
+ a `prepackage` build hook** — it does **NOT** put a `docker:` block on an `appservice` host
(azd does not support that). In the prebuilt flow the same App Service instead uses
`linuxFxVersion: 'DOCKER|<registry>/macaefrontend:<tag>'` (a bicep-referenced prebuilt image, still
no azd docker build on appservice).

---

## 1. `azure.yaml` services entries

### 1a. Active default `azure.yaml` — NO services block

File: data/sample_code/macae/azure.yaml (lines 1-7 are the entire non-hook head)

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/Azure/azure-dev/main/schemas/v1.0/azure.yaml.json
name: multi-agent-custom-automation-engine-solution-accelerator
metadata:
  template: multi-agent-custom-automation-engine-solution-accelerator@1.0
requiredVersions:
  azd: '>= 1.18.0 != 1.23.9'
hooks:
  postdeploy:
    windows: { ... interactive post-deploy message ... }   # azure.yaml lines 9-45
    posix:   { ... interactive post-deploy message ... }    # azure.yaml lines 46-72
```

There is **no `services:` key at all** in the active `azure.yaml`. The only top-level keys are
`name`, `metadata`, `requiredVersions`, `hooks`. The `hooks.postdeploy` block (azure.yaml lines
8-72) just prints "run `infra/scripts/post-provision/post_deploy.*`" and the frontend URL. So in
the default flow azd has **nothing to build or deploy** as a service — it provisions infra and the
running images come from the bicep image params (section 3).

### 1b. `azure_custom.yaml` — full services block (the build-from-source variant)

File: data/sample_code/macae/azure_custom.yaml (lines 8-44)

```yaml
services:
  backend:
    project: ./src/backend
    language: py
    host: containerapp
    docker:
      path: ./Dockerfile.NoCache
      image: backend
      registry: ${AZURE_CONTAINER_REGISTRY_ENDPOINT}
      remoteBuild: true

  mcp:
    project: ./src/mcp_server
    language: py
    host: containerapp
    docker:
      image: mcp
      registry: ${AZURE_CONTAINER_REGISTRY_ENDPOINT}
      remoteBuild: true

  frontend:
    project: ./src/App
    language: py
    host: appservice
    dist: ./dist
    hooks:
      prepackage:
        windows:
          shell: pwsh
          run: ../../infra/scripts/build/package_frontend.ps1
          interactive: true
          continueOnError: false
        posix:
          shell: sh
          run: bash ../../infra/scripts/build/package_frontend.sh
          interactive: true
          continueOnError: false
```

Per-service summary (from `azure_custom.yaml`):

| service | host | language | project | docker.path | docker.image | docker.registry | remoteBuild | dist | service hooks |
|---------|------|----------|---------|-------------|--------------|-----------------|-------------|------|----------------|
| **backend** | containerapp | py | `./src/backend` | `./Dockerfile.NoCache` | `backend` | `${AZURE_CONTAINER_REGISTRY_ENDPOINT}` | `true` | — | — |
| **mcp** | containerapp | py | `./src/mcp_server` | *(omitted → defaults to `./Dockerfile`)* | `mcp` | `${AZURE_CONTAINER_REGISTRY_ENDPOINT}` | `true` | — | — |
| **frontend** | **appservice** | py | `./src/App` | *(none — not a docker service)* | — | — | — | `./dist` | `prepackage` → `package_frontend.ps1` / `package_frontend.sh` |

Top-level `hooks.postdeploy` is identical to the default `azure.yaml` (azure_custom.yaml lines 46+).
The `mcp` service has **no `docker.path`**, so azd uses the default `./Dockerfile` inside
`./src/mcp_server` (that Dockerfile exists — section 6).

---

## 2. How azd builds the container during `azd up`

- **Default flow:** azd builds **nothing**. No `services:` block → no build step. The container
  images already exist in the public registry `biabcontainerreg.azurecr.io` and are referenced by
  the bicep image params (section 3). This is what makes the default `azd up` fast / "one-shot".

- **Custom flow:** **ACR remote build** (server-side), not local docker build+push. Each
  containerapp service sets `docker.remoteBuild: true` and `docker.registry:
  ${AZURE_CONTAINER_REGISTRY_ENDPOINT}` (azure_custom.yaml lines 13-18, 25-26). azd uploads the
  build context to the target ACR and runs the build there, then pushes the resulting image and
  updates the live Container App (matched by the `azd-service-name` resource tag — section 3) to
  the freshly built image.

- **Where the target ACR is declared:** In **bicep**, not azure.yaml. The registry is created only
  in the custom flow and surfaced as a bicep output that azd reads back into the env:
  - infra/bicep/main.bicep line 491: `module container_registry './modules/compute/container-registry.bicep' = if(isCustom) { ... }`
  - infra/bicep/main.bicep line 994: `output AZURE_CONTAINER_REGISTRY_ENDPOINT string? = isCustom ? container_registry!.outputs.loginServer : null`
  - infra/main_custom.bicep line 425: re-exports `output AZURE_CONTAINER_REGISTRY_ENDPOINT string? = bicepDeployment!.outputs.AZURE_CONTAINER_REGISTRY_ENDPOINT!`

  azd provisions infra first (which creates the ACR + emits this output into the azd env), then on
  the deploy phase resolves `${AZURE_CONTAINER_REGISTRY_ENDPOINT}` in `azure_custom.yaml` to that
  login server for the remote build. (The default flow's `parameters.json` registry mapping uses a
  *different* env var — see section 4 note.)

---

## 3. How bicep references the container image for each app

The image is composed **inline as a string** `'<hostname>/<name>:<tag>'` — there is **no resource
lookup** (no `reference()`, no ACR `existing` symbolic resource). The three pieces are plain params
with public defaults.

### 3a. Image params (defaults) — infra/main.bicep lines 148-173 (mirrored in infra/bicep/main.bicep lines 120-145)

```bicep
@description('Optional. The Container Registry hostname where the docker images for the backend are located.')
param backendContainerRegistryHostname string = 'biabcontainerreg.azurecr.io'   // main.bicep:149

@description('Optional. The Container Image Name to deploy on the backend.')
param backendContainerImageName string = 'macaebackend'                          // main.bicep:152

@description('Optional. The Container Image Tag to deploy on the backend.')
param backendContainerImageTag string = 'latest_v5'                              // main.bicep:155

param frontendContainerRegistryHostname string = 'biabcontainerreg.azurecr.io'   // main.bicep:158
param frontendContainerImageName string = 'macaefrontend'                        // main.bicep:161
param frontendContainerImageTag string = 'latest_v5'                             // main.bicep:164

param MCPContainerRegistryHostname string = 'biabcontainerreg.azurecr.io'        // main.bicep:167
param MCPContainerImageName string = 'macaemcp'                                   // main.bicep:170
param MCPContainerImageTag string = 'latest_v5'                                   // main.bicep:173
```

> Note the param naming convention: `<service>ContainerRegistryHostname` /
> `<service>ContainerImageName` / `<service>ContainerImageTag` — NOT azd's stock
> `webappImageName` / `SERVICE_*_IMAGE_NAME` convention. MACAE deliberately uses its own param
> trio and inline composition.

### 3b. Backend Container App — infra/bicep/main.bicep lines 506-545

```bicep
module backend_container_app './modules/compute/container-app.bicep' = {      // line 506
  name: take('module.backend-container-app.${solutionSuffix}', 64)
  params: {
    name: backendContainerAppName
    ...
    tags: isCustom ? union(allTags, { 'azd-service-name': 'backend' }) : allTags   // line 511
    managedIdentities: {
      userAssignedResourceIds: [userAssignedIdentity.outputs.resourceId]
    }
    ...
    registries: isCustom ? [                                                       // line 535
      {
        server: container_registry!.outputs.loginServer
        identity: userAssignedIdentity.outputs.resourceId      // managed-identity ACR pull
      }
    ] : []                                                                          // public registry → no creds
    containers: [
      {
        name: 'backend'
        image: '${backendContainerRegistryHostname}/${backendContainerImageName}:${backendContainerImageTag}'  // line 544
        resources: { cpu: 2, memory: '4Gi' }
        env: [ ... COSMOSDB_ENDPOINT / DATABASE / CONTAINER ... ]
      }
    ]
  }
}
```

### 3c. MCP Container App — infra/bicep/main.bicep lines 680-711

```bicep
module mcp_container_app './modules/compute/container-app.bicep' = {          // line 680
  params: {
    tags: isCustom ? union(allTags, { 'azd-service-name': 'mcp' }) : allTags  // line 685
    registries: isCustom ? [ { server: ..., identity: ... } ] : []            // line 702
    containers: [
      {
        image: '${MCPContainerRegistryHostname}/${MCPContainerImageName}:${MCPContainerImageTag}'  // line 711
      }
    ]
  }
}
```

### 3d. The `isCustom` switch (this is MACAE's equivalent of azd's `<service>Exists` placeholder pattern)

MACAE does **not** use the azd-stock `param <service>Exists bool` + helloworld-placeholder idiom.
Instead a single boolean `isCustom` flips every container concern:

- infra/bicep/main.bicep line 189: `param isCustom bool = false`
- Default entry infra/main.bicep passes **no** `isCustom` → bicep/main.bicep keeps `false`.
- Custom entry infra/main_custom.bicep line 262: passes `isCustom: true` into the bicep module.

When `isCustom`:
- a per-deploy ACR is created (`if(isCustom)`, line 491),
- container apps add the `azd-service-name` tag so `azd deploy` can find + update them,
- container apps add `registries: [{ server, identity: UAMI }]` for managed-identity ACR pull,
- the frontend App Service switches from a prebuilt DOCKER image to native Python (section 5).

The actual running image after `azd deploy` (custom flow) is whatever azd builds+pushes and patches
onto the Container App; the bicep `image:` string is the **initial placeholder** (still composed
from the same name+tag params, defaults `macaebackend:latest_v5`, etc.).

### 3e. Managed-identity ACR pull

Container Apps: `registries: [{ server: container_registry.loginServer, identity:
userAssignedIdentity.resourceId }]` (lines 535-540, 702) — UAMI-based pull, no admin creds, no
Key Vault. The UAMI is also attached via `managedIdentities.userAssignedResourceIds`.

Frontend App Service prebuilt-DOCKER path additionally sets `DOCKER_REGISTRY_SERVER_URL:
'https://${frontendContainerRegistryHostname}'` (infra/bicep/main.bicep line 819) — the default
public registry is anonymous-pullable so no server creds are supplied.

---

## 4. `infra/main.parameters.json` mappings

File: data/sample_code/macae/infra/main.parameters.json (lines 74-93)

```jsonc
"backendContainerRegistryHostname":  { "value": "${AZURE_ENV_CONTAINER_REGISTRY_ENDPOINT}" },
"backendContainerImageTag":          { "value": "${AZURE_ENV_IMAGE_TAG=latest_v5}" },
"frontendContainerRegistryHostname": { "value": "${AZURE_ENV_CONTAINER_REGISTRY_ENDPOINT}" },
"frontendContainerImageTag":         { "value": "${AZURE_ENV_IMAGE_TAG=latest_v5}" },
"MCPContainerRegistryHostname":      { "value": "${AZURE_ENV_CONTAINER_REGISTRY_ENDPOINT}" },
"MCPContainerImageTag":              { "value": "${AZURE_ENV_IMAGE_TAG=latest_v5}" },
"deploymentFlavor":                  { "value": "${AZURE_ENV_DEPLOYMENT_FLAVOR=bicep}" }   // line 6
```

Key observations:

- The parameters file maps only **registry hostname** + **image tag** — the **image NAMES are NOT
  mapped** here. They fall through to the bicep defaults (`macaebackend` / `macaefrontend` /
  `macaemcp`). This is the opposite of the azd-stock `${SERVICE_BACKEND_IMAGE_NAME}` /
  `${SERVICE_WEB_IMAGE_NAME}` convention — MACAE does NOT use those tokens at all.
- `${...=latest_v5}` and `${...=bicep}` are azd's default-value syntax: if the env var is unset,
  the literal after `=` is used. So a clean `azd up` resolves `backendContainerImageTag` →
  `latest_v5` and `deploymentFlavor` → `bicep`.
- Subtle env-var-name nuance: the parameters file references `${AZURE_ENV_CONTAINER_REGISTRY_ENDPOINT}`
  (note the `_ENV_` segment), whereas azure_custom.yaml's `docker.registry` and the bicep output use
  `${AZURE_CONTAINER_REGISTRY_ENDPOINT}` (no `_ENV_`). In the default flow neither is set, so the
  registry hostname param simply resolves empty and the **bicep default**
  `biabcontainerreg.azurecr.io` wins. In the custom flow azd writes
  `AZURE_CONTAINER_REGISTRY_ENDPOINT` (the bicep output name) for the remote build; the parameters
  file's `AZURE_ENV_CONTAINER_REGISTRY_ENDPOINT` stays unset so the placeholder image again uses the
  bicep default until azd patches the live app.

No `*Exists` parameters appear in `main.parameters.json` (MACAE uses `isCustom` / `deploymentFlavor`
instead of the azd `<service>Exists` idiom).

---

## 5. Is the frontend a Container App or App Service? (critical for CWYD)

**App Service** (`Microsoft.Web/sites`), in BOTH modes. It is never a Container App.

Module call: infra/bicep/main.bicep lines 798-828

```bicep
module frontend_app './modules/compute/app-service.bicep' = {                 // line 798
  name: take('module.frontend-app.${solutionSuffix}', 64)
  params: {
    solutionName: frontendAppName                                              // 'app-${solutionSuffix}' (line 257)
    serverFarmResourceId: app_service_plan.outputs.resourceId
    tags: isCustom ? union(allTags, { 'azd-service-name': 'frontend' }) : allTags          // line 803
    linuxFxVersion: isCustom
      ? 'python|3.11'
      : 'DOCKER|${frontendContainerRegistryHostname}/${frontendContainerImageName}:${frontendContainerImageTag}'   // line 805
    appCommandLine: isCustom
      ? 'python3 -m uvicorn frontend_server:app --host 0.0.0.0 --port 8000'
      : ''                                                                      // line 806
    appSettings: isCustom ? {                                                  // line 807  (BUILD-FROM-SOURCE)
      SCM_DO_BUILD_DURING_DEPLOYMENT: 'True'
      WEBSITES_PORT: '8000'
      BACKEND_API_URL: 'https://${backend_container_app.outputs.fqdn}'
      AUTH_ENABLED: 'false'
      PROXY_API_REQUESTS: 'false'
      ENABLE_ORYX_BUILD: 'True'
      APPLICATIONINSIGHTS_CONNECTION_STRING: app_insights.outputs.connectionString
      APPINSIGHTS_INSTRUMENTATIONKEY: app_insights.outputs.instrumentationKey
    } : {                                                                      // (PREBUILT DOCKER IMAGE)
      SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
      DOCKER_REGISTRY_SERVER_URL: 'https://${frontendContainerRegistryHostname}'
      WEBSITES_PORT: '3000'
      WEBSITES_CONTAINER_START_TIME_LIMIT: '1800'
      BACKEND_API_URL: 'https://${backend_container_app.outputs.fqdn}'
      AUTH_ENABLED: 'false'
      PROXY_API_REQUESTS: 'false'
      APPLICATIONINSIGHTS_CONNECTION_STRING: app_insights.outputs.connectionString
      APPINSIGHTS_INSTRUMENTATIONKEY: app_insights.outputs.instrumentationKey
    }
  }
}
```

The app-service module just forwards these to the site's `siteConfig`:
- infra/bicep/modules/compute/app-service.bicep line 22: `param linuxFxVersion string`
- infra/bicep/modules/compute/app-service.bicep line 38: `param appCommandLine string`
- infra/bicep/modules/compute/app-service.bicep lines 64-83: `resource appService 'Microsoft.Web/sites@2025-05-01'` with `siteConfig: { linuxFxVersion, appCommandLine, ... }`

### Two frontend serving paths

**(A) Custom / build-from-source (`isCustom=true`, what an azd-built frontend uses):**
- App Service runs **native Python 3.11** (`linuxFxVersion: 'python|3.11'`), Oryx build on
  (`ENABLE_ORYX_BUILD`, `SCM_DO_BUILD_DURING_DEPLOYMENT`), listens on `WEBSITES_PORT=8000`.
- Start command: `python3 -m uvicorn frontend_server:app --host 0.0.0.0 --port 8000`.
- azd packages the service via the `frontend` service's `dist: ./dist` + `prepackage` hook and
  **zip-deploys** the `dist/` folder (no container at all).
- Build artifact `dist/` is produced by data/sample_code/macae/src/App/package_frontend.sh:
  ```bash
  mkdir -p dist
  rm -rf dist/*
  cp -f requirements.txt dist          # python deps for App Service Oryx
  cp -f *.py dist                       # frontend_server.py etc.
  npm install
  npm run build                         # Vite build → ./build
  cp -rf build dist                     # SPA assets land at dist/build
  ```
  (PowerShell twin: data/sample_code/macae/src/App/package_frontend.ps1.)

**(B) Default / prebuilt (`isCustom=false`, what a clean `azd up` uses):**
- App Service runs a **prebuilt container** via `linuxFxVersion:
  'DOCKER|biabcontainerreg.azurecr.io/macaefrontend:latest_v5'`, `WEBSITES_PORT=3000`,
  `DOCKER_REGISTRY_SERVER_URL` set, anonymous public pull. Still an App Service, just hosting a
  container image referenced by bicep — **azd does not build it**.

### How the SPA gets the backend URL (both paths)

Server is data/sample_code/macae/src/App/frontend_server.py (FastAPI):
- Serves `build/index.html` at `/` and static assets from `build/assets` (lines 28-39).
- Exposes a **runtime `/config` endpoint** (lines 41-58) that returns `API_URL` to the browser:
  - If `PROXY_API_REQUESTS=true` (WAF/private mode): `API_URL = "/api"` (same-origin; the frontend
    proxies — `/api/{path}` reverse-proxy + websocket proxy, lines 67-120).
  - Else: `API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000") + "/api"` — the browser
    calls the backend Container App FQDN directly.
- `BACKEND_API_URL` is injected by bicep App Service `appSettings`:
  `BACKEND_API_URL: 'https://${backend_container_app.outputs.fqdn}'` (lines 811 / 822). So the SPA
  fetches `/config` at startup and learns the backend URL at runtime — **no build-time bake-in**.

### Why this matters for CWYD

CWYD v2's frontend deploy is broken because it pairs `host: appservice` with a `docker:` block —
**azd does not support building a container for an `appservice` host**. MACAE sidesteps this in two
clean ways, both reusable for CWYD:
1. **Build-from-source:** `appservice` + `dist: ./dist` + `prepackage` build hook → Python
   zip-deploy (`linuxFxVersion: 'python|3.11'`, uvicorn start command). No docker block on the
   appservice service.
2. **Prebuilt image:** reference a prebuilt frontend image straight from bicep via
   `linuxFxVersion: 'DOCKER|<registry>/<name>:<tag>'`. azd never builds it; bicep just points the
   App Service at an existing image by name+tag.

---

## 6. Dockerfiles and how azure.yaml points at them

| Dockerfile | Used by | How referenced |
|------------|---------|----------------|
| data/sample_code/macae/src/backend/Dockerfile.NoCache | backend container image | azure_custom.yaml `backend.docker.path: ./Dockerfile.NoCache` (relative to `project: ./src/backend`). Multi-stage uv build, `python:3.11-slim-bookworm`. |
| data/sample_code/macae/src/backend/Dockerfile | backend (alt, not wired in azure_custom.yaml) | not referenced by azure.yaml; the active backend path is `Dockerfile.NoCache`. |
| data/sample_code/macae/src/mcp_server/Dockerfile | mcp container image | azure_custom.yaml `mcp` service omits `docker.path` → azd default `./Dockerfile` inside `project: ./src/mcp_server`. |
| data/sample_code/macae/src/App/Dockerfile | prebuilt **frontend** image `macaefrontend` (default-flow DOCKER linuxFxVersion) | NOT referenced by azure.yaml. Multi-stage `node:20-alpine` (Vite build) + `python:3.11-slim-bookworm` (uv) → final image serving the SPA + `frontend_server.py`. Built offline / in CI and pushed to the public registry; the running App Service references it by `DOCKER|...macaefrontend:latest_v5`. |

`docker.path` is resolved relative to the service `project:` dir. `docker.context` is not set on any
MACAE service, so the context defaults to the `project:` directory.

---

## 7. The file-swap that selects the mode (DeploymentGuide)

File: data/sample_code/macae/docs/DeploymentGuide.md lines 519-537 ("Advanced: Deploy Local Changes"):

1. Root: rename `azure.yaml` → `azure_custom2.yaml`, then `azure_custom.yaml` → `azure.yaml`.
2. `infra/`: rename `main.bicep` → `main_custom2.bicep`, then `main_custom.bicep` → `main.bicep`.
3. `azd up`.

So "build from source" = swap in BOTH the services-bearing azure.yaml AND the `isCustom: true`
bicep router. The shipped default (no swap) is the prebuilt-image one-shot path.

infra/main_custom.bicep is a thin wrapper over the same `./bicep/main.bicep` orchestrator: it
forwards every param and adds `isCustom: true` (line 262) and re-exports
`AZURE_CONTAINER_REGISTRY_ENDPOINT` (line 425). infra/main.bicep (default router) instead dispatches
by `deploymentFlavor` (`bicep` | `avm` | `avm-waf`; lines 250-251, 317) and never sets `isCustom`.

---

## 8. Evidence index (exact paths + lines)

- azure.yaml (no services; hooks only): data/sample_code/macae/azure.yaml lines 1-72
- azure_custom.yaml services block: data/sample_code/macae/azure_custom.yaml lines 8-44
- main.parameters.json image/tag/registry mappings: data/sample_code/macae/infra/main.parameters.json lines 6, 74-93
- Image params + defaults (router): data/sample_code/macae/infra/main.bicep lines 148-173
- Router deploymentFlavor logic: data/sample_code/macae/infra/main.bicep lines 18, 250-251, 317
- Image params + defaults (orchestrator): data/sample_code/macae/infra/bicep/main.bicep lines 120-145
- `param isCustom bool = false`: data/sample_code/macae/infra/bicep/main.bicep line 189
- ACR created if(isCustom): data/sample_code/macae/infra/bicep/main.bicep line 491
- Backend container app + image string: data/sample_code/macae/infra/bicep/main.bicep lines 506-545 (image line 544)
- Backend ACR registries/UAMI pull: data/sample_code/macae/infra/bicep/main.bicep lines 535-540
- MCP container app + image string: data/sample_code/macae/infra/bicep/main.bicep lines 680-711 (image line 711)
- Frontend App Service module: data/sample_code/macae/infra/bicep/main.bicep lines 798-828 (linuxFxVersion line 805, appCommandLine line 806)
- ACR endpoint output: data/sample_code/macae/infra/bicep/main.bicep line 994
- App Service module (siteConfig): data/sample_code/macae/infra/bicep/modules/compute/app-service.bicep lines 22, 38, 64-83
- Custom router sets isCustom + re-exports ACR endpoint: data/sample_code/macae/infra/main_custom.bicep lines 262, 425
- Frontend server /config + proxy: data/sample_code/macae/src/App/frontend_server.py lines 28-58, 67-120
- Frontend package build: data/sample_code/macae/src/App/package_frontend.sh (whole file)
- Backend Dockerfile.NoCache: data/sample_code/macae/src/backend/Dockerfile.NoCache
- MCP Dockerfile: data/sample_code/macae/src/mcp_server/Dockerfile
- Frontend prebuilt-image Dockerfile: data/sample_code/macae/src/App/Dockerfile
- File-swap procedure: data/sample_code/macae/docs/DeploymentGuide.md lines 519-537

---

## 9. Clarifying questions for the requester

1. For CWYD v2, do you want to adopt MACAE's **build-from-source frontend** pattern (App Service +
   `dist:` zip-deploy + `prepackage` build hook + `linuxFxVersion: 'python|3.11'`), or the
   **prebuilt-image** pattern (`linuxFxVersion: 'DOCKER|<registry>/<name>:<tag>'` referenced from
   bicep)? CWYD's current breakage is specifically `appservice` + `docker:` block, which MACAE
   never uses.
2. CWYD v2 frontend is a Vite SPA — is there an equivalent runtime `/config` server (or does CWYD
   bake `VITE_BACKEND_URL` at build time)? MACAE serves the SPA from a small FastAPI
   `frontend_server.py` that injects the backend URL at runtime via `/config`; replicating that
   removes any build-time backend-URL coupling.
3. Does CWYD want MACAE's dual-mode `isCustom` swap (prebuilt vs build-from-source), or a single
   always-build-from-source path? The single-mode path is simpler but loses the fast no-build
   `azd up`.

## 10. Recommended follow-on research (not done this session)

- [ ] Read infra/bicep/modules/compute/container-app.bicep to confirm exactly how the `registries`
      array maps to AVM `acrUseManagedIdentityCreds` / `userAssignedIdentityResourceId` on the
      `Microsoft.App/containerApps` resource.
- [ ] Read infra/bicep/modules/compute/container-registry.bicep (anonymous pull? admin disabled?
      AcrPull role assignment to the UAMI?).
- [ ] Confirm how azd patches the live Container App image after a custom-flow `azd deploy`
      (digest pinning vs tag) — verify the `azd-service-name` tag is the sole match key.
- [ ] Compare against CWYD v2's current v2/azure.yaml + v2/infra/main.bicep frontend block to scope
      the exact fix (swap docker block for dist+prepackage, or switch to DOCKER linuxFxVersion).
