---
title: CWYD v2 — Cloud Deployment Runbook
description: Step-by-step operator runbook for deploying CWYD v2 code to an existing azd environment (no re-provision). Covers preflight, per-service deploy, lazy Foundry agent bootstrap, and post-deploy smoke verification.
author: CWYD Engineering
ms.date: 2026-06-05
topic: runbook
keywords: deployment, azd, container apps, app service, function app, foundry, smoke test
estimated_reading_time: 10
---

# CWYD v2 — Cloud Deployment Runbook

**Pillar:** Stable Core (process)
**Phase:** 7 (Testing + Documentation)
**Companion to:** [development_plan.md](development_plan.md), [project_status.md](project_status.md), [agents.md](agents.md)

This runbook deploys the current `v2/src/**` code to the existing `<AZD_ENV_NAME>` azd environment **without re-provisioning infrastructure**. All Azure resources are assumed already deployed in resource group `<RESOURCE_GROUP>`.

---

## 1. Resource inventory (existing)

The `<AZD_ENV_NAME>` azd environment in [v2/.azure/<AZD_ENV_NAME>/.env](../.azure/<AZD_ENV_NAME>/.env) binds the three v2 application services to these Azure resources:

| Service | Resource type | Resource name | Endpoint |
|---|---|---|---|
| `backend` | Container App | `ca-backend-<SUFFIX>` | `https://ca-backend-<SUFFIX>.<ACA_ENV_DOMAIN>.<REGION>.azurecontainerapps.io` |
| `frontend` | App Service | `app-frontend-<SUFFIX>` | `https://app-frontend-<SUFFIX>.azurewebsites.net` |
| `function` | Function App | `func-<SUFFIX>` | `https://func-<SUFFIX>.azurewebsites.net` |

Supporting resources (shared with v1 footprint by design; `existing*` Bicep params in [v2/infra/main.bicep](../infra/main.bicep) wire them in):

| Concern | Resource name |
|---|---|
| AI Foundry project | `proj-<SUFFIX>` (account `aisa-<SUFFIX>`) |
| Chat history (Cosmos) | `cosmos-<DATA_SUFFIX>` |
| Vector index (Search) | `srch-<DATA_SUFFIX>` |
| Document storage | `st<DATA_SUFFIX>` (container `documents`, queue `doc-processing`) |
| Event Grid topic | `evgt-<DATA_SUFFIX>` |
| Content Safety | `cs-<SUFFIX>` |
| Speech | `spch-<SUFFIX>` |
| User-Assigned Managed Identity | `id-<SUFFIX>` |

Model deployments on the Foundry account:

| Env var | Deployment |
|---|---|
| `AZURE_OPENAI_GPT_DEPLOYMENT` | `gpt-5.1` |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | `text-embedding-3-large` |
| `AZURE_OPENAI_API_VERSION` | `2025-01-01-preview` |

---

## 2. Preflight gates

Run from a PowerShell prompt at the repo root.

```powershell
# 2.1 Tooling versions
az --version | Select-String '^azure-cli'
azd version
docker --version

# 2.2 Auth
az account show --query "{sub:id, tenant:tenantId, user:user.name}" -o jsonc
# Expect subscription <AZURE_SUBSCRIPTION_ID> and tenant <AZURE_TENANT_ID>.
azd auth login --check-status

# 2.3 Docker daemon up
docker info --format "{{.ServerVersion}} | {{.OperatingSystem}}"

# 2.4 azd env selection
cd v2
azd env list
# Expect <AZD_ENV_NAME> marked DEFAULT=true. If not, run:
#   azd env select <AZD_ENV_NAME>

# 2.5 Env value sanity
azd env get-values | Select-String -Pattern "^(AZURE_RESOURCE_GROUP|AZURE_BACKEND_URL|AZURE_FRONTEND_URL|AZURE_FUNCTION_APP_URL|AZURE_AI_PROJECT_ENDPOINT|AZURE_OPENAI_GPT_DEPLOYMENT)"
```

Local test gates (block on failure):

```powershell
# Backend
cd v2
uv run pytest -q
# Expect: 2047 passed, 1 skipped, 3 deselected

uv run pyright src/backend src/functions
# Expect: 0 errors, 0 warnings, 0 informations

# Frontend
cd src/frontend
npm test -- --run
# Expect: 361 passed, 32 suites
npx tsc --noEmit
npm run lint
# Expect: 0 errors (advisory warnings on react-refresh OK)
```

---

## 3. Deploy

Per-service `azd deploy` is used instead of `azd up` to skip the provision layer entirely. Run from `v2/`.

### 3.1 Backend (Container App)

```powershell
azd deploy backend
```

Builds [v2/docker/Dockerfile.backend](../docker/Dockerfile.backend), pushes to the Bicep-deployed ACR, and updates `ca-backend-<SUFFIX>`. Verify the new revision took traffic:

```powershell
az containerapp revision list -g <RESOURCE_GROUP> -n ca-backend-<SUFFIX> -o table
# Expect the newest revision with TrafficWeight=100 and Active=True.
```

