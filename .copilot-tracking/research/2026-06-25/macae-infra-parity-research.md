<!-- markdownlint-disable-file -->
# Task Research: MACAE infra parity for one-shot `azd up` (CWYD v2)

Make CWYD v2 deployable end-to-end with a single `azd up`: provision the infrastructure **and** build + deploy the frontend, backend, and function code from source — no manual `az ... update` steps afterward. Use the known-working MACAE sample infra (`data/sample_code/macae`) as the reference for the patterns that v2/infra is missing or getting wrong.

## Task Implementation Requests

* `azd up` deploys infra and the three code services (frontend, backend, function) in one shot.
* The operator selects `cosmosdb` or `postgresql` at provision time.
  * `cosmosdb` → also deploy Azure AI Search service(s).
  * `postgresql` → do NOT deploy Azure AI Search.
* A post-provision (post-deploy) script uploads the sample/data files automatically.
* Build the container(s) from the current source during `azd up` (ACR build), and have bicep reference that built image by **container name + tag only** — no resource "search"/lookup in bicep, just the image coordinates azd injects from the build.
* Identify every place v2/infra currently requires a manual change (the "durable bicep fix pending" debt) and close the parity gap against MACAE.

## Scope and Success Criteria

* Scope: v2 infrastructure + deployment wiring only — `v2/azure.yaml`, `v2/infra/**`, `v2/scripts/**` (post-provision / prepackage), `v2/docker/**` Dockerfiles, and the azd image-injection contract. Compared against `data/sample_code/macae` (azure.yaml + infra). Excludes application runtime code fixes (the open BUG list) except where a bicep env-var/role wiring is the durable fix.
* Assumptions:
  * MACAE is a working, azd-deployable reference for the container-build + image-injection + post-provision pattern.
  * v2 already has a `databaseType` parameter (per BUG-0060) and a partially-wired conditional Search path.
  * Many "manual changes" are already catalogued in `v2/docs/bugs.md` as deferred bicep back-ports.
* Success Criteria:
  * A complete map of the MACAE azd-up flow (build → push → bicep image reference → deploy → post-provision).
  * A complete map of v2's current flow and a gap list against MACAE.
  * The conditional-deploy mechanism (cosmos↔Search) verified for v2 and corrected against MACAE's conditional pattern.
  * A consolidated list of every manual change v2 currently needs, each mapped to the durable bicep/azure.yaml fix.
  * A selected, sequenced remediation approach (research-only; no code changes in this phase).

## Outline

1. The single biggest insight: v2's database↔Search branch is ALREADY correct; the real gaps are (a) the frontend deploy host, (b) the image-reference contract, (c) ~11 un-back-ported bicep env/RBAC/network fixes, and (d) a missing sample-data upload.
2. MACAE container-build + image-reference pattern (param-trio, no resource lookup; App Service frontend, never appservice+docker).
3. MACAE identity/RBAC + conditional-module idiom + post-provision data upload.
4. v2/infra current state + the precise gap list.
5. The consolidated manual-change debt (A1–A12) that reverts on every `azd up`.
6. Selected remediation approach + sequence (Phase 2).

## Potential Next Research

* Confirm exact current line numbers in v2/infra/main.bicep before any edit turn (orchestrator env ≈L1776; postgres principal backend ≈L1760 / function ≈L2066; backend `env` block; Event Grid module + `eventGridQueueSenderRole`; function storage `networkRuleSet`).
  * Reasoning: the back-port edits target specific lines; line numbers drift.
  * Reference: subagents/2026-06-24/manual-change-debt-deployment-iac.md "Recommended next research".
* Confirm v2/infra/modules/container_registry.bicep exposes a `policies` / AVM param for the ARM-auth policy (A10).
  * Reasoning: A10 fix depends on the module surface.
  * Reference: subagents/2026-06-24/manual-change-debt-deployment-iac.md A10.
* Read a MACAE `content_packs/*/pack.json` for the exact upload-manifest schema if v2 adopts a manifest-driven uploader.
  * Reasoning: informs the sample-data uploader design.
  * Reference: subagents/2026-06-25/macae-identity-env-hooks.md §4.

## Research Executed

### File Analysis

