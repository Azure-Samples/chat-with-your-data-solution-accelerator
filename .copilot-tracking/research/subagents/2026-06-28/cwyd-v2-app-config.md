<!-- markdownlint-disable-file -->

# CWYD v2 — Frontend ↔ Backend communication: application-config diagnosis (RESEARCH ONLY)

Scope: read-only investigation of why the v2 frontend and backend cannot
communicate after `azd up`. No code was modified. Every path/line below was
read directly from the working tree. Env-specific values use placeholder
tokens (`<SUFFIX>`, `<RESOURCE_GROUP>`, …) per the repo's no-secrets rule.

---

## TL;DR — likely application-level root cause

There are **two** distinct config concerns, and they must not be conflated:

1. **The "expects vs provides" mismatch the task points at (config gap, latent).**
   The backend FastAPI CORS layer is driven by the **bare** env var
   `BACKEND_CORS_ORIGINS` (read by `NetworkSettings.cors_origins`), but
   **`main.bicep` never sets `BACKEND_CORS_ORIGINS` on the backend Container
   App** (zero matches anywhere under `v2/infra/**`). The backend therefore
   falls back to wildcard `["*"]` with `allow_credentials=False`. This is a
   real, documented wiring gap (BUG-0069 observed `cors_origins: []` live), and
   the bicep even has an output comment "Backend CORS must allow this origin"
   (line 2583) describing a wire that was never connected.
   **Caveat (important):** a wildcard `["*"]` + credentials-off CORS policy
   *does* permit the frontend's actual request shape (a non-credentialed,
   header-only `fetch` — no cookies, no `credentials: "include"`). So on its
   own the missing `BACKEND_CORS_ORIGINS` does **not** block the current client
   code; it is a latent/incomplete-wiring issue that would bite the moment
   credentialed CORS is needed or the wildcard is tightened.

2. **The stronger, more probable real blocker (runtime backend-URL resolution).**
   In the azd `host: appservice` build-from-source deployment, the deployed SPA
   resolves the backend origin **entirely at runtime** from `GET /config`
   (served by `frontend_app.py`, fed by the `BACKEND_API_URL` app setting). The
   build-time fallback `VITE_BACKEND_URL` is **empty** in that build path. If
   `/config` is unavailable, stale, or returns an empty/wrong `backendUrl`
   (e.g. the frontend serving a placeholder/old build, `BACKEND_API_URL` not
   set, or private-networking making the backend FQDN unreachable from the
   browser), then `getBackendUrl()` returns `""` and **every `/api/*` call
   resolves against the frontend App Service's own origin**, whose SPA catch-all
   returns `index.html` (HTTP 200 + HTML) → `response.json()` throws → the chat
   path, health probe, admin probe, etc. all silently break. This exact failure
   class is documented repeatedly (BUG-0050, BUG-0070, BUG-0090, BUG-1205) and
   the frontend deployment mechanism itself has a troubled history
   (BUG-0081/BUG-0090: "the frontend has never been deployable as designed").

**Net:** Report the `BACKEND_CORS_ORIGINS` mismatch as the clear infra
"expects vs provides" config gap (deliverable d), but flag the wildcard caveat
so it is not overstated. The most likely *active* break after `azd up` is the
runtime `/config` / `BACKEND_API_URL` backend-URL seam (and its deployability
history), not CORS.

---

## (a) Key files and exact locations

### Frontend (`v2/src/frontend/`)