### 3.2 Function App (modular RAG indexing pipeline)

```powershell
azd deploy function
```

Builds [v2/docker/Dockerfile.functions](../docker/Dockerfile.functions). Brings the four Phase 6 blueprints live: `batch_start`, `batch_push`, `add_url`, `search_skill`. Verify:

```powershell
az functionapp function show -g <RESOURCE_GROUP> -n func-<SUFFIX> --function-name batch_push -o tsv --query name
az functionapp function show -g <RESOURCE_GROUP> -n func-<SUFFIX> --function-name add_url -o tsv --query name
```

### 3.3 Frontend (App Service)

```powershell
azd deploy frontend
```

Builds [v2/docker/Dockerfile.frontend](../docker/Dockerfile.frontend) with the `prod` stage. Verify:

```powershell
(Invoke-WebRequest -Uri "https://app-frontend-<SUFFIX>.azurewebsites.net" -UseBasicParsing).StatusCode
# Expect 200.
```

#### 3.3.1 Pinned-tag deploy (operator alternative to `azd deploy frontend`)

Use this path when you need (a) traceable image tags for audit, (b) faster iteration than the full `azd` build, or (c) to recover from a stale `:latest` that masks which build is live. Tag scheme: `cwyd-<UTC_YYYYMMDDHHMM>-<GIT_SHA7>`.

```powershell
# Variables (operator runs from v2/)
$ACR_NAME = "cr<SUFFIX>"
$ACR_LOGIN = "$ACR_NAME.azurecr.io"
$REPO = "chat-with-your-data-v2/frontend-<AZD_ENV_NAME>"
$SHA7 = (git rev-parse --short=7 HEAD)
$STAMP = (Get-Date -AsUTC -Format "yyyyMMddHHmm")
$TAG = "cwyd-$STAMP-$SHA7"
$IMAGE = "$ACR_LOGIN/${REPO}:$TAG"

# Build (linux/amd64 for App Service Linux) and push
az acr login -n $ACR_NAME
docker build --platform linux/amd64 -f docker/Dockerfile.frontend --target prod `
  --build-arg VITE_BACKEND_URL=<AZURE_BACKEND_URL> `
  -t $IMAGE .
docker push $IMAGE

# Pin the new tag onto the site (linuxFxVersion + MI pull creds)
$SITE_ID = "/subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.Web/sites/app-frontend-<SUFFIX>"
az webapp config container set -g <RESOURCE_GROUP> -n app-frontend-<SUFFIX> --container-image-name $IMAGE
az resource update --ids "$SITE_ID/config/web" `
  --set "properties.acrUseManagedIdentityCreds=true" `
        "properties.acrUserManagedIdentityID=<AZURE_UAMI_CLIENT_ID>"
az webapp restart -g <RESOURCE_GROUP> -n app-frontend-<SUFFIX>
```

> **Footgun:** `az webapp config container set` does **not** persist `acrUserManagedIdentityID`. Always follow it with the `az resource update --ids "$SITE_ID/config/web"` form shown above — the `az webapp config container set --identity` shorthand silently drops the value on a subsequent revision.

#### 3.3.2 Prerequisites for managed-identity ACR pull

App Service pulls the image as the site identity. Both must be true:

1. The UAMI (or SMI) holds **AcrPull** on the registry:

   ```powershell
   az role assignment create --assignee-object-id <AZURE_UAMI_PRINCIPAL_ID> `
     --assignee-principal-type ServicePrincipal --role AcrPull `
     --scope "/subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.ContainerRegistry/cr<SUFFIX>"
   ```

2. The registry has **Azure AD authentication as ARM** enabled (default on new ACRs is **disabled** for Basic SKU):

   ```powershell
   az acr config authentication-as-arm update -r cr<SUFFIX> --status enabled
   # Verify:
   az acr show -n cr<SUFFIX> --query "policies.azureAdAuthenticationAsArmPolicy.status" -o tsv
   # Expect: enabled
   ```

   Without this, MI-based pulls fail with `ACRTokenRetrievalFailure -- Unauthorized` even when AcrPull is correctly assigned — App Service exchanges the MI's AAD token for an ACR refresh token via the ARM path, which the policy gates.

---

## 4. Foundry agent bootstrap

Per [agents.md](agents.md), Foundry agent identity is a **runtime concern**. Two built-in agents (`cwyd`, `rai`) self-create on the first chat request that resolves the `agent_framework` orchestrator branch. No manual creation step.

### 4.1 Trigger

```powershell
$body = '{"messages":[{"role":"user","content":"hello"}],"conversation_id":"smoke-bootstrap-001"}'
Invoke-RestMethod -Uri "https://ca-backend-<SUFFIX>.<ACA_ENV_DOMAIN>.<REGION>.azurecontainerapps.io/api/conversation" `
  -Method POST -ContentType "application/json" -Body $body