* data/sample_code/macae/azure.yaml + azure_custom.yaml
  * Default `azure.yaml` has NO `services:` block (only `hooks:`) → `azd up` provisions infra only, references prebuilt public images by name+tag. `azure_custom.yaml` adds backend+mcp (`host: containerapp`, `docker.remoteBuild: true`, `registry: ${AZURE_CONTAINER_REGISTRY_ENDPOINT}`) and frontend (`host: appservice`, `dist: ./dist`, `prepackage` build hook — NO docker block).
* data/sample_code/macae/infra/bicep/main.bicep
  * Image referenced inline `'${<svc>ContainerRegistryHostname}/${<svc>ContainerImageName}:${<svc>ContainerImageTag}'` (lines 506-545 backend, 680-711 mcp). Params at 148-173. `isCustom` boolean (line 189) flips ACR creation (`if(isCustom)`, line 491/734), `azd-service-name` tags, `registries: [{server, identity: UAMI}]`, and the frontend `linuxFxVersion` (`python|3.11` vs `DOCKER|...`, line 805).
  * Frontend is `Microsoft.Web/sites` (App Service) in BOTH modes (module call line 798). Never a Container App, never appservice+docker. SPA gets backend URL at runtime via `frontend_server.py` `/config` fed by appSetting `BACKEND_API_URL`.
  * Conditional-module idiom: `module x '…' = if (condition) {…}`, consumed via `x!.outputs…` and `output Y string? = condition ? x!.outputs.z : null`.
* data/sample_code/macae/infra/scripts/post-provision/post_deploy.sh/.ps1
  * Uploads sample files via `az storage blob upload-batch --auth-mode login` from in-repo `content_packs/<usecase>/` (manifest `pack.json`); builds Search indexes (`index_datasets.py`, AzureCliCredential); seeds vector stores / Foundry IQ KBs. `azure.yaml` only has a `postdeploy` hook that PRINTS the command (MACAE runs the upload semi-manually).
* v2/azure.yaml
  * backend `host: containerapp` + docker (works via azd placeholder-swap). frontend `host: appservice` + `docker:` block (**BROKEN — BUG-0081**, azd ignores the Dockerfile and zip-deploys). function `host: function` + service-scoped `prepackage` hook (works after BUG-0080). Project-level `postprovision` hook only; NO `postdeploy`, NO sample-data upload.
* v2/infra/main.bicep
  * Backend image = MCR placeholder `mcr.microsoft.com/k8se/quickstart:latest` (line ~1714), frontend = `DOCKER|mcr.microsoft.com/appsvc/staticsite:latest` (line ~1971); azd swaps both at deploy via `azd-service-name` tags + bicep-provisioned ACR `cr<suffix>`. No `SERVICE_*_IMAGE_NAME` param, no name+tag param trio.
  * `databaseType` (allowed cosmosdb/postgresql, default cosmosdb). **Search conditional is CORRECT** — cosmosdb ⇒ Search + KB connection + search DNS zone; postgresql ⇒ pgvector, Search service/RBAC/connection/DNS all skipped, search env+outputs empty (see the 13-row conditional table in the subagent doc).
  * Env gaps: `AZURE_AI_SERVICES_ENDPOINT` on NEITHER backend nor function env (only a stack output) → DocumentIntelligence parsing breaks (BUG-0034/0052). `ORCHESTRATOR` env var set but backend reads `CWYD_ORCHESTRATOR_NAME` (dead var, masked by the agent_framework default; wrong value for postgresql).
  * RBAC gap: Cognitive Services User (`a97b65f3…`) granted only on Content Safety, NOT the AI Services/Foundry account → DI auth breaks (BUG-0052).
* v2/scripts/post_provision.py
  * Enables pgvector (postgres mode), seeds the `cwyd-index` Search index schema + Foundry IQ KB (cosmos mode). Does NOT upload documents. No `v2/data/` exists; sample docs live in root `data/`.

### Code Search Results

* databaseType conditional gating — 13 conditional sites enumerated in subagents/2026-06-25/v2-infra-current-state.md §2b; all correct.
* `AZURE_AI_SERVICES_ENDPOINT` — present only as `output` (main.bicep ~L2359), absent from both runtime `env` blocks.
* `ORCHESTRATOR` vs `CWYD_ORCHESTRATOR_NAME` — bicep emits `ORCHESTRATOR` (~L1810), settings.py reads `env_prefix="CWYD_ORCHESTRATOR_"` field `name`.

### External Research

* azd schema: `host: appservice` does NOT support a `docker:` block (only `containerapp`, `aks`, `ai.endpoint`, `azure.ai.agent` do) — root cause of BUG-0081, corroborated by the MACAE App Service never pairing appservice+docker.