| Concern | File | Symbol / line |
| --- | --- | --- |
| Runtime backend-URL seam | `src/api/runtimeConfig.tsx` | `getBackendUrl()` (~L34), `loadRuntimeConfig()` (~L48), `CONFIG_URL = "/config"` |
| Chat SSE client | `src/api/streamChat.tsx` | `CONVERSATION_PATH = "/api/conversation"` (~L46), `conversationUrl()` (~L66) → `${getBackendUrl()}${CONVERSATION_PATH}` |
| Identity headers | `src/api/auth.tsx` | `getUserInfo()` → `GET /.auth/me` (SPA origin), `userIdHeaders()` → `x-ms-client-principal-id`, `DEFAULT_USER_ID = 00000000-…` |
| Boot ordering + health | `src/App.tsx` | `useEffect` (~L130): `loadRuntimeConfig().then(() => fetchHealth(...))`; `fetchHealth` (~L70) → `${getBackendUrl().replace(/\/$/,"")}/api/health` |
| Vite dev proxy | `vite.config.ts` | port 5273; dev-only `server.proxy["/api"] → http://localhost:8000` |
| Prod static server + `/config` | `frontend_app.py` | `GET /config` (~L50) → `FrontendConfig(backend_url=os.environ.get("BACKEND_API_URL",""))`; SPA catch-all `GET /{full_path:path}` (~L55) |
| Build script | `package.json` | `"build": "tsc -b && vite build"` — **no** OpenAPI codegen step |

### Backend (`v2/src/backend/`)

| Concern | File | Symbol / line |
| --- | --- | --- |
| App factory + CORS | `app.py` | `create_app()` (~L234): `origins = list(network.cors_origins) or ["*"]`; `allow_credentials = origins != ["*"]`; `CORSMiddleware(...)` |
| CORS env var | `core/settings.py` | `NetworkSettings` (L291, `env_prefix="AZURE_"`); `cors_origins` field (L317) `validation_alias=AliasChoices("BACKEND_CORS_ORIGINS","cors_origins")`; `_split_cors_origins` (L322) empty→`[]` |
| Router prefixes | `routers/health.py` `/api`; `routers/conversation.py` `/api`; `routers/files.py` `/api`; `routers/admin.py` `/api/admin`; `routers/history.py` `/api/history`; `routers/speech.py` `/api/speech` | — |
| Health | `routers/health.py` | `GET /api/health` (always 200); `GET /api/health/ready` (503 on FAIL) |

### Infra (`v2/infra/main.bicep`)

| Concern | Line | Detail |
| --- | --- | --- |
| Backend Container App | `module backendContainerApp` (~L1742) | `ingressTargetPort: 8000`; `ingressExternal: !enablePrivateNetworking`; `ingressAllowInsecure: false` |
| Backend env array | ~L1808–1916 | `AZURE_CLIENT_ID`, `AZURE_ENVIRONMENT='production'`, Foundry/OpenAI/DB/storage/speech/content-safety, `CWYD_ORCHESTRATOR_NAME`, conditional `AZURE_APP_INSIGHTS_CONNECTION_STRING`. **No `BACKEND_CORS_ORIGINS`.** |
| Frontend App Service | `module frontendWebApp` (~L1969) | `linuxFxVersion: 'PYTHON\|3.11'`; `appCommandLine: 'uvicorn frontend_app:app --host 0.0.0.0 --port 8000'`; `SCM_DO_BUILD_DURING_DEPLOYMENT=true`; **`BACKEND_API_URL = https://${backendContainerApp.outputs.fqdn}`** (~L2016) |
| Smoking-gun output | ~L2583–2584 | `output AZURE_FRONTEND_URL` with description "Backend CORS must allow this origin" — never fed back into the backend env |

### Functions (`v2/src/functions/`) — brief

- Reuses the backend's settings + provider tree: every blueprint imports
  `backend.core.settings` + `backend.core.providers.*` (e.g.
  `add_url/blueprint.py` L55–59, `search_skill/blueprint.py` L55–57). Same
  `AZURE_`-prefixed settings model as the backend.
- Triggers: HTTP (`add_url`, `search_skill`, `batch_start`) + queue
  (`batch_push`) + blob/event-grid (`function_app.py` registers the blueprint
  set). Shares the storage account + `doc-processing` queue with the backend.
- **Not on the frontend↔backend chat path.** Ingestion-only; no CORS surface
  relevant to the browser. Excluded as a cause of the chat-path break.

---

## (b) How the frontend resolves the backend URL — RUNTIME, not build-time

**Mechanism (current code):** runtime `/config`, with a build-time fallback.

1. On boot, `App.tsx` `useEffect` calls `loadRuntimeConfig()` and only then
   `fetchHealth()` — ordering is **correct**, no race.