```

First call takes 3–5 s (Foundry `create_agent` round-trip + Cosmos `upsert_agent_id`). Subsequent calls hit the in-process cache (<1 ms).

### 4.2 Verify

Foundry portal: open project `proj-<SUFFIX>` → **Agents** pane → expect rows `cwyd` (tools: `search`) and `rai` (no tools).

DB-side verification (Cosmos):

```powershell
az cosmosdb sql query `
  -a cosmos-<DATA_SUFFIX> `
  -d db_conversation_history `
  -c conversations `
  --query-text "SELECT c.id, c.agent_id FROM c WHERE c.type = 'agent'"
# Expect two rows: id='cwyd' and id='rai', both with non-null agent_id.
```

### 4.3 Force-recreate (operational only)

```sql
-- Cosmos: delete the row, then restart the Container App to clear the in-process cache.
-- Postgres backend uses the same shape on table `agents`.
```

See [agents.md](agents.md) §4.1 for the full procedure.

---

## 5. Smoke verification matrix

| # | Surface | Command | Expected |
|---|---|---|---|
| 1 | Backend liveness | `Invoke-RestMethod https://ca-backend-<SUFFIX>.<ACA_ENV_DOMAIN>.<REGION>.azurecontainerapps.io/api/health` | `200`, body status `pass` |
| 2 | Backend readiness | `Invoke-RestMethod .../api/health/ready` | `200`, body status ∈ {`pass`, `degraded`} |
| 3 | OpenAPI surface | `Invoke-RestMethod .../openapi.json` | `paths` includes `/api/conversation`, `/api/admin/config`, `/api/admin/documents`, `/api/history/conversations` |
| 4 | Frontend shell | Browser → `https://app-frontend-<SUFFIX>.azurewebsites.net` | React shell loads, no console errors |
| 5 | End-to-end chat | Send "hello" via FE chat box | SSE `reasoning` panel + `answer` content render |
| 6 | Foundry agents present | Foundry portal Agents pane | `cwyd` + `rai` listed |
| 7 | Indexing — blob ingest | Drop a small PDF into Blob container `documents` on `st<DATA_SUFFIX>` | Within ~60 s `GET /api/admin/documents` lists the source with `chunk_count > 0` |
| 8 | Indexing — citation | Ask FE about the uploaded doc | Response includes a `citation` event referencing the source |
| 9 | Function logs healthy | `az functionapp log tail -g <RESOURCE_GROUP> -n func-<SUFFIX>` | One `batch_start` + one `batch_push` per blob, no poison-queue entries |

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `azd deploy backend` fails with `open ...\imgId: The system cannot find the file specified` | Docker BuildKit transient state | `docker buildx prune -f`; restart Docker Desktop; re-run |
| `azd deploy` reports `solutionName` minLength violation | Wrong azd env active (likely a stale or empty env) | `azd env select <AZD_ENV_NAME>` then re-run |
| First chat call returns 500 / no agent created | Cold start exceeded request timeout | Re-issue the request; the agent persists from the first partial run |
| `/api/health/ready` returns `fail` for `foundry` check | Foundry data-plane RBAC missing on `id-<SUFFIX>` | Verify role `Azure AI Developer` on `aisa-<SUFFIX>` for the UAMI |
| Indexing pipeline silent after blob upload | Event Grid subscription on `evgt-<DATA_SUFFIX>` not routed to the function queue | `az eventgrid event-subscription list --source-resource-id <evgt-id>` and verify the `doc-processing` queue is the endpoint |
| Frontend container fails to start with `ACRTokenRetrievalFailure -- Unauthorized` in docker log | Any of: (a) `azureAdAuthenticationAsArmPolicy` disabled on ACR; (b) `acrUserManagedIdentityID` not persisted on site config; (c) AcrPull missing on the chosen identity; (d) legacy `DOCKER_REGISTRY_SERVER_URL/USERNAME/PASSWORD` app settings still present and colliding with MI mode | See §3.3.2 for (a) + (c). For (b) use `az resource update --ids "$SITE_ID/config/web" --set properties.acrUserManagedIdentityID=<AZURE_UAMI_CLIENT_ID>` (the `az webapp config container set` form does not persist it). For (d) `az webapp config appsettings delete -g <RESOURCE_GROUP> -n app-frontend-<SUFFIX> --setting-names DOCKER_REGISTRY_SERVER_URL DOCKER_REGISTRY_SERVER_USERNAME DOCKER_REGISTRY_SERVER_PASSWORD`. Always pin a discrete tag (§3.3.1) rather than `:latest` — `:latest` masks which build is live and blocks root-cause analysis. After multiple consecutive failures, App Service applies a ~2 min cold-start block (`Site is blocked due to multiple, consecutive cold start failures`); wait it out before retrying. |

---

## 7. Re-provision (only if Bicep drift forces it)

When `v2/infra/main.bicep` adds new resources or env keys that the current deployment lacks, the missing features gate off gracefully (defaults disabled). To pick up the deltas without data loss:

```powershell
cd v2
azd provision --no-prompt
# Idempotent: AVM modules + `existing*` reuse params keep existing data resources untouched.
azd deploy --all
```

Otherwise, prefer per-service `azd deploy` for routine code rolls.