### Project Conventions

* Standards referenced: `.github/copilot-instructions.md` Hard Rules — #4 (registry/no resource lookup), #10 (structural change requires user confirmation: frontend host, image contract, Event Grid restructure are all #10), #18 (no env-specific content in tracked files — back-ported bicep must use placeholders/params), Hard Rule #19 (worklog/bugs durability).
* Instructions followed: Task Researcher mode (research-only; all exploration delegated to subagents); `v2-infra.instructions.md`.

## Key Discoveries

### Project Structure

The deployment surface splits into three independently-fixable concerns:

1. **Code build + image reference** — backend already builds-from-source correctly (azd placeholder-swap); frontend does not (wrong host). The user wants an explicit "bicep references the built image by name+tag, no lookup" contract — that is MACAE's param-trio.
2. **Database/Search branch** — already correct in v2; no change needed. This is the single most important finding: the cosmosdb↔Search-vs-pgvector conditional the user asked for **already works**.
3. **The 11-item un-back-ported manual-change debt** (A1–A12) — every live `az ... update` fix reverts on the next `azd up`. This is the actual reason "v2/infra doesn't work without manual changes."
4. **Missing sample-data upload** — no hook uploads the root `data/` docs, so a fresh deploy grounds on nothing.

### Implementation Patterns

**MACAE image-reference (the pattern the user described):** three plain params per service (`<svc>ContainerRegistryHostname` / `<svc>ContainerImageName` / `<svc>ContainerImageTag`) composed inline as `'${hostname}/${name}:${tag}'`. No `reference()`, no `existing` ACR symbol, no resource lookup. `main.parameters.json` maps registry hostname + tag from azd env (`${AZURE_ENV_CONTAINER_REGISTRY_ENDPOINT}`, `${AZURE_ENV_IMAGE_TAG=latest_v5}`); image names fall through to bicep defaults. Build-from-source uses `docker.remoteBuild: true` so azd builds in ACR and patches the live app by `azd-service-name` tag.

**MACAE conditional-module idiom (for any future "skip Search entirely"):** `module search '…' = if (databaseType == 'cosmosdb') {…}` + `output … string? = databaseType == 'cosmosdb' ? search!.outputs.endpoint : null` + RBAC tolerance `resource … existing = if (!empty(id))`. v2 already applies this idiom correctly to Search.

**MACAE frontend (the fix for BUG-0081):** App Service, never appservice+docker. Two clean options — (A) build-from-source: `linuxFxVersion: 'python|3.11'` + `dist: ./dist` + `prepackage` build hook + uvicorn `appCommandLine` → zip deploy; (B) prebuilt: `linuxFxVersion: 'DOCKER|<registry>/<name>:<tag>'` referenced straight from bicep. A third v2-native option is to move the frontend to a **Container App** (mirrors the backend exactly, fully azd-supported container build).

### Complete Examples

```bicep
// MACAE-style explicit image reference — backend Container App (no resource lookup)
param backendContainerRegistryHostname string = ''           // azd writes the ACR login server
param backendContainerImageName string = 'cwyd-backend'
param backendContainerImageTag string = 'latest'
// ...
containers: [
  {
    name: 'backend'
    image: '${backendContainerRegistryHostname}/${backendContainerImageName}:${backendContainerImageTag}'
    // ...
  }
]
registries: [
  { server: '${backendContainerRegistryHostname}', identity: userAssignedIdentity.outputs.resourceId }  // A11
]
```

```yaml
# MACAE-style frontend on App Service — build-from-source (no docker block on appservice)
services:
  frontend:
    project: ./src/frontend
    language: js
    host: appservice
    dist: ./dist
    hooks:
      prepackage:
        posix: { shell: sh, run: ../scripts/package-frontend.sh }
        windows: { shell: pwsh, run: ../scripts/package-frontend.ps1 }
```

### API and Schema Documentation

* azd `azure.yaml` schema — `host` ∈ {containerapp, appservice, function, aks, staticwebapp, springapp, ai.endpoint}; `docker:` block supported only on containerapp/aks/ai.endpoint/azure.ai.agent. Source of BUG-0081.
* `Microsoft.ContainerRegistry/registries` `policies.azureADAuthenticationAsArmPolicy.status` — must be `enabled` for App Service/Container App MI→ACR token exchange (A10).
* `Microsoft.Web/sites/config` `functionAppConfig.scaleAndConcurrency.alwaysReady` — Flex Consumption scale-from-zero for queue triggers (A2).

