# Research: v2 Frontend → App Service build-from-source migration (BUG-0081)

Status: Complete
Date: 2026-06-25
Scope: READ-ONLY scoping for migrating `v2/src/frontend` App Service deploy from an
unsupported `docker:` block to MACAE's build-from-source pattern (`linuxFxVersion: python|3.11`
+ `dist: ./dist` + `prepackage` build hook + runtime `/config` endpoint fed by `BACKEND_API_URL`).

---

## Research questions

1. Quote the full `services.frontend` block in `v2/azure.yaml` (+ backend, function, hooks).
2. Describe all stages of `v2/docker/Dockerfile.frontend`; how the prod stage serves static files and injects `VITE_BACKEND_URL`.
3. Find + read the static-serving server script; does it expose `/config`? Read an env var for backend URL? Serve `dist/`?
4. How does the SPA consume the backend base URL today (build-time vs runtime `/config`)?
5. `package.json` build script + output dir; `vite.config.ts` `base`/`outDir`.
6. `v2/scripts/` conventions (`post_provision.py`, `prepackage_function.py`) to match for new prepackage + postdeploy scripts.
7. Confirm no `v2/data/`; list curated sample docs at repo-root `data/`.

---

## 1. `v2/azure.yaml` — services + hooks

### `services.frontend` (verbatim, `v2/azure.yaml` lines 107-126)

```yaml
  frontend:
    project: ./src/frontend
    language: js
    host: appservice
    docker:
      path: ../../docker/Dockerfile.frontend
      context: ../..
      target: prod
      # Vite bakes the backend URL into the static bundle at build time.
      # AZURE_BACKEND_URL is a Bicep output of the backend Container App
      # (see v2/infra/main.bicep -> output azureBackendUrl). azd resolves
      # ${AZURE_BACKEND_URL} from the active azd env before invoking
      # `docker build`, so the bundle ships pointing at the right
      # backend without a separate runtime config fetch.
      buildArgs:
        - VITE_BACKEND_URL=${AZURE_BACKEND_URL}
```

KEY DEFECT (BUG-0081): `host: appservice` + `docker:` is the unsupported combination. azd's
App Service target does NOT build/push the Dockerfile — it silently zip-deploys
`project: ./src/frontend` source and ignores the `docker:` block entirely. The `target: prod`,
`context`, and `buildArgs` (including `VITE_BACKEND_URL`) are all no-ops on App Service.

### `services.backend` (verbatim, lines 100-106)

```yaml
  backend:
    project: ./src/backend
    language: py
    host: containerapp
    docker:
      path: ../../docker/Dockerfile.backend
      context: ../..
```

(Container App host DOES honor `docker:` — backend is unaffected by BUG-0081.)

### `services.function` (verbatim, lines 127-152)

```yaml
  function:
    project: ./build-functions
    language: py
    host: function
    # prepackage is SERVICE-scoped (not project-scoped) so it fires on a
    # targeted `azd deploy function` as well as `azd package` / `azd up`.
    # ... (BUG-0058 commentary) ...
    hooks:
      prepackage:
        posix:
          shell: sh
          run: ../scripts/prepackage-function.sh
          continueOnError: false
          interactive: false
        windows:
          shell: pwsh
          run: ../scripts/prepackage-function.ps1
          continueOnError: false
          interactive: false
```

NOTE — service-scoped `prepackage` already exists for `function`. This is the exact precedent a
new `services.frontend.hooks.prepackage` (npm build → dist/) should follow.

### Project-level hooks (verbatim, lines 168-180)

```yaml
hooks:
  postprovision:
    posix:
      shell: sh
      run: ./scripts/post-provision.sh
      continueOnError: false
      interactive: true
    windows:
      shell: pwsh
      run: ./scripts/post-provision.ps1
      continueOnError: false
      interactive: true
```

- Only `postprovision` is wired at project level. There is currently **NO `postdeploy` hook** at
  project or service level → a new sample-data uploader needs a brand-new `postdeploy` hook.