2. `loadRuntimeConfig()` (`runtimeConfig.tsx` ~L48) does `fetch("/config")`
   against the **SPA's own origin** (the frontend App Service), reads the
   JSON field `backendUrl`, and caches it. On any failure it leaves the cache
   unset.
3. `getBackendUrl()` (~L34) returns the cached value if set, else falls back to
   the build-time `import.meta.env.VITE_BACKEND_URL` — which is **empty** in the
   azd build-from-source App Service path (Oryx does not set it).
4. Every API client composes absolute URLs as `${getBackendUrl()}/api/...`
   (`streamChat.tsx`, `App.tsx` health, admin, history, speech, file links).

**Variable names:**

- Runtime value lives in the **`BACKEND_API_URL`** App Service app setting
  (`main.bicep` ~L2016) → surfaced by `frontend_app.py` `GET /config` as the
  wire field **`backendUrl`**.
- Build-time fallback variable is **`VITE_BACKEND_URL`** (empty in the deployed
  bundle; only set in the docker-compose / manual-container path,
  `Dockerfile.frontend` L43–44).

**Failure characteristic:** if `/config` is missing or returns `""`,
`getBackendUrl()` → `""` → `/api/*` hits the frontend origin's SPA catch-all
(`frontend_app.py` ~L55) → `index.html` (200, HTML) → JSON parse throws. This
is the documented break class (BUG-0050/0070/0090/1205).

---

## (c) Backend CORS configuration

- `app.py` `create_app()` (~L234+):
  - `network = NetworkSettings()`
  - `origins = list(network.cors_origins) or ["*"]`
  - `allow_credentials = origins != ["*"]`
  - `app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=allow_credentials, allow_methods=["*"], allow_headers=["*"])`
- `NetworkSettings.cors_origins` (`settings.py` L317) reads the **bare**
  `BACKEND_CORS_ORIGINS` (note: NOT `AZURE_`-prefixed, via `AliasChoices`).
  `_split_cors_origins` maps empty string → `[]`.
- **Effective deployed policy:** with no `BACKEND_CORS_ORIGINS` set, origins is
  `[]` → wildcard `["*"]`, `allow_credentials=False`. (BUG-0069 confirms
  `cors_origins: []` on a live backend.)
- The frontend never sends `credentials: "include"` (grep: zero usages), so the
  wildcard policy is *compatible* with the current request shape.

---

## (d) The env-var mismatch (expects vs provides) — the requested focus

| Layer | Variable | Set where? | Read where? | Status |
| --- | --- | --- | --- | --- |
| Backend CORS | `BACKEND_CORS_ORIGINS` | **Nowhere in `v2/infra/**`** (0 matches) | `settings.py` L317 → `app.py` CORS | **MISSING — expects-vs-provides gap.** Falls back to `["*"]`. |
| Frontend backend URL | `BACKEND_API_URL` | `main.bicep` ~L2016 (frontend App Service) | `frontend_app.py` `/config` | Wired correctly (runtime seam). |
| Frontend build fallback | `VITE_BACKEND_URL` | only docker/manual path | `runtimeConfig.tsx` fallback | Empty in azd App Service build → relies on `/config`. |
| Infra advertises | `AZURE_FRONTEND_URL` output | `main.bicep` L2583 ("Backend CORS must allow this origin") | **Never consumed by backend env** | Dangling — documents the wire that was never connected. |

**Conclusion for (d):** The backend *expects* `BACKEND_CORS_ORIGINS`; infra
*provides* it nowhere. That is the clean, documented config mismatch. But
because the fallback is a permissive wildcard that the current
non-credentialed frontend can use, treat it as a **latent/incomplete-wiring
defect** rather than the definitive active blocker. The active blocker is more
likely the runtime `/config`/`BACKEND_API_URL` seam and the frontend's
deployability history (BUG-0081/0090), or — if `enablePrivateNetworking=true`
— the backend's internal-only ingress being unreachable from the browser.

---

## (e) API base-path comparison (frontend vs backend) — no prefix mismatch

