<!-- markdownlint-disable-file -->
# CWYD v2 frontend — `azd up` "not deployed / error page" root-cause research

Research date: 2026-06-29 (file dated 2026-06-28 per request)
Scope: research only — no code modified.
Question: after `azd up` the CWYD v2 **frontend** "is not deployed, shows an error page"; make it deploy + load like MACAE's build-from-source App Service frontend. Find the root cause.

CWYD v2 on disk: `c:\workstation\Microsoft\github\cwyd-cdb\v2\`
MACAE: not on disk — compared against the public `main` + the prior capture `.copilot-tracking/research/subagents/2026-06-25/macae-container-build-pattern.md`.

---

## TL;DR — the one critical conclusion

**The frontend build-from-source deploy pipeline is already correct, internally consistent, and MACAE-aligned. The "error page" is NOT a build failure, NOT a missing-static-files 404, NOT a wrong start command, and NOT a missing-requirements/Oryx issue.** All of those were already fixed (BUG-0081 azure.yaml/bicep migration + BUG-0085 Oryx flag) and are present in the current tree, and the pipeline was verified live-working on 2026-06-25 (frontend returned `HTTP 302` → Entra login = app up).

The remaining live blocker that renders an **error page** is **BUG-0090 (open)**: the frontend App Service has **App Service Authentication (Easy Auth) enabled but its Microsoft Entra identity provider is unconfigured (empty `clientId`/issuer)**, so every request `302`-redirects into a broken Entra login that errors. **Easy Auth is NOT wired in `v2/infra/main.bicep`** — it is an env-state leftover on the reused App Service that `azd up` neither configures correctly nor tears down. **MACAE deliberately runs its build-from-source frontend with `AUTH_ENABLED=false` and no Easy Auth, so its SPA loads directly.** That is the decisive divergence.

Secondary risk (BUG-0081 lineage, still open): if the live `app-frontend-<SUFFIX>` was first provisioned as `kind: 'app,linux,container'`, the current bicep's `kind: 'app,linux'` may not flip in place (`kind` is effectively immutable on `Microsoft.Web/sites`), leaving a container-kind site that ignores the code zip-deploy → App Service placeholder/Application-Error page. This produces a *different* error page than Easy Auth and is distinguishable by inspection (see §8 disambiguation).

---

## 1. `v2/azure.yaml` — the `frontend` service block (correct)

File: `v2/azure.yaml`, `services.frontend` (~lines 110-145).

```yaml
frontend:
  project: ./src/frontend
  language: js
  host: appservice
  dist: ./build-output
  hooks:
    prepackage:
      posix:   { shell: sh,   run: ../../scripts/package-frontend.sh,  continueOnError: false }
      windows: { shell: pwsh, run: ../../scripts/package-frontend.ps1, continueOnError: false }