- `azure.yaml` already references: `scripts/post-provision.{sh,ps1}` (project postprovision) and
  `scripts/prepackage-function.{sh,ps1}` (function service prepackage). It does NOT reference any
  frontend build script or any sample-data script yet.

---

## 2. `v2/docker/Dockerfile.frontend` — stages

Three stages (file is 60 lines total; quoted relevant lines).

- **`dev`** (lines 22-29): `node:20-alpine`, `npm install`, Vite dev server, `EXPOSE 5173`,
  `CMD ["npm","run","dev",...]`. Used by docker-compose.dev.yml only.
- **`build`** (lines 38-49): `node:20-alpine`, `npm install`, copies `src/frontend`, takes
  `VITE_BACKEND_URL` as a build ARG, runs `npm run build` → emits `/app/dist`.

  ```dockerfile
  FROM node:20-alpine AS build
  WORKDIR /app
  COPY src/frontend/package.json ./
  RUN npm install
  COPY src/frontend ./
  ARG VITE_BACKEND_URL=""
  ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}
  RUN npm run build
  ```

- **`prod`** (lines 51-60): Python 3.11 + uvicorn serving the built `dist/`.

  ```dockerfile
  # ---- prod stage: Python + uvicorn (matches v1 hosting model) ----
  FROM python:3.11-slim AS prod
  ENV PYTHONUNBUFFERED=1 \
      PYTHONDONTWRITEBYTECODE=1
  WORKDIR /usr/src/app
  RUN pip install --no-cache-dir uvicorn fastapi
  # Static assets from the build stage; small ASGI app serves them.
  COPY --from=build /app/dist /usr/src/app/dist
  COPY src/frontend/frontend_app.py /usr/src/app/frontend_app.py
  EXPOSE 80
  CMD ["uvicorn", "frontend_app:app", "--host", "0.0.0.0", "--port", "80"]
  ```

ANSWERS for prod stage:
- Base image: `python:3.11-slim`.
- Serves static files via: an ASGI app `frontend_app:app` (FastAPI) — see item 3.
- Command: `uvicorn frontend_app:app --host 0.0.0.0 --port 80`.
- Port: `80`.
- `VITE_BACKEND_URL` injection: **build-time** — build ARG → ENV in the `build` stage, consumed by
  Vite during `npm run build`. It is NOT present at runtime in the prod stage at all. There is no
  runtime backend-URL mechanism in this image.

The Dockerfile header explicitly states the current design: "VITE_BACKEND_URL is baked at build."
This entire Docker prod stage is what App Service ignores (BUG-0081); after migration the build is
done by the `prepackage` hook + the `dist:` source upload + `linuxFxVersion: python|3.11`, not this
image. (Open question: is `Dockerfile.frontend` retired or retained for compose-only dev/prod-test?)

---

## 3. Static-serving server script — `v2/src/frontend/frontend_app.py`

Full file (43 lines) read. It is the FastAPI app the prod Docker stage runs.

```python
"""Production frontend ASGI app: serve the Vite-built SPA.
Pillar: Stable Core
Phase: 1
... catch-all returns file when present, else index.html (BrowserRouter deep links) ...
"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse

# `DIST_DIR` env var lets tests point at a fixture without rebuilding.
_DIST_DIR = Path(os.environ.get("DIST_DIR", "/usr/src/app/dist"))

app = FastAPI(title="cwyd-frontend")


@app.get("/{full_path:path}")
def serve_spa(full_path: str) -> FileResponse:
    dist_root = _DIST_DIR.resolve()
    candidate = (dist_root / full_path).resolve()
    if full_path and candidate.is_file() and candidate.is_relative_to(dist_root):
        return FileResponse(candidate)
    return FileResponse(dist_root / "index.html")
```