### Configuration Examples

```jsonc
// main.parameters.json — backend image only (frontend is App Service python-zip, no image)
"backendContainerRegistryHostname":  { "value": "${AZURE_CONTAINER_REGISTRY_ENDPOINT}" },
"backendContainerImageTag":          { "value": "${AZURE_ENV_IMAGE_TAG=latest}" }
```

## Technical Scenarios

### Scenario 1 — One-shot `azd up` that builds + deploys all three services with bicep referencing the built image by name+tag

The user wants: build the container from current source during `azd up`, and have bicep point to that image by name+tag only (no resource lookup). v2's backend already build-from-source via azd's placeholder-swap, but bicep references a throwaway MCR placeholder, not the named image — so it does not match the requested contract, and the frontend deploy is outright broken.

**Requirements:**

* Backend builds from source on `azd up` via ACR remote build (Container App) and runs the freshly built image; bicep references it as `'${hostname}/${name}:${tag}'` from params — no `existing` ACR symbol, no `reference()`.
* Frontend builds from source on `azd up` via **App Service python-zip** — Vite `npm run build` in a `prepackage` hook → `dist/` zip-deployed by azd. MACAE's exact pattern: no container image, no `docker:` block on the `appservice` host.
* Function continues as a Flex zip deploy (no container) with its working `prepackage` hook.
* ACR pull works under managed identity on first provision for the backend Container App (A10 ARM-auth policy + A11 `registries:` block).

**Preferred Approach (match MACAE exactly):**

* **Frontend stays an App Service**, served build-from-source via `linuxFxVersion: 'python|3.11'` + `dist: ./dist` + a `prepackage` build hook (npm build → copy to `dist` → azd zip-deploys). **Remove the unsupported `docker:` block** from `services.frontend` — that combination is the root cause of BUG-0081. The SPA reads the backend URL at **runtime** from a `/config` endpoint fed by an App Service app setting (`BACKEND_API_URL` ← `${AZURE_BACKEND_URL}`), exactly as MACAE does — no build-time `VITE_BACKEND_URL` bake.
* **Backend keeps `host: containerapp`** and adopts the MACAE explicit image param-trio so bicep references the built image by name+tag (the "no search in bicep" contract); set the initial `image:` to `${hostname}/cwyd-backend:${tag}`. Wire `main.parameters.json` to feed the ACR login server + tag from the azd env; image name defaults in bicep.

```text
v2/azure.yaml
  services.frontend  host: appservice + docker block   ->  host: appservice + dist: ./dist + prepackage hook (no docker)
  services.backend   host: containerapp + docker        ->  unchanged (build-from-source)
v2/infra/main.bicep
  + param backendContainerRegistryHostname / ImageName / ImageTag
  ~ backend image:  MCR placeholder                     ->  '${hostname}/${name}:${tag}'
  + registries: [{ server, identity: UAMI }]            (A11, backend only)
  + ACR policies.azureADAuthenticationAsArmPolicy='enabled'  (A10)
  ~ frontend Microsoft.Web/sites linuxFxVersion         ->  'python|3.11' + appCommandLine (uvicorn static server)
  + frontend appSetting BACKEND_API_URL = backend FQDN  (runtime /config)
v2/infra/main.parameters.json
  + backendContainerRegistryHostname = ${AZURE_CONTAINER_REGISTRY_ENDPOINT}
  + backendContainerImageTag         = ${AZURE_ENV_IMAGE_TAG=latest}
v2/scripts/  (+ package-frontend.{sh,ps1} prepackage hook: npm ci && npm run build -> dist/)
```

**Implementation Details:** MACAE's runtime `/config` pattern (App Service app setting → `/config` endpoint) decouples the Vite build from the provisioned backend URL, so the `prepackage` build does not need `${AZURE_BACKEND_URL}` available at build time. v2's `Dockerfile.frontend` prod stage already runs a Python/uvicorn static server — reuse that server script as the App Service `appCommandLine` entrypoint. The Dockerfile.frontend dev/build stages remain for local `docker compose`; its prod stage is no longer used for azd deploy.

#### Considered Alternatives