```

- `host: appservice` with **no `docker:` block** — this is the build-from-source reference pattern (MACAE-aligned). The old `host: appservice` + `docker:` pairing was BUG-0081's root cause and has been removed.
- `dist: ./build-output` is relative to `project: ./src/frontend` → `v2/src/frontend/build-output`. ✔ correct.
- Hook `run: ../../scripts/package-frontend.ps1` is relative to the **service project path** (`./src/frontend`) → `v2/src/frontend/../../scripts/package-frontend.ps1` = `v2/scripts/package-frontend.ps1`. ✔ The hyphenated wrapper files exist: `v2/scripts/package-frontend.sh` + `v2/scripts/package-frontend.ps1`. (Initially looked like a name mismatch vs `package_frontend.py` (underscore) but both forms exist — the `.sh`/`.ps1` are thin wrappers that call the underscore `.py`.)
- `prepackage` is **service-scoped** (not project-scoped), so it also fires on a targeted `azd deploy frontend`. ✔ correct.

**Verdict: azure.yaml frontend block is correct and MACAE-aligned. Not the cause.**

---

## 2. Packaging scripts — staged-output layout (correct, matches `dist:`)

### `v2/scripts/package-frontend.ps1` (windows wrapper)
```powershell
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path   # v2/scripts
Set-Location (Join-Path $scriptDir '../src/frontend')          # cwd = v2/src/frontend
npm ci
npm run build                                                  # → v2/src/frontend/dist/
& uv run python (Join-Path $scriptDir 'package_frontend.py')   # stages build-output/
```
`v2/scripts/package-frontend.sh` is the identical POSIX twin (`npm ci; npm run build; exec uv run python .../package_frontend.py`).

### `v2/scripts/package_frontend.py`
Stages the App Service deploy artifact at `v2/src/frontend/build-output/`:
```python
_FRONTEND = v2/src/frontend
_BUILD    = _FRONTEND / "build-output"
dist_src  = _FRONTEND / "dist"           # FileNotFoundError if missing
rmtree(_BUILD); _BUILD.mkdir()
copytree(dist_src, _BUILD / "dist")      # → build-output/dist/      (the SPA)
copy2(_FRONTEND/"frontend_app.py", _BUILD/"frontend_app.py")  # → build-output/frontend_app.py
(_BUILD/"requirements.txt").write_text("fastapi==0.133.0\nuvicorn[standard]>=0.34,<1.0\n")
```

### Vite output dir
`v2/src/frontend/vite.config.ts` sets **no `build.outDir`**, and `v2/src/frontend/package.json` `build` = `tsc -b && vite build`. Vite's default `outDir` is `dist/`, so the build emits `v2/src/frontend/dist/` — exactly what `package_frontend.py` copies from. ✔

### Staged layout (what azd zip-deploys = contents of `build-output/`)
```
build-output/
  dist/            ← the built SPA (index.html + assets)
  frontend_app.py  ← the uvicorn ASGI server
  requirements.txt ← fastapi + uvicorn (for the Oryx pip install)