ANSWERS:
- `/config` endpoint: **NO.** Only one route exists: the catch-all `GET /{full_path:path}`.
- Reads an env var for the backend URL: **NO.** The only env var it reads is `DIST_DIR`
  (test-fixture path override). It does NOT read `BACKEND_API_URL`, `VITE_BACKEND_URL`, or any
  backend-URL var.
- Serves the built SPA: **YES** — serves `dist/` with `index.html` fallback for client routes.

GAP: The `/config` runtime endpoint that the MACAE pattern needs does NOT exist. It must be added
here (or in a new server module). The catch-all currently swallows `/{full_path}` — a `/config`
route MUST be registered BEFORE the catch-all (route ordering matters in FastAPI) or the catch-all
will intercept `/config` and return `index.html`.

NOTE for App Service build-from-source: App Service Linux Python (`linuxFxVersion: python|3.11`)
uses Oryx, which by default looks for a WSGI/ASGI entry (gunicorn). The current `frontend_app.py`
hard-codes `_DIST_DIR = /usr/src/app/dist` (the Docker path) as the default. On App Service the
deployed source root is `/home/site/wwwroot`, so either (a) `DIST_DIR` app-setting is set, or
(b) the default path is changed to a wwwroot-relative `./dist`. The MACAE pattern ships `dist:`
as the deploy artifact root, so the server + dist co-locate under wwwroot — the default path needs
to resolve relative to the app file, not `/usr/src/app`.

---

## 4. SPA backend-base-URL consumption today (build-time only)

The base URL is read **purely at build time** from `import.meta.env.VITE_BACKEND_URL` (Vite static
replacement). There is **NO runtime `/config` fetch anywhere** in the SPA. Five read sites:

| File | Line | Snippet |
|------|------|---------|
| `v2/src/frontend/src/App.tsx` | 62-63 | `const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL as string \| undefined) ?? "";` (module-level const; used by `fetchHealth` → `/api/health`) |
| `v2/src/frontend/src/api/admin.tsx` | 43-49 | `function backendUrl(){ return (import.meta.env.VITE_BACKEND_URL ...) ?? ""; }` + `function apiUrl(path){ return backendUrl().replace(/\/$/,"")+path; }` |
| `v2/src/frontend/src/api/conversationHistory.tsx` | 46-47 | `function backendUrl(){ return (import.meta.env.VITE_BACKEND_URL ...) ?? ""; }` |
| `v2/src/frontend/src/api/streamChat.tsx` | 66-68 | `function conversationUrl(){ const base = (import.meta.env.VITE_BACKEND_URL ...) ?? ""; return `${base}${CONVERSATION_PATH}`; }` |
| `v2/src/frontend/src/api/speech.tsx` | 32-38 | `function backendUrl(){ ... }` + `function apiUrl(path){ ... }` |

Pattern: each api module has its own private `backendUrl()` / `apiUrl()` helper (duplicated, not
shared) reading the same `import.meta.env.VITE_BACKEND_URL`. `App.tsx` has a module-level
`BACKEND_URL` const instead.

`/api/admin/config` (in `admin.tsx` lines 29-30) is the **admin runtime-toggle config** surface
(`RuntimeConfig` overlay, documented in `v2/docs/admin_runtime_config.md`) — it is UNRELATED to the
frontend `/config` bootstrap endpoint the migration needs. Do not conflate them.

GAP: To move backend URL to runtime, all 5 read sites must switch from `import.meta.env...` to a
value fetched once from `/config` at app boot (e.g. a `runtimeConfig()` provider seam consumed by
the shared `backendUrl()`). There is currently NO shared module and NO `/config` fetch path — this
is net-new SPA wiring. The duplicated per-file `backendUrl()` helpers are the refactor surface; they
should converge on a single shared seam that reads the runtime-fetched value.

---

## 5. `package.json` build + `vite.config.ts`

`v2/src/frontend/package.json` (lines 5-10):

```json
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint ."
  },
```