* **Alt-1a — Frontend as a Container App (uniform with the backend).** Mirrors the backend, fully azd-supported container build, a single deploy mechanism; but it diverges from MACAE (which deliberately keeps the frontend on App Service) and bakes `VITE_BACKEND_URL` at build time instead of MACAE's runtime `/config`. Viable, but the user chose to match MACAE.
* **Alt-1b — App Service with prebuilt `DOCKER|…` linuxFxVersion (MACAE prebuilt mode).** No build-from-source — contradicts the "build the code on azd up" goal. Rejected.
* **Alt-1c — keep azd's placeholder-swap for the backend (no name+tag params).** Minimal change; but bicep keeps referencing an MCR placeholder, not the named image — does not satisfy the "name+tag, no search in bicep" contract. Rejected in favor of the param-trio.

### Scenario 2 — Operator selects cosmosdb (deploy Search) or postgresql (no Search)

**Requirements:** cosmosdb ⇒ deploy Azure AI Search + KB connection; postgresql ⇒ pgvector only, no Search.

**Preferred Approach:** **No change required.** v2 already implements this correctly (13 verified conditional sites; postgresql skips the Search service, all Search RBAC, the Project↔Search connection, and the search private-DNS zone, and resolves search env/outputs to empty). The only postgresql-path correctness fix is the orchestrator default (A8: `CWYD_ORCHESTRATOR_NAME = databaseType == 'postgresql' ? 'langgraph' : 'agent_framework'`), which is an env-wiring item, not a conditional-deploy gap.

#### Considered Alternatives

* Re-architecting the conditional with MACAE's `isCustom`-style boolean — unnecessary; v2's `databaseType`-keyed `if (...)` is already the canonical idiom.

### Scenario 3 — Post-provision sample-data upload

**Requirements:** after deploy, sample documents are uploaded and ingested so chat grounds out-of-the-box.

**Preferred Approach:** add a **`postdeploy`** hook (currently absent) — run after all three services deploy so the function is live — that (1) uploads the curated sample docs from root `data/` to the `documents` blob container via the deployer credential (idempotent: skip blobs already present), and (2) enqueues them onto `doc-processing` (the same store→`batch_push` path the admin upload uses) so the deployed function ingests → embeds → indexes. Keep the existing `postprovision` index/KB schema seed as-is (it must run before ingestion). Gate the whole step on a curated allow-list of filenames so it is small and deterministic; skip entirely if the index/KB already has documents.

```text
v2/azure.yaml
  + hooks.postdeploy  (posix sh + windows pwsh)  ->  scripts/post-deploy-upload.{sh,ps1} -> upload_sample_data.py
v2/scripts/  (+ upload_sample_data.py: blob upload-batch + queue enqueue, idempotent)
v2/data/sample/  (+ a small curated copy of the grounding docs, or read from root data/ via a manifest)
```

**Implementation Details:** uploading at `postdeploy` (not `postprovision`) is the key correctness point — at `postprovision` the function is not yet deployed, so an enqueue would sit until deploy. MACAE's `index_datasets.py` direct-index approach is an alternative that does not depend on the function, but it bypasses the real ingestion pipeline (parsers, chunking, embeddings) and would diverge from production behavior; prefer the enqueue path.

#### Considered Alternatives

* **Direct index push in the script (MACAE `index_datasets.py` style).** Independent of the function; but re-implements parsing/embedding outside the pipeline and risks index-shape drift. Use only as a fallback if the function ingestion is unreliable at deploy time.
* **`postprovision` upload.** Wrong order — function not deployed yet.

### Scenario 4 — Eliminate the manual-change debt so `azd up` needs zero `az` follow-ups

**Requirements:** every fix currently applied live must live in bicep/host config/azure.yaml.