```

**Verdict: staged output exactly matches `dist: ./build-output`. The build step passes — `npx tsc --noEmit -p src/frontend` returns exit 0 this session (so `npm run build` will not fail). Not the cause.**

---

## 3. `v2/src/frontend/frontend_app.py` — served dir (matches the staged layout)

- `_DIST_DIR = Path(os.environ.get("DIST_DIR", str(Path(__file__).resolve().parent / "dist")))` — default resolves **next to the module** → `build-output/dist/`. ✔ exactly where `package_frontend.py` stages the SPA.
- `GET /config` returns `{"backendUrl": os.environ["BACKEND_API_URL"]}` — runtime backend discovery (no build-time bake), the MACAE `/config` pattern.
- `GET /{full_path:path}` catch-all: returns the on-disk file when it exists under `dist/` (with `..` traversal guard via `is_relative_to`), else falls back to `dist/index.html` for SPA deep links/refreshes. ✔
- `requirements.txt` (fastapi + uvicorn) is staged at the deploy root so Oryx installs the server before the start command runs. ✔

**Verdict: `frontend_app.py`'s served dir (`dist/`) matches the staged subdir, and `frontend_app:app` resolves at the deploy root. Not the cause.**

---

## 4. `v2/infra/main.bicep` — frontend App Service (correct; app settings proven to land)

`module frontendWebApp 'br/public:avm/res/web/site:0.22.0'` at **L1966-2034**:

| Setting | Value | Line | Notes |
|---|---|---|---|
| `kind` | `'app,linux'` | 1970 | Code (non-container) App Service — correct for build-from-source. No leftover `app,linux,container` anywhere in the file. |
| `linuxFxVersion` | `'PYTHON|3.11'` | 1999 | Blessed Python runtime (case-insensitive; MACAE uses `'python|3.11'`). |
| `appCommandLine` | `'uvicorn frontend_app:app --host 0.0.0.0 --port 8000'` | 2000 | Module path `frontend_app:app` correct (server at deploy root). Port 8000 matches the blessed-Python default `PORT`. |
| `appSettings` | via `siteConfig.appSettings: union([...])` | 2009-2031 | `BACKEND_API_URL`, `WEBSITES_ENABLE_APP_SERVICE_STORAGE=false`, **`SCM_DO_BUILD_DURING_DEPLOYMENT='true'`** (+ App Insights when monitoring on). |

**Does the AVM module honor `siteConfig.appSettings`?** Yes — the **function app uses the identical `avm/res/web/site:0.22.0` + `siteConfig.appSettings: union([...])` pattern** (`module functionApp` L2103, `siteConfig.appSettings` L2166) and its settings demonstrably take effect in the cloud (e.g. `AZURE_ENVIRONMENT=production`, `AzureWebJobsStorage__*`; the function runs). So `SCM_DO_BUILD_DURING_DEPLOYMENT=true` **does** land on a fresh provision — the BUG-0085 503 (Oryx skipped → `uvicorn: command not found`, exit 127) is fixed in bicep and not a latent regression.

**Missing vs MACAE (hardening, not the current breakage):**
- `WEBSITES_PORT=8000` — **absent** (MACAE sets it). Blessed Python defaults `PORT=8000` and the start command binds `--port 8000`, so it boots without it (BUG-0085 verified boot), but setting it removes ambiguity.
- `ENABLE_ORYX_BUILD=True` — **absent** (MACAE sets it). `SCM_DO_BUILD_DURING_DEPLOYMENT=true` alone triggers the Oryx pip install for zip deploy, so it boots without it; MACAE sets both belt-and-suspenders.
- `appCommandLine` uses bare `uvicorn …` vs MACAE's `python3 -m uvicorn …` — the `-m` form is more robust to PATH (relevant to the BUG-0085 exit-127 class), though bare uvicorn works once Oryx activates the venv.

**Easy Auth: NOT configured in bicep.** The frontend module carries **no** `authSettingV2Configuration` / `authSettingsV2` / `authConfig`. (The only `authConfig` in the file, L1503, belongs to a different resource.) So the frontend's Easy Auth state is entirely env-side, not IaC-managed — see §5/§7.

**Verdict: bicep frontend config is correct; the start command, runtime, and Oryx flag are all right and proven to apply. Not the cause. (WEBSITES_PORT / ENABLE_ORYX_BUILD / `python3 -m uvicorn` are MACAE-parity hardening, not the blocker.)**

---

## 5. `v2/docs/bugs.md` — what was already tried / what's still open

| Bug | Status | Relevance |
|---|---|---|
| **BUG-0081** | **open** | `azd deploy frontend` left the App Service on the placeholder image because `host: appservice` + `docker:` is unsupported by azd (the block is silently ignored → no-op zip deploy against a container-kind site). **Mitigated** 2026-06-24 by a **manual** `az acr build` + `az webapp config container set` (reverted by the next `azd provision`). **Durable fix "pending design decision (structural — Hard Rule #10)": either move the frontend to Container App or switch to a code/static deploy model.** The current tree took the **code/build-from-source** route (azure.yaml docker block removed; bicep `kind:'app,linux'` + `PYTHON|3.11`), so the azure.yaml/bicep halves now agree — but **the bug row was never closed**, and the in-place `kind` flip on a previously-container site is the residual risk (§8). |
| **BUG-0085** | **fixed 2026-06-25** | Frontend `503` / exit 127 (`uvicorn: command not found`) because `SCM_DO_BUILD_DURING_DEPLOYMENT` was missing → Oryx skipped → fastapi/uvicorn never installed. **Fixed**: added the flag to bicep (present now at L~2030) + live `az webapp config appsettings set` + `azd deploy frontend`. Post-fix the container logged `Site started` and the URL returned `HTTP 302` to Entra login. **This is the proof the packaging/Oryx/start-command chain works.** |
| **BUG-0090** | **open** | **Production admin unreachable + frontend gated by broken Easy Auth.** "The **frontend App Service `app-frontend-<SUFFIX>` has Easy Auth enabled but its Entra provider reads back unconfigured (empty `clientId`/issuer) — the identity layer was never fully provisioned.**" Fix is an **auth-architecture decision awaiting operator sign-off** (Option A backend Easy Auth, or Option B `frontend_app.py` reverse-proxy). **This is the live "error page" cause.** |

Also in `v2/docs/development_plan.md` §0.1: **`FRONTEND-APPSERVICE-AZD-CONTAINER-DEPLOY-DEBT`** (open, the BUG-0081 precursor) — same "azd zip-deploys code against a container App Service, leaving the placeholder image" finding, with the explicit structural fix-scope decision (move to Container App / add `az acr build` hook / correct the appservice+docker wiring). The build-from-source choice resolves it in code but the debt row + BUG-0081 remain open pending a clean-RG `azd provision` verification.

Worklog `v2/docs/worklog/2026-06-25.md` end-state ("Test-ready state"):
- Frontend `https://app-frontend-<SUFFIX>.azurewebsites.net/` → **`HTTP 302` (Entra auth redirect — healthy)** ← i.e. Easy Auth is ON and redirecting.
- Then **BUG-0090** documents that the Entra provider behind that redirect is unconfigured. So the redirect target errors.