- Build command: `npm run build` → `tsc -b && vite build`.
- Output dir: `dist` (Vite default; `vite.config.ts` does NOT override `build.outDir`).
- Node expectation: `node:20-alpine` per Dockerfile; standalone package (own deps, not the v2
  workspace). React 19 + Vite 7 + TS 5.7.

`v2/src/frontend/vite.config.ts` (full, 38 lines):
- `base`: **NOT set** (defaults to `/` — fine for App Service root host).
- `build.outDir`: **NOT set** (defaults to `dist`).
- Has a dev-only `server.proxy` `/api → http://localhost:8000` and `server.port: 5273`.
- Header comment says "Backend URL is read at runtime from `import.meta.env.VITE_BACKEND_URL`" —
  this comment is INACCURATE (Vite substitutes it at BUILD time, not runtime). Worth correcting as
  part of the migration since the migration makes it genuinely runtime.

`dist/` is gitignored (`v2/src/frontend/.gitignore` line 5: `dist/`). The `dist/` dir present in
the working tree is a local build artifact, not tracked — confirms the build hook must regenerate it
on every `azd package`/`deploy`.

---

## 6. `v2/scripts/` conventions

Directory listing:
```
post-provision.ps1      post-provision.sh      post_provision.py
prepackage-function.ps1 prepackage-function.sh prepackage_function.py
tests/
```

### Wrapper pattern (the convention to copy)

Each azd hook is a thin OS-specific wrapper that shells into a single Python script via `uv run`.

`post-provision.sh` (full):
```bash
#!/usr/bin/env bash
# Pillar: Stable Core
# Phase:  1 ...
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run python "${SCRIPT_DIR}/post_provision.py" "$@"
```

`post-provision.ps1` (full):
```powershell
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& uv run python (Join-Path $scriptDir 'post_provision.py') @args
exit $LASTEXITCODE
```

`prepackage-function.{sh,ps1}` are byte-identical in shape (just point at `prepackage_function.py`).
Header comments state the azd guarantees: cwd == azure.yaml project dir (== `v2/`), all Bicep
`AZURE_*` outputs + `AZURE_ENV_*` typed-prompt answers are exported as env vars. The Python script
resolves all paths from its own location (`Path(__file__).resolve().parents[1]`) so hook cwd is
irrelevant.

NEW scripts should follow this exactly: `package-frontend.{sh,ps1}` → `uv run python
package_frontend.py`; `upload_sample_data.{sh,ps1}` → `uv run python upload_sample_data.py`.
(Note hyphenated wrapper filenames, underscored Python filenames — established convention.)
CAVEAT: a frontend build hook runs `npm` not Python — the wrapper may need to call `npm run build`
directly OR the Python script shells out to `npm`. The function prepackage is pure-Python file
staging; a frontend build is fundamentally an `npm` invocation, so the cleanest match is a thin
`package-frontend.{sh,ps1}` that runs `npm ci && npm run build` in `src/frontend/` and leaves
`dist/` for azd to upload — Python is optional here.

### `post_provision.py` style (auth + structure)

- Auth: `azure.identity.DefaultAzureCredential` (works for interactive deployer, CI SP, MI).
  Docstring explicitly: "works unchanged for an interactive deployer, a service principal in CI,
  or a managed identity in Cloud Shell."
- Reads config from env vars (`os.environ.get`), `_require(name)` helper that `sys.exit(2)` on
  missing. Module-level `UPPER_SNAKE` constants. `--dry-run` arg via `argparse` that skips all SDK
  calls. Idempotent. Prints a compact `AZURE_*` summary block. Pillar/Phase docstring header.
- Used Azure SDKs: `azure.search.documents.indexes` (SearchIndexClient), `psycopg2`, `httpx`.
- For a sample-data uploader: same idiom — `DefaultAzureCredential` to a Blob client
  (`AZURE_STORAGE_ACCOUNT_NAME` is already in `SUMMARY_KEYS`, so the storage account name is an
  available azd output env var), `--dry-run`, idempotent (skip-if-exists), `_require` for required
  env. The grounding pipeline is blob-triggered (`blob_event` is a function subpackage) so uploading
  the curated docs to the ingestion container is the trigger.

