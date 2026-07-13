# v1 Local Runbook

How to start, stop, and restart the v1 stack locally against the **shared cloud
infrastructure** in `<RESOURCE_GROUP>` (subscription
`<AZURE_SUBSCRIPTION_ID>`).

> v1 lives in `code/`. v2 lives in `v2/`. Never share venvs, ports, or env
> files between the two.

---

## 0. Prerequisites (one-time, already done on this machine)

- Python **3.11.9** on `PATH` (`python --version` → `Python 3.11.9`)
- Node 20+, Docker Desktop, Azure Functions Core Tools v4
- `.venv\` at the repo root, populated with v1 deps
  (`code/backend/requirements.txt`)
- `code/dist/static/` (built React bundle)
- `scripts/load_v1_env.ps1` (gitignored, sources `.azure/<AZD_ENV_NAME>/.env`)
- `az login` as `<AZURE_PRINCIPAL_UPN>`
- RBAC roles on `<RESOURCE_GROUP>` (already granted):
  - **Storage** `st<DATA_SUFFIX>`: Blob Data Owner, Blob Data Contributor,
    Blob Delegator, Queue Data Contributor, Table Data Contributor
  - **OpenAI** `oai-<DATA_SUFFIX>`: Cognitive Services OpenAI User
  - **Doc Intel** `di-<DATA_SUFFIX>`: Cognitive Services User
  - **CogSvc** `cs-<DATA_SUFFIX>`: Cognitive Services User
  - **Search** `srch-<DATA_SUFFIX>`: Search Index Data Contributor + Search
    Service Contributor
  - **Cosmos** `cosmos-<DATA_SUFFIX>`: Cosmos DB Built-in Data Contributor
  - **Key Vault** `kv-<DATA_SUFFIX>`: Key Vault Secrets User
- Public network access **enabled** on Storage + Cosmos (required because the
  laptop is not in the VNet).

---

## 1. Start the stack

Open **four PowerShell terminals at the repo root**
(`C:\workstation\Microsoft\github\chat-with-your-data-solution-accelerator`)
and run one block per terminal **in order**. Each block first ensures
`az login` is fresh, then activates the v1 venv, then loads env vars from
`.azure/<AZD_ENV_NAME>/.env`.

> All four terminals must keep running. Don't close them.

### Sanity check (any terminal)

```powershell
az account show --query "{user:user.name, sub:id}" -o table
# expect: <AZURE_PRINCIPAL_UPN> / <AZURE_SUBSCRIPTION_ID>
# if not: az login
```

### Terminal 1 — Azure Functions host (port 7071)

Hosts the queue trigger `batch_push_results` plus the HTTP endpoints
(`batch_start_processing`, `add_url_embeddings`, etc.). Bound to the
**cloud** storage account via `DefaultAzureCredential`.

```powershell
$env:Path = "$PWD\.venv\Scripts;$env:Path"
. .\scripts\load_v1_env.ps1
cd code\backend\batch
func start --port 7071 --python
```

Wait for: `Host lock lease acquired by instance ID '...'`.

### Terminal 2 — Flask backend (port 5050)

```powershell
$env:Path = "$PWD\.venv\Scripts;$env:Path"
. .\scripts\load_v1_env.ps1
cd code
python -m flask --app app run --host 0.0.0.0 --port 5050
```

Wait for: `Running on http://0.0.0.0:5050`.

### Terminal 3 — Vite dev server (port 5173, proxies `/api` → 5050)

```powershell
cd code\frontend
npm run dev
```

Wait for: `VITE v7.x  ready in ... ms` and `Local: http://localhost:5173/`.

### Terminal 4 — Streamlit admin (port 8501)

> Must be launched from `code\backend\` so the page scripts can resolve
> relative paths (`pages/common.css`, `images/...`).

```powershell
$env:Path = "$PWD\.venv\Scripts;$env:Path"
. .\scripts\load_v1_env.ps1
cd code\backend
streamlit run Admin.py --server.port 8501 --server.headless true
```

Wait for: `Local URL: http://localhost:8501`.

---

## 2. URLs

| Surface | URL |
|---|---|
| Chat (React) | <http://127.0.0.1:5173> |
| Flask API direct | <http://127.0.0.1:5050> |
| Functions host | <http://127.0.0.1:7071> |
| Admin (Streamlit) | <http://127.0.0.1:8501> |

---

## 3. Smoke test

1. Open Streamlit admin → **Ingest Data** → drop a small PDF.
2. Watch **Terminal 1** (Functions). You should see:
   - `Executing 'Functions.batch_push_results' (Reason='New queue message ...)`
   - `prebuilt-layout:analyze ... 202`
   - `text-embedding-3-small ... 200 OK` (multiple)
   - `srch-<DATA_SUFFIX>.search.windows.net ... /docs/search.index ... 200`
