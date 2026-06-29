<!-- markdownlint-disable-file -->
# MACAE — application-level frontend/backend communication after `azd up`

Research date: 2026-06-28
Scope: How the MACAE reference *application* (frontend SPA ↔ backend API) communicates once deployed by `azd up`, for porting to CWYD v2.
Status: Complete. Research-only — no code modified.

---

## 0. IMPORTANT — where the evidence came from (read first)

The local sample folder the task pointed at — `data/sample_code/macae/` — **no longer exists in this
workspace.** It was deleted (the 2026-06-25 "scrub" tracking docs recommended removing the reference
clone). Confirmed by `list_dir data/sample_code` → only `prototypes-main/` and
`python_agent_framework_dev_template-main/` remain.

To answer the task faithfully with **exact file paths + line numbers**, this report draws on two
high-fidelity sources:

1. **The public MACAE GitHub repo, `main` branch** (the sanctioned read-only pattern source named in
   `.github/copilot-instructions.md`): `https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator`.
   All `src/App/**`, `src/backend/**`, and `infra/**` line numbers below are from `main` as fetched today.
2. **Prior local subagent research** captured *before* the folder was deleted:
   `.copilot-tracking/research/subagents/2026-06-25/macae-container-build-pattern.md` (read from the
   then-present local files). Where I cite the *deleted local* layout (`infra/bicep/main.bicep`,
   `src/App/package_frontend.sh`) I label it **[local-2026-06-25]**; where I cite **[GitHub main]**
   it is live today. The two agree on the mechanism; only bicep file/line layout has since drifted.

⚠️ One caveat on line numbers: GitHub's code-search excerpts report line ranges that can be off by a
few lines from the rendered file. Treat every line number as "±3 lines, look for the named symbol."
The **symbol names + file paths are exact.**

---

## 1. TL;DR — the definitive communication pattern

**MACAE does NOT use nginx. It does NOT bake the backend URL at Vite build time. It uses a runtime
`/config` endpoint served by a small FastAPI "frontend server" (`frontend_server.py`).** That server
both (a) serves the built SPA and (b) tells the browser, at page boot, where the backend is.

MACAE ships a **hybrid of your Option A and Option B, selected at runtime by one env var,
`PROXY_API_REQUESTS`:**

| `PROXY_API_REQUESTS` | Deployment mode | Pattern | Browser → backend chain |
|----------------------|-----------------|---------|--------------------------|
| `'false'` (**public default**) | backend Container App has a public FQDN | **Option B — cross-origin, runtime-injected URL** | browser → `https://<backend-fqdn>/api/*` directly. CORS is allowed by (i) Container Apps ingress `corsPolicy.allowedOrigins` = the frontend App Service origin, and (ii) FastAPI `CORSMiddleware allow_origins=["*"]`. |
| `'true'` (**WAF / private networking**) | backend Container App is VNet-internal / IP-restricted | **Option A — same-origin reverse proxy** | browser → `https://<frontend>/api/*` (same origin) → `frontend_server.py` httpx/websocket proxy → private backend over VNet. **No browser CORS at all.** |

**Definitively NOT Option C** (no build-time Vite bake). A stale `REACT_APP_API_URL` type is declared
in `src/App/src/vite-env.d.ts` but the runtime flow ignores it; the only baked value is a localhost
*fallback* default in `config.tsx`.

The single mechanism that makes both modes work is the **runtime `/config` fetch**: the SPA's first
action on load is `fetch('/config')`, and `frontend_server.py` computes `API_URL` from
`os.getenv("BACKEND_API_URL")` and `PROXY_API_REQUESTS` *at request time* — so the same built image
points at any backend with no rebuild.

---

## 2. FRONTEND

The frontend lives at **`src/App/`** (a React + Vite SPA in `src/App/src/`, served by a FastAPI server
`src/App/frontend_server.py`). It is hosted on **Azure App Service** (native Python), not a container,
in the build-from-source flow.