### `prepackage_function.py` style

- Pure stdlib (`shutil`, `tomllib`, `pathlib`), no Azure SDK. Resolves `_V2_ROOT =
  Path(__file__).resolve().parents[1]`. Stages a deploy artifact dir, `sys.exit(2/3)` on missing
  inputs, `main() -> int`, `if __name__ == "__main__": sys.exit(main())`. Pillar/Phase header.
- This is the closest template for a Python-based `package_frontend.py` if the team prefers Python
  orchestration over a raw npm wrapper.

---

## 7. Sample data location

- `v2/data/` : **DOES NOT EXIST** (`file_search v2/data/**` → no files; `azure.yaml` `services.function.project`
  staging never references it).
- Repo-root `data/` holds the grounding sample docs. Listing:

```
Benefit_Options.pdf
employee_handbook.pdf
MSFT_FY23Q4_10K.docx
Northwind_Health_Plus_Benefits_Details.pdf
Northwind_Standard_Benefits_Details.pdf
PerksPlus.pdf
PressReleaseFY23Q4.docx
role_library.pdf
Woodgrove - Cyber Risk Insurance Policy_Commercial Insurance.pdf
Woodgrove - Cyber Risk Insurance Policy_Commercial Insurance_Important Prompts For_Claims Handlers.pdf
Woodgrove - Insurance Underwriting_Key Prompts for Underwriters when evaluating Financial Results.pdf
Woodgrove - Insurance_Summary Plan Description_Employee Benefits.pdf
Woodgrove - Insurance_Summary Plan Description_Employee Benefits_Important Prompts For_Employees.pdf
Woodgrove - Insurance_Summary Plan Description_Employee Benefits_Important Prompts For_Insurance Agents.pdf
Woodgrove - Mortgage Product Manual - 1.0.pdf
Woodgrove Asset Management  - Prospective of Asset Management Funds.pdf
```

Plus subfolders `data/contract_data/` and `data/sample_code/` (not part of the flat doc set;
likely contract/code samples for other scenarios — out of scope for the curated grounding upload
unless explicitly chosen).

The flat PDFs/DOCXs at `data/` root are the v1 sample corpus (Northwind/Woodgrove/Contoso benefits)
and are the natural curated upload set. The uploader must reference this repo-ROOT path
(`../data/` relative to `v2/`, or an explicit repo-root resolve), since there is no `v2/data/`.
OPEN QUESTION for planner: curate a subset (the v1 default was the Northwind/Benefits set) vs upload
all root PDFs/DOCXs vs copy a curated subset into a new `v2/data/`. This is a product decision.

---

## What already exists vs. what must be newly created

### (a) Prepackage frontend build hook
- EXISTS: the service-scoped `prepackage` hook PATTERN (`services.function.hooks.prepackage` + thin
  `prepackage-function.{sh,ps1}` wrappers + `uv run python` convention). `npm run build` produces
  `dist/`.
- MUST CREATE: `services.frontend.hooks.prepackage` block in `azure.yaml`; new
  `v2/scripts/package-frontend.{sh,ps1}` (and optional `package_frontend.py`) that runs the npm
  build in `src/frontend/` so `dist/` is fresh before azd uploads `dist: ./dist`.
- MUST CHANGE: replace `services.frontend.docker:` block with `dist: ./dist` (+ remove `buildArgs`/
  `VITE_BACKEND_URL`); set App Service `linuxFxVersion: python|3.11` in Bicep.

### (b) App Service static server + `/config` endpoint
- EXISTS: `v2/src/frontend/frontend_app.py` — a FastAPI ASGI app that serves `dist/` with
  index.html fallback (catch-all `GET /{full_path:path}`).
