<!-- markdownlint-disable-file -->
# CWYD v2 — Infrastructure Research: Frontend ↔ Backend Communication After `azd up`

> RESEARCH ONLY. No code was modified. All findings cite exact file paths + line numbers.

## 0. TL;DR — Root-Cause Candidates (ranked)

The user reported "frontend and backend **container apps** cannot communicate and some configuration is missing." First correction: **the frontend is NOT a Container App — it is an App Service** (`Microsoft.Web/sites`, Python/uvicorn). The backend is a Container App. They are **two different origins** (`*.azurewebsites.net` vs `*.azurecontainerapps.io`), so the browser SPA must make **cross-origin** calls to the backend, and the deployed topology depends on three pieces of configuration — two of which are missing/unwired.

| # | Root cause | Certainty | Blast radius |
|---|---|---|---|
| **RC-1** | **No Easy Auth / `authConfig` is wired on EITHER the backend Container App or the frontend App Service**, yet the backend is hard-pinned to `AZURE_ENVIRONMENT=production`. In production the admin gate (`requires_role`) **fails closed (401)** for every caller because no platform injects the `x-ms-client-principal` claims header. The entire admin/ingest surface (`/api/admin/*`) is unreachable. | **Certain** (code + infra both verified) | Admin upload/ingest/config UI → 401 for everyone |
| **RC-2** | **`BACKEND_CORS_ORIGINS` is never set on the backend Container App** (it exists only in local `.env`/docs/tests). The infra author's OWN output comment says "Backend CORS must allow this origin," but the env var is never wired. The backend code falls back to `allow_origins=["*"], allow_credentials=False`. This masks the gap for plain public-mode non-credentialed GET/POST, but is genuinely "missing configuration" and breaks the moment the deployment is private, credentialed, or origin-restricted. | **Certain** (gap confirmed) | Latent; breaks under private-net / credentialed / restricted-origin |
| **RC-3** | **Private-networking mode dead-ends the browser.** When `enablePrivateNetworking=true`, the backend ingress is **internal-only** and the SPA's runtime `getBackendUrl()` returns the backend's **internal CAE FQDN**, which the user's browser (outside the VNet) cannot resolve/reach. `frontend_app.py` does **not** reverse-proxy `/api` → backend, so there is no same-origin path. | **Certain** for that flag | Total comms failure **iff** `enablePrivateNetworking=true` |

Secondary design tension (explains why RC-2 was left unwired): a **circular FQDN dependency** — the frontend App Service reads the backend FQDN (`backendContainerApp.outputs.fqdn`), so the backend module cannot reference the frontend module's FQDN output without a cycle. See §7.

---

## 1. Focus Area: Deployment Topology & Hosting Model

### Files

- [v2/azure.yaml](../../../../v2/azure.yaml) — azd manifest.
- [v2/infra/main.bicep](../../../../v2/infra/main.bicep) — single entry-point template (`targetScope = resourceGroup`).

### Findings

`azure.yaml` declares three services with **mixed hosting**:

| Service | `host` | How it's built/served | bicep tag |
|---|---|---|---|
| `backend` | `containerapp` | `docker` block → `Dockerfile.backend`, `remoteBuild: true` | `azd-service-name: backend` |
| `frontend` | **`appservice`** | build-from-source, `dist: ./build-output`, prepackage hook | `azd-service-name: frontend` |
| `function` | `function` | `project ./build-functions`, prepackage hook | `azd-service-name: function` |