### 2.1 How the SPA determines the backend base URL — the runtime `/config` chain

Boot sequence (4 files):

**(a) `src/App/src/index.tsx` (≈L20-52)** — on mount, the SPA fetches `/config` (same origin) and pushes
`API_URL` into the client config:

```tsx
// src/App/src/index.tsx  (≈L20-52)
useEffect(() => {
  const initConfig = async () => {
    window.appConfig = config;
    setEnvData(config);
    setApiUrl(config.API_URL);
    try {
      const response = await fetch('/config');        // <-- runtime fetch, same origin
      let config = defaultConfig;
      if (response.ok) {
        config = await response.json();               // { API_URL, ENABLE_AUTH }
        config.ENABLE_AUTH = toBoolean(config.ENABLE_AUTH);
      }
      window.appConfig = config;
      setEnvData(config);
      setApiUrl(config.API_URL);                      // <-- backend base URL applied at runtime
      setConfig(config);
      ...
    } catch (error) {
      console.info("frontend config did not load from python", error);
    } finally { setIsConfigLoaded(true); setIsUserInfoLoaded(true); }
  };
  initConfig();
}, []);
```

**(b) `src/App/src/api/config.tsx`** — holds the live `API_URL` and the localhost fallback:

```tsx
// src/App/src/api/config.tsx  (≈L12-24)
export let API_URL: string | null = null;
export let config = {
  API_URL: "http://localhost:8000/api",   // <-- localhost FALLBACK only (the lone baked value)
  ENABLE_AUTH: false,
};
export function setApiUrl(url: string | null) {
  if (url) {
    API_URL = url.includes('/api') ? url : `${url}/api`;
  }
}
export function setEnvData(configData: Record<string, any>) {
  if (configData) {
    config.API_URL = configData.API_URL || "";
    config.ENABLE_AUTH = configData.ENABLE_AUTH || false;
  }
}
// getApiUrl() (≈L72-86) returns API_URL, falling back to window.appConfig.API_URL.
```

**(c) `src/App/src/api/apiClient.tsx` (≈L14-19)** — every request lazily syncs the HTTP client's base URL
to the runtime `API_URL`:

```tsx
// src/App/src/api/apiClient.tsx  (≈L14-19)
function syncBaseUrl(): void {
  const apiUrl = getApiUrl();
  if (apiUrl && httpClient.getBaseUrl() !== apiUrl) {
    httpClient.setBaseUrl(apiUrl);     // base URL set after /config resolves
  }
}
// apiClient.get/post/put/delete/upload each call syncBaseUrl() first.
```

**(d) `src/App/src/api/httpClient.ts`** — the singleton fetch wrapper. `buildUrl` (≈L48-61) composes
`${baseUrl}${path}`, and `request` (≈L67-99) calls `fetch(finalUrl, …)`. So every API call goes to
`API_URL + path` — i.e. the backend FQDN cross-origin in the public default, or `/api/...` same-origin
in WAF mode. The auth interceptor (≈L228-244) adds `x-ms-client-principal-id` + `Authorization` headers
(header-based auth, **not cookies** — this matters for CORS, §3.3).

WebSocket URL is built the same way: `src/App/src/store/WebSocketService.tsx` imports `getApiUrl` and
derives the ws/wss URL from the runtime `API_URL`.

Searched-for tokens and the verdict:
- `VITE_` / `import.meta.env` — **not used for the backend URL.** `src/App/vite.config.ts` has **no
  `define`** for any backend URL; `outDir: 'build'`.
- `REACT_APP_API_URL` — declared in `src/App/src/vite-env.d.ts` (≈L3-6) but **dead**; the runtime
  `/config` path supersedes it.
- `process.env` — not used to resolve the backend URL at runtime in the browser.
- `config.json` / `env.js` / `window.__APP_CONFIG__` — **none.** The runtime config is `window.appConfig`,
  populated from the `fetch('/config')` JSON, not from a generated static file.