- MUST CREATE: a `/config` route (registered BEFORE the catch-all) returning JSON
  `{ "backendApiUrl": os.environ["BACKEND_API_URL"] }` (or similar). Wire the `BACKEND_API_URL` App
  Service app setting in Bicep (from the backend Container App URL output).
- MUST CHANGE: default `DIST_DIR` resolution so it works under App Service `/home/site/wwwroot`
  (relative to the app file, not the hard-coded `/usr/src/app/dist`); ensure App Service start
  command runs uvicorn/gunicorn against `frontend_app:app`.

### (c) SPA runtime-config consumption
- EXISTS: five build-time `import.meta.env.VITE_BACKEND_URL` read sites (App.tsx const + 4 private
  `backendUrl()` helpers in api/admin, conversationHistory, streamChat, speech). NO runtime `/config`
  fetch, NO shared backend-URL module.
- MUST CREATE: a shared runtime-config seam (fetch `/config` once at boot, expose `backendApiUrl`),
  and refactor all 5 read sites to consume it. Update the inaccurate "read at runtime" comment in
  `vite.config.ts` / App.tsx accordingly.

### (d) Postdeploy sample-data uploader
- EXISTS: NOTHING. No `postdeploy` hook in `azure.yaml`; no uploader script. `AZURE_STORAGE_ACCOUNT_NAME`
  IS already an exported azd output (in `post_provision.py` SUMMARY_KEYS) so the target storage
  account name is available to a hook.
- MUST CREATE: `services`-or-project-level `postdeploy` hook in `azure.yaml`; new
  `v2/scripts/upload_sample_data.{sh,ps1}` wrappers + `upload_sample_data.py` (DefaultAzureCredential
  → Blob upload to the ingestion container, `--dry-run`, idempotent skip-if-exists, `_require` env
  pattern matching `post_provision.py`). Blob upload triggers the existing `blob_event` ingestion
  function.

### (e) Curated sample-data set/location
- EXISTS: repo-root `data/*.pdf|*.docx` (Northwind/Woodgrove/Contoso corpus). NO `v2/data/`.
- MUST DECIDE (planner/product): which subset to upload + whether to reference repo-root `data/`
  directly or stage a curated `v2/data/`. No code exists either way.

---

## Clarifying questions for the planner / user

1. Is `Dockerfile.frontend` retired entirely, or kept for docker-compose dev/prod-test only? (App
   Service no longer uses it; backend/function still use their Dockerfiles.)
2. `/config` response shape + key name — `{ "backendApiUrl": ... }` vs `{ "BACKEND_API_URL": ... }`
   vs MACAE's exact contract? Confirm the App Service app-setting name is literally `BACKEND_API_URL`.
3. Curated sample-data set: full root `data/` flat docs, a Northwind subset, or a new `v2/data/`
   staging copy? And which blob container is the ingestion trigger source (confirm the container name
   the `blob_event` function watches)?
4. Frontend build hook — raw `npm`-only wrapper, or Python orchestrator shelling to npm (to match the
   `uv run python` convention used by the other two hooks)?

## Recommended follow-on research (not done here)
- [ ] Read `v2/infra/main.bicep` frontend App Service module (tag `frontend`, ~L1240) to confirm
      current `linuxFxVersion`/site config and where `BACKEND_API_URL` app setting + `python|3.11`
      runtime would be set; confirm the backend URL Bicep output name (`azureBackendUrl`).
- [ ] Confirm the `blob_event` ingestion container name + storage path the uploader must target
      (`v2/src/functions/blob_event/` + `v2/infra` storage module).
- [ ] Pull MACAE's exact `frontend` App Service azure.yaml + server + `/config` source to mirror
      the contract precisely (external read-only reference per repo instructions).
- [ ] Check `v2/src/frontend/tests` (relocated to `v2/tests/frontend/`) for existing
      `frontend_app.py` tests + any `backendUrl()` tests that the refactor must update.
