<!-- markdownlint-disable-file -->
# MACAE infra research — how `azd up` makes frontend+backend communicate out of the box

Research date: 2026-06-28
Reference target (requested): `data/sample_code/macae` (Multi-Agent Custom Automation Engine Solution Accelerator)
Status: Complete — with a SOURCING CAVEAT (read §0 first)

---

## 0. CRITICAL SOURCING CAVEAT — the live MACAE source is NOT on disk

The path the task names, `c:\workstation\Microsoft\github\cwyd-cdb\data\sample_code\macae`, **does not exist in the working tree** and is **gitignored**:

- `list_dir data/sample_code/` → only `prototypes-main/` and `python_agent_framework_dev_template-main/`. No `macae/`.
- `git ls-files "data/sample_code/macae/*"` → `0` files (never tracked).
- `git check-ignore data/sample_code/macae` → matches (the folder is ignored, so even a re-clone would be untracked).
- The 2026-06-25 inventory recorded the folder as a "full read-only clone … hundreds of matches"; it has since been removed from disk (or was never re-materialized on this machine). A `grep_search` for `Multi-Agent Custom Automation Engine|MACAE` finds matches only in `.copilot-tracking/**` and `v2/**`, never under `data/sample_code/macae/`.

**Therefore a fresh read of the live source was impossible.** This report is reconstructed from two evidence classes, both reliable:

1. **Prior subagent research that read the live MACAE source on 2026-06-25** (with exact file paths + line numbers, captured while `data/sample_code/macae/**` existed). These are the primary citations below; their line numbers are MACAE's, not CWYD's:
   - `.copilot-tracking/research/subagents/2026-06-25/macae-container-build-pattern.md`
   - `.copilot-tracking/research/subagents/2026-06-25/macae-identity-env-hooks.md`
   - `.copilot-tracking/research/subagents/2026-06-25/macae-reference-inventory-and-bicep-removal.md`
   - `.copilot-tracking/research/2026-06-25/macae-infra-parity-research.md`
2. **CWYD v2's own on-disk `v2/infra/main.bicep`**, which is a *faithful adaptation* of the MACAE mixed-hosting pattern (comments at L1929-1931, L2014, L2031 explicitly cite "the reference architecture" = MACAE). I read it directly to corroborate the frontend↔backend wiring. Where I cite `v2/infra/main.bicep`, those line numbers are CWYD's adaptation, clearly labelled.

Every MACAE line number below is sourced from class (1). One single detail — the verbatim `var frontendAppUrl = …` definition — was never captured verbatim; it is a strong inference, flagged explicitly in §3.3.

---

## TL;DR — the mechanism in one paragraph

MACAE makes `azd up` yield a working frontend↔backend **by hosting the frontend as an App Service and the backend as a Container App**, and wiring the URL handshake in **two opposite directions using two different techniques**:

