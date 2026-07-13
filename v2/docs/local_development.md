---
title: CWYD v2 — Local Development Against Cloud Resources
description: Operator runbook for running the CWYD v2 backend and Functions host natively on a developer workstation while wiring them to the live cloud data plane (Foundry, Cosmos DB, Azure AI Search, Storage). No emulators, no Azurite — real Azure resources, gated by Managed Identity / az login RBAC.
author: CWYD Engineering
ms.date: 2026-06-11
topic: runbook
keywords: local development, native run, uvicorn, func host start, vite frontend, vs code one-click, compound launch, cosmos, azure ai search, storage public access, rbac, azure cli credential
estimated_reading_time: 14
---

# CWYD v2 — Local Development Against Cloud Resources

**Pillar:** Stable Core (process)
**Phase:** 7 (Testing + Documentation)
**Companion to:** [cloud_deployment.md](cloud_deployment.md), [env-vars.md](env-vars.md), [infrastructure.md](infrastructure.md)

This runbook runs the v2 **backend** (FastAPI/uvicorn) and the v2 **Functions host** (`func host start`) **natively on your workstation**, wired to the **live cloud data plane** — the same Foundry project, Cosmos DB, Azure AI Search index, and Storage account that the deployed services use.

It is the right path when you want to:

* iterate on backend or Functions code with a debugger and hot reload, while reading/writing **real** chat history (Cosmos) and **real** vectors (Search);
* drive the ingestion pipeline (`batch_start` → `batch_push`) end-to-end against cloud Storage and Foundry **without** redeploying;
* reproduce a cloud-only issue locally.

> **Not** the self-contained dev stack. If you want fully local, throwaway dependencies, use the compose stack instead — `docker compose -f v2/docker/docker-compose.dev.yml up` — which bundles its own Postgres/etc. This runbook is the opposite: **local app, cloud data**.

> **No Azurite, no emulators.** Storage, queues, Cosmos, and Search are all the real cloud resources. Local credentials flow through `AzureCliCredential` (your `az login`), so every call is RBAC-gated exactly like production.

---

## Quick start (all three tiers)