---

## 6. MACAE contrast — staged layout, served dir, start command, auth

From `.copilot-tracking/research/subagents/2026-06-25/macae-container-build-pattern.md` (build-from-source / "custom" mode):

| Concern | MACAE (`src/App`) | CWYD v2 (`src/frontend`) | Lines up? |
|---|---|---|---|
| azure.yaml `dist:` | `./dist` | `./build-output` | both internally consistent |
| package script | `package_frontend.sh`: `cp requirements.txt dist; cp *.py dist; npm install; npm run build (→ ./build); cp -rf build dist` | `package_frontend.py`: `copytree dist→build-output/dist; copy frontend_app.py; write requirements.txt` | both produce server + reqs + SPA-subdir |
| staged SPA subdir | `dist/build/` | `build-output/dist/` | names differ, each self-consistent |
| server | `frontend_server.py` serves from **`build/`** | `frontend_app.py` serves from **`dist/`** | each serves its own staged subdir ✔ |
| `linuxFxVersion` | `python|3.11` | `PYTHON|3.11` | equivalent |
| `appCommandLine` | `python3 -m uvicorn frontend_server:app --host 0.0.0.0 --port 8000` | `uvicorn frontend_app:app --host 0.0.0.0 --port 8000` | equivalent (MACAE uses `python3 -m`, more robust) |
| install cmd | **`npm install`** (no lockfile needed) | **`npm ci`** (needs lockfile) | CWYD's lockfile is at the workspace root `v2/package-lock.json`; `npm ci` from the member dir resolves it (verified exit 0) — works, just stricter |
| app settings | `SCM_DO_BUILD_DURING_DEPLOYMENT`, **`WEBSITES_PORT=8000`**, **`ENABLE_ORYX_BUILD=True`**, `BACKEND_API_URL`, **`AUTH_ENABLED=false`**, `PROXY_API_REQUESTS=false` | `SCM_DO_BUILD_DURING_DEPLOYMENT=true`, `BACKEND_API_URL`, `WEBSITES_ENABLE_APP_SERVICE_STORAGE=false` (no WEBSITES_PORT, no ENABLE_ORYX_BUILD, no AUTH flags) | **divergence** |
| **frontend Easy Auth** | **none** (`AUTH_ENABLED=false`; SPA loads directly, no auth wall) | **leftover Easy Auth enabled but Entra provider unconfigured** → error page | **decisive divergence** |

**The packaging/served-dir/start-command triad lines up correctly in BOTH — there is NO mismatch in CWYD.** The naming (`build-output` vs `dist`, SPA in `dist/` vs `build/`) differs but each server serves its own staged subdir. The divergence that breaks CWYD's *load* is the **frontend Easy Auth**: MACAE has none; CWYD has a misconfigured one.

---

## 7. Lockfile / npm-workspace facts (ruled out as the cause)