- Backend Container App: [v2/infra/main.bicep#L1742](../../../../v2/infra/main.bicep#L1742) (`module backendContainerApp 'br/public:avm/res/app/container-app:0.22.1'`), name `ca-backend-${solutionSuffix}` ([L1585](../../../../v2/infra/main.bicep#L1585)).
- Frontend App Service: [v2/infra/main.bicep#L1962](../../../../v2/infra/main.bicep#L1962) (`module frontendWebApp 'br/public:avm/res/web/site:0.22.0'`), name `app-frontend-${solutionSuffix}` ([L1939](../../../../v2/infra/main.bicep#L1939)), `linuxFxVersion: 'PYTHON|3.11'`, `appCommandLine: 'uvicorn frontend_app:app --host 0.0.0.0 --port 8000'` ([L1994-1995](../../../../v2/infra/main.bicep#L1994)).
- Function App (Flex Consumption FC1): [v2/infra/main.bicep#L2102](../../../../v2/infra/main.bicep#L2102).

**Implication:** the user's mental model ("two container apps") is wrong. The cross-origin browser→backend hop is the crux, and it depends on CORS (RC-2) + reachability (RC-3) + auth for admin (RC-1).

---

## 2. Focus Area: Frontend → Backend URL Wiring (build-time vs runtime)

**Determination: RUNTIME. Not baked at build time for the deployed App Service.**

### Mechanism (verified end-to-end)

1. bicep sets the App Service app setting `BACKEND_API_URL = 'https://${backendContainerApp.outputs.fqdn}'` — [v2/infra/main.bicep#L2009-2012](../../../../v2/infra/main.bicep#L2009).
2. The App Service runs `frontend_app.py` (uvicorn), which exposes `GET /config` returning `{ "backendUrl": <BACKEND_API_URL> }` — [v2/src/frontend/frontend_app.py#L47-50](../../../../v2/src/frontend/frontend_app.py#L47).
3. The SPA fetches `/config` once at boot and caches it; every REST wrapper reads it synchronously via `getBackendUrl()` — [v2/src/frontend/src/api/runtimeConfig.tsx#L34-75](../../../../v2/src/frontend/src/api/runtimeConfig.tsx#L34). Build-time `VITE_BACKEND_URL` is only the **local-dev fallback** ([L38](../../../../v2/src/frontend/src/api/runtimeConfig.tsx#L38)).
4. The packaging script stages `frontend_app.py` + `requirements.txt` (fastapi+uvicorn) + `dist/` into `build-output/`, and `SCM_DO_BUILD_DURING_DEPLOYMENT=true` ([v2/infra/main.bicep#L2021](../../../../v2/infra/main.bicep#L2021)) makes Oryx pip-install them — [v2/scripts/package_frontend.py#L40-66](../../../../v2/scripts/package_frontend.py#L40).

> Note: `VITE_BACKEND_URL` as a **build ARG** appears only in [v2/docker/Dockerfile.frontend#L41-43](../../../../v2/docker/Dockerfile.frontend#L41) — that image (uvicorn on **port 80**) is for `docker-compose` dev/smoke, **not** the App Service deploy (uvicorn on **port 8000**). The deployed frontend does NOT bake a backend URL.

**Verdict:** this wiring is **correct and sufficient** in public mode. The frontend URL pointer is *not* the bug. (It DOES become a dead pointer in private mode — see RC-3.)

---

## 3. Focus Area: Backend CORS (RC-2 — MISSING)

### What the backend code expects

- [v2/src/backend/app.py#L241-263](../../../../v2/src/backend/app.py#L241): `network = NetworkSettings()`; `origins = list(network.cors_origins) or ["*"]`; `allow_credentials = origins != ["*"]`; `app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=allow_credentials, allow_methods=["*"], allow_headers=["*"])`.
- [v2/src/backend/core/settings.py#L304-320](../../../../v2/src/backend/core/settings.py#L304): `cors_origins` reads env var **`BACKEND_CORS_ORIGINS`** (bare, no `AZURE_` prefix) via `AliasChoices("BACKEND_CORS_ORIGINS", "cors_origins")`.

### What the infra provides

- **Nothing.** The backend Container App `env` array ([v2/infra/main.bicep#L1820-1916](../../../../v2/infra/main.bicep#L1820)) contains **no** `BACKEND_CORS_ORIGINS`. A full-tree grep confirms it appears only in `v2/.env`, `v2/.env.sample`, `v2/docs/**`, and `v2/tests/**` — never in `main.bicep` and never in any deploy hook (`post_provision.py`, packaging scripts).
- The infra author **knew** it was required — the output is annotated: `@description('Public URL of the frontend Web App (React/Vite SPA). Backend CORS must allow this origin.')` — [v2/infra/main.bicep#L2583](../../../../v2/infra/main.bicep#L2583) — yet `AZURE_FRONTEND_URL` ([L2584](../../../../v2/infra/main.bicep#L2584)) is never fed back into the backend.

### Net effect

Deployed backend → `cors_origins=[]` → `allow_origins=["*"]`, `allow_credentials=False` (intentional + unit-tested: [v2/tests/backend/test_app_lifespan.py#L536-540](../../../../v2/tests/backend/test_app_lifespan.py#L536)). In **default public mode** the SPA makes **non-credentialed** fetches (no `credentials: 'include'` anywhere in `v2/src/frontend/src/**`), so the wildcard actually permits them — meaning **CORS is not the hard blocker in the default profile**, but it IS the literal "missing configuration" the user senses, and it is a real break under private-net / credentialed / restricted-origin scenarios.

---

## 4. Focus Area: Backend Ingress (external vs internal, port, transport)

- [v2/infra/main.bicep#L1770-1779](../../../../v2/infra/main.bicep#L1770):
  - `ingressTargetPort: 8000` ✔ matches `Dockerfile.backend` uvicorn port (backend listens on 8000).
  - `ingressExternal: !enablePrivateNetworking` → **external in default mode**, **internal-only** when `enablePrivateNetworking=true` (RC-3).
  - `ingressAllowInsecure: false`, `ingressTransport: 'auto'`.
- `scaleSettings.minReplicas: enableScalability ? 1 : 0` ([L1781](../../../../v2/infra/main.bicep#L1781)) → **scale-to-zero in the default profile**. First request after idle pays a cold-start; SSE clients with short timeouts could perceive this as "can't communicate" on the very first hit, though it self-heals.
- In private mode the CAE itself is `internal: true` ([L1632](../../../../v2/infra/main.bicep#L1632)) and a wildcard private-DNS A-record `*.<defaultDomain>` → static internal IP ([L1681-1701](../../../../v2/infra/main.bicep#L1681)) makes the backend reachable **only from inside the VNet** (frontend App Service via regional VNet integration, Function App, Bastion). The **browser is not in the VNet** → RC-3.

---

## 5. Focus Area: Admin Auth Gate (RC-1 — MISSING Easy Auth)

### Backend is pinned to production

[v2/infra/main.bicep#L1845](../../../../v2/infra/main.bicep#L1845): `{ name: 'AZURE_ENVIRONMENT', value: 'production' }` (with an explicit comment that this makes the admin auth gate *fail closed* and disables the local-dev bypass). The Function App is likewise pinned ([L2186](../../../../v2/infra/main.bicep#L2186)).

### The gate fails closed in production

[v2/src/backend/dependencies.py#L425-486](../../../../v2/src/backend/dependencies.py#L425) (`requires_role`):
- Reads `x-ms-client-principal` (claims blob) + `x-ms-client-principal-id`.
- If the **claims blob is absent** and `environment != LOCAL` → `raise HTTPException(401, "Missing client principal claims; Easy Auth claims header required.")`.
- `REQUIRE_ADMIN_USER = requires_role("admin")` gates the entire admin router.

### No platform injects that header

A grep for `authConfig|easyAuth|identityProviders|x-ms-client-principal` across `main.bicep` returns exactly **one** hit — [v2/infra/main.bicep#L1503](../../../../v2/infra/main.bicep#L1503) — which is the **PostgreSQL `authConfig` (AAD/password)** block, NOT App Service/Container App Easy Auth. Neither `frontendWebApp` nor `backendContainerApp` declares an auth/identity-provider config. Azure Container Apps do **not** emit `x-ms-client-principal` unless an auth config is attached.

**Net effect:** every `/api/admin/*` call (document upload, ingest, runtime config) returns **401** in the deployed environment. This is the most certain "cannot communicate + missing configuration" symptom. (Plain chat via `/api/conversation` is NOT role-gated, so it is *not* blocked by RC-1 — only the admin surface is.)

---

## 6. Focus Area: Environment-Variable Injection (used vs should-use)

### Backend Container App `env` ([v2/infra/main.bicep#L1820-1916](../../../../v2/infra/main.bicep#L1820)) — present, correct

Identity (`AZURE_CLIENT_ID`, `AZURE_UAMI_CLIENT_ID`, `AZURE_TENANT_ID`), `AZURE_ENVIRONMENT=production`, Foundry/OpenAI endpoints, model deployments, DB routing (`AZURE_DB_TYPE`, `AZURE_INDEX_STORE`, `AZURE_COSMOS_ENDPOINT`, `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_POSTGRES_ENDPOINT`), Foundry-IQ KB vars, Speech, Content Safety, `CWYD_ORCHESTRATOR_NAME`, Storage (account/container/queue), `AZURE_INGESTION_TRIGGER`, and (when monitoring on) `AZURE_APP_INSIGHTS_CONNECTION_STRING`.

### Frontend App Service `appSettings` ([v2/infra/main.bicep#L2007-2030](../../../../v2/infra/main.bicep#L2007))

`BACKEND_API_URL` (→ backend FQDN), `WEBSITES_ENABLE_APP_SERVICE_STORAGE=false`, `SCM_DO_BUILD_DURING_DEPLOYMENT=true`, optional App Insights.

### Function App `appSettings` ([v2/infra/main.bicep#L2166-2216](../../../../v2/infra/main.bicep#L2166))

AAD-only `AzureWebJobsStorage__*`, `FUNCTIONS_EXTENSION_VERSION=~4`, identity, Foundry endpoints, embedding deployment, DB routing, storage wiring.

### Variable names — used vs should-use

| Concern | Backend reads (code) | Infra sets | Match? |
|---|---|---|---|
| CORS allow-list | `BACKEND_CORS_ORIGINS` ([settings.py#L319](../../../../v2/src/backend/core/settings.py#L319)) | *(nothing)* | ❌ **MISSING (RC-2)** |
| Admin auth | `x-ms-client-principal` header (Easy Auth) ([dependencies.py#L440](../../../../v2/src/backend/dependencies.py#L440)) | no `authConfig` | ❌ **MISSING (RC-1)** |
| Backend URL for SPA | `BACKEND_API_URL` ([frontend_app.py#L49](../../../../v2/src/frontend/frontend_app.py#L49)) | set ✔ | ✅ |
| App Insights (backend) | `AZURE_APP_INSIGHTS_CONNECTION_STRING` | set when monitoring ✔ | ✅ |

No env-var **name mismatches** were found among the wired vars; the failures are **omissions**, not typos.

---

## 7. Focus Area: Circular FQDN Dependency (design tension behind RC-2)

- The **frontend module depends on the backend module's output**: `BACKEND_API_URL = 'https://${backendContainerApp.outputs.fqdn}'` ([L2011](../../../../v2/infra/main.bicep#L2011)). So the backend is realized **before** the frontend in the dependency DAG.
- To allow-list the frontend origin on the backend (`BACKEND_CORS_ORIGINS`), the backend module would need the **frontend FQDN** — but referencing `frontendWebApp.outputs.defaultHostname` from inside `backendContainerApp` creates a **module-output cycle** (Bicep rejects it).
- **Why it's still solvable (and why the gap is an omission, not a hard constraint):** the frontend App Service hostname is **deterministic** — `app-frontend-${solutionSuffix}.azurewebsites.net`. The backend CORS env could be set to a **composed literal** `https://app-frontend-${solutionSuffix}.azurewebsites.net` (no module-output reference, no cycle), or set post-hoc via a `post_provision` `az containerapp update` once both FQDNs exist. Neither is implemented today.

---

## 8. Focus Area: First-`azd up` Ordering & Placeholder Image

- On a clean first `azd up`, `backendContainerRegistryHostname` is empty, so the backend boots a **public placeholder** `mcr.microsoft.com/k8se/quickstart:latest` ([L1801-1803](../../../../v2/infra/main.bicep#L1801)). `azd deploy` then builds/pushes the real image and patches the live revision via the `azd-service-name: backend` tag swap.
- The frontend's `BACKEND_API_URL` points at the backend **FQDN**, which is stable across the placeholder→real image swap, so the pointer stays valid. **Not a root cause**, but during the window between provision and `azd deploy` the backend FQDN serves the quickstart page (no `/api/*`), which can look like "backend not responding" if probed too early.

---

## Deliverables Summary

### (a) Exact file paths + line numbers

- azd manifest: [v2/azure.yaml](../../../../v2/azure.yaml).
- Backend Container App + env: [v2/infra/main.bicep#L1742-1916](../../../../v2/infra/main.bicep#L1742); ingress [#L1770-1779](../../../../v2/infra/main.bicep#L1770); production pin [#L1845](../../../../v2/infra/main.bicep#L1845).
- Frontend App Service + appSettings: [v2/infra/main.bicep#L1962-2034](../../../../v2/infra/main.bicep#L1962); `BACKEND_API_URL` [#L2009-2012](../../../../v2/infra/main.bicep#L2009).
- Function App: [v2/infra/main.bicep#L2102-2230](../../../../v2/infra/main.bicep#L2102).
- Outputs (frontend URL + "CORS must allow" note): [v2/infra/main.bicep#L2583-2588](../../../../v2/infra/main.bicep#L2583).
- Backend CORS code: [v2/src/backend/app.py#L241-263](../../../../v2/src/backend/app.py#L241); setting [v2/src/backend/core/settings.py#L304-320](../../../../v2/src/backend/core/settings.py#L304).
- Admin gate: [v2/src/backend/dependencies.py#L425-486](../../../../v2/src/backend/dependencies.py#L425).
- Runtime config: [v2/src/frontend/frontend_app.py](../../../../v2/src/frontend/frontend_app.py); [v2/src/frontend/src/api/runtimeConfig.tsx](../../../../v2/src/frontend/src/api/runtimeConfig.tsx).
- Frontend packaging: [v2/scripts/package_frontend.py](../../../../v2/scripts/package_frontend.py).

### (b) MISSING / BROKEN configuration list

1. **MISSING — Easy Auth / `authConfig`** on backend Container App (and/or frontend App Service), while backend is pinned `AZURE_ENVIRONMENT=production` → admin/ingest endpoints 401. (RC-1)
2. **MISSING — `BACKEND_CORS_ORIGINS`** on the backend Container App env (infra author flagged it in an output comment but never wired it). Masked by wildcard fallback in public mode; broken otherwise. (RC-2)
3. **BROKEN (conditional) — private-networking reachability**: backend internal-only + SPA points at internal FQDN + no reverse proxy → browser cannot reach backend when `enablePrivateNetworking=true`. (RC-3)
4. **NOTE — scale-to-zero** backend (`minReplicas: 0` in default profile): first-hit cold start can read as a transient comms failure.

### (c) Env-var names — used vs should-use

- CORS: code reads `BACKEND_CORS_ORIGINS`; infra sets nothing → should set `BACKEND_CORS_ORIGINS=https://app-frontend-${solutionSuffix}.azurewebsites.net` (deterministic literal, avoids the cycle).
- Admin auth: code expects platform-injected `x-ms-client-principal`; infra should attach an Easy Auth/identity-provider `authConfig` to produce it (or the environment must run with an auth proxy in front).
- All other wired vars (`BACKEND_API_URL`, identity, endpoints, DB routing, storage, App Insights) match between code and infra — no name drift.

### (d) Build-time vs runtime determination

**RUNTIME.** The deployed frontend (App Service, uvicorn `frontend_app.py`, port 8000) learns the backend URL from `BACKEND_API_URL` via `GET /config` at boot — nothing is baked into the Vite bundle. `VITE_BACKEND_URL` build-arg is used **only** by the `docker-compose` image (`Dockerfile.frontend`, port 80), not the App Service deploy.

### (e) Circular FQDN dependency analysis

Real and explains RC-2: frontend depends on backend FQDN, so backend cannot reference frontend FQDN output (Bicep module-output cycle). **Resolvable** without a cycle because the frontend hostname is deterministic (`app-frontend-${solutionSuffix}.azurewebsites.net`) — set CORS to that composed literal, or patch it post-provision via `az containerapp update`. Not implemented today.

---

## Open Questions for the Requester

1. **Which symptom are you actually seeing?** (a) Admin/upload page returns 401/403, (b) chat itself fails cross-origin, or (c) total failure (nothing loads/responds). (a) → RC-1; (b) → RC-2/RC-3; (c) → RC-3 / cold-start.
2. **Did you deploy with `enablePrivateNetworking=true`?** If yes, RC-3 is almost certainly the primary blocker (browser cannot reach the internal backend at all).
3. **Is any authentication expected in front of the app** (App Service Easy Auth, APIM, a gateway)? RC-1 hinges on whether `x-ms-client-principal` is meant to be injected by the platform or by something the bicep doesn't provision.
4. Do you want the follow-up (implementation) task to **wire `BACKEND_CORS_ORIGINS` + Easy Auth**, or first reproduce against your specific `azd env get-values` to confirm which RC fires?

---

## 12. Default-path verification (follow-up)

> Scope: determine, for a **DEFAULT `azd up` (no special flags)**, the single most likely active blocker for "frontend and backend cannot communicate." All answers re-verified against source on 2026-06-28.

### 12.1 — MACAE reference is ABSENT on disk (confirmed)

`list_dir` on `data/sample_code` returns exactly two subfolders:

- `prototypes-main/`
- `python_agent_framework_dev_template-main/`

**`macae/` exists on disk right now: NO.** The earlier "MACAE public-mode CORS gate" framing is a *pattern reference only*; there is no MACAE source vendored in this repo to copy from.

### 12.2 — Backend ingress CORS policy: NONE configured (confirmed)

- Grep `corsPolicy|allowedOrigins|ingressCorsPolicy` over `v2/infra/main.bicep` (the Bicep source) → **No matches.** The backend Container App module call ([v2/infra/main.bicep#L1742](../../../../v2/infra/main.bicep#L1742)) sets `ingressTargetPort`, `ingressExternal`, `ingressAllowInsecure`, `ingressTransport` ([#L1770-1779](../../../../v2/infra/main.bicep#L1770)) but **no `corsPolicy`** on ingress.
- Broad grep `corsPolicy|allowedOrigins|cors` over `v2/infra/**` → the only `*.bicep` hit is the **output description comment** `'... Backend CORS must allow this origin.'` ([v2/infra/main.bicep#L2583](../../../../v2/infra/main.bicep#L2583)). Every other hit is in the compiled `v2/infra/main.json` and is a **storage-account `corsRules` AVM *type definition*** (`blobCorsRuleType` / `fileCorsRuleType` / `queueCorsRuleType` / `tableCorsRuleType` at `main.json#L23255-23475`, with `allowedOrigins` at `main.json#L23732`) — i.e., the storage module's schema, **not** an ingress CORS policy and **not** applied to the backend.

**Verdict:** CWYD does **NOT** set the MACAE-style Container Apps ingress `corsPolicy.allowedOrigins`. Cross-origin enforcement lives **only** in the backend app code (FastAPI `CORSMiddleware`, [v2/src/backend/app.py#L241-263](../../../../v2/src/backend/app.py#L241)), which falls back to `allow_origins=["*"], allow_credentials=False` when `BACKEND_CORS_ORIGINS` is unset (it is unset in infra — see §3/RC-2).

### 12.3 — Feature-flag parameter DEFAULTS (confirmed)

| Param | Default | Line |
|---|---|---|
| `enableMonitoring` | **`true`** | [main.bicep#L215](../../../../v2/infra/main.bicep#L215) |
| `enableScalability` | **`false`** | [main.bicep#L218](../../../../v2/infra/main.bicep#L218) |
| `enableRedundancy` | **`false`** | [main.bicep#L221](../../../../v2/infra/main.bicep#L221) |
| `enablePrivateNetworking` | **`false`** | [main.bicep#L224](../../../../v2/infra/main.bicep#L224) |

**Consequence for a vanilla `azd up`:** `enablePrivateNetworking=false` → backend ingress `ingressExternal: !enablePrivateNetworking` = **EXTERNAL** ([main.bicep#L1772](../../../../v2/infra/main.bicep#L1772)) → the backend gets a public `*.azurecontainerapps.io` FQDN the **browser can reach**. RC-3 (internal-only dead-end) does **NOT** fire in the default profile. `enableScalability=false` → backend `minReplicas: 0` (scale-to-zero, cold-start on first hit). `enableMonitoring=true` → App Insights wired.

### 12.4 — Frontend has NO reverse proxy; serves static SPA + `/config` only (confirmed)

Full read of [v2/src/frontend/frontend_app.py](../../../../v2/src/frontend/frontend_app.py) (66 lines). It defines **exactly two routes**:

- `GET /config` → `FrontendConfig(backend_url=os.environ["BACKEND_API_URL"])` ([#L48-51](../../../../v2/src/frontend/frontend_app.py#L48)).
- `GET /{full_path:path}` → static file from `dist/` if it exists (with `..` traversal guard), else `index.html` (SPA catch-all) ([#L54-66](../../../../v2/src/frontend/frontend_app.py#L54)).

There is **no `/api/{path}` proxy route** forwarding to the backend, and **no `PROXY_API_REQUESTS`-style flag anywhere** — grep `PROXY_API_REQUESTS|proxy` over `v2/src/frontend/**` returns only doc-comment uses of the word "proxy" (the module docstring says "no extra proxy"; `admin.tsx#L40-41` references the *local Vite* dev proxy). The deployed SPA therefore makes **direct cross-origin** calls to the backend FQDN (`getBackendUrl()` from `/config`); there is **no same-origin `/api` path** through the App Service. MACAE's `PROXY_API_REQUESTS=true` same-origin mode does **not** exist in CWYD.

### 12.5 — Environment default, production pin, and the two gates (confirmed)

- **Code default:** `environment: Environment = Environment.LOCAL` ([v2/src/backend/core/settings.py#L534](../../../../v2/src/backend/core/settings.py#L534); enum `Environment` `LOCAL="local"` / `PRODUCTION="production"` at [#L41-52](../../../../v2/src/backend/core/settings.py#L41)). A clean checkout boots `local` (matches repo convention).
- **Infra hard-pins production:** `{ name: 'AZURE_ENVIRONMENT', value: 'production' }` on the backend Container App at [v2/infra/main.bicep#L1845](../../../../v2/infra/main.bicep#L1845) (Function App likewise at [#L2186](../../../../v2/infra/main.bicep#L2186)). So the deployed backend runs `environment=PRODUCTION`.
- **Admin role gate (`requires_role`)** — [v2/src/backend/dependencies.py#L425-486](../../../../v2/src/backend/dependencies.py#L425): if the `x-ms-client-principal` **claims blob** is absent and `environment is not LOCAL` → **`raise HTTPException(401, "Missing client principal claims; Easy Auth claims header required.")`** ([#L450-457](../../../../v2/src/backend/dependencies.py#L450)). `REQUIRE_ADMIN_USER = requires_role("admin")` ([#L494](../../../../v2/src/backend/dependencies.py#L494)); `AdminUserIdDep = Annotated[str, Depends(REQUIRE_ADMIN_USER)]` ([#L495](../../../../v2/src/backend/dependencies.py#L495)).
- **Which routers are gated:** grep `REQUIRE_ADMIN_USER|requires_role|AdminUserIdDep` over `v2/src/backend/**` → the role gate is consumed **only** by `routers/admin.py` (every admin route: [#L118](../../../../v2/src/backend/routers/admin.py#L118), [#L155](../../../../v2/src/backend/routers/admin.py#L155), [#L189](../../../../v2/src/backend/routers/admin.py#L189), [#L273](../../../../v2/src/backend/routers/admin.py#L273), [#L418](../../../../v2/src/backend/routers/admin.py#L418), [#L467](../../../../v2/src/backend/routers/admin.py#L467), [#L548](../../../../v2/src/backend/routers/admin.py#L548), [#L604](../../../../v2/src/backend/routers/admin.py#L604)). No other router imports it.
- **`/api/conversation` is NOT role-gated**, but it **is identity-gated** via `UserIdDep` ([v2/src/backend/routers/conversation.py#L73](../../../../v2/src/backend/routers/conversation.py#L73)). `UserIdDep` → `get_user_id` ([dependencies.py#L346-378](../../../../v2/src/backend/dependencies.py#L346)) **also fails closed in production** — *but only when the `x-ms-client-principal-id` header is absent* ([#L373-377](../../../../v2/src/backend/dependencies.py#L373)).
- **Why chat still clears the identity gate with no Easy Auth:** the SPA **self-supplies** that header on every call. `userIdHeaders()` ([v2/src/frontend/src/api/auth.tsx#L108](../../../../v2/src/frontend/src/api/auth.tsx#L108)) returns `{ "x-ms-client-principal-id": getUserId() }`, defaulting to `DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000000"` ([#L42](../../../../v2/src/frontend/src/api/auth.tsx#L42)) because `/.auth/me` returns `null` with no identity provider. The chat SSE client spreads it onto `POST /api/conversation`: `headers: { ..., ...userIdHeaders() }` ([v2/src/frontend/src/api/streamChat.tsx#L246](../../../../v2/src/frontend/src/api/streamChat.tsx#L246)). The all-zeros UUID satisfies the backend allow-pattern `_PRINCIPAL_ID_PATTERN = [A-Za-z0-9._@-]{1,128}` ([dependencies.py#L326](../../../../v2/src/backend/dependencies.py#L326)), so `get_user_id` returns it — **no 401**. The admin gate cannot be satisfied this way because it requires the **claims blob** (`x-ms-client-principal`), which the SPA never sends and which only a platform Easy Auth layer injects.

**Net:** in the deployed default profile, **plain chat is UNgated in practice** (self-supplied id clears `UserIdDep`); the **entire `/api/admin/*` surface fails closed 401** (no claims blob → `requires_role` rejects every caller).

### 12.6 — Easy Auth / identity-provider config on the apps: NONE (confirmed)

Grep `authsettingsV2|authConfig|identityProviders|easyAuth|login|x-ms-client-principal` over `v2/infra/**`:

- The only `*.bicep` `authConfig` is **PostgreSQL** AAD/password auth at [v2/infra/main.bicep#L1503](../../../../v2/infra/main.bicep#L1503) (the Postgres flexible-server module), echoed in `main.json#L37892`/`#L38307`.
- `main.json#L37082` `authConfig` + `administratorLogin*` (`#L37868-37879`, `#L38305-38306`) are the **ACR / PostgreSQL** module schemas — not app auth.
- **Zero** `authsettingsV2`, `identityProviders`, or `Microsoft.Web/sites/config` auth-settings blocks on **either** the frontend App Service (`frontendWebApp`, [#L1962](../../../../v2/infra/main.bicep#L1962)) **or** the backend Container App (`backendContainerApp`, [#L1742](../../../../v2/infra/main.bicep#L1742)). The `login*` hits are all container-registry **`loginServer`** strings (`#L1600`, `#L1759`, `#L1765`, `#L2592-2593`), unrelated to Easy Auth.

**Verdict:** **NO** Easy Auth / `authConfig` / identity-provider config is attached to the frontend App Service or backend Container App. Therefore nothing injects `x-ms-client-principal` claims, and `/.auth/me` on the frontend origin returns `null`.

### 12.7 — Single most likely active blocker (verdict)

For a **true default `azd up`** (`enablePrivateNetworking=false` → backend reachable; CORS wildcard non-credentialed → chat preflight passes; production pin on):

- **Sub-case (b) — only ADMIN / UPLOAD fails (chat works):**
  **DECISIVE — RC-1: no Easy Auth `authConfig` is wired on the backend Container App while `AZURE_ENVIRONMENT=production`, so `requires_role("admin")` fails closed with HTTP 401 for every caller.** The `/api/admin/*` routes ([admin.py](../../../../v2/src/backend/routers/admin.py)) demand the `x-ms-client-principal` claims blob ([dependencies.py#L450-457](../../../../v2/src/backend/dependencies.py#L450)); the SPA only forwards the forgeable `x-ms-client-principal-id`, and no platform injects the claims blob ([§12.6](#126--easy-auth--identity-provider-config-on-the-apps-none-confirmed)). This is certain and is the single blocker for the admin surface.

- **Sub-case (a) — EVEN PLAIN CHAT fails (nothing works):**
  In a genuine default deploy this is **NOT** an auth or CORS wiring gap — §12.5 proves chat clears `UserIdDep` via the self-supplied id, and §12.2 + §3 prove wildcard non-credentialed CORS admits the SPA's `POST /api/conversation` (no `credentials:'include'` anywhere). So the single most likely active blocker is **backend availability, not configuration: the backend Container App is not serving the real CWYD image to the browser** — most commonly because the backend is still on the public placeholder `mcr.microsoft.com/k8se/quickstart:latest` ([main.bicep#L1801-1803](../../../../v2/infra/main.bicep#L1801)) when `azd deploy` for the `backend` service has not completed or failed (the placeholder has no `/api/*`, so every SPA call 404s), or — secondarily — the scale-to-zero backend (`minReplicas:0`, §12.3) cold-starts slower than the first SSE client's timeout.
  **Alternative to rule out first:** if "nothing works" persists after a confirmed-successful full `azd up`, verify the deploy was *truly* default — `azd env get-values | findstr PRIVATE` / check the active parameters file. If `enablePrivateNetworking=true` slipped in (e.g., the WAF parameters set), then **RC-3 is the blocker**: internal-only backend ingress + SPA pointed at the internal CAE FQDN + no reverse proxy in `frontend_app.py` ([§12.4](#124--frontend-has-no-reverse-proxy-serves-static-spa--config-only-confirmed)) = total browser→backend failure for chat *and* admin alike.

**One-line summary:** *Default `azd up` → admin/upload is blocked by the missing Easy Auth `authConfig` (RC-1, certain); plain chat is not blocked by config and, if it also fails, the cause is backend image/availability (placeholder-image or cold-start) — unless private networking was unknowingly enabled, in which case RC-3 takes everything down.*