> **TL;DR for returning developers.** Do the one-time setup once, then use either the VS Code one-click or three terminals. Sections [§2](#2-prerequisites)–[§10](#10-troubleshooting-quick-reference) explain every step and the cloud-side gotchas in full.

**One-time setup** (skip anything already done):

```powershell
# From the repo root.
cd v2
uv sync                                   # build v2/.venv with backend + functions deps
cd src/frontend; npm install; cd ../..    # frontend deps
az login                                  # local creds resolve to AzureCliCredential
```

Ensure the two **gitignored, already-populated** config files exist (they hold your real cloud endpoints — never copy those values into tracked files):

* `v2/.env` — backend config ([§5.1](#51-v2env-gitignored)). Keep `AZURE_UAMI_CLIENT_ID` empty.
* `v2/src/functions/local.settings.json` — Functions config ([§6.1](#61-v2srcfunctionslocalsettingsjson-gitignored)); isolates onto the `doc-processing-local` queue.

Confirm Storage public access is open for your workstation (one-time, [§4](#4-enable-storage-public-network-access)): `publicNetworkAccess: Enabled`.

### Fast path — VS Code one-click

Run and Debug panel → **`v2: Run all (backend + functions + frontend)`** → ▶. The compound starts all three tiers through their pre-launch tasks (`v2: uv sync`, `v2: func host start`, `v2: frontend dev`).

> The compound's `v2: Attach to Python Functions` step attaches a debugger on port `9091`. If that attach times out, the Functions host itself still runs (its task is independent) — ignore the attach error, or start Functions via the manual path below.

### Manual path — three terminals (from the repo root)

```powershell
# Terminal 1 — backend (FastAPI on :8000). uv run --env-file injects v2/.env into the process env.
cd v2
uv run --env-file .env uvicorn backend.app:app --app-dir src --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 2 — frontend (Vite on :5273; proxies /api to the backend).
cd v2/src/frontend
npm run dev
```

```powershell
# Terminal 3 — Functions host (:7071). Point at v2/.venv + PYTHONPATH, then start.
cd v2
$env:VIRTUAL_ENV = "$PWD\.venv"; $env:PATH = "$PWD\.venv\Scripts;$env:PATH"; $env:PYTHONPATH = "$PWD\src"
cd src/functions
func host start
```

### Verify

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health/ready | ConvertTo-Json -Depth 5   # backend: every check PASS
(Invoke-WebRequest http://localhost:5273/ -UseBasicParsing).StatusCode               # frontend: 200
Invoke-RestMethod http://localhost:7071/api/health                                   # functions: {"status":"ok"}
```

| Tier | URL |
|---|---|
| Backend (FastAPI) | `http://127.0.0.1:8000` |
| Frontend (Vite) | `http://localhost:5273` |
| Functions host | `http://localhost:7071` |

---

## 1. What runs where

| Component | Where it runs | Talks to (cloud) |
|---|---|---|
| Backend API (`backend.app:app`) | local `uvicorn` on `127.0.0.1:8000` | Foundry `proj-<SUFFIX>`, Cosmos `cosmos-<DATA_SUFFIX>`, Search `srch-<DATA_SUFFIX>` |
| Functions host (`batch_start`, `batch_push`, `add_url`, `search_skill`) | local `func host start` on `:7071` | Storage `st<DATA_SUFFIX>`, Foundry (Document Intelligence + embeddings), Search |
| Frontend (optional) | local Vite dev server on `:5273` | the local backend (the Vite dev server proxies `/api` → `127.0.0.1:8000`) |

The deployed Container App / Function App keep running untouched. See [§7](#7-coexisting-with-the-deployed-function-app) for the one place they can collide (the shared Storage queue) and how this runbook isolates around it.

---

## 2. Prerequisites

| Tool | Version used | Check |
|---|---|---|
| Azure CLI | latest | `az version` |
| Azure Functions Core Tools | 4.x | `func --version` |
| uv | 0.11+ | `uv --version` |
| Python | 3.13 | `python --version` |

```powershell
# From repo root: create/refresh the v2 virtualenv with all backend + functions deps.
cd v2
uv sync

# Sign in. Local credentials resolve to AzureCliCredential (see §3).
az login
az account set --subscription <AZURE_SUBSCRIPTION_ID>
az account show --query "{sub:id, tenant:tenantId, user:user.name}" -o jsonc
```

Pull the real resource names/endpoints for your environment from the azd env (never hard-code them in tracked files):

```powershell
azd env get-values | Select-String -Pattern "^(AZURE_RESOURCE_GROUP|AZURE_AI_PROJECT_ENDPOINT|AZURE_AI_SERVICES_ENDPOINT|AZURE_COSMOS_ENDPOINT|AZURE_AI_SEARCH_ENDPOINT|AZURE_STORAGE_ACCOUNT_NAME|AZURE_OPENAI_GPT_DEPLOYMENT|AZURE_OPENAI_EMBEDDING_DEPLOYMENT)"
```

---

## 3. Identity & RBAC

Locally there is **no managed identity** — credentials resolve through the `providers/credentials/` registry to **`AzureCliCredential`**, reusing your `az login` token.

**Keep `AZURE_UAMI_CLIENT_ID` empty** in your local config. When it is set, the credential provider selects `ManagedIdentityCredential`, which does not exist on a workstation and will fail. Empty → `cli` fallback (see [env-vars.md](env-vars.md), Identity section).

Because every call is RBAC-gated, your **user principal** needs the same data-plane roles the deployed UAMI has. Grant them once, scoped to each resource. Resolve your object id with `az ad signed-in-user show --query id -o tsv` and substitute `<AZURE_PRINCIPAL_OBJECT_ID>`.

| Resource | Role | Why |
|---|---|---|
| Storage `st<DATA_SUFFIX>` | **Storage Blob Data Contributor** | read documents, write ingestion metadata |
| Storage `st<DATA_SUFFIX>` | **Storage Queue Data Contributor** | enqueue/dequeue `doc-processing` messages |
| Search `srch-<DATA_SUFFIX>` | **Search Index Data Contributor** | write chunk vectors during ingest |
| Search `srch-<DATA_SUFFIX>` | **Search Service Contributor** | create/inspect the index |
| Cosmos `cosmos-<DATA_SUFFIX>` | **Cosmos DB Built-in Data Contributor** (SQL data-plane role) | chat history read/write |
| AI Services account `aisa-<SUFFIX>` | **Cognitive Services OpenAI User** | chat completions + embeddings |
| AI Services account `aisa-<SUFFIX>` | **Cognitive Services User** | Document Intelligence (`FormRecognizer .../documentmodels:analyze`) during `batch_push` |
| Foundry project `proj-<SUFFIX>` | **Azure AI Developer** | lazy Foundry agent bootstrap |

> **Cognitive Services User is required for ingestion.** `Cognitive Services OpenAI User` only covers OpenAI operations (chat + embeddings). The Document Intelligence "analyze" call in `batch_push` needs the broader **Cognitive Services User** data action `Microsoft.CognitiveServices/accounts/FormRecognizer/documentmodels:analyze/action`. Without it the parse step returns **401 PermissionDenied** even though chat works fine.

Example grant (Cognitive Services User on the AI Services account):

```powershell
az role assignment create `
  --assignee <AZURE_PRINCIPAL_OBJECT_ID> `
  --role "Cognitive Services User" `
  --scope "/subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.CognitiveServices/accounts/aisa-<SUFFIX>"
```

> Cognitive Services **data-plane** RBAC propagation can take a few minutes. If a freshly-granted role still 401s, wait and retry before assuming a config error.

---

## 4. Enable Storage public network access

By default the Storage account may have `publicNetworkAccess: Disabled` (private-endpoint only). From a workstation that returns **403 AuthorizationFailure** — a *network* block, not an RBAC failure. To use the real Storage account from your local machine you must open the public endpoint.

> This is a **shared cloud resource** mutation. Confirm it is acceptable for your environment before running it, and re-lock it when you are done ([§9](#9-teardown)).

Inspect current posture:

```powershell
az storage account show -n st<DATA_SUFFIX> -g <RESOURCE_GROUP> `
  --query "{pna:publicNetworkAccess, default:networkRuleSet.defaultAction, bypass:networkRuleSet.bypass}" -o jsonc
```

Two postures that work for local development:

**Option A — RBAC-gated open endpoint (simplest; matches the Cosmos/Search posture).** Public endpoint reachable, but every request still requires a valid data-plane role. This is consistent with how Cosmos and Search are already exposed.

```powershell
az storage account update -n st<DATA_SUFFIX> -g <RESOURCE_GROUP> `
  --public-network-access Enabled `
  --default-action Allow `
  --bypass AzureServices
```

**Option B — IP-scoped allow-list (tighter, but fiddly).** Public endpoint reachable only from named IPs. Note your **data-plane egress IP** is frequently *not* the IP a "what's my IP" service reports (NAT / IPv6 / corporate egress), so the rule may silently fail to match and you still get 403. If you go this route, add the rule and verify a blob list works; fall back to Option A if it does not.

```powershell
az storage account update -n st<DATA_SUFFIX> -g <RESOURCE_GROUP> `
  --public-network-access Enabled --default-action Deny --bypass AzureServices
az storage account network-rule add -n st<DATA_SUFFIX> -g <RESOURCE_GROUP> --ip-address <YOUR_PUBLIC_IP>
```

Verify reachability (RBAC + network both satisfied):

```powershell
az storage blob list --account-name st<DATA_SUFFIX> --container-name documents --auth-mode login --query "[].name" -o tsv
```

---

## 5. Run the backend

The backend reads config from process env. The Pydantic settings models use `env_prefix` but **no `env_file`**, so the values must be injected — `uv run --env-file` does that from a gitignored `v2/.env`.

### 5.1 `v2/.env` (gitignored)

Copy [v2/.env.sample](../.env.sample) to `v2/.env` and fill in the cloud values from `azd env get-values`. The essentials for local-against-cloud:

```dotenv
# Identity — EMPTY uami id so the credential provider falls back to az login.
AZURE_TENANT_ID=
AZURE_UAMI_CLIENT_ID=

# Foundry
AZURE_AI_PROJECT_ENDPOINT=https://aisa-<SUFFIX>.services.ai.azure.com/api/projects/proj-<SUFFIX>
AZURE_AI_SERVICES_ENDPOINT=https://aisa-<SUFFIX>.cognitiveservices.azure.com/
AZURE_OPENAI_GPT_DEPLOYMENT=gpt-5.1
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_OPENAI_API_VERSION=2025-04-01-preview

# Data plane
AZURE_DB_TYPE=cosmosdb
AZURE_INDEX_STORE=AzureSearch
AZURE_COSMOS_ENDPOINT=https://cosmos-<DATA_SUFFIX>.documents.azure.com:443/
AZURE_COSMOS_DATABASE_NAME=db_conversation_history
AZURE_COSMOS_CONTAINER_NAME=conversations
AZURE_AI_SEARCH_ENDPOINT=https://srch-<DATA_SUFFIX>.search.windows.net
AZURE_AI_SEARCH_INDEX=cwyd-index
AZURE_STORAGE_ACCOUNT_NAME=st<DATA_SUFFIX>
AZURE_DOCUMENTS_CONTAINER=documents
AZURE_LOG_LEVEL=INFO
```

> `v2/.env` is gitignored and may hold real endpoint values on your machine. **Never** copy those real values into any tracked file (docs, ADRs, fixtures). See [adr/0019-no-env-specific-content-in-tracked-files.md](adr/0019-no-env-specific-content-in-tracked-files.md).

### 5.2 Launch

```powershell
cd v2
uv run --env-file .env uvicorn backend.app:app --app-dir src --host 127.0.0.1 --port 8000
```

### 5.3 Verify

```powershell
# Readiness probe: every dependency should report PASS.
Invoke-RestMethod http://127.0.0.1:8000/api/health/ready | ConvertTo-Json -Depth 5

# Chat round-trip (writes history to cloud Cosmos).
$body = '{"messages":[{"role":"user","content":"hello"}]}'
Invoke-WebRequest http://127.0.0.1:8000/api/conversation -Method Post -ContentType 'application/json' -Body $body -SkipHttpErrorCheck
```

`/api/health/ready` should show the Foundry, database (`cosmosdb`), and search (`AzureSearch`) checks all green. Chat citations will be empty until the index is populated ([§6](#6-run-the-functions-host-ingestion)).

---

## 6. Run the Functions host (ingestion)

The Functions host loads `local.settings.json` `Values` as process env vars automatically. This file is **gitignored** (it names your Storage account + endpoints) — create it under `v2/src/functions/`.

### 6.1 `v2/src/functions/local.settings.json` (gitignored)

```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsFeatureFlags": "EnableWorkerIndexing",
    "AzureFunctionsJobHost__extensions__queues__messageEncoding": "none",
    "AzureWebJobsStorage__blobServiceUri": "https://st<DATA_SUFFIX>.blob.core.windows.net",
    "AzureWebJobsStorage__queueServiceUri": "https://st<DATA_SUFFIX>.queue.core.windows.net",
    "AZURE_TENANT_ID": "",
    "AZURE_UAMI_CLIENT_ID": "",
    "AZURE_AI_PROJECT_ENDPOINT": "https://aisa-<SUFFIX>.services.ai.azure.com/api/projects/proj-<SUFFIX>",
    "AZURE_AI_SERVICES_ENDPOINT": "https://aisa-<SUFFIX>.cognitiveservices.azure.com/",
    "AZURE_OPENAI_GPT_DEPLOYMENT": "gpt-5.1",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "text-embedding-3-large",
    "AZURE_OPENAI_API_VERSION": "2025-04-01-preview",
    "AZURE_DB_TYPE": "cosmosdb",
    "AZURE_INDEX_STORE": "AzureSearch",
    "AZURE_AI_SEARCH_ENDPOINT": "https://srch-<DATA_SUFFIX>.search.windows.net",
    "AZURE_AI_SEARCH_INDEX": "cwyd-index",
    "AZURE_STORAGE_ACCOUNT_NAME": "st<DATA_SUFFIX>",
    "AZURE_DOCUMENTS_CONTAINER": "documents",
    "AZURE_DOC_PROCESSING_QUEUE": "doc-processing-local",
    "AZURE_LOG_LEVEL": "INFO"
  }
}
```

Key points:

* **No `AzureWebJobsStorage__accountName` connection string and no `__credential`.** The two `__*ServiceUri` entries plus DefaultAzureCredential (→ your `az login`) are enough for the host's own queue/blob bookkeeping.
* **`messageEncoding: none`** and **`AZURE_DOC_PROCESSING_QUEUE: doc-processing-local`** are the two settings that work around current repo issues — see [§8](#8-known-repo-issues-worked-around-locally).
* **`AZURE_AI_SERVICES_ENDPOINT`** is mandatory for ingestion (Document Intelligence). Without it the parser builds a non-https endpoint and fails.

### 6.2 Launch

Because async/native shells start at the repo root, set the venv + `PYTHONPATH` explicitly and `cd` into the functions folder:

```powershell
$root = (Resolve-Path .).Path  # run from v2/
$env:VIRTUAL_ENV = "$root\.venv"
$env:PATH = "$root\.venv\Scripts;" + $env:PATH
$env:PYTHONPATH = "$root\src"
Set-Location "$root\src\functions"
func host start
```

When indexing completes the host prints the routes (`batch_start`, `add_url`, `search_skill`, `health`) plus `batch_push: queueTrigger`.

### 6.3 Drive the pipeline

```powershell
# Enqueue every blob in the documents container (force_reindex re-processes existing docs).
$body = '{"container_name":"documents","force_reindex":true}'
Invoke-WebRequest http://localhost:7071/api/batch_start -Method Post -ContentType 'application/json' -Body $body -SkipHttpErrorCheck
```

`batch_start` lists the container and enqueues one message per blob. `batch_push` (queue trigger) then runs per message: **download → Document Intelligence parse → embed → push chunks to Search**. Watch the host log for `Executed 'Functions.batch_push' (Succeeded)`.

### 6.4 Verify the index is populated

```powershell
# Document count in the index (should be > 0 after a successful run).
az search query --service-name srch-<DATA_SUFFIX> --index-name cwyd-index --search "*" --query "value | length(@)" 2>$null
```

Then re-run a chat turn against the backend — answers should now include **citations** drawn from the freshly-ingested chunks.

---

## 7. Coexisting with the deployed Function App

The deployed `func-<SUFFIX>` polls the **`doc-processing`** queue (its own `AZURE_DOC_PROCESSING_QUEUE`). If your local host also produced to `doc-processing`, the deployed function would **race you for messages** and process them with its own (possibly stale) config.

This runbook isolates the local run onto a separate queue, **`doc-processing-local`** (set in `local.settings.json`). The `batch_push` trigger binds `%AZURE_DOC_PROCESSING_QUEUE%`, so both the producer (`batch_start`) and the consumer (`batch_push`) move together — your local run is fully isolated and the deployed function never sees your messages.

Create the queue once if it does not exist:

```powershell
az storage queue create --name doc-processing-local --account-name st<DATA_SUFFIX> --auth-mode login
```

---

## 8. Known repo issues worked around locally

This section records genuine repo bugs that also affect the **deployed** Function App, so the local workarounds are understood and the proper fixes are tracked. §8.1–§8.2 are papered over by the local config above; §8.3 is a deployed-app config note; §8.4–§8.5 are now **fixed in code** (kept here so the fixes are not regressed and the deployed app picks them up on its next image build).

### 8.1 Queue message encoding mismatch

* **Symptom:** queue messages go straight to poison within seconds, `batch_push` never executes (failure is at the host binding layer, before any user code).
* **Cause:** the queue producer (Storage Queue SDK v12) sends the message body as **raw UTF-8 text**, but the Functions host's queue trigger **defaults to base64** decoding. Decoding raw JSON (`{...}`) as base64 fails → poison. (The docstring in `batch_start/queue_writer.py` claiming the SDK "base64-encodes the body by default" is incorrect for SDK v12.)
* **Local workaround:** `"AzureFunctionsJobHost__extensions__queues__messageEncoding": "none"` in `local.settings.json`.
* **Proper repo fix (tracked separately):** either set `extensions.queues.messageEncoding: none` in `host.json`, **or** make the producer base64-encode (attach `TextBase64EncodePolicy` to the `QueueClient`). Pick one and apply it consistently to producer + host.

### 8.2 Missing `AZURE_AI_SERVICES_ENDPOINT` on the Function App

* **Symptom:** `batch_push` downloads the blob, then fails at the parse step with `ServiceRequestError: Bearer token authentication is not permitted for non-TLS protected (non-https) URLs`, or a 401 once the endpoint is set but RBAC is missing.
* **Cause:** the Document Intelligence parser reads `settings.foundry.services_endpoint` (env `AZURE_AI_SERVICES_ENDPOINT`). When unset it collapses to `"/"` (non-https). The deployed Function App is also missing this app setting.
* **Local fix:** set `AZURE_AI_SERVICES_ENDPOINT` to the AI Services account endpoint (`https://aisa-<SUFFIX>.cognitiveservices.azure.com/`) **and** grant **Cognitive Services User** ([§3](#3-identity--rbac)).

### 8.3 Stale embedding deployment name (deployed app only)

The deployed Function App was observed with `AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small`, but the actual model deployment on `aisa-<SUFFIX>` is **`text-embedding-3-large`**. The local config uses the correct `-large` name. (Mismatch noted for the deployed app; fix on next deploy.)

### 8.4 Embeddings routed to the project endpoint (fixed in code)

* **Symptom:** `batch_push` downloads + parses + reaches the embed step, then fails with `404 Not Found` from `.../api/projects/<project>/openai/v1/embeddings`.
* **Cause:** `FoundryIQ.embed()` reused the **project-scoped** OpenAI client (correct for chat / agents) for embeddings; the Foundry **project** route exposes no `embeddings` path. It also never passed the `dimensions` parameter, so a `text-embedding-3-large` deployment returns 3072-dim vectors against the 1536-dim `content_vector` index field.
* **Repo fix (applied):** `embed()` now calls a separate `_get_embeddings_client()` that targets the **account** endpoint (`AZURE_AI_SERVICES_ENDPOINT` + `/openai/v1`) and passes `dimensions=settings.openai.embedding_dimensions` (`v2/src/backend/core/providers/llm/foundry_iq.py`).

### 8.5 Invalid Azure Search document key (fixed in code)

* **Symptom:** `batch_push` parses + embeds successfully, then fails the Search push with `(InvalidName) Invalid document key: '<filename>.pdf__0'. Keys can only contain letters, digits, underscore (_), dash (-), or equal sign (=).`
* **Cause:** parsers minted chunk IDs as `f"{source}__{index}"`; when `source` is a filename, the extension dot (`.pdf`) is an illegal Azure Search document-key character.
* **Repo fix (applied):** new Stable-Core helper `BaseParser.make_chunk_id(source, index)` SHA-256-hashes the readable `f"{source}__{index}"` into a key-safe hex digest (mirrors v1's `hashlib` document-key precedent); both the text and Document Intelligence parsers call it. The readable filename survives on `Chunk.source` / the Search `title` field, and the read-side mapping treats `id` as opaque (`v2/src/backend/core/providers/parsers/base.py`).

---

## 9. Teardown

```powershell
# Stop the local processes: Ctrl+C in the uvicorn and func host terminals.

# Re-lock Storage if you opened it for local dev (restore private-only posture).
az storage account update -n st<DATA_SUFFIX> -g <RESOURCE_GROUP> --public-network-access Disabled

# (Optional) remove the local-dev role grants you no longer need, e.g.:
az role assignment delete `
  --assignee <AZURE_PRINCIPAL_OBJECT_ID> `
  --role "Cognitive Services User" `
  --scope "/subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.CognitiveServices/accounts/aisa-<SUFFIX>"
```

Leaving `doc-processing-local` in place is harmless; the deployed function never reads it.

---

## 10. Troubleshooting quick reference

| Symptom | Likely cause | Fix |
|---|---|---|
| `403 AuthorizationFailure` on Storage | public network access disabled | [§4](#4-enable-storage-public-network-access) |
| `403`/`AuthorizationPermissionMismatch` after enabling public access | missing data-plane role | grant the [§3](#3-identity--rbac) role for that resource |
| Chat works, but ingestion parse returns `401 PermissionDenied` | missing **Cognitive Services User** | [§3](#3-identity--rbac) |
| `ManagedIdentityCredential` errors locally | `AZURE_UAMI_CLIENT_ID` is set | leave it empty so the provider falls back to `cli` |
| Queue messages poison instantly, no `batch_push` exec | encoding mismatch | `messageEncoding: none` ([§8.1](#81-queue-message-encoding-mismatch)) |
| `batch_push` fails on parse with non-https URL error | `AZURE_AI_SERVICES_ENDPOINT` unset | [§8.2](#82-missing-azure_ai_services_endpoint-on-the-function-app) |
| Local messages disappear / processed with wrong config | deployed function stole them from `doc-processing` | isolate on `doc-processing-local` ([§7](#7-coexisting-with-the-deployed-function-app)) |
| Freshly-granted role still 401s | RBAC propagation delay | wait a few minutes, retry |