### 2.2 Build-time vs runtime — definitive

**Runtime-injected, not build-time baked.** The only value compiled into the bundle is the localhost
*fallback* in `config.tsx`. The real backend URL arrives at page load via `fetch('/config')`, whose
answer is computed live by `frontend_server.py` from container env vars. No rebuild is needed to
re-point the SPA at a different backend.

### 2.3 The runtime-config mechanism, verbatim — `src/App/frontend_server.py`

This is the heart of the pattern. It is a FastAPI app (NOT nginx) that serves the SPA and exposes
`/config`:

```py
# src/App/frontend_server.py  (≈L1-31)
import asyncio, os
import httpx, uvicorn, websockets
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BUILD_DIR = os.path.join(os.path.dirname(__file__), "build")
INDEX_HTML = os.path.join(BUILD_DIR, "index.html")

# The two env vars that drive everything:
PROXY_API_REQUESTS = os.getenv("PROXY_API_REQUESTS", "false").lower() == "true"   # ≈L29
BACKEND_API_URL    = os.getenv("BACKEND_API_URL", "http://localhost:8000")        # ≈L30
app.mount("/assets", StaticFiles(directory=os.path.join(BUILD_DIR, "assets")), name="assets")
```

```py
# src/App/frontend_server.py  (≈L38-64)  — the runtime /config endpoint
@app.get("/")
async def serve_index():
    return FileResponse(INDEX_HTML)

@app.get("/config")
async def get_config():
    auth_enabled = os.getenv("AUTH_ENABLED", "false")
    if PROXY_API_REQUESTS:
        # WAF mode: frontend proxies API calls, so tell the browser to use same origin
        api_url = "/api"                                            # Option A
    else:
        # Non-WAF mode: browser calls backend directly
        backend_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        api_url = backend_url + "/api"                             # Option B
    return {"API_URL": api_url, "ENABLE_AUTH": auth_enabled}

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

```py
# src/App/frontend_server.py  (≈L67-126)  — same-origin reverse proxy, mounted ONLY in WAF mode
if PROXY_API_REQUESTS:

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy_api(request: Request, path: str):
        """Proxy API requests to the private backend over VNet."""
        target_url = f"{BACKEND_API_URL}/api/{path}"
        query_string = str(request.query_params)
        if query_string:
            target_url = f"{target_url}?{query_string}"
        headers = dict(request.headers); headers.pop("host", None)
        body = await request.body()
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.request(
                method=request.method, url=target_url, headers=headers, content=body)
        return StreamingResponse(iter([response.content]),
                                 status_code=response.status_code, headers=dict(response.headers))

    @app.websocket("/api/{path:path}")
    async def proxy_websocket(websocket: WebSocket, path: str):
        """Proxy WebSocket connections to the private backend over VNet."""
        await websocket.accept()
        backend_ws_url = BACKEND_API_URL.replace("https://", "wss://").replace("http://", "ws://")
        target_url = f"{backend_ws_url}/api/{path}"
        ... # bidirectional forward via websockets.connect(target_url)

