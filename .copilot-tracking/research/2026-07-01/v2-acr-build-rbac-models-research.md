<!-- markdownlint-disable-file -->
# Task Research: CWYD v2 — ACR Build-and-Push Pipeline, RBAC Readiness, and Model Retirement Cleanup

New tenant, clean-slate build of CWYD v2. Before running `azd up`, verify three concerns and produce actionable guidance:

1. Infrastructure provisions a **container registry (ACR)** used to build+push the frontend, backend, and function images from source (analogous to how v1 uses `cwydcontainerreg`), PLUS an explicit **build process that rebuilds and pushes updated code on every build** — not a static pre-built image.
2. **Authorizations (RBAC + auth)** are ready end-to-end for a fresh tenant.
3. **Remove every `gpt-4` reference** and confirm no configured model is on the Microsoft Foundry retirement schedule (<https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule>).

## Task Implementation Requests

* Confirm/gap-check that `v2/infra` creates an ACR and wires a build→push→deploy loop for backend + frontend + function so each build ships updated code.
* Confirm/gap-check RBAC role assignments + authentication for a clean-tenant deploy.
* Enumerate and remove `gpt-4` references; cross-check every configured model against the retirement schedule and recommend current replacements.

## Scope and Success Criteria

* Scope: READ-ONLY survey of `v2/` (infra, azure.yaml, scripts, docker, settings, docs). Cross-referenced the live Microsoft Foundry model-retirement schedule. Excludes v1 except as a reference for the `cwydcontainerreg` pattern.
* Assumptions:
  * Brand-new tenant/subscription; nothing pre-provisioned; single-tenant deployment.
  * `azd up` is the only supported provision+deploy path (Hard Rule #7 — no ARM one-click button).
  * The user wants an explicit, repeatable image build/push process that updates code each build.
* Success Criteria (all met):
  * A decisive answer on the ACR + build/push contract, with concrete files/lines.
  * A complete RBAC/auth readiness checklist with each gap + fix location.
  * A complete list of `gpt-4`/retiring-model references with recommended replacements + exact edit sites.

## ⚠️ Baseline correction — the user-attached 2026-06-25 research is STALE

Two independent subagents confirmed the user-attached baseline (`.copilot-tracking/research/subagents/2026-06-25/v2-infra-current-state.md`) no longer matches the codebase. Treat these corrections as current truth:

| 2026-06-25 baseline claim | Current truth (2026-07-01) | Evidence |
|---|---|---|
| Frontend is `host: appservice` + `docker:` (container on App Service) | Frontend is a **Python App Service source-build** (`kind: 'app,linux'`, `linuxFxVersion: 'PYTHON|3.11'`), no container (BUG-0081) | v2/infra/main.bicep:2074; v2/azure.yaml frontend block |
| Cognitive Services User missing on Foundry account | **Granted** on the Foundry account | v2/infra/main.bicep:611-615 |
| `AZURE_AI_SERVICES_ENDPOINT` missing from both runtimes | **Present on both** backend + function | v2/infra/main.bicep:1871, 2276 |
| `ORCHESTRATOR` vs `CWYD_ORCHESTRATOR_NAME` mismatch | **Fixed** — `CWYD_ORCHESTRATOR_NAME` emitted; dead `ORCHESTRATOR` removed | v2/infra/main.bicep:1933 |
| No sample-data upload step exists | **Exists + auto-wired** via project `postdeploy` hook | v2/azure.yaml:218-228 |

## Outline

* Part A — Container registry + build/push pipeline (ACR already provisioned; only backend is an image)
* Part B — RBAC + authentication readiness (UAMI RBAC complete; end-user auth is opt-in)
* Part C — Model references (only `o4-mini` is a real retirement risk; `gpt-4` refs are cosmetic)
* Selected approach + implementation impact per part
* Open decisions requiring the user

## Research Executed

### Subagent research (all complete)

* Part A → .copilot-tracking/research/subagents/2026-07-01/v2-acr-build-pipeline-research.md
* Part B → .copilot-tracking/research/subagents/2026-07-01/v2-rbac-auth-readiness-research.md
* Part C → .copilot-tracking/research/subagents/2026-07-01/v2-model-retirement-research.md
* Residual gaps → .copilot-tracking/research/subagents/2026-07-01/v2-residual-gaps-research.md
* Prior baseline (superseded where noted) → .copilot-tracking/research/subagents/2026-06-25/v2-infra-current-state.md

### External research

* Microsoft Foundry model-retirement schedule (page updated 2026-06-05)
  * Source: <https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule>

## Key Discoveries

### Part A — Container registry + build/push pipeline

* **ACR is already provisioned by infra.** Module `containerRegistry` (AVM `container-registry/registry:0.12.1`), name `cr<suffix>`, Basic SKU, admin user OFF, `azureADAuthenticationAsArmPolicyStatus: 'enabled'`, AcrPull granted to the shared UAMI. Login server exported as `AZURE_CONTAINER_REGISTRY_ENDPOINT`. No change required.
  * v2/infra/main.bicep:1751 (module), :2680 (output)
* **Only the BACKEND is a Docker image today.** Per-service reality:

  | Service | `host:` | Image? | Build/deploy mechanism | Ships fresh code each build? |
  |---|---|---|---|---|
  | backend | `containerapp` | **Yes** | ACR remote build (`remoteBuild: true`) → push → unique per-build tag → live revision patch | Yes |
  | frontend | `appservice` | **No** | `npm ci && npm run build` → zip-deploy to App Service (`PYTHON|3.11` static server) | Yes |
  | function | `function` | **No** | regenerate `build-functions/` → zip-to-blob deploy (Flex Consumption) | Yes |

* **The repeatable, code-updating loop already exists: `azd deploy` / `azd up`.** The backend image swap uses a **unique per-build tag** (not fixed `latest`), so a rebuild reliably rolls a new Container App revision to the new code. The bicep `image: ...:latest` value is only a placeholder that azd overwrites at deploy.
  * v2/azure.yaml:124 (`remoteBuild: true`); v2/infra/main.bicep:1781 (`azd-service-name: backend`), :1624-1632 + :1820-1828 (authoritative placeholder/swap comments)
* **Flex Consumption cannot run a custom container.** Microsoft Learn confirms Flex has a single deploy path (build → zip → blob). Containerizing the function would require changing the hosting model (→ Functions on Container Apps, or Premium/Dedicated) — a structural change (Hard Rule #10). `v2/docker/Dockerfile.functions` is compose-only; azd does not use it.
* **CGSA + MACAE parallel.** Both accelerators ship a *default* `main.bicep` that pulls pre-built images from a Microsoft-owned public ACR (the v1 `cwydcontainerreg` model) AND a *custom* path that provisions its own ACR + builds from source. CWYD v2 already matches MACAE's `main_custom` (frontend `python|3.11` + `SCM_DO_BUILD_DURING_DEPLOYMENT`, ACR `cr${solutionSuffix}` Basic/admin-off). v2 already adopted the proven modern pattern — it does **not** use the static pre-built-image model of v1.
* **No standalone `az acr build` / `docker push` script exists in v2** — the image build is driven entirely by `azd`.

### Part B — RBAC + authentication readiness

* **UAMI RBAC is COMPLETE for a fresh-tenant `azd up`.** A single shared User-Assigned Managed Identity `id-<suffix>` backs all workloads. Every data-plane operation the runtimes perform (OpenAI inference, embeddings, Foundry Project/Agents, Document Intelligence parsing, AI Search read/write, Cosmos data, Postgres, Blob, Queue, Speech, Content Safety, ACR pull, App Insights) maps to a granted role on the correct scope. **Zero UAMI gaps.** 34 role assignments across 6 principals (UAMI, Foundry Project MI, Search system MI, Event Grid system MI, deployer, monitoring).
* **All prior RBAC/endpoint gaps are closed** (BUG-0051/0052/0059/0061/0062/0063/0064/0069 durable back-ports landed 2026-06-22…06-29). The dev_plan §0.1 debt queue has **no open RBAC/endpoint row**.
* **End-user authentication is the ONE authorization area not wired — by design (opt-in).** Frontend Easy Auth is explicitly disabled (`platform.enabled: false`, anonymous); the backend Container App has **no `authConfigs`**; `AZURE_REQUIRE_ADMIN_AUTH=false`. The backend *code* fully implements Easy Auth (`x-ms-client-principal` parsing, `requires_role("admin")`, `get_user_id`), but a fresh deploy runs **anonymous in production mode**. There is **no Entra app registration anywhere in `v2/infra/**`**.
  * v2/infra/main.bicep:2050-2069 (frontend Easy Auth disabled); backend dependencies.py (code-side auth implemented)
* **Fresh-tenant prerequisite:** the deployer must hold **Owner or User-Access-Administrator** to create the 34 role assignments, plus the usual resource-provider registrations and model quota.
* **cosmos-mode KB grounding (BUG-0059 residual) is CLOSED.** `post_provision.py::_ensure_kb_mcp_connection` creates the `cwyd-kb-mcp` connection (`RemoteTool`, `authType: ProjectManagedIdentity`, `audience: https://search.azure.com`) that the backend env references, and seeds KB `cwyd-kb` + source `cwyd-index-ks`. The Project MI has Search data-plane RBAC and `AZURE_AI_PROJECT_RESOURCE_ID` is a bicep output, so the happy path authenticates. Residual 401 risk is **low** (only if the postprovision hook aborts or the env var never reaches the hook).
  * v2/scripts/post_provision.py:517 (`_ensure_kb_mcp_connection`), :577-586 (properties), :391 (KB/source seed); v2/infra/main.bicep:939-951 (Project MI Search RBAC), :2570 (`AZURE_AI_PROJECT_RESOURCE_ID` output)

### Part C — Model references (gpt-4 + retirement schedule)

* **The deployable config is already clean of `gpt-4`.** It ships `gpt-5.1` / `o4-mini` / `text-embedding-3-large`.
* **Retirement-schedule status of the three deployed models:**

  | Role | Model / version | Status | Retires | Verdict |
  |---|---|---|---|---|
  | chat | `gpt-5.1` / `2025-11-13` | GA | 2027-05-15 | ✅ safe (longest gpt-5.x runway) |
  | embedding | `text-embedding-3-large` / `1` | GA | 2027-04-15 | ✅ safe |
  | reasoning | `o4-mini` / `2025-04-16` | **Deprecated** | **2026-10-16** | ❌ **must replace** |

* **`o4-mini` is the single deployable retirement risk.** Recommended replacement: **`gpt-5-mini` / `2025-08-07`** (GA → 2027-02-06), OR drop the dedicated reasoning deployment entirely because `gpt-5.1` already auto-emits reasoning.
* **All `gpt-4o` / `gpt-4o-mini` / `gpt-4.1` and the full o-series are Deprecated/retiring** (retire 2026-10-01…2026-12-10). CWYD does not deploy any of them. The `-chat` gpt-5 variants are all Retired; CWYD correctly uses base `gpt-5.1`.
* **`gpt-4` reference count: 56 total** — infra **0**, top-level v2 config **0**, src **2** (docstring examples), tests **43** (mocked fixtures), docs **11** (historical/roadmap). **0 affect deployment.**
* **Exact model edit sites (o4-mini → replacement):**
  * v2/infra/main.bicep:161 (name), :164 (value), :171 (version), :175 (sku/capacity); deployments array :557-595
  * v2/infra/main.parameters.json:35 (`reasoningModelName`), :36 (value), :38-39 (version), :41-42 (sku), :44-45 (capacity)
  * v2/infra/main.waf.parameters.json — byte-identical to main.parameters.json (same line map; earlier `~36/~40` estimate corrected)
  * v2/src/backend/core/settings.py — `OpenAISettings` deployment fields default to `""` (infra-pinned); env names `AZURE_OPENAI_GPT_DEPLOYMENT` / `_REASONING_DEPLOYMENT` / `_EMBEDDING_DEPLOYMENT` / `_API_VERSION`
* **Non-retirement notes:** `embedding_dimensions=1536` intentionally truncates `text-embedding-3-large` (native 3072) to match the index — keep. Cosmetic API-version drift: `.env.sample` uses `2024-12-01-preview` vs bicep `2025-01-01-preview` (both valid). `business-cases.md` roadmap mentions `GPT-4 Vision` (no longer a standalone model).

## Technical Scenarios

### Scenario A — ACR + build/push contract for a fresh `azd up`

The user confirmed **all three services (backend, frontend, function) become Docker images built from source and pushed to the infra-provisioned ACR (`cr<suffix>`), rebuilt each deploy** — the `cwydcontainerreg`-style "code ready-built in the container" pattern. Backend already does this. This scenario is now the SELECTED path (Hard Rule #10 structural changes apply — implementation needs a per-unit sign-off).

**Target end-state — one primitive, one environment, one registry, one identity for all three:**

| Service | Current host | Target host | azure.yaml edit | bicep edit | Dockerfile | Risk |
|---|---|---|---|---|---|---|
| backend | `containerapp` | `containerapp` (unchanged) | none | none | `Dockerfile.backend` | — |
| frontend | `appservice` (Python source-build) | **`containerapp`** | `host: containerapp` + `docker:` (`Dockerfile.frontend`, `target: prod`) | replace App Service with `Microsoft.App/containerApps` tagged `azd-service-name: frontend`, external ingress `targetPort: 80`, UAMI identity, ACR registry, `BACKEND_API_URL` env | reuse `Dockerfile.frontend` `prod` stage (uvicorn :80, serves `/config`) | Medium |
| function | `function` (Flex Consumption zip) | **`containerapp`** (Azure Functions on ACA) | `host: containerapp` + `docker:` (new prod `Dockerfile.functions`); drop the `prepackage` zip hook | replace Flex Function App + App Service Plan + deployment-package container with `Microsoft.App/containerApps` `kind: functionapp` on the shared env, `azd-service-name: function`, `AzureWebJobsStorage__accountName`, ACR image, UAMI | prod rewrite of `Dockerfile.functions` reproducing `prepackage_function.py`'s `functions/`-subpackage nesting | High |

**Preferred Approach: Azure Functions on Azure Container Apps for the function; mirror the backend Container App for the frontend.**

* **Function host = Azure Functions on Azure Container Apps** (`Microsoft.App/containerApps` with `kind: functionapp`, deployed via azd `host: containerapp`). This is the ONLY azd-supported containerized-Functions path — azd's `host: function` target is zip-deploy-only (the azure.yaml schema forbids `docker:`/`image:` under `host: function`), and Flex Consumption cannot host custom containers. Functions-on-ACA keeps the Functions programming model, gives KEDA event-driven scaling for the HTTP + Queue triggers (the Event-Grid-fed-queue design sidesteps the blob-trigger caveat), managed-identity ACR pull + `AzureWebJobsStorage`, and collapses the function onto the SAME primitive + environment (`cae-<suffix>`) + registry (`cr<suffix>`) + UAMI/AcrPull the backend already uses. It is a NET REDUCTION in infra: deletes the Flex plan, the App Service Plan, the deployment-package container, and the `flexDeploymentRole` (Storage Blob Data Owner).
* **Frontend = mirror the backend Container App block.** External ingress on `targetPort: 80`; the frontend resolves the backend URL at RUNTIME via its `/config` endpoint → `BACKEND_API_URL` env var (NOT a `VITE_BACKEND_URL` build-arg — do not bake it). AcrPull is already registry-scoped on the shared UAMI, so no new RBAC.
* **All three share:** one ACR (`cr<suffix>`, Basic SKU is fine for 3 repos), one Container Apps Environment (`cae-<suffix>`), one UAMI. `azd deploy --all` builds + pushes + rolls all three with unique per-build tags.

**Implementation risks to sequence around (from v2-containerize-frontend-function-research.md):**

1. **Function import layout (High)** — the current `Dockerfile.functions` is compose-only and `COPY src/functions → wwwroot` flattens blueprints, breaking `from functions.<sub>` imports. The prod image MUST reproduce the `functions/`-subpackage nesting that `prepackage_function.py` builds today.
2. **AVM `container-app` module version** — `kind: functionapp` needs a newer AVM version than the backend's pinned `0.22.1`; either bump the shared module (re-validate the backend) or author a raw `Microsoft.App/containerApps` resource for the function only.
3. **`alwaysReady` → `minReplicas`** — Flex `alwaysReady: [batch_push:1, blob_event:1]` becomes ACA `minReplicas ≥ 1` (warm queue consumers, no scale-to-zero).
4. **Drop Flex deployment RBAC** — remove `flexDeploymentRole` + the deployment-package container; confirm nothing else references them.
5. **CORS / skillset repointing** — repoint any backend CORS/frontend-origin env and any AI Search skillset referencing `AZURE_FUNCTION_APP_URL` to the new Container App FQDNs.

**Considered Alternatives (rejected):**

* *Keep frontend on App Service / function on Flex (fresh-code-only, no containers)* — rejected: the user explicitly wants all three as ACR images.
* *Function on Premium/Dedicated plan with a container image* — rejected: not the azd-supported modern path; adds a plan resource where ACA collapses onto the existing environment.
* *Parameterized `SERVICE_*_IMAGE_NAME` bicep param* — rejected: chicken-and-egg on first deploy; azd's placeholder + unique-tag swap is the documented pattern and stays.

### Scenario B — Authorization readiness (SELECTED: no change)

Decision #2: accept anonymous, no code change, no manual identity in the frontend config. **UAMI RBAC is already complete; nothing to implement.** Easy Auth stays off (`platform.enabled: false`), backend `authConfigs` absent, `AZURE_REQUIRE_ADMIN_AUTH=false`. The only fresh-tenant prerequisite is that the deployer holds **Owner or User-Access-Administrator** to create the 34 role assignments during `azd up`.

*Note:* the two new Container Apps (frontend, function) inherit the same shared UAMI + AcrPull; no new role assignments are required for the containerization beyond what already exists.

### Scenario C — Model cleanup (SELECTED: drop reasoning + full scrub)

Decisions #4 + #5. Full detail in v2-reasoning-drop-gpt4-scrub-research.md.

**Drop the dedicated reasoning deployment — confirmed SAFE.** The `o4-mini` reasoning deployment is **dead in the production runtime path**: the `FoundryIQ` provider overrides `complete()` and never reads `reasoning_deployment`; it probes the CHAT deployment (`gpt-5.1`) via `supports_reasoning()` and streams reasoning summaries through the Responses API. `gpt-5.1` keeps emitting chain-of-thought, so the reasoning panel survives. Empty `AZURE_OPENAI_REASONING_DEPLOYMENT=""` never crashes the prod path.

* **Recommended collapse = Option (b) full removal** — remove the `o4-mini` model deployment + `reasoningModel*` params + the `AZURE_OPENAI_REASONING_DEPLOYMENT` env + the settings field + dead routing branches (keep `reason()` but retarget its default resolution to the chat deployment). Aligns with the user's "no dedicated reasoning" + "reduce code debt." Edit sites (from the subagent doc): bicep lines 69/122/160-175/551/571-584/654/681-699/708/1881/2563/2581-2582; `main.parameters.json` + `main.waf.parameters.json` lines 35-46; plus settings.py / base / foundry_iq / definitions / admin / frontend / post_provision.
* **Fallback = Option (a)** — point `AZURE_OPENAI_REASONING_DEPLOYMENT` at the `gpt-5.1` deployment (infra-only, minimal), leaving a redundant field. Use only if the structural removal is deferred.
* **Tests that break under full removal (must be updated in the same sweep):** `test_foundry_iq.py:338` (asserts `model == "o4-mini"`), `agents/test_base.py:318` (`deployment_attr="reasoning_deployment"`), `test_admin.py:245/391/400` (asserts `reasoning_deployment` in `AdminConfig`).

**Scrub all `gpt-4` — 58 first-party lines, 0 in infra/config.**

| Category | Count | Scrub action |
|---|---|---|
| A — production `v2/src/**` (docstring examples) | 2 | replace literal with `gpt-5.1` |
| B — infra/config (`infra`, `azure.yaml`, `.env*`, `docker*`) | 0 | already clean (`gpt-5.1`) |
| C — tests `v2/tests/**` (19 routing-tied `[R]`) | 43 | replace fixture literal with `gpt-5.1`; preserve each assertion's intent — the 19 routing-tied cases need care |
| D — docs `v2/docs/**` (all 11 historical `[H]`) | 11 | live docs → replace; dated records (`bugs.md`, `worklog/**`) → recommend LEAVE (Hard Rule #16/#19), `docs/plan/**` is a user call |
| E — scripts `v2/scripts/**` (comments) | 2 | replace/remove comment literal |

* Deployable config is already `gpt-4`-free and ships `gpt-5.1` / `text-embedding-3-large`. The scrub is a code-hygiene sweep, not a deploy blocker.
* `embedding_dimensions=1536` (truncates `text-embedding-3-large`) is intentional — keep.

## Potential Next Research / open implementation choices

* **Function scaling:** `minReplicas: 1` (warm, mirrors Flex `alwaysReady`) vs `0` (true scale-to-zero, queue cold-start). Recommend `1` to preserve current warm-consumer behavior; confirm with user (cost trade-off).
* **Function Dockerfile strategy:** keep `prepackage_function.py` + a thin Dockerfile (minimal diff) vs a self-contained prod Dockerfile that deletes `prepackage_function.py` + `build-functions/` (cleaner end-state, more churn). Recommend the self-contained prod Dockerfile for a clean container end-state.
* **AVM module approach:** bump the shared `container-app` AVM version (affects backend — re-validate) vs a raw `Microsoft.App/containerApps` for the function only. Recommend bumping the shared module for consistency.
* **Reasoning removal depth:** narrow `DeploymentAttr` to `Literal["gpt_deployment"]` vs remove the `deployment_attr` field entirely (Hard Rule #10 structural confirmation).
* **Region/quota:** verify `gpt-5.1` + `text-embedding-3-large` GlobalStandard quota in `eastus2` (default) on the fresh tenant before `azd up`.
* **azd version:** confirm the operator's `azd version` honors unique per-build containerapp tags (repo pins `>= 1.18.0 != 1.23.9`).


## Confirmed decisions (user, 2026-07-01)

1. **Image scope = ALL THREE as Docker images in the provisioned ACR** ("yes"). The user wants the `cwydcontainerreg`-style pattern: backend + frontend + function are each built as a container image, pushed to the infra-provisioned ACR, and rebuilt (code updated) on every deploy. This is the literal interpretation and it **forces two structural changes (Hard Rule #10 — requires implementation sign-off):**
   * Frontend: `host: appservice` (Python source-build) → **`host: containerapp`** with `Dockerfile.frontend` (backend already does this; `Dockerfile.frontend` prod stage already exists).
   * Function: `host: function` on **Flex Consumption cannot run a custom container** → must move to a container-capable Functions host (**Azure Functions on Azure Container Apps** is the recommended target — keeps the Functions programming model + KEDA event-driven scaling for the blob/queue/event-grid/http triggers).
2. **End-user auth = accept anonymous. NO code change, NO manual identity in the frontend config.** RBAC (UAMI) already complete; leave Easy Auth off. Nothing to implement.
3. **Database mode = `cosmosdb`** (default) — deploys Azure AI Search + Foundry IQ KB.
4. **Reasoning model = DROP the dedicated reasoning deployment; no `gpt-5-mini`, no separate reasoning model.** Remove the `o4-mini` deployment entirely; the reasoning slot reuses/collapses into `gpt-5.1`. Requires verifying the backend behaves correctly when there is no dedicated reasoning deployment.
5. **gpt-4 scrub = remove ALL `gpt-4` references** across the tree (src + tests + docs), subject to not breaking o-series routing test assertions and flagging any historical records (bugs.md / worklog) where a rewrite is inadvisable.

### Follow-on research launched for the confirmed path

* Containerize frontend + function → .copilot-tracking/research/subagents/2026-07-01/v2-containerize-frontend-function-research.md
* Drop dedicated reasoning + full gpt-4 scrub inventory → .copilot-tracking/research/subagents/2026-07-01/v2-reasoning-drop-gpt4-scrub-research.md