**Preferred Approach:** a sequenced infra-hardening pass that back-ports A1–A12. Group by file and land one unit per turn (Hard Rule #1), test-first where a bicep what-if or a script test applies:

| # | Item | Durable fix | File |
|---|---|---|---|
| A1 | `AZURE_AI_SERVICES_ENDPOINT` env + UAMI Cognitive Services User on Foundry | add env on backend+function; add role assignment | main.bicep |
| A4 | `AZURE_AI_SEARCH_CONNECTION_NAME` → `cwyd-kb-mcp` | resolve to the RemoteTool conn; create conn + project-MI Search Service Contributor | main.bicep |
| A5 | Event Grid MI queue-sender ordering (chicken-and-egg) | split the subscription out of the system-topic module, `dependsOn` the role (structural, #10) | main.bicep |
| A6 | Function storage firewall blocks Flex deploy | `networkRuleSet.defaultAction=Allow` (no-private-net profile) or resource-instance rule | main.bicep |
| A7 | `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` wrong principal | set to `'id-${solutionSuffix}'` (UAMI) on both runtimes | main.bicep |
| A8 | `ORCHESTRATOR` dead var + wrong pgvector value | rename → `CWYD_ORCHESTRATOR_NAME`, value mode-conditional | main.bicep |
| A9 | `AZURE_ENVIRONMENT=production` | already wired 2026-06-22 — verify in cloud | main.bicep |
| A10 | ACR ARM-auth policy | `policies.azureADAuthenticationAsArmPolicy='enabled'` | container_registry.bicep |
| A11 | ACA missing `registries:` block | add `registries:[{server,identity:UAMI}]` (backend only — frontend is App Service, not a container) | main.bicep |
| A2 | Flex scale-from-zero | `functionAppConfig.scaleAndConcurrency.alwaysReady` (`batch_push`, `blob_event`) | function bicep |
| A3 | Queue `messageEncoding=none` | add to `host.json` or function app settings | host.json / bicep |
| A12 | Frontend never deploys | resolved by Scenario 1 (App Service python-zip; drop the `docker:` block) | azure.yaml + main.bicep |

#### Considered Alternatives

* Leaving the live `az` overrides as a documented runbook — rejected: they revert on every reconcile and re-break `azd up`, which is exactly the user's complaint.

## Selected Approach (summary)

1. **Frontend → App Service python-zip (MACAE-exact)** — drop the unsupported `docker:` block, serve build-from-source via `linuxFxVersion: 'python|3.11'` + `dist: ./dist` + a `prepackage` hook, with the SPA reading the backend URL at runtime from a `/config` endpoint fed by the `BACKEND_API_URL` app setting. **Backend keeps `host: containerapp`** and adopts the MACAE explicit image param-trio so bicep references the built image by name+tag (the "no search in bicep" contract), plus the `registries:` block + ACR ARM-auth policy. Fixes BUG-0081. (Structural — Hard Rule #10.)
2. **Database/Search branch — leave as-is** (already correct); only fix the orchestrator default value (A8).
3. **Add a `postdeploy` sample-data uploader** (upload to `documents` + enqueue to `doc-processing`), idempotent, after services deploy.
4. **Back-port the A1–A12 manual-change debt** into bicep/host config in a sequenced one-unit-per-turn pass, after the user lifts the "bicep edits paused" hold and confirms the Event Grid restructure (A5). Frontend host is settled (App Service python-zip, MACAE-exact).

## Open Decisions for the User (block the implementation plan)

* **D1 — Frontend host:** ✅ DECIDED — **App Service python-zip, matching MACAE exactly** (drop the `docker:` block; `python|3.11` + `dist` + `prepackage` + runtime `/config`). Container App remains a documented alternative (Alt-1a).
* **D2 — Image-reference contract:** adopt the MACAE explicit name+tag param-trio for the **backend** container (matches the request); the frontend has no image (App Service zip). (Hard Rule #10.)
* **D3 — Event Grid restructure (A5):** split the subscription out of the system-topic module. (Hard Rule #10.)
* **D4 — Is the "bicep edits paused by the operator" hold lifted** so the A1–A12 back-port can proceed?
* **D5 — Sample-data source:** curated `v2/data/sample/` copy vs a manifest pointing at root `data/`; and enqueue-via-pipeline (recommended) vs direct-index push.

## Considered Alternatives (cross-cutting, rejected)

* **Mirror MACAE's dual-mode `isCustom` file-swap** (prebuilt default + opt-in build). Rejected: v2's goal is a single always-build `azd up`; the file-swap adds operator ceremony v2 does not want. Borrow MACAE's image-param composition, not its mode-switch.
* **MACAE's runtime `/config` frontend server — ADOPTED** (folded into Scenario 1, no longer rejected). The App Service serves the SPA and exposes `/config` fed by the `BACKEND_API_URL` app setting, decoupling the Vite build from the provisioned backend URL — MACAE's exact pattern, and the cleaner path now that the frontend stays on App Service.
* **Treat the open bugs (BUG-0054/55/58/77/81/82) as the unit of work.** Per the user, the unit is infra parity, not the bug list — though A12=BUG-0081 and several A-items are the durable fixes those bugs already described.