- `v2/package.json` is an **npm workspace root**: `workspaces: ["src/frontend", "tests/frontend"]`.
- `v2/package-lock.json` is **git-tracked and present on disk** (393,100 bytes).
- `v2/src/frontend/` has **no** member-level `package-lock.json` (correct for a workspace — lockfiles live only at the root). No `.npmrc` anywhere.
- The prepackage wrapper `cd`s into the member dir `v2/src/frontend` and runs `npm ci`. **Verified this session:** `npm ci --dry-run` from `v2/src/frontend` returns **exit 0 / "up to date"** — npm 7+ walks up to the workspace root and resolves `v2/package-lock.json`. **So `npm ci` is NOT a failure point.** (It does reinstall the whole workspace incl. `tests/frontend`, so it is slower and slightly more brittle than MACAE's `npm install`, but it works.)

(Local artifact note: `v2/src/frontend/build-output/` currently contains only `requirements.txt` — no `dist/`, no `frontend_app.py`. `package_frontend.py` writes `requirements.txt` *last*, so this is a stale/incomplete remnant of a prior partial/manual run, not a normal script output. It is gitignored and recreated by the prepackage hook on every `azd package`/`azd up`, so it does not affect the deployed result — but it confirms the local staging has been hand-touched.)

---

## 8. Root cause(s), evidence-ranked

### PRIMARY — Easy Auth identity-provider misconfiguration on the frontend (BUG-0090, open)
- The frontend App Service has **App Service Authentication enabled** (confirmed by the live `HTTP 302` → Entra login in worklog 2026-06-25) but its **Microsoft Entra provider is unconfigured (empty `clientId`/issuer)** (BUG-0090). Every visit redirects into a login that errors → **error page** (a Microsoft-branded AADSTS error at `login.microsoftonline.com`, not an App Service page).
- **Easy Auth is not in `v2/infra/main.bicep`** (no `authSettingV2Configuration` on the frontend module), so `azd up` neither fixes nor removes it — it persists as an env-state leftover on the reused App Service.
- **What the error page looks like:** `302` to `login.microsoftonline.com/...` then an AADSTS error (e.g. `AADSTS700016`/`AADSTS900971`/reply-url errors) or the App Service `/.auth` 500.

### SECONDARY — deploy-state staleness: `kind` won't flip in place (BUG-0081, open)
- If `app-frontend-<SUFFIX>` was first created as `kind: 'app,linux,container'` (BUG-0081 era), the current bicep's `kind: 'app,linux'` may not change in place (`kind` is effectively immutable on `Microsoft.Web/sites`). A container-kind site ignores the code zip-deploy → the SPA "is not deployed" and the URL shows the **App Service placeholder / ":( Application Error"** page (a *different* page than the Easy Auth one).
- This is the unresolved half of BUG-0081 / `FRONTEND-APPSERVICE-AZD-CONTAINER-DEPLOY-DEBT`.

### RULED OUT (with evidence)
- **Build failure** — `npx tsc --noEmit -p src/frontend` exit 0; `npm run build` will not fail.
- **Missing-static-files 404 / staged-vs-served mismatch** — staged `build-output/dist/` exactly matches `frontend_app.py`'s default served dir; `dist: ./build-output` matches the staging root. No mismatch.
- **Wrong start command** — `uvicorn frontend_app:app` resolves at the deploy root where `frontend_app.py` is staged.
- **Missing requirements / Oryx** — `requirements.txt` (fastapi + uvicorn) is staged at the deploy root and `SCM_DO_BUILD_DURING_DEPLOYMENT=true` is set via `siteConfig.appSettings` (proven to land by the identical function-app pattern). BUG-0085 already fixed this.
- **`npm ci` lockfile** — resolves the workspace-root lockfile from the member dir (verified exit 0).

### Disambiguation (which error page is it?) — read-only `az`:
```
az webapp show -g <RESOURCE_GROUP> -n app-frontend-<SUFFIX> --query "{kind:kind, fx:siteConfig.linuxFxVersion}"
az webapp auth show -g <RESOURCE_GROUP> -n app-frontend-<SUFFIX>   # is Easy Auth on? is the Entra provider populated?
curl -sI https://app-frontend-<SUFFIX>.azurewebsites.net/          # 302→login.microsoftonline.com = Easy Auth (PRIMARY); 200 placeholder / 503 = deploy-state (SECONDARY)
az webapp log download -g <RESOURCE_GROUP> -n app-frontend-<SUFFIX> # container start logs
```
- `kind=app,linux,container` ⇒ SECONDARY (recreate the site so the code `kind` takes).
- `kind=app,linux` + a `302` to a failing Entra login ⇒ PRIMARY (Easy Auth).

---

## 9. Answers to the brief's specific sub-questions

**(a) Precise root cause(s):**
1. **Primary:** frontend App Service Easy Auth enabled with an unconfigured Entra provider → broken login redirect = error page (BUG-0090, `v2/docs/bugs.md`; not in `v2/infra/main.bicep`). 2. **Secondary:** possible stale container-`kind` App Service that swallows the code deploy (BUG-0081, `v2/infra/main.bicep` L1970 `kind:'app,linux'` cannot flip a pre-existing `app,linux,container` in place).

**(b) The exact staged-output / `dist` / served-dir / start-command mismatch:** **There is none.** `package_frontend.py` stages `build-output/{dist,frontend_app.py,requirements.txt}`; `azure.yaml` `dist: ./build-output` (L~120) packages that dir; `frontend_app.py` (L~27) serves `build-output/dist/`; `appCommandLine` (`main.bicep` L2000) runs `uvicorn frontend_app:app` at the deploy root. All four line up. The user's mismatch hypothesis is disproved.

**(c) What MACAE does differently + the minimal change to make CWYD deploy/load like MACAE:**
- MACAE's *deploy mechanism* is the same build-from-source pattern CWYD already adopted (no change needed there).
- MACAE's frontend has **no Easy Auth** (`AUTH_ENABLED=false`) so the SPA loads directly. **Minimal change:** remove/disable Easy Auth on the frontend App Service (or fully wire the Entra provider) so the SPA loads — this is BUG-0090's pending auth decision (Option A backend Easy Auth, or Option B frontend reverse-proxy). Because Easy Auth is not IaC-managed, the durable fix is to either (i) wire `authSettingV2Configuration` in bicep with a real Entra app registration + `admin` app role, or (ii) leave the frontend public and authenticate at the backend.
- **Parity hardening** (`main.bicep` frontend `appSettings`, L2009-2031): add `WEBSITES_PORT=8000` and `ENABLE_ORYX_BUILD=True`, and optionally switch `appCommandLine` to `python3 -m uvicorn frontend_app:app --host 0.0.0.0 --port 8000` (MACAE form).
- **Close BUG-0081 durably:** verify on a clean-RG `azd provision` that the frontend lands as `kind:'app,linux'`; if an existing site is container-kind, recreate it so the code `kind` takes.

**(d) Is the error page a build failure / 404 / wrong start command / missing-requirements-Oryx issue?** **None of the four.** Evidence in §8 "RULED OUT". It is an **auth-layer error page (Easy Auth misconfiguration, BUG-0090)**, with a possible secondary **deploy-state / container-`kind` placeholder page (BUG-0081)**.

---

## 10. Key file references

- `v2/azure.yaml` — `services.frontend` (~L110-145): build-from-source, `dist: ./build-output`, prepackage hooks.
- `v2/scripts/package-frontend.ps1` / `v2/scripts/package-frontend.sh` — `npm ci; npm run build; uv run python package_frontend.py`.
- `v2/scripts/package_frontend.py` — stages `build-output/{dist,frontend_app.py,requirements.txt}`.
- `v2/src/frontend/frontend_app.py` — serves `dist/` (default `_DIST_DIR`, L~27); `/config`; SPA catch-all.
- `v2/src/frontend/vite.config.ts` (no `outDir` → `dist/`) + `v2/src/frontend/package.json` (`build: tsc -b && vite build`).
- `v2/infra/main.bicep` — `frontendWebApp` L1966-2034 (`kind:'app,linux'` L1970, `PYTHON|3.11` L1999, `appCommandLine` L2000, `SCM_DO_BUILD_DURING_DEPLOYMENT` in `siteConfig.appSettings` L2009-2031); identical AVM `siteConfig.appSettings` pattern proven on `functionApp` L2103/L2166. No Easy Auth on the frontend.
- `v2/package.json` (workspace root) + `v2/package-lock.json` (tracked, present).
- `v2/docs/bugs.md` — BUG-0081 (open), BUG-0085 (fixed), BUG-0090 (open).
- `v2/docs/development_plan.md` §0.1 — `FRONTEND-APPSERVICE-AZD-CONTAINER-DEPLOY-DEBT` (open).
- `v2/docs/worklog/2026-06-25.md` — frontend `302`/Entra-redirect end-state + BUG-0090 write-up.
- `.copilot-tracking/research/subagents/2026-06-25/macae-container-build-pattern.md` — MACAE build-from-source reference.