# SPA fallback for client-side routes:
@app.get("/{full_path:path}")
async def serve_app(full_path: str):
    ...   # returns index.html

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=3000, access_log=False, log_level="info")
```

Key facts:
- The reverse-proxy routes (`proxy_api`, `proxy_websocket`) are **conditionally registered** — they only
  exist when `PROXY_API_REQUESTS=true`. In the public default they are never mounted, so `/api/*` 404s on
  the frontend and the browser talks to the backend FQDN directly.
- The proxy strips the inbound `host` header (≈L80) and re-issues with `httpx` so the backend sees the
  correct upstream — classic same-origin reverse-proxy hygiene.

### 2.4 Frontend Dockerfile — `src/App/Dockerfile` (full read)

This is the **prebuilt-image** path (not what `azd` builds in the from-source flow; see §2.5). It is a
3-stage build that ends by serving the SPA with the **same `frontend_server.py`** — **no nginx, no
entrypoint script, no envsubst/sed**:

```dockerfile
# src/App/Dockerfile
# Stage 1: Node build environment for React
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY package*.json ./
RUN npm ci --silent
COPY . ./
RUN rm -rf node_modules && npm ci && npm rebuild esbuild --force
RUN npm run build                      # Vite build → /app/frontend/build

# Stage 2: Python build environment with UV
FROM python:3.11-slim-bullseye AS python-builder
COPY --from=ghcr.io/astral-sh/uv:0.6.3 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml requirements.txt* uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f "requirements.txt" ]; then \
      uv pip install --system -r requirements.txt && uv pip install --system "uvicorn[standard]"; \
    else \
      uv pip install --system pyproject.toml && uv pip install --system "uvicorn[standard]"; \
    fi

# Stage 3: Final production image
FROM python:3.11-slim-bullseye
ENV NODE_ENV=production PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN adduser --disabled-password --gecos "" appuser && mkdir -p /app/static && chown -R appuser:appuser /app
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-builder /usr/local/bin /usr/local/bin
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/build /app/build   # SPA assets
COPY --chown=appuser:appuser ./*.py /app/                                             # frontend_server.py
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs
USER appuser
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1
CMD ["/usr/local/bin/uvicorn", "frontend_server:app", "--host", "0.0.0.0", "--port", "3000"]
```

There is **no `ENTRYPOINT` script, no `envsubst`, no `sed`, no `config.js`/`env.js` generation at
container start.** Config injection happens purely at HTTP-request time inside `frontend_server.py`'s
`/config` handler reading `os.getenv(...)`. The image is environment-agnostic; the env vars are supplied
by the host (App Service appSettings).

### 2.5 The from-source (azd) frontend path — App Service, not a container  [local-2026-06-25]

In the build-from-source flow that `azd up` uses, the frontend is **not** containerized. App Service runs
native Python (`linuxFxVersion: 'python|3.11'`) and the start command is
`python3 -m uvicorn frontend_server:app --host 0.0.0.0 --port 8000`. `azd` zip-deploys a `dist/` produced
by `package_frontend.sh` (`npm run build` → copy `build/` + `*.py` + `requirements.txt` into `dist/`).
Same `frontend_server.py`, same `/config` mechanism — just zip-deployed instead of imaged. (Detail in
`.copilot-tracking/research/subagents/2026-06-25/macae-container-build-pattern.md` §5.)

---

## 3. BACKEND

The backend lives at **`src/backend/`** (FastAPI, `src/backend/app.py`), hosted on **Azure Container
Apps** with **public external ingress** in the default flow.

### 3.1 FastAPI CORS — `src/backend/app.py` (≈L97-103)

```py
# src/backend/app.py  (≈L74-103)
app = FastAPI(lifespan=lifespan)
frontend_url = config.FRONTEND_SITE_NAME       # ≈L76 — READ but NOT used for CORS (see note)
...
# Add this near the top of your app.py, after initializing the app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Allow all origins for development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(HealthCheckMiddleware, password="", checks={})
app.include_router(app_v4)        # /api/v4/* routes
```

Notes:
- **App-level CORS is wildcard** (`allow_origins=["*"]`) — it is *not* driven by an env var. The
  `frontend_url = config.FRONTEND_SITE_NAME` value is read but **not** wired into `CORSMiddleware`. So the
  FastAPI layer accepts any origin.
- The spec-illegal combo `allow_origins=["*"]` **+** `allow_credentials=True` is shipped as-is. It works in
  practice only because the SPA authenticates with **headers** (`x-ms-client-principal-id`,
  `Authorization: Bearer`), not cookies — so the browser never needs a credentialed wildcard response. If
  CWYD relied on cookies, this combo would break; with header auth it is benign. (See §3.3.)

### 3.2 Container Apps ingress CORS — the real origin gate  [GitHub main]

The *effective* CORS allow-list that matters in the public flow is set at the **Container Apps ingress**
(AVM `container-app` module), not the FastAPI app. Backend container app:

```bicep
// infra/main.bicep  (≈L1216-1227)  and  infra/main_custom.bicep  (≈L1236-1255)
ingressTargetPort: 8000
ingressExternal: true                  // <-- public FQDN in the default flow
ingressAllowInsecure: false
corsPolicy: {
  allowedOrigins: [
    'https://${webSiteResourceName}.azurewebsites.net'   // the frontend App Service origin
    'http://${webSiteResourceName}.azurewebsites.net'
  ]
  allowedMethods: ['GET','POST','PUT','DELETE','OPTIONS']
}
```

So in Option B the cross-origin preflight is allowed because the **ingress `corsPolicy.allowedOrigins`
contains the frontend App Service FQDN** (`https://${webSiteResourceName}.azurewebsites.net`), with the
FastAPI wildcard behind it as a backstop. The MCP container app sets an identical `corsPolicy`
(`infra/main.bicep` ≈L1413-1430, `infra/main_custom.bicep` ≈L1457-1473).

### 3.3 Backend settings / env-var names — `src/backend/common/config/app_config.py`

```py
# src/backend/common/config/app_config.py  (≈L71-73)
self.FRONTEND_SITE_NAME = self._get_optional("FRONTEND_SITE_NAME", "http://127.0.0.1:3000")
```

- `FRONTEND_SITE_NAME` — the frontend origin, env-driven, default `http://127.0.0.1:3000`. Present and
  read, but (per §3.1) **not** wired into the FastAPI CORS middleware on `main`. The local-dev guide sets
  it to `*` (`docs/LocalDevelopmentSetup.md` §4.2: `FRONTEND_SITE_NAME=*`).
- There is **no** `BACKEND_API_URL` on the backend — that var lives only on the *frontend* App Service.
- Backend host/port come from the `uvicorn` start command / `ingressTargetPort: 8000`, not a settings field.

---

## 4. THE COMMUNICATION CONTRACT — definitive A/B/C answer

**MACAE = Option B by default (public), Option A under WAF/private networking — one image/codebase,
toggled by `PROXY_API_REQUESTS`. Never Option C.**

### Option B chain (public default, `PROXY_API_REQUESTS='false'`)

```
browser
  └─ GET https://<frontend>.azurewebsites.net/config        (same origin; served by frontend_server.py)
       → { "API_URL": "https://<backend-fqdn>/api", "ENABLE_AUTH": "false" }   (frontend_server.py ≈L42-59)
  └─ setApiUrl("https://<backend-fqdn>/api")                 (index.tsx ≈L37 → config.tsx setApiUrl)
  └─ httpClient.setBaseUrl("https://<backend-fqdn>/api")     (apiClient.tsx syncBaseUrl ≈L14-19)
  └─ GET/POST https://<backend-fqdn>/api/v4/...              (httpClient.ts fetch — CROSS-ORIGIN)
       ↑ allowed by Container Apps ingress corsPolicy.allowedOrigins = https://<frontend>.azurewebsites.net
         (infra/main.bicep ≈L1216-1227) + FastAPI allow_origins=["*"] (app.py ≈L97-103)
  └─ WSS  wss://<backend-fqdn>/api/v4/socket/...             (WebSocketService.tsx from getApiUrl)
```

### Option A chain (WAF / private, `PROXY_API_REQUESTS='true'`)

```
browser
  └─ GET https://<frontend>/config  →  { "API_URL": "/api", ... }              (frontend_server.py ≈L46-48)
  └─ httpClient base URL = "/api"   (relative → SAME ORIGIN; no CORS)
  └─ GET/POST https://<frontend>/api/v4/...                                     (same origin)
       └─ frontend_server.py proxy_api (httpx) → https://<backend-internal-fqdn>/api/v4/...  over VNet
  └─ WSS  wss://<frontend>/api/...  →  proxy_websocket  → backend over VNet     (frontend_server.py ≈L100-126)
```

Why not C: the bundle contains only the localhost fallback `http://localhost:8000/api` (`config.tsx`
≈L16); the deployed backend URL is delivered at runtime by `/config`. No `VITE_*` define, no
`import.meta.env` backend URL.

---

## 5. ENV-VAR FLOW — `BACKEND_API_URL` end to end (one concrete trace)

```
1. Bicep provisions the backend Container App  →  output  containerApp.outputs.fqdn   (the public FQDN)
2. Bicep sets the FRONTEND App Service appSetting:
      BACKEND_API_URL: 'https://${containerApp.outputs.fqdn}'
   [GitHub main]  infra/main_custom.bicep ≈L1609   (frontend App Service `configs[].properties`)
   [local-2026-06-25]  infra/bicep/main.bicep ≈L811 / ≈L822 (both isCustom branches of appSettings)
3. App Service exposes BACKEND_API_URL as a process env var to uvicorn frontend_server:app
4. frontend_server.py reads it:  BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")  (≈L30)
5. /config returns  API_URL = BACKEND_API_URL + "/api"   (when PROXY_API_REQUESTS=false)   (≈L52-53)
6. SPA fetch('/config') → setApiUrl(API_URL) → httpClient.setBaseUrl(...)  → all calls hit the backend FQDN
```

The sibling toggle is wired the same way:
```
[GitHub main] infra/main_custom.bicep ≈L1612:  PROXY_API_REQUESTS: enablePrivateNetworking ? 'true' : 'false'
```
So enabling private networking flips the *entire* browser→backend path from Option B to Option A with no
code change — the App Service appSetting is the only switch.

Other frontend App Service appSettings in the same block (≈L1604-1613, main_custom.bicep): `WEBSITES_PORT`
(`8000` from-source / `3000` prebuilt image), `SCM_DO_BUILD_DURING_DEPLOYMENT`, `ENABLE_ORYX_BUILD`,
`AUTH_ENABLED: 'false'`, `APPLICATIONINSIGHTS_CONNECTION_STRING`.

---

## 6. LOCAL-DEV docker-compose / proxy parity

**There is no full-stack docker-compose mirroring the proxy/CORS pattern.** The only compose file in the
repo is `src/mcp_server/docker-compose.yml` (just the MCP server on `9000:9000`) — not the frontend or
backend. A repo-wide search for `nginx` returns **nothing**.

Local development is a **3-process model** (`docs/LocalDevelopmentSetup.md` §4.2, §7), which itself
mirrors the deployed Option-B contract without a proxy:

| Terminal | Service | Command | URL |
|----------|---------|---------|-----|
| 1 | Backend | `python app.py` (uvicorn :8000) | http://localhost:8000 |
| 2 | MCP server | `python mcp_server.py --transport streamable-http --host 0.0.0.0 --port 9000` | http://localhost:9000 |
| 3 | Frontend | `python frontend_server.py` (uvicorn :3000) | http://localhost:3000 |

`.env` for local dev keeps `BACKEND_API_URL=http://localhost:8000`, `FRONTEND_SITE_NAME=*`,
`MCP_SERVER_ENDPOINT=http://localhost:9000/mcp`. With `PROXY_API_REQUESTS` unset (→ false), the local SPA
fetches `/config`, gets `http://localhost:8000/api`, and calls the local backend cross-origin — exactly
the deployed Option-B chain, no proxy needed. (Vite's own dev server `:3001` exists in
`src/App/vite.config.ts` but the documented flow runs the SPA through `frontend_server.py:3000` so
`/config` is available.)

---

## 7. TO REPLICATE THIS IN CWYD v2 — concrete X, Y, Z

CWYD v2's frontend currently relies on a **build-time `VITE_BACKEND_URL`** baked into the OpenAPI client
(Hard Rule #4 / v2-frontend instructions). To adopt MACAE's runtime-config + optional same-origin-proxy
pattern, you need:

1. **A frontend runtime `/config` endpoint.** Add a tiny FastAPI (or static-serving) layer in front of
   the built SPA — the CWYD analogue of `frontend_server.py` — exposing `GET /config` that returns
   `{ "API_URL": <computed>, ... }` from `os.getenv("CWYD_BACKEND_URL"|"BACKEND_API_URL")` +
   `os.getenv("PROXY_API_REQUESTS")`. (CWYD's MACAE-parity change `ID-02 / PD-01`, logged in
   `.copilot-tracking/changes/2026-06-25/macae-infra-parity-changes.md`, already chose this `/config`
   approach — confirm it is fully wired.)

2. **SPA boots from `/config`, not from a baked env.** On app init, `fetch('/config')` → set the API
   client base URL at runtime (mirror `index.tsx` + `config.tsx` + `apiClient.tsx`). Keep
   `VITE_BACKEND_URL` only as a *localhost fallback default*, not the production source of truth. This
   lets one built artifact target any backend (Hard Rule #4 "backend headless / frontend takes
   `VITE_BACKEND_URL`" is preserved — the value just arrives at runtime).

3. **Decide the deployed transport and wire CORS to match:**
   - **Option B (simplest, public):** give the CWYD backend Container App **external ingress** + set its
     ingress `corsPolicy.allowedOrigins` to the frontend's deployed origin (the MACAE bicep pattern,
     `infra/main.bicep` ≈L1216-1227). Keep backend FastAPI CORS env-driven (CWYD already has a CORS
     settings field — point `allow_origins` at the frontend origin, **not** wildcard, to satisfy WAF/SFI;
     MACAE's `["*"]` is a dev shortcut you should not copy verbatim).
   - **Option A (WAF/private, no browser CORS):** add the conditional same-origin reverse proxy
     (`/api/{path}` + websocket) to the CWYD frontend server, gated on `PROXY_API_REQUESTS`, forwarding via
     `httpx`/`websockets` to the internal backend FQDN over the VNet. The SPA then uses `API_URL="/api"`.

4. **Inject the backend FQDN as a frontend App Service / Container App env var from bicep**, exactly like
   `BACKEND_API_URL: 'https://${containerApp.outputs.fqdn}'` — the bicep output → appSetting → `os.getenv`
   → `/config` chain (§5). Add the `PROXY_API_REQUESTS: <private?'true':'false'>` toggle next to it.

5. **Mirror the contract in local dev.** Run the CWYD SPA through its `/config`-serving frontend layer
   (not the bare Vite dev server) so `fetch('/config')` works locally, with
   `BACKEND_API_URL=http://localhost:8000` (or CWYD's port) and `PROXY_API_REQUESTS` unset. CWYD's
   `v2/docker/docker-compose.dev.yml` should set those env vars on the frontend service; no nginx required.

6. **Do NOT introduce nginx or an entrypoint config-injection script.** MACAE deliberately keeps config
   injection in-app (`/config` reading `os.getenv` at request time). This is simpler than envsubst/`env.js`
   generation and aligns with CWYD's "no invented sidecars / one runtime per container" rule (Hard Rule #9).

7. **Watch the credentials+wildcard CORS trap.** If CWYD authenticates with cookies, you cannot copy
   MACAE's `allow_origins=["*"] + allow_credentials=True`. Use an explicit origin list (the frontend FQDN)
   when credentials are involved. MACAE only gets away with the wildcard because it authenticates with
   headers.

---

## 8. Evidence index (file → what it proves)

Frontend (GitHub main):
- `src/App/frontend_server.py` ≈L1-31 (CORS `["*"]`, `PROXY_API_REQUESTS` L29, `BACKEND_API_URL` L30),
  ≈L42-59 (`/config` — the runtime injection), ≈L67-126 (conditional `/api` reverse proxy + ws proxy).
- `src/App/src/index.tsx` ≈L20-52 — `fetch('/config')` → `setApiUrl`.
- `src/App/src/api/config.tsx` ≈L12-24 (`API_URL`, localhost fallback, `setApiUrl`, `setEnvData`), ≈L72-86 (`getApiUrl`).
- `src/App/src/api/apiClient.tsx` ≈L14-19 (`syncBaseUrl`).
- `src/App/src/api/httpClient.ts` ≈L48-61 (`buildUrl`), ≈L67-99 (`request`/fetch), ≈L228-244 (auth header interceptor).
- `src/App/src/store/WebSocketService.tsx` L0+ (`getApiUrl` → ws URL).
- `src/App/src/vite-env.d.ts` ≈L3-6 (dead `REACT_APP_API_URL`).
- `src/App/vite.config.ts` ≈L0-46 (no backend-URL `define`; `outDir: 'build'`).
- `src/App/Dockerfile` (full) — node:18-alpine build → python:3.11 UV → `CMD uvicorn frontend_server:app … :3000`; no nginx/entrypoint/envsubst.

Backend (GitHub main):
- `src/backend/app.py` ≈L74-103 — `frontend_url = config.FRONTEND_SITE_NAME` (unused for CORS); `CORSMiddleware allow_origins=["*"], allow_credentials=True`.
- `src/backend/common/config/app_config.py` ≈L71-73 — `FRONTEND_SITE_NAME` default `http://127.0.0.1:3000`.
- `src/backend/v4/api/router.py` ≈L47-50 — `APIRouter(prefix="/api/v4")` (the routes the SPA hits).

Infra (GitHub main):
- `infra/main.bicep` ≈L1216-1227 — backend Container App `ingressExternal: true`, `corsPolicy.allowedOrigins = frontend FQDN`.
- `infra/main_custom.bicep` ≈L1236-1255 (backend corsPolicy), ≈L1597-1618 (frontend App Service: `linuxFxVersion python|3.11`, `uvicorn frontend_server:app`, appSettings `BACKEND_API_URL`, `PROXY_API_REQUESTS: enablePrivateNetworking ? 'true':'false'`).

Infra (local-2026-06-25, since deleted):
- `infra/bicep/main.bicep` ≈L798-828 — frontend App Service module; appSettings `BACKEND_API_URL: 'https://${backend_container_app.outputs.fqdn}'` (L811/L822), `PROXY_API_REQUESTS: 'false'` both branches.
- `src/App/package_frontend.sh` — `npm run build` → `dist/` (App Service zip-deploy artifact).

Local dev / compose:
- `docs/LocalDevelopmentSetup.md` §4.2 (`BACKEND_API_URL=http://localhost:8000`, `FRONTEND_SITE_NAME=*`), §7 (3-terminal table).
- `src/mcp_server/docker-compose.yml` — only compose in repo (MCP only). No nginx anywhere (repo-wide search empty).

---

## 9. Clarifying questions for the requester

1. **Target transport for CWYD v2:** do you want the simple public Option B (external backend ingress +
   ingress CORS to the frontend origin), or the WAF/private Option A (same-origin reverse proxy, no
   browser CORS)? MACAE supports both via `PROXY_API_REQUESTS`; CWYD should pick a default and decide
   whether to keep the toggle.
2. **CWYD auth model:** header-based (like MACAE's `x-ms-client-principal-id` / Easy Auth) or cookie-based?
   This decides whether the backend CORS may stay permissive or must be an explicit origin list (the
   wildcard+credentials combo only survives with header auth).
3. **Has CWYD's `ID-02 / PD-01` `/config` work already landed?** The 2026-06-25 change log says CWYD chose
   the MACAE-exact `/config` approach. If it's already wired, this becomes a verification task rather than
   a new build — confirm before implementing.
4. **Re-clone MACAE?** The local `data/sample_code/macae/` reference was deleted. If you want byte-exact
   local line numbers (vs. the GitHub `main` numbers here, which may differ by a few lines), I can re-fetch
   specific files — tell me which.