- **frontend → backend: runtime injection (not build-time bake).** Bicep sets the App Service `appSettings.BACKEND_API_URL = 'https://${backend_container_app.outputs.fqdn}'` (the backend's *real* output FQDN). The frontend's FastAPI server (`frontend_server.py`) exposes a `/config` endpoint that hands the browser `API_URL` at runtime. The Vite bundle is **never** rebuilt with the backend URL baked in.
- **backend → frontend: deterministic construction (not an output reference).** Bicep sets the backend Container App env `FRONTEND_SITE_NAME = frontendAppUrl`, where `frontendAppUrl` is **constructed as a string** from the known App Service name (`app-${solutionSuffix}.azurewebsites.net`), NOT read from `frontend_app.outputs.fqdn`.

Because only the frontend→backend edge uses a real resource output, **there is no dependency cycle**: the backend never references the frontend resource. The deterministic `*.azurewebsites.net` hostname (App Service hostnames are predictable from the site name) is what makes this work — it is the single most important reason MACAE uses **App Service** (deterministic FQDN) for the frontend instead of a second Container App (whose FQDN embeds the environment's random default domain and is only knowable post-create).

By default the browser calls the backend **cross-origin** (`PROXY_API_REQUESTS=false`), and the backend allows the frontend origin via `FRONTEND_SITE_NAME`. A second mode (`PROXY_API_REQUESTS=true`, used for WAF/private networking) flips the frontend into a **same-origin reverse proxy** that forwards `/api/*` (and websockets) to the backend.

---

## 1. `azure.yaml` — services, host types, hooks (focus area 1)

MACAE ships **two parallel azure.yaml files** and selects a deployment mode by **swapping files**, not by an azd flag. Source: `macae-container-build-pattern.md` §1.

### 1a. Default `azure.yaml` — NO `services:` block (prebuilt-image mode)

File: `data/sample_code/macae/azure.yaml` (lines 1-7 are the entire non-hook head; hooks at lines 8-72).

```yaml
name: multi-agent-custom-automation-engine-solution-accelerator
metadata:
  template: multi-agent-custom-automation-engine-solution-accelerator@1.0
requiredVersions:
  azd: '>= 1.18.0 != 1.23.9'
hooks:
  postdeploy:
    windows: { ... interactive post-deploy message ... }   # lines 9-45
    posix:   { ... interactive post-deploy message ... }    # lines 46-72
```

- **Top-level keys are only** `name`, `metadata`, `requiredVersions`, `hooks`. There is **no `services:` key at all**.
- **Only one hook: `postdeploy`** (both `windows` + `posix`, `interactive: true`). It does **not run any seeding**; it prints instructions to manually run `infra/scripts/post-provision/post_deploy.{sh,ps1}` and prints the frontend URL `https://$env:webSiteDefaultHostname`. (Source: `macae-identity-env-hooks.md` §4.1.)
- **No `postprovision`, `predeploy`, or `prepackage` hook** at the top level in the default file.
- Consequence: in the default flow azd has **nothing to build/deploy as a service** — it only provisions infra; the running images come from bicep image params (focus area 7 / §7). This is why the default `azd up` is fast and "one-shot": it does **zero building**.

### 1b. `azure_custom.yaml` — full `services:` block (build-from-source mode)

File: `data/sample_code/macae/azure_custom.yaml` (services block lines 8-44). To use it, the repo renames `azure_custom.yaml` → `azure.yaml` and `infra/main_custom.bicep` → `infra/main.bicep`.

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
      image: mcp                      # no docker.path → azd default ./Dockerfile
      registry: ${AZURE_CONTAINER_REGISTRY_ENDPOINT}
      remoteBuild: true
  frontend:
    project: ./src/App
    language: py
    host: appservice                  # <-- App Service, NOT containerapp
    dist: ./dist
    hooks:
      prepackage:
        windows: { shell: pwsh, run: ../../infra/scripts/build/package_frontend.ps1, interactive: true, continueOnError: false }
        posix:   { shell: sh,   run: bash ../../infra/scripts/build/package_frontend.sh, interactive: true, continueOnError: false }
```

| service | host | language | project | docker.path | docker.image | remoteBuild | dist | service hooks |
|---------|------|----------|---------|-------------|--------------|-------------|------|----------------|
| backend | containerapp | py | `./src/backend` | `./Dockerfile.NoCache` | `backend` | true | — | — |
| mcp | containerapp | py | `./src/mcp_server` | *(default `./Dockerfile`)* | `mcp` | true | — | — |
| frontend | **appservice** | py | `./src/App` | *(none — not a docker service)* | — | — | `./dist` | `prepackage` → `package_frontend.{ps1,sh}` |

**How azd maps services → infra:** by the `azd-service-name` resource **tag**. In custom mode the bicep tags each app `union(allTags, { 'azd-service-name': '<backend|mcp|frontend>' })` (focus area 7). `azd deploy <svc>` finds the live resource carrying that tag and pushes the freshly built artifact onto it.

**Key takeaway for the CWYD problem:** MACAE's frontend service is `host: appservice` + `dist: ./dist` + a `prepackage` build hook → azd **zip-deploys** the built `dist/`. It does **NOT** put a `docker:` block on an `appservice` host (azd does not support building a container for an appservice host). CWYD v2 adopted exactly this: `v2/infra/main.bicep` L2014 comment "Build-from-source App Service (reference-architecture pattern, BUG-0081 fix)".

---

## 2. `infra/` topology — main.bicep + modules (focus area 2)

MACAE `infra/` uses a **deployment-router** pattern. Source: `macae-identity-env-hooks.md` §0.

- `infra/main.bicep` is a thin router choosing a flavor via `deploymentFlavor` param (`'bicep' | 'avm' | 'avm-waf'`):
  - L144-145: `var isAvm = deploymentFlavor == 'avm' || deploymentFlavor == 'avm-waf'`; `var isBicep = deploymentFlavor == 'bicep'`.
  - L258: `module avmDeployment './avm/main.bicep' = if (isAvm) {...}`.
  - L318: `module bicepDeployment './bicep/main.bicep' = if (isBicep) {...}`.
  - All outputs coalesced: `output X = isAvm ? avmDeployment!.outputs.X : bicepDeployment!.outputs.X`.
- The **vanilla bicep flavor** (`infra/bicep/`) is the simplest single-RG, UAMI-based, managed-identity-only path and is what the citations below document.

Vanilla bicep module tree (`infra/bicep/modules/`):
- `identity/` — `managed-identity.bicep`, `role-assignments.bicep`, `cross-scope-role-assignment.bicep`
- `compute/` — `container-app.bicep`, `container-app-environment.bicep`, `container-registry.bicep`, `app-service.bicep`, `app-service-plan.bicep`
- `data/` — `storage-account.bicep`, `cosmos-db-nosql.bicep`
- `ai/` — `ai-foundry-project.bicep`, `ai-foundry-model-deployment.bicep`, `ai-search.bicep`, `ai-foundry-connection.bicep`, `existing-project-setup.bicep`
- `monitoring/` — `log-analytics.bicep`, `app-insights.bicep`

Resources enumerated (vanilla bicep flavor, `infra/bicep/main.bicep`):

| Resource | Module call (line) | Notes |
|----------|--------------------|-------|
| User-assigned managed identity (single, shared) | `userAssignedIdentity` L320 | `id-${solutionSuffix}` |
| Log Analytics | `log_analytics` L298 (`if (!useExistingLogAnalytics)`) | conditional |
| App Insights | `app_insights` | consumed via env vars only, no RBAC |
| Storage account | `storage_account` | blob endpoint env-injected |
| Cosmos DB (NoSQL) | `cosmosDBModule` | data-plane RBAC, no key |
| Azure AI Search | `ai_search` L370 (**unconditional**) | `disableLocalAuth: true` L380 |
| AI Foundry project (new) | `ai_foundry_project` L330 (`if (!useExistingAiFoundryAiProject)`) | |
| Existing-project setup | `existing_project_setup` L341 (`if (useExistingAiFoundryAiProject)`) | |
| Container Apps Environment | (compute module) | hosts backend + mcp |
| Backend Container App | `backend_container_app` L506 / env L528-678 | targetPort 8000 |
| MCP Container App | `mcp_container_app` L680 / env L680-787 | port 9000 |
| Container Registry | `container_registry` L491 / L734 (`if (isCustom)`) | only in build-from-source mode |
| App Service Plan | `app_service_plan` | Linux |
| Frontend App Service | `frontend_app` L798-828 | **App Service, not a Container App** |
| Role assignments (centralized) | `role_assignments` L831 | see §6 |

> Note: line numbers differ slightly between `infra/main.bicep` (router-relative) and `infra/bicep/main.bicep` (flavor file). The §6 RBAC table cites `infra/bicep/main.bicep`; §3/§5 env cites `infra/bicep/main.bicep` L528-829. There is **no Azure Function app** anywhere in MACAE's bicep tree (`macae-identity-env-hooks.md` §2.5).

---

## 3. How MACAE wires frontend↔backend communication (focus area 3 — the crux)

### 3.1 frontend → backend: runtime injection via `BACKEND_API_URL` + `/config`

The frontend App Service receives the backend's real FQDN as an app setting (`infra/bicep/main.bicep` L811 / L822, both branches of the `isCustom` ternary):

```bicep
appSettings: {
  BACKEND_API_URL: 'https://${backend_container_app.outputs.fqdn}'   // <-- real backend output FQDN
  AUTH_ENABLED: 'false'
  PROXY_API_REQUESTS: 'false'
  WEBSITES_PORT: '8000'        // (3000 in the prebuilt-DOCKER branch)
  APPLICATIONINSIGHTS_CONNECTION_STRING: app_insights.outputs.connectionString
  APPINSIGHTS_INSTRUMENTATIONKEY: app_insights.outputs.instrumentationKey
  ...
}
```

The frontend server reads it at runtime. File: `data/sample_code/macae/src/App/frontend_server.py` (FastAPI):
- Serves `build/index.html` at `/` and static assets from `build/assets` (lines 28-39).
- Exposes a **`/config` endpoint** (lines 41-58) returning `API_URL` to the browser:
  - If `PROXY_API_REQUESTS=true`: `API_URL = "/api"` (same-origin; the server reverse-proxies — see §3.4).
  - Else: `API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000") + "/api"` (browser calls the backend FQDN directly, cross-origin).

So the SPA fetches `/config` once at boot and **learns the backend URL at runtime — no build-time bake-in**. Source: `macae-container-build-pattern.md` §5 "How the SPA gets the backend URL".

### 3.2 backend → frontend: `FRONTEND_SITE_NAME` for CORS

The backend Container App env array (`infra/bicep/main.bicep` L528-678) includes (`macae-identity-env-hooks.md` §2.1):

```bicep
{ name: 'FRONTEND_SITE_NAME', value: frontendAppUrl }
```

This is how the backend learns the frontend origin so its FastAPI CORS middleware can allow it. There is **no separate `ALLOWED_ORIGINS` / `CORS_*` env var** — MACAE passes the single frontend URL via `FRONTEND_SITE_NAME` and the backend app builds its CORS allow-list from it.

### 3.3 How the circular FQDN dependency is AVOIDED (deterministic construction)

This is the key architectural decision. The cycle would be: *frontend needs backend FQDN; backend needs frontend FQDN for CORS.* MACAE breaks it by making the two edges asymmetric:

- **frontend → backend** uses the backend's **real resource output**: `backend_container_app.outputs.fqdn` (a genuine dependency; the frontend module depends on the backend module). Fine — one direction only.
- **backend → frontend** uses a **deterministically constructed string**, `frontendAppUrl`, **NOT** `frontend_app.outputs.fqdn`. The backend module therefore has **zero reference** to the frontend module, so there is no cycle.

Why deterministic construction is possible: **the frontend is an App Service**, and App Service hostnames are predictable — `<siteName>.azurewebsites.net`. The site name is `frontendAppName = 'app-${solutionSuffix}'` (`macae-container-build-pattern.md` L301 comment cites `infra/bicep/main.bicep` line 257). `solutionSuffix` is known at template-evaluation time (derived from the resource token), so the full frontend URL is knowable **before** the frontend resource is created. A Container App's FQDN, by contrast, embeds the Container Apps Environment's random `defaultDomain` and is only knowable post-create — which is exactly why MACAE does **not** make the frontend a second Container App.

> **VERBATIM CAVEAT (the single unconfirmed detail):** the prior research captured that the backend env uses `FRONTEND_SITE_NAME: value: frontendAppUrl` and that the router emits `output webSiteDefaultHostname string  // frontend host (https stripped)`, but it did **not** capture the literal `var frontendAppUrl = …` line. Based on (a) `frontendAppName = 'app-${solutionSuffix}'`, (b) App Service's deterministic `*.azurewebsites.net` hostname, and (c) the `webSiteDefaultHostname` output being "frontend host (https stripped)", the construction is almost certainly:
>
> ```bicep
> var frontendAppName = 'app-${solutionSuffix}'
> var frontendAppUrl  = 'https://${frontendAppName}.azurewebsites.net'   // inferred; not captured verbatim
> ```
>
> This is the one expression to confirm against the live source if it is ever restored. Everything else in §3 is sourced verbatim.

### 3.4 Same-origin reverse-proxy mode (`PROXY_API_REQUESTS=true`)

When set true (used for WAF/private-networking deployments where the backend has internal-only ingress), the frontend `frontend_server.py` becomes a **same-origin reverse proxy**: it serves `/config` with `API_URL="/api"` and forwards `/api/{path}` + websocket connections to the backend (proxy + websocket-proxy handlers, lines 67-120). The browser then makes only same-origin calls, sidestepping CORS entirely. Source: `macae-container-build-pattern.md` §5.

So MACAE supports **both** architectures behind one flag: cross-origin direct (default) and same-origin proxy (private). The default `azd up` uses cross-origin (`PROXY_API_REQUESTS=false`).

### 3.5 Contrast with CWYD v2 (on-disk corroboration + a relevant gap)

CWYD v2 adopted the frontend→backend half faithfully but **omits the backend→frontend CORS env wiring** in bicep:

- `v2/infra/main.bicep` L2016-2017 — frontend `BACKEND_API_URL: 'https://${backendContainerApp.outputs.fqdn}'` (same runtime-injection pattern; comment L2011 "feeds the frontend_app.py /config endpoint … No build-time bake").
- `v2/infra/main.bicep` L2581 — `output AZURE_BACKEND_URL = 'https://${backendContainerApp.outputs.fqdn}'`.
- `v2/infra/main.bicep` L2583-2584 — `output AZURE_FRONTEND_URL = 'https://${frontendWebApp.outputs.defaultHostname}'` with the description **"Backend CORS must allow this origin."** — but a `grep_search` of `v2/infra/main.bicep` finds **no** `ALLOWED_ORIGINS` / `FRONTEND_SITE_NAME` / CORS env var injected into the `backendContainerApp` module. CWYD emits the frontend URL only as an *output* (which is cycle-safe), and never feeds it into the backend's runtime env the way MACAE feeds `FRONTEND_SITE_NAME`. This is a strong candidate root cause for CWYD's "frontend and backend cannot communicate" symptom (the backend's CORS would reject the frontend origin). The MACAE-faithful fix is to add the deterministic-construction `FRONTEND_SITE_NAME` (or equivalent `CWYD_ALLOWED_ORIGINS`) to the backend env — `v2/infra/main.bicep` already has `frontendAppName = 'app-frontend-${solutionSuffix}'` at L1939, so `'https://${frontendAppName}.azurewebsites.net'` is constructible with no cycle.

---

## 4. Build-time bake vs runtime injection (focus area 4)

**Runtime-injected, not build-time baked.** Evidence:

- The Vite build runs in the `prepackage` hook (`package_frontend.sh`, `macae-container-build-pattern.md` §5) **before** the backend FQDN is knowable, producing static `build/` assets that contain **no** backend URL.
- The backend URL reaches the browser only at runtime via the `/config` endpoint of `frontend_server.py`, fed by the `BACKEND_API_URL` App Service setting (§3.1).
- There is **no Vite `--build-arg` / `VITE_BACKEND_URL` bake** in the Dockerfile path used for deployment. (The prebuilt-image Dockerfile at `src/App/Dockerfile` multi-stage-builds the SPA, but the runtime URL still comes from `frontend_server.py /config`, not a baked constant.)

Exact mechanism: **a runtime `config.json`-style endpoint** (`GET /config` returning `{ API_URL }`) written by the FastAPI server process from env vars — not an `env.js` file written by an entrypoint, not an nginx `/api` proxy in the default mode. (The nginx-style proxy only appears in `PROXY_API_REQUESTS=true` mode, and it is implemented inside `frontend_server.py`, not nginx.)

`package_frontend.sh` (build artifact assembly, `macae-container-build-pattern.md` §5):
```bash
mkdir -p dist; rm -rf dist/*
cp -f requirements.txt dist          # python deps for App Service Oryx
cp -f *.py dist                       # frontend_server.py etc.
npm install
npm run build                         # Vite build → ./build
cp -rf build dist                     # SPA assets land at dist/build
```

---

## 5. Ingress config per app + the same-origin vs cross-origin decision (focus area 5)

| App | Host | targetPort | external/internal | transport / notes |
|-----|------|-----------|-------------------|-------------------|
| Backend | Container App | `ingressTargetPort: 8000` (`infra/bicep/main.bicep` L528-678) | External in default mode; **internal** in WAF/private mode (the post-deploy script's "WAF/private-networking routing" branch keys off internal ingress / IP restrictions / `PROXY_API_REQUESTS=true`, `macae-identity-env-hooks.md` §4.2 step 4) | Standard ACA ingress; UAMI attached; `registries: isCustom ? [...] : []` |
| MCP | Container App | `PORT=9000` (`macae-identity-env-hooks.md` §2.4) | (internal/external per same WAF logic) | `/mcp` path; backend reaches it via `MCP_SERVER_ENDPOINT='https://${mcp_container_app.outputs.fqdn}/mcp'` |
| Frontend | App Service | `WEBSITES_PORT=8000` (custom/python) or `3000` (prebuilt docker) | Public `*.azurewebsites.net` | `httpsOnly`; uvicorn on 8000 in build-from-source mode |

`allowInsecure` / `transport` weren't captured verbatim in the prior research (they live inside the `container-app.bicep` module defaults). The CWYD adaptation sets `ingressExternal: !enablePrivateNetworking` for the backend (`v2/infra/main.bicep` L1777), which matches MACAE's "external by default, internal under private networking" behavior.

**The key architectural decision:** By default MACAE is **cross-origin** — the browser calls the backend Container App FQDN directly (`PROXY_API_REQUESTS=false`), and the backend allows the frontend origin via `FRONTEND_SITE_NAME` (§3.2). The **same-origin reverse-proxy** path (`PROXY_API_REQUESTS=true`, §3.4) exists only for private/WAF deployments where the backend ingress is internal and the browser cannot reach it directly. One flag toggles between the two; no code change.

---

## 6. Managed identity + RBAC, no-Key-Vault env-var pattern (focus area 6)

Source: `macae-identity-env-hooks.md` §1.

- **One shared UAMI** (`infra/bicep/modules/identity/managed-identity.bicep`, resource L23, named `id-${solutionName}`), instantiated at `infra/bicep/main.bicep` L320. Attached to backend + mcp Container Apps via `managedIdentities.userAssignedResourceIds`; its `clientId` is injected as `AZURE_CLIENT_ID` (the runtime auth handle for `DefaultAzureCredential`/`ManagedIdentityCredential`).
- **All RBAC centralized** in `infra/bicep/modules/identity/role-assignments.bicep` (one module call, `infra/bicep/main.bicep` L831). A `workloadPrincipals` loop (module L73) today wraps exactly the one shared UAMI; the deployer (signed-in user/SP) gets a parallel grant set so the post-deploy seeding scripts can write blobs / build indexes.

Full RBAC table (Role | Assignee | Scope), `infra/bicep/modules/identity/role-assignments.bicep`:

| # | Role | Assignee | Scope | Symbol / line |
|---|------|----------|-------|---------------|
| 1 | Cognitive Services OpenAI User | AI Search identity | AI Foundry account | `assignOpenAIRoleToAISearch` L122 |
| 2 | Azure AI User (Foundry User) | Workload UAMI | AI Foundry account | `workloadAiUserAssignment` L148 |
| 3 | Cognitive Services OpenAI Contributor | Workload UAMI | AI Foundry account | `workloadOpenAIContributor` L160 |
| 4 | Search Index Data Reader | AI Foundry project identity | AI Search | `projectSearchReader` L204 |
| 5 | Search Service Contributor | AI Foundry project identity | AI Search | `projectSearchContributor` L215 |
| 6 | Search Index Data Contributor | Workload UAMI | AI Search | `workloadSearchIndexContributor` L228 |
| 7 | Search Service Contributor | Workload UAMI | AI Search | `workloadSearchServiceContributor` L240 |
| 8 | Storage Blob Data Contributor | Workload UAMI | Storage account | `workloadStorageContributor` L258 |
| 9 | Cosmos DB Built-in Data Contributor (data-plane) | Workload UAMI | Cosmos DB account | `workloadCosmosRoleAssignment` L275 |
| 10 | Cognitive Services User | Deployer | AI Foundry account | `deployerAiServicesAccess` L291 |
| 11 | Azure AI User (Foundry User) | Deployer | AI Foundry account | `deployerAzureAIAccess` L302 |
| 12 | Search Index Data Contributor | Deployer | AI Search | `deployerSearchIndexContributor` L332 |
| 13 | Search Service Contributor | Deployer | AI Search | `deployerSearchServiceContributor` L343 |
| 14 | Storage Blob Data Contributor | Deployer | Storage account | `deployerStorageBlobContributor` L354 |
| 15 | Cosmos DB Built-in Data Contributor (data-plane) | Deployer | Cosmos DB account | `deployerCosmosRoleAssignment` L365 |
| 16 | AcrPull | Workload UAMI | Container Registry (only `isCustom`) | `workloadAcrPull` L393 |

- **Cosmos** uses a **data-plane SQL role** (`00000000-0000-0000-0000-000000000002`, `Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments`), NOT an ARM role assignment.
- **No Azure Key Vault anywhere** in the vanilla bicep flavor. The `container-app.bicep` module has an unused optional `secrets` param + `secretRef` capability, but the backend/mcp calls pass **no secrets** and **no env entry uses `secretRef`** — every value is inline `value:`. App Insights connection string / instrumentation key are passed in the clear as env vars. App Insights gets **no RBAC grant**. (Source: `macae-identity-env-hooks.md` §2.3.)
- ACR pull (custom mode) is UAMI-based: `registries: [{ server: container_registry.loginServer, identity: userAssignedIdentity.resourceId }]` — no admin creds.

This is the "managed-identity + RBAC + no-Key-Vault env-var" pattern: one UAMI, `AZURE_CLIENT_ID` injected, AAD tokens for Cosmos/Storage/Search/OpenAI; endpoints/URLs as plain env vars; no keys, no connection strings (except App Insights).

---

## 7. Dockerfiles (focus area 7)

Source: `macae-container-build-pattern.md` §6.

| Dockerfile | Used by | How referenced | Build details |
|------------|---------|----------------|---------------|
| `data/sample_code/macae/src/backend/Dockerfile.NoCache` | backend image | `azure_custom.yaml backend.docker.path` (relative to `project: ./src/backend`) | Multi-stage `uv` build on `python:3.11-slim-bookworm` |
| `data/sample_code/macae/src/backend/Dockerfile` | backend (alt) | NOT wired in azure.yaml (active path is `.NoCache`) | — |
| `data/sample_code/macae/src/mcp_server/Dockerfile` | mcp image | `mcp` service omits `docker.path` → azd default `./Dockerfile` | — |
| `data/sample_code/macae/src/App/Dockerfile` | prebuilt **frontend** image `macaefrontend` (default-flow `DOCKER` linuxFxVersion) | NOT referenced by azure.yaml; built offline/CI, pushed to public registry, App Service references it by `DOCKER|...macaefrontend:latest_v5` | Multi-stage `node:20-alpine` (Vite build) + `python:3.11-slim-bookworm` (uv) → serves SPA + `frontend_server.py` |

**Bicep image referencing (prebuilt mode):** the image is composed **inline as a string** `'<hostname>/<name>:<tag>'` from three plain params with public defaults — **no `reference()`, no ACR `existing` lookup** (`macae-container-build-pattern.md` §3):

```bicep
param backendContainerRegistryHostname string = 'biabcontainerreg.azurecr.io'   // main.bicep:149
param backendContainerImageName        string = 'macaebackend'                    // main.bicep:152
param backendContainerImageTag         string = 'latest_v5'                       // main.bicep:155
// ... in the container:
image: '${backendContainerRegistryHostname}/${backendContainerImageName}:${backendContainerImageTag}'   // main.bicep:544
```

Frontend App Service two-path serving (`infra/bicep/main.bicep` L798-828):
- **Custom (`isCustom=true`):** `linuxFxVersion: 'python|3.11'`, `appCommandLine: 'python3 -m uvicorn frontend_server:app --host 0.0.0.0 --port 8000'`, `SCM_DO_BUILD_DURING_DEPLOYMENT`, `ENABLE_ORYX_BUILD`, `WEBSITES_PORT=8000`; azd zip-deploys `dist/`.
- **Prebuilt (`isCustom=false`):** `linuxFxVersion: 'DOCKER|${frontendContainerRegistryHostname}/${frontendContainerImageName}:${frontendContainerImageTag}'`, `WEBSITES_PORT=3000`, `DOCKER_REGISTRY_SERVER_URL` set (anonymous public pull); azd never builds it.

No env-substitution entrypoint is used at container start for the backend URL — the URL injection is the App Service `appSettings` → `frontend_server.py /config` path (§3.1/§4), not a shell entrypoint rewriting a JS file.

---

## 8. Postprovision / postdeploy scripts that set env / CORS / restart (focus area 8)

Source: `macae-identity-env-hooks.md` §4.

- **Hooks in `azure.yaml`:** exactly one — `postdeploy` (both OS variants, `interactive: true`). It **does not set env vars, update CORS, or restart apps**. It only **prints** the command to run `infra/scripts/post-provision/post_deploy.{sh,ps1}` and the frontend URL (`$env:webSiteDefaultHostname`). There is **no `postprovision`/`predeploy`** hook in the default file.
- **The real engine — `post_deploy.{sh,ps1}`** (run manually/interactively, `main()` lines 643-908): auth + subscription resolve → resolve resource values from `azd env`/`az deployment`/naming-convention → interactive use-case menu → **WAF/private routing** (route API through the frontend proxy when backend ingress is internal) → `ensure_role_assignments_for_kbmcp()` (grants the signed-in user Foundry User on the Foundry resource, then `sleep 60` for propagation) → `enable_public_access_if_waf()` (temporarily flip Storage/Search/Foundry public access for seeding, with an `EXIT` trap to restore) → venv setup → per-use-case seeding.
- **Data seeding** (the part CWYD needs): content packs under `content_packs/<usecase>/` with a `pack.json` manifest; `az storage blob upload-batch … --auth-mode login` (AAD/MI auth, relying on the deployer's Storage Blob Data Contributor role) then a Python indexer (`index_datasets.py`, AAD auth, no admin key) builds the AI Search index; `upload_team_config.py` POSTs agent configs to the backend REST API with retry/backoff; `seed_{vector_stores,knowledge_bases,kb_connections}.py` create Foundry IQ vector stores + KBs + per-KB RemoteTool connections.

**Net:** MACAE does **not** automate post-deploy CORS/env/restart in the azd hook. The frontend↔backend wiring is entirely **bicep-time** (env vars at provision); the postdeploy script only seeds data and is run by hand. So the "works out of the box" claim refers to the **app-to-app communication** (bicep env wiring), not to the data seeding (manual).

---

## 9. Complete env-var list per app (focus area d)

### 9.1 Backend Container App (`infra/bicep/main.bicep` L528-678; all plain `value:`)

`COSMOSDB_ENDPOINT`, `COSMOSDB_DATABASE`, `COSMOSDB_CONTAINER`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`, `AZURE_OPENAI_RAI_DEPLOYMENT_NAME`, `AZURE_OPENAI_API_VERSION`, `APPLICATIONINSIGHTS_INSTRUMENTATION_KEY`, `APPLICATIONINSIGHTS_CONNECTION_STRING`, `AZURE_AI_SUBSCRIPTION_ID`, `AZURE_AI_RESOURCE_GROUP`, `AZURE_AI_PROJECT_NAME`, **`FRONTEND_SITE_NAME` (= `frontendAppUrl`, the deterministic frontend URL → CORS)**, `APP_ENV` (`'Prod'`), `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_COGNITIVE_SERVICES` (`'https://cognitiveservices.azure.com/.default'`), `ORCHESTRATOR_MODEL_NAME`, `AZURE_OPENAI_IMAGE_DEPLOYMENT`, `MCP_SERVER_ENDPOINT` (`'https://${mcp_container_app.outputs.fqdn}/mcp'`), `MCP_SERVER_NAME`, `MCP_SERVER_DESCRIPTION`, `AZURE_TENANT_ID`, **`AZURE_CLIENT_ID` (= UAMI clientId, MI auth handle)**, `SUPPORTED_MODELS`, `AZURE_STORAGE_BLOB_URL`, `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_AGENT_ENDPOINT`, `AZURE_BASIC_LOGGING_LEVEL` (`INFO`), `AZURE_PACKAGE_LOGGING_LEVEL` (`WARNING`), `AZURE_LOGGING_PACKAGES` (`''`).
- `AZURE_AI_SEARCH_CONNECTION_NAME` is **intentionally omitted** (commented in source); the app defaults to per-KB RemoteTool connection names with ProjectManagedIdentity auth. No `AZURE_AI_SEARCH_KEY`.

### 9.2 MCP Container App (`infra/bicep/main.bicep` L680-787; all plain `value:`)

`HOST`, `PORT` (`9000`), `SERVER_NAME`, `ENABLE_AUTH` (`'false'`), `TENANT_ID`, `CLIENT_ID` (= UAMI clientId), `JWKS_URI`, `ISSUER`, `AUDIENCE` (`'api://${userAssignedIdentity.outputs.clientId}'`), `AZURE_CLIENT_ID`, `AZURE_OPENAI_ENDPOINT`, `AZURE_STORAGE_BLOB_URL`, `BACKEND_URL`.

### 9.3 Frontend App Service (`infra/bicep/main.bicep` L807-827; `appSettings` map)

- Custom branch: `SCM_DO_BUILD_DURING_DEPLOYMENT` (`'True'`), `WEBSITES_PORT` (`'8000'`), **`BACKEND_API_URL` (`'https://${backend_container_app.outputs.fqdn}'`)**, `AUTH_ENABLED` (`'false'`), `PROXY_API_REQUESTS` (`'false'`), `ENABLE_ORYX_BUILD` (`'True'`), `APPLICATIONINSIGHTS_CONNECTION_STRING`, `APPINSIGHTS_INSTRUMENTATIONKEY`.
- Prebuilt branch: same plus `DOCKER_REGISTRY_SERVER_URL` (`'https://${frontendContainerRegistryHostname}'`), `WEBSITES_PORT` (`'3000'`), `WEBSITES_CONTAINER_START_TIME_LIMIT` (`'1800'`).
- **No `AZURE_CLIENT_ID`** on the frontend (the SPA never calls Azure directly; all Azure calls route through the backend).

### 9.4 Router outputs azd writes to `.azure/<env>/.env`

`resourceGroupName`, `webSiteDefaultHostname` (frontend host, https-stripped), `AZURE_STORAGE_BLOB_URL`, `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_AI_SEARCH_NAME`, `AZURE_SEARCH_ENDPOINT`, `COSMOSDB_ENDPOINT`, `COSMOSDB_DATABASE`, `COSMOSDB_CONTAINER`, `COSMOSDB_ACCOUNT_NAME`, `AZURE_OPENAI_*`, `AZURE_AI_SUBSCRIPTION_ID`, `AZURE_AI_RESOURCE_GROUP`, `AZURE_AI_PROJECT_NAME`, `AI_FOUNDRY_RESOURCE_ID`, `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_AGENT_ENDPOINT`, `AI_SERVICE_NAME`, `ORCHESTRATOR_MODEL_NAME`, `SUPPORTED_MODELS`, `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_COGNITIVE_SERVICES`, `APP_ENV`, **`BACKEND_URL` (`'https://${backend_container_app.outputs.fqdn}'`)**, `MCP_SERVER_NAME`, `MCP_SERVER_DESCRIPTION`, `AZURE_STORAGE_CONTAINER_NAME_*`, `AZURE_AI_SEARCH_INDEX_NAME_*`. (Source: `macae-identity-env-hooks.md` §5.)

---

## 10. Answers to the four required deliverables

**(a) Exact file paths + line numbers:** provided throughout (MACAE lines from the 2026-06-25 live-source capture; CWYD corroboration lines from on-disk `v2/infra/main.bicep`).

**(b) Precise mechanism (same-origin proxy vs cross-origin CORS vs runtime env shim):**
> **Default = cross-origin CORS + runtime env shim.** The frontend (App Service, FastAPI `frontend_server.py`) serves a `GET /config` endpoint returning `API_URL = BACKEND_API_URL + "/api"`; `BACKEND_API_URL` is the backend Container App's real FQDN, injected as an App Service `appSettings` value by bicep (`infra/bicep/main.bicep` L811/L822). The browser fetches `/config` at boot and calls the backend cross-origin. The backend allows the frontend origin via the `FRONTEND_SITE_NAME` env var (backend Container App env, `infra/bicep/main.bicep` L528-678). A second mode (`PROXY_API_REQUESTS=true`, for private/WAF) turns `frontend_server.py` into a **same-origin reverse proxy** of `/api/*` + websockets. It is **NOT** build-time baked, **NOT** an nginx proxy (the proxy, when used, is FastAPI in-process), and **NOT** an `env.js` entrypoint shim — it is a runtime `/config` JSON endpoint.

**(c) How MACAE avoids the circular FQDN dependency:**
> Asymmetric edges. frontend→backend reads the backend's **real** output `backend_container_app.outputs.fqdn`; backend→frontend reads a **deterministically constructed** `frontendAppUrl` (≈ `'https://app-${solutionSuffix}.azurewebsites.net'`), **not** `frontend_app.outputs.fqdn`. Because the backend module never references the frontend resource, there is no dependency cycle. This is only possible because the frontend is an **App Service** with a predictable `*.azurewebsites.net` hostname (a Container App FQDN would not be constructible pre-create). [The literal `var frontendAppUrl =` line is the single detail not captured verbatim — see §3.3 caveat.]

**(d) Complete env-var list per app:** §9.1 (backend), §9.2 (mcp), §9.3 (frontend), §9.4 (outputs).

---

## 11. Subagent file path + clarifying questions

- **Subagent file:** `.copilot-tracking/research/subagents/2026-06-28/macae-infra.md` (this file).
- **Key mechanism summary:** App Service frontend + Container App backend; cross-origin by default; **runtime `/config` endpoint** injects the backend FQDN into the SPA (no build-time bake); backend CORS allow-list fed by `FRONTEND_SITE_NAME` built via **deterministic `*.azurewebsites.net` construction**, which breaks the circular FQDN dependency; managed-identity + RBAC, no Key Vault; data seeding is manual (postdeploy hook only advertises it). CWYD v2 copied the frontend→backend half but appears to **omit** the backend→frontend CORS env wiring (likely root cause of its communication failure).

### Clarifying questions

1. **Source restoration:** The live `data/sample_code/macae/` is gone and gitignored. Do you want it re-cloned/restored so the one unconfirmed expression (`var frontendAppUrl`) and the exact ingress `external/transport/allowInsecure` values can be verified against the real bicep? Everything else in this report is from a prior verbatim capture.
2. **Scope of intent:** This report is MACAE-only per the task. The §3.5 finding (CWYD backend missing the `FRONTEND_SITE_NAME`/CORS env wiring) is the actionable port — should a follow-up research/plan unit target that fix specifically?
3. **CWYD frontend naming:** CWYD uses `frontendAppName = 'app-frontend-${solutionSuffix}'` (`v2/infra/main.bicep` L1939) vs MACAE's `'app-${solutionSuffix}'`. Confirm the CWYD deterministic origin to inject is `'https://app-frontend-${solutionSuffix}.azurewebsites.net'` when porting the pattern.
