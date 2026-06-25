<!-- markdownlint-disable-file -->
# Research: CWYD v2 Infrastructure — Current Provisioning + Deployment State

Status: Complete
Date: 2026-06-25
Scope: READ-ONLY survey of c:\workstation\Microsoft\github\cwyd-cdb\v2 — how it provisions + deploys today vs a one-shot `azd up`.
Files reviewed: v2/azure.yaml, v2/infra/main.bicep (~2500 lines), v2/infra/main.parameters.json, v2/scripts/post_provision.py, v2/scripts/prepackage_function.py, v2/docker/Dockerfile.{frontend,backend,functions,ci-validate}, v2/docs/bugs.md (BUG-0051/0052), root data/.

---

## 1. v2/azure.yaml — services + hooks

File: v2/azure.yaml

### infra block (lines 30-33)
```yaml
infra:
  provider: bicep
  path: infra
  module: main
```

### parameters block (typed `azd up` prompts, lines 40-95)
`databaseType` (default `cosmosdb`, allowed `cosmosdb`/`postgresql`), `azureAiServiceLocation` (default `eastus2`), and WAF booleans `enableMonitoring`/`enableScalability`/`enableRedundancy`/`enablePrivateNetworking` (all default `false`).

### services block (lines 104-159)

backend (lines 105-111):
```yaml
  backend:
    project: ./src/backend
    language: py
    host: containerapp
    docker:
      path: ../../docker/Dockerfile.backend
      context: ../..
```
- host = `containerapp`. No `target`. azd builds the image, pushes to the bicep ACR, updates the Container App tagged `azd-service-name: backend`.

frontend (lines 112-125):
```yaml
  frontend:
    project: ./src/frontend
    language: js
    host: appservice
    docker:
      path: ../../docker/Dockerfile.frontend
      context: ../..
      target: prod
      buildArgs:
        - VITE_BACKEND_URL=${AZURE_BACKEND_URL}
```
- **This IS the host: appservice + docker: combination the prompt flagged.** Frontend is an App Service (`kind: 'app,linux,container'`) fed a custom container image. `VITE_BACKEND_URL` is baked at build time from the azd env value `${AZURE_BACKEND_URL}` (a bicep output). `target: prod` selects the prod Dockerfile stage.

function (lines 126-159):
```yaml
  function:
    project: ./build-functions
    language: py
    host: function
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
- host = `function` (Flex Consumption **zip/code deploy** — NO `docker:` block). project points at `./build-functions` (a generated, gitignored staging dir).
- **YES, the function service has a SERVICE-scoped `prepackage` hook** (lines 134-159). It is intentionally service-scoped (not project-scoped) so it also fires on a targeted `azd deploy function` (per the comment, this closed BUG-0058). It shells to v2/scripts/prepackage-function.{sh,ps1} → prepackage_function.py.

### project-level hooks (lines 161-200)
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
- Only `postprovision` is project-scoped. No `postdeploy`, no project-level `prepackage`. `prepackage` is deliberately under `services.function.hooks` instead.

Hooks summary: prepackage (function service-scoped) → builds build-functions/ artifact; postprovision (project-scoped) → post_provision.py. There is NO postdeploy hook and NO sample-data upload hook anywhere.

---

## 2. v2/infra/main.bicep

### 2a. Container image reference — PLACEHOLDER images, not parameterized, not a registry literal

There is NO `SERVICE_*_IMAGE_NAME` parameter, and NO `cwydcontainerreg.azurecr.io/...` literal. Both compute resources are seeded with **public MCR placeholder images** that `azd deploy` swaps post-provision:

- Backend Container App (line 1714):
```bicep
        // Placeholder image. Replaced by `azd deploy` once the real
        // backend Dockerfile ships ...
        image: 'mcr.microsoft.com/k8se/quickstart:latest'
```
- Frontend Web App (line 1971, siteConfig.linuxFxVersion):
```bicep
      // Placeholder image. Replaced by `azd deploy` ...
      linuxFxVersion: 'DOCKER|mcr.microsoft.com/appsvc/staticsite:latest'