3. Open chat at <http://127.0.0.1:5173> and ask a question about the doc.
4. Expect the answer with citations in the side panel.

A quick CLI smoke check (PowerShell):

```powershell
$body = @{
  conversation_id = "smoke-$(Get-Date -Format 'yyyyMMddHHmmss')"
  messages = @(@{ role = "user"; content = "Reply with exactly: pong" })
} | ConvertTo-Json -Depth 5
$resp = Invoke-WebRequest -Uri "http://127.0.0.1:5050/api/conversation" `
  -Method POST -Body $body -ContentType "application/json"
"Status: $($resp.StatusCode)"
$resp.Content
```

Expect `Status: 200`.

---

## 4. Stop the stack

In each terminal: `Ctrl+C` (twice if needed). That's it — there's no Azurite,
no Docker container, no orchestrator to clean up.

If a port stays held:

```powershell
Get-NetTCPConnection -LocalPort 7071,5050,5173,8501 -ErrorAction SilentlyContinue |
  Select-Object LocalPort, OwningProcess |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
```

---

## 5. Restart the stack

Stop (section 4), then start (section 1).

If you only need to bounce one service (e.g., after editing Flask code), just
`Ctrl+C` that terminal and re-run its block.

---

## 6. Tear-down (when fully done with v1)

Restore the cloud network posture and remove dev-only RBAC:

```powershell
$me = "<AZURE_PRINCIPAL_OBJECT_ID>"   # real value: az ad signed-in-user show --query id -o tsv
$st = "/subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.Storage/storageAccounts/st<DATA_SUFFIX>"
$di = "/subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.CognitiveServices/accounts/di-<DATA_SUFFIX>"

az role assignment delete --assignee $me --role "Storage Blob Data Owner"        --scope $st
az role assignment delete --assignee $me --role "Storage Table Data Contributor" --scope $st
az role assignment delete --assignee $me --role "Storage Blob Delegator"          --scope $st
az role assignment delete --assignee $me --role "Cognitive Services User"         --scope $di

az storage account update --name st<DATA_SUFFIX> --resource-group <RESOURCE_GROUP> --public-network-access Disabled
az cosmosdb update         --name cosmos-<DATA_SUFFIX> --resource-group <RESOURCE_GROUP> --public-network-access Disabled
```

Leave the Storage Blob Data Contributor / Queue Data Contributor / Search /
OpenAI / Cosmos / KeyVault role assignments alone — those are needed by the
deployed v1 app + by future v2 work.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `FileNotFoundError: pages/common.css` in Streamlit | Launched Streamlit from `code/` instead of `code/backend/` | Restart Terminal 4 with `cd code\backend` |
| Functions host hangs at boot, blob 403 | Missing **Storage Blob Data Owner** on `st<DATA_SUFFIX>` | See section 0 RBAC list |
| Chat returns 500 with `get_user_delegation_key` failure | Missing **Storage Blob Delegator** | See section 0 RBAC list |
| Cosmos calls return 403 / "Forbidden by firewall" | Public network access **Disabled** | `az cosmosdb update --public-network-access Enabled` |
| Storage calls return 403 with same wording | Public network access **Disabled** | `az storage account update --public-network-access Enabled --default-action Allow` |
| Functions restart loop, lock lease errors | Two Functions hosts pointing at same `azure-webjobs-hosts` (deployed cloud app vs. local) | Stop the cloud Container App / App Service, or change `AzureWebJobsStorage` to a different account in `code/backend/batch/local.settings.json` |
| Empty/garbage answers in chat | Search index empty | Upload via Streamlit admin → wait for Functions logs to show `search.index ... 200` |
| Flask boot fails with `ImportError: cannot import name 'hdrs' from partially initialized module 'aiohttp'` | Corrupted `aiohttp` install in `.venv` (typically caused by killing a Python process mid-pip-op) | `pip install --force-reinstall aiohttp` from repo root with `.venv` activated |

---

## 8. File reference

| File | Purpose |
|---|---|
| `scripts/load_v1_env.ps1` | Sources `.azure/<AZD_ENV_NAME>/.env`, sets `BACKEND_URL=http://localhost:7071`, `FUNCTION_KEY`, `USE_KEY_VAULT=false`, `AZURE_AUTH_TYPE=rbac` |
| `code/backend/batch/local.settings.json` | Functions host config — uses `AzureWebJobsStorage__accountName=st<DATA_SUFFIX>` (RBAC, no key) |
| `.azure/<AZD_ENV_NAME>/.env` | All 84 env vars produced by `azd env get-values` |
| `code/dist/static/` | Built React bundle Flask serves at `/` |