- Frontend builds: `${getBackendUrl()}/api/<route>` (absolute, cross-origin).
- Backend serves: `/api` (health, conversation, files), `/api/admin`,
  `/api/history`, `/api/speech`. FastAPI has **no `root_path`/base prefix**.
- The path segments line up exactly — the break is **origin** (cross-host),
  never path. When `getBackendUrl()` is empty the same `/api/...` path simply
  lands on the wrong origin (the frontend App Service), which returns
  `index.html`.
- OpenAPI schema is served at `/openapi.json` (default FastAPI).
- Backend listens on **port 8000** (bicep `ingressTargetPort: 8000`; App
  Service `--port 8000`). Frontend App Service also runs uvicorn on 8000.

---

## OpenAPI contract (deliverable 4) — hand-written, no codegen

- **No OpenAPI client generator** is wired: no `openapi-typescript`, `orval`,
  or `openapi-generator` dependency or script (grep: zero matches in `v2/**`
  outside docs). `package.json` build is `tsc -b && vite build` only.
- The TS API clients under `src/api/*.tsx` and wire models under `src/models/*`
  are **hand-authored** typed `fetch` wrappers. Each reads `getBackendUrl()` at
  call time, so there is no generated client base-URL config to misconfigure —
  the single source of base-URL truth is the runtime `/config` seam.
- The backend `/openapi.json` is reachable and lists the routes (verified by
  smoke test `v2/tests/smoke/test_backend_only.py`).

---

## Supporting evidence from the defect registry (`v2/docs/bugs.md`)

- **BUG-0069** (high/infra/fixed): deployed backend reported `environment:
  local`, `cors_origins: []`, `app_insights_enabled: false` — env-var-wiring
  class; confirms `BACKEND_CORS_ORIGINS` was never set on the Container App.
- **BUG-0050 / BUG-0070 / BUG-0090 / BUG-1205** (fixed): individual frontend
  clients that used **relative** `/api/*` URLs resolved against the frontend
  SPA catch-all (`index.html`, 200) instead of the backend; fixed by prepending
  the backend base. Demonstrates the dominant real-world failure mode is
  origin/URL resolution, not CORS.
- **BUG-0081 / BUG-0090**: frontend deployment-mechanism mismatch
  (`azure.yaml host: appservice` vs originally container-kind bicep) — "the
  frontend has never been deployable as designed." Now reconciled to
  build-from-source (`SCM_DO_BUILD_DURING_DEPLOYMENT`, `package_frontend`
  staging), but if a stale/placeholder build is live, `/config` and the SPA
  break.
- Identity bugs (the `/.auth/me` + `x-ms-client-principal-id` forwarding work):
  confirm there is **no Easy Auth fronting the backend Container App** and the
  frontend is genuinely cross-origin from the backend.

---

## Clarifying questions to confirm the active break

1. **Is the failing deployment using `enablePrivateNetworking=true`?** If so the
   backend Container App ingress is **internal-only** and the backend FQDN
   returned by `/config` is unreachable from the browser — that would be the
   decisive blocker regardless of CORS.
2. **Is the frontend App Service serving the real SPA or a placeholder/stale
   build?** (Check `GET https://app-frontend-<SUFFIX>.azurewebsites.net/config`
   returns a JSON `{"backendUrl": "https://ca-backend-<SUFFIX>…"}` and the page
   title is `CWYD v2`, not a placeholder.) If `/config` 404s or returns an
   empty `backendUrl`, that is the break.
3. **What is the actual browser error?** A genuine CORS error in devtools vs a
   `Failed to parse JSON` / 404 / "unexpected token `<`" (HTML) error
   distinguishes a CORS-policy block from the same-origin SPA-catch-all
   collapse. The latter (HTML parse) is far more consistent with the evidence.
4. **Does `GET https://ca-backend-<SUFFIX>…/api/admin/status` (or
   `/api/health`) report `cors_origins: []`** and is the backend reaching
   healthy? (`project_status.md` Gate 7 notes a path where "the backend never
   reaches healthy," which would break communication independent of URL/CORS.)