```

The real images are built locally by `azd deploy` from the Dockerfiles, pushed to the bicep-provisioned ACR (`cr<suffix>`, module `containerRegistry`, lines ~1676-1700; login server exported as `AZURE_CONTAINER_REGISTRY_ENDPOINT`, line ~2470), and azd updates the resource image via the `azd-service-name` tags (`backend` line ~1700, `frontend` line ~1932, `function` line ~2026). UAMI gets AcrPull (`7f951dda-4ed3-4680-a7ca-43fe172d538d`, line ~1690).

Conclusion: bicep does NOT "reference the built image by name+tag only." It uses the standard azd placeholder pattern (public MCR image at provision, azd swaps to the ACR image at deploy). There is no operator-facing image-name/tag param.

### 2b. databaseType param + Search gating

Declared at lines 84-89:
```bicep
@allowed([
  'cosmosdb'
  'postgresql'
])
@description('Required. Selects BOTH the chat-history backend AND the vector index store. cosmosdb: Cosmos DB + Azure AI Search. postgresql: PostgreSQL Flexible Server with pgvector (Azure AI Search is NOT deployed). Locked at deploy time.')
param databaseType string = 'cosmosdb'
```
- Allowed: `cosmosdb`, `postgresql`. Default: `cosmosdb`. Bound in main.parameters.json via `${AZURE_ENV_DATABASE_TYPE=cosmosdb}`.

Every `databaseType`-keyed conditional (cosmosdb ⇒ Search; postgresql ⇒ pgvector, no Search):

| What | Line | Condition |
|---|---|---|
| Private DNS zone selection (cosmos adds search.windows.net; postgres adds postgres.database.azure.com) | ~360 | `databaseType == 'postgresql' ? postgresModePrivateDnsZones : cosmosModePrivateDnsZones` |
| `aiSearch` module (new Search service) | ~872 | `if (databaseType == 'cosmosdb' && !useExistingSearch)` |
| `existingSearch` reuse + its 3 role assignments | ~960-1010 | `if (databaseType == 'cosmosdb' && useExistingSearch)` |
| Search MI → OpenAI User (Foundry) | ~1030 | `if (databaseType == 'cosmosdb' && !useExistingSearch && !useExistingOpenAi)` |
| Search MI → OpenAI User (reused OAI) | ~1043 | `if (databaseType == 'cosmosdb' && !useExistingSearch && useExistingOpenAi)` |
| `effectiveSearchName` / `effectiveSearchEndpoint` | ~1055-1056 | `databaseType == 'cosmosdb' ? ... : ''` |
| `aiProjectSearchConnection` module (Project↔Search KB connection) | ~1063 | `if (databaseType == 'cosmosdb')` |
| `cosmosDb` module | ~1310 | `if (databaseType == 'cosmosdb' && !useExistingCosmos)` |
| `existingCosmos` reuse (+ db/container/role) | ~1395-1440 | `if (databaseType == 'cosmosdb' && useExistingCosmos)` |
| `postgresServer` module | ~1495 | `if (databaseType == 'postgresql')` |
| `indexStoreValue` var (`AzureSearch` vs `pgvector`) | ~1576 | `databaseType == 'cosmosdb' ? 'AzureSearch' : 'pgvector'` |
| `AZURE_AI_SEARCH_CONNECTION_NAME` backend env | ~1798 | `databaseType == 'cosmosdb' ? aiProjectSearchConnection!.outputs.name : ''` |
| Output `AZURE_AI_SEARCH_ENDPOINT` / `_NAME` | ~2403-2406 | `databaseType == 'cosmosdb' ? ... : ''` |

Conclusion: **The cosmos↔Search conditional is CORRECT.** In postgresql mode the Search service, Search RBAC, the Project↔Search connection, and the search DNS zone are all skipped; pgvector inside Postgres Flexible Server is the index store. Search endpoint/name/connection env + outputs resolve to empty strings. post_provision.py also no-ops the index/KB seed when `AZURE_AI_SEARCH_ENDPOINT` is empty.

### 2c. Env-var wiring — backend Container App + Function App

Backend Container App `env:` array (lines ~1745-1842). PRESENT:
```bicep
        env: union(
          [
            { name: 'AZURE_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
            { name: 'AZURE_UAMI_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
            { name: 'AZURE_TENANT_ID', value: subscription().tenantId }
            { name: 'AZURE_ENVIRONMENT', value: 'production' }
            { name: 'AZURE_AI_PROJECT_ENDPOINT', value: aiProject.outputs.projectEndpoint }
            { name: 'AZURE_OPENAI_ENDPOINT', value: effectiveOpenAiEndpoint }
            { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
            { name: 'AZURE_AI_AGENT_API_VERSION', value: azureAiAgentApiVersion }
            { name: 'AZURE_OPENAI_GPT_DEPLOYMENT', value: gptModelName }
            { name: 'AZURE_OPENAI_REASONING_DEPLOYMENT', value: reasoningModelName }
            { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
            { name: 'AZURE_DB_TYPE', value: databaseType }
            { name: 'AZURE_INDEX_STORE', value: indexStoreValue }
            { name: 'AZURE_COSMOS_ENDPOINT', value: effectiveCosmosEndpoint }
            { name: 'AZURE_AI_SEARCH_ENDPOINT', value: effectiveSearchEndpoint }
            { name: 'AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME', value: searchKnowledgeBaseName }
            { name: 'AZURE_AI_SEARCH_KNOWLEDGE_SOURCE_NAME', value: searchKnowledgeSourceName }
            { name: 'AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION', value: searchKnowledgeBaseApiVersion }
            { name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: databaseType == 'cosmosdb' ? aiProjectSearchConnection!.outputs.name : '' }
            { name: 'AZURE_POSTGRES_ENDPOINT', value: postgresLibpqUri }
            { name: 'AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME', value: databaseType == 'postgresql' ? postgresAdminPrincipalName : '' }
            { name: 'AZURE_SPEECH_SERVICE_NAME', value: speechService.outputs.name }
            { name: 'AZURE_SPEECH_SERVICE_REGION', value: azureAiServiceLocation }
            { name: 'AZURE_SPEECH_ACCOUNT_RESOURCE_ID', value: speechService.outputs.resourceId }
            { name: 'AZURE_CONTENT_SAFETY_ENABLED', value: 'true' }
            { name: 'AZURE_CONTENT_SAFETY_ENDPOINT', value: cogContentSafety.outputs.endpoint }
            { name: 'ORCHESTRATOR', value: 'agent_framework' }
            { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: effectiveStorageName }
            { name: 'AZURE_DOCUMENTS_CONTAINER', value: documentsContainerName }
            { name: 'AZURE_DOC_PROCESSING_QUEUE', value: docProcessingQueueName }
            { name: 'AZURE_INGESTION_TRIGGER', value: ingestionTrigger }
          ],
          enableMonitoring ? [ { name: 'AZURE_APP_INSIGHTS_CONNECTION_STRING', value: applicationInsights!.outputs.connectionString } ] : []
        )
```

Checklist of the env vars the prompt asked about, backend Container App:
| Env var | Backend status |
|---|---|
| AZURE_STORAGE_ACCOUNT_NAME | PRESENT (line ~1819) |
| AZURE_DOCUMENTS_CONTAINER | PRESENT (line ~1820) |
| AZURE_DOC_PROCESSING_QUEUE | PRESENT (line ~1821) |
| AZURE_AI_SERVICES_ENDPOINT | **MISSING** — only emitted as a stack output (line 2359), never on the backend container env |
| AZURE_AI_SEARCH_CONNECTION_NAME | PRESENT (line ~1798, cosmos-gated) |
| CWYD_ORCHESTRATOR_NAME | **MISSING / WRONG NAME** — bicep sets `ORCHESTRATOR=agent_framework` (line 1810), but the backend reads `env_prefix="CWYD_ORCHESTRATOR_"` field `name` (settings.py line 373/389), i.e. it expects `CWYD_ORCHESTRATOR_NAME`. The wired `ORCHESTRATOR` var is ignored; the orchestrator only defaults to agent_framework because that is the field default `OrchestratorName.AGENT_FRAMEWORK`. |
| AZURE_ENVIRONMENT | PRESENT (line ~1738, hardcoded `'production'`) |
| AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME | PRESENT (line ~1799, postgres-gated) |

Function App `siteConfig.appSettings` (lines ~2078-2130). PRESENT:
`AzureWebJobsStorage__accountName`/`__credential`/`__clientId`, `FUNCTIONS_EXTENSION_VERSION`, `AZURE_CLIENT_ID`, `AZURE_UAMI_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_ENVIRONMENT=production`, `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`, `AZURE_DB_TYPE`, `AZURE_INDEX_STORE`, `AZURE_COSMOS_ENDPOINT`, `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_POSTGRES_ENDPOINT`, `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME`, `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_DOCUMENTS_CONTAINER`, `AZURE_DOC_PROCESSING_QUEUE`, plus monitoring `APPLICATIONINSIGHTS_CONNECTION_STRING`.

Checklist, Function App:
| Env var | Function status |
|---|---|
| AZURE_STORAGE_ACCOUNT_NAME / _DOCUMENTS_CONTAINER / _DOC_PROCESSING_QUEUE | PRESENT (lines ~2127-2129) |
| AZURE_AI_SERVICES_ENDPOINT | **MISSING** — function does parsing (DocumentIntelligence builds its client from `AZURE_AI_SERVICES_ENDPOINT`); this is the BUG-0034/0052 endpoint and it is NOT on the function env either |
| AZURE_AI_SEARCH_CONNECTION_NAME | MISSING (function does not need the KB connection; pushes vectors directly — acceptable) |
| CWYD_ORCHESTRATOR_NAME | N/A (function has no orchestrator) |
| AZURE_ENVIRONMENT | PRESENT (line ~2098) |
| AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME | PRESENT (line ~2113) |

Key gap: **`AZURE_AI_SERVICES_ENDPOINT` is wired onto NEITHER runtime** (backend or function), despite being required by DocumentIntelligence/Content Understanding parsing. bugs.md BUG-0052 says it was fixed live (`az` set on both runtimes) and a "durable bicep back-port" was to land — but the current main.bicep does NOT contain `AZURE_AI_SERVICES_ENDPOINT` in either env block. The durable back-port regressed / never landed.

### 2d. UAMI role assignments present

Single shared User-Assigned Managed Identity `id-<suffix>` (module `userAssignedIdentity`, line ~290). All workloads use it. Role assignments in the new-resource (non-reuse) path:

| Role (GUID) | Assignee | Scope (resource) | Line |
|---|---|---|---|
| Monitoring Metrics Publisher | UAMI | Application Insights | ~316 (if enableMonitoring) |
| Cognitive Services OpenAI User (`5e0bd9bd…`) | UAMI | AI Services (Foundry) account | ~595 |
| Azure AI User (`53ca6127…`) | UAMI | AI Services (Foundry) account | ~600 |
| Cognitive Services Speech User (`f2dc8367…`) | UAMI | Speech account | ~770 |
| Cognitive Services User (`a97b65f3…`) | UAMI | **Content Safety account ONLY** (line 847) | ~845 |
| Search Index Data Contributor (`8ebe5a00…`) | UAMI | Search service | ~905 (cosmos) |
| Search Service Contributor (`7ca78c08…`) | UAMI | Search service | ~910 (cosmos) |
| Search Index Data Reader (`1407120a…`) | Foundry Project MI | Search service | ~915 (cosmos) |
| Cognitive Services OpenAI User (`5e0bd9bd…`) | Search system MI | Foundry account | ~1033 (cosmos) |
| Storage Blob Data Contributor (`ba92f5b4…`) | UAMI | Storage account | ~1117 |
| Storage Queue Data Contributor (`974c5e8b…`) | UAMI | Storage account | ~1122 |
| Storage Account Contributor (`17d1049b…`) | UAMI | Storage account | ~1127 |
| Cosmos DB Built-in Data Contributor (`00000002`) | UAMI | Cosmos account (data-plane) | ~1355 (cosmos) |
| AcrPull (`7f951dda…`) | UAMI | Container Registry | ~1690 |
| Storage Blob Data Owner (`b7e6dc6d…`, `flexDeploymentRole`) | UAMI | Storage account | ~2155 |
| Storage Queue Data Message Sender (`c6a89b2d…`) | Event Grid system topic MI | Storage account | ~2230 (if !useExistingEventGridTopic) |

Missing / notable RBAC gaps vs the prompt's checklist:
- **Cognitive Services User on the AI Services (Foundry) account — MISSING.** `a97b65f3…` is granted ONLY on the Content Safety account (line 847), NOT on the `aiServices` Foundry account. DocumentIntelligence + Content Understanding run against `<account>.services.ai.azure.com/...` on the Foundry account and need this role. bugs.md BUG-0052 explicitly granted it live + flagged a durable back-port; the back-port is absent in current bicep. The Foundry account UAMI roles are only OpenAI User + Azure AI User. **This is a confirmed RBAC gap.**
- Search Service Contributor on the search service — PRESENT (not missing).
- Storage roles on the backend identity — PRESENT (Blob Data Contributor + Queue Data Contributor + Account Contributor + Blob Data Owner via flexDeploymentRole). Not missing.

---

## 3. v2/scripts/

### post_provision.py (v2/scripts/post_provision.py, ~520 lines)
Wired from azure.yaml project-level `postprovision` hook via post-provision.{sh,ps1}. Idempotent. Does three things, gated on env:
1. `_enable_pgvector()` (lines ~140-210) — postgresql mode only: connects to Postgres Flexible Server with the deployer's Entra token and runs `CREATE EXTENSION IF NOT EXISTS vector`. Has a private-networking pre-flight that prints a Bastion-tunnel command and exits if the host is in the private DNS zone.
2. `_ensure_search_index()` (lines ~230-330) — cosmosdb mode only (no-op if `AZURE_AI_SEARCH_ENDPOINT` empty): creates the `cwyd-index` Search index (id/content/title/url/content_vector + HNSW vector profile + `default` semantic config) if missing.
3. `_ensure_knowledge_base()` (lines ~340-510) — cosmosdb mode only: PUTs a Foundry IQ `searchIndex` knowledge source (`cwyd-index-ks`) then a knowledge base (`cwyd-kb`) referencing the chat model for query planning, via the Search data-plane REST endpoints.
Then `_print_summary()` prints the AZURE_* outputs.

**post_provision.py does NOT upload any sample data.** It seeds the Search index + Foundry IQ KB (schema only, no documents) and enables pgvector. It does NOT grant any roles (RBAC is entirely in bicep). It does NOT push documents into the `documents` blob container.

### prepackage_function.py (v2/scripts/prepackage_function.py, ~190 lines)
Wired from azure.yaml `services.function.hooks.prepackage` via prepackage-function.{sh,ps1}. Regenerates the gitignored `v2/build-functions/` deploy artifact from scratch on every run:
- copies `function_app.py` + `host.json` to the build root;
- copies the function subpackages (`add_url`, `batch_push`, `batch_start`, `blob_event`, `search_skill`, `core`) under `build-functions/functions/` with a marker `__init__.py` so `from functions.<sub>...` resolves at the Functions deploy root;
- copies `v2/src/backend/` to `build-functions/backend/` so `from backend.core...` resolves;
- generates `requirements.txt` from `v2/pyproject.toml` `[project].dependencies` and emits `.funcignore`.
It does NOT touch infra, RBAC, or data.

### Sample data location
There is **no v2/data/ folder** (file_search returned nothing). Sample documents live in the **root** data/ folder (v1 assets): Benefit_Options.pdf, employee_handbook.pdf, MSFT_FY23Q4_10K.docx, Northwind_Health_Plus/Standard_Benefits_Details.pdf, PerksPlus.pdf, role_library.pdf, PressReleaseFY23Q4.docx, multiple Woodgrove insurance/mortgage PDFs, plus contract_data/ and sample_code/. **No v2 script or hook uploads any of these to the documents container** — sample-data seeding is entirely absent from the v2 azd flow.

---

## 4. v2/docker/

| Dockerfile | Used by | Stages / target | Notes |
|---|---|---|---|
| Dockerfile.frontend | azd `services.frontend` (`target: prod`) + compose | `dev` (Vite HMR :5173) / `build` (npm run build → /dist) / `prod` (Python 3.11 + uvicorn serving /dist on :80) | Prod is a Python/uvicorn static-file server (NOT nginx, despite the bicep comment). `VITE_BACKEND_URL` is baked at build: `build` stage has `ARG VITE_BACKEND_URL=""` → `ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}` → `RUN npm run build`. The ARG is fed by azure.yaml `buildArgs: VITE_BACKEND_URL=${AZURE_BACKEND_URL}`. |
| Dockerfile.backend | azd `services.backend` + compose | single stage (Python 3.11 + uv) | `CMD uvicorn backend.app:app --port 8000`. No multi-stage target. |
| Dockerfile.functions | docker-compose.dev / .smoke ONLY | single stage (mcr azure-functions/python:4-python3.11) | NOT used by `azd deploy` — the function service has no `docker:` block; it is a Flex Consumption zip deploy of build-functions/. This image copies src/functions + src/backend into wwwroot for local runs. |
| Dockerfile.ci-validate | CI (`docker build -f ... -t cwyd-ci .`) | python:3.11-slim + azure-cli + node20 + bicep | Runs bicep build/what-if, pytest, frontend tests, lints. Not a deploy artifact. |

VITE_BACKEND_URL flow end-to-end: bicep emits `AZURE_BACKEND_URL` output (`https://<backend-aca-fqdn>`, line ~2460) → azd persists it in the env → azure.yaml `buildArgs` passes `VITE_BACKEND_URL=${AZURE_BACKEND_URL}` → Dockerfile build stage bakes it into the static bundle. The frontend Web App also sets a parity-only `VITE_BACKEND_URL` appSetting (bicep line ~2005) that the running container does NOT read (the SPA is fully static once built).

---

## 5. GAPS vs a working one-shot `azd up`

Goal restated: one `azd up` provisions infra + builds & deploys frontend/backend/function from source; operator picks cosmosdb (also deploy AI Search) or postgresql (no Search); a post-provision script uploads sample data; bicep references the built image by name+tag only.

| Concern | Current state | Gap vs goal |
|---|---|---|
| Image build/reference | Bicep seeds public MCR **placeholder** images (`mcr.microsoft.com/k8se/quickstart:latest`, `DOCKER|mcr.microsoft.com/appsvc/staticsite:latest`); `azd deploy` builds from Dockerfiles, pushes to bicep ACR, swaps the image via `azd-service-name` tags. | Works via azd's placeholder-swap pattern, but bicep does NOT reference the built image by name+tag — it references a throwaway public image. There is no `SERVICE_*_IMAGE_NAME` param. If the goal is "bicep references the built image by name+tag only," that contract is not implemented (no parameterized image name). |
| Frontend host type | `host: appservice` + `docker:` (custom container on App Service, `kind: app,linux,container`). | This is the App-Service-+-container combination the prompt flagged as known-broken/finicky under azd. Container Apps (as the backend uses) is the more reliable azd container target. Frontend container deploy to App Service is the highest-risk service in a one-shot `azd up`. |
| Conditional Search | databaseType gating is correct: cosmosdb ⇒ Search + KB connection + search DNS; postgresql ⇒ pgvector, Search fully skipped, search env/outputs empty. | **No gap.** Correct in both directions. |
| Env wiring | Storage/queue, DB routing, Foundry/OpenAI endpoints, KB, Speech, Content Safety, AZURE_ENVIRONMENT, postgres admin all wired on both runtimes. | Two gaps: (1) **`AZURE_AI_SERVICES_ENDPOINT` is on NEITHER backend nor function env** (only a stack output) — DocumentIntelligence parsing fails without it (BUG-0034/0052 durable back-port absent). (2) **Orchestrator env name mismatch** — bicep sets `ORCHESTRATOR=…` but the backend reads `CWYD_ORCHESTRATOR_NAME`; the set var is ignored (default still selects agent_framework, so it works by accident, but the var is dead). |
| RBAC | UAMI has OpenAI User + Azure AI User on Foundry; Speech User; Cognitive Services User on Content Safety; full Search (Index Data Contributor + Service Contributor) cosmos-gated; full Storage (Blob/Queue Contributor + Account Contributor + Blob Data Owner); Cosmos data contributor; AcrPull; Event Grid queue sender. | **Gap: Cognitive Services User (`a97b65f3…`) is NOT granted on the AI Services (Foundry) account** — only on Content Safety. DocumentIntelligence/Content Understanding parsing on the Foundry account needs it (BUG-0052 live fix; durable bicep back-port absent). |
| Post-provision data upload | post_provision.py enables pgvector, seeds the Search index schema, and seeds the Foundry IQ KB. | **Gap: no sample-data upload exists.** Nothing copies the root data/ documents into the `documents` blob container, so a fresh `azd up` yields an empty index/KB and the chat has nothing to ground on until the operator manually uploads via the admin UI. There is no v2/data/ source folder either. |

### One-shot `azd up` readiness — net assessment
- Provisioning + build/deploy of 3 services via one `azd up`: wired (services + prepackage hook + ACR + placeholder-swap), modulo the frontend appservice-container risk.
- Database/Search branch: correct.
- Three concrete blockers to a clean grounded experience out of the box:
  1. `AZURE_AI_SERVICES_ENDPOINT` not on backend/function env (parsing breaks).
  2. Cognitive Services User not granted on the Foundry account (DI auth breaks).
  3. No sample-data upload step (empty index after deploy).
- One cosmetic correctness issue: `ORCHESTRATOR` vs `CWYD_ORCHESTRATOR_NAME` env-name mismatch (currently masked by the default).

---

## Clarifying questions
None blocking. (If the intended contract really is "bicep references the built image by name+tag only," confirm whether the design should move to an azd `SERVICE_*_IMAGE_NAME` parameter pattern or keep the current placeholder-swap pattern — they are mutually exclusive choices.)

## Recommended follow-on research (not done here)
- [ ] Confirm whether `AZURE_AI_SERVICES_ENDPOINT` is currently set live on the deployed runtimes (azd env / az) vs only the bicep gap — bugs.md says it was set live but bicep regressed.
- [ ] Read v2/src/backend/core/settings.py FoundrySettings to confirm the exact env name (`AZURE_AI_SERVICES_ENDPOINT`) and FoundrySettings.services_endpoint default behavior.
- [ ] Check v2/docs/development_plan.md §0.1 debt queue for any open row tracking the BUG-0052 durable bicep back-port (env var + Cognitive Services User on Foundry).
- [ ] Inspect whether docker-compose / a Makefile target already has a sample-data upload helper that could be promoted into a postprovision/postdeploy hook.
- [ ] Verify azd behavior for `host: appservice` + `docker:` in the pinned azd version (`>= 1.18.0 != 1.23.9`) to quantify the frontend deploy risk.
