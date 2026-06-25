<!-- markdownlint-disable-file -->

# Research: MACAE KB MCP Foundry Project connection — post-deploy seeding pattern

Status: Complete
Date: 2026-06-25
Scope: read-only investigation of the MACAE sample copied at data/sample_code/macae/ plus CWYD v2 post-deploy machinery for replication fit.

---

## TL;DR — the mechanism

MACAE creates **one Foundry Project connection per knowledge base** at **post-deploy**, named `{kb_name}-mcp`, via a **PUT to the ARM management plane**:

```
PUT https://management.azure.com{projectResourceId}/connections/{kb_name}-mcp?api-version=2025-04-01-preview
```

with a `RemoteTool` / `ProjectManagedIdentity` payload (`audience: https://search.azure.com`). The script is `infra/scripts/post-provision/seed_kb_connections.py`. It is **not** auto-run by the azd `postdeploy` hook — that hook only prints a banner telling the operator to run `post_deploy.sh` / `post_deploy.ps1` manually. Those wrappers create a venv, `pip install -r requirements.txt`, export endpoints from `azd env get-value`, then run `seed_knowledge_bases.py` followed by `seed_kb_connections.py` (both filtered with `--only <csv>`).

The base `CognitiveSearch` / `AAD` connection IS created in Bicep; the per-KB `RemoteTool` connections are created ONLY by the script (confirmed — both exist).

---

## 1. The seeding script — `seed_kb_connections.py`

Path: data/sample_code/macae/infra/scripts/post-provision/seed_kb_connections.py (≈230 lines, read fully)

### 1a. The exact PUT payload (lines 119–150)

```python
# ARM endpoint for connections:
# PUT https://management.azure.com{resource_id}/connections/{name}?api-version=2025-04-01-preview
arm_url = f"https://management.azure.com{resource_id}/connections/{connection_name}?api-version=2025-04-01-preview"

body = {
    "properties": {
        "category": "RemoteTool",
        "target": target_url,
        "authType": "ProjectManagedIdentity",
        "useWorkspaceManagedIdentity": True,
        "isSharedToAll": True,
        "audience": "https://search.azure.com",
        "metadata": {
            "ApiType": "Azure",
        },
    }
}

headers = _get_management_headers(credential)
resp = httpx.put(arm_url, json=body, headers=headers, timeout=30)
if resp.status_code in (200, 201):
    return True
elif resp.status_code == 409:
    # Already exists — treat as success
    return True
else:
    print(f"  ✗ Failed ({resp.status_code}): {resp.text[:300]}")
    return False
```

Field-by-field:

| Field | Value |
| --- | --- |
| connection name | `f"{kb_name}-mcp"` (line ~205) |
| `category` | `RemoteTool` |
| `target` | `f"{SEARCH_ENDPOINT}/knowledgebases/{kb_name}/mcp?api-version={KB_API_VERSION}"` where `KB_API_VERSION = "2025-11-01-preview"` (line ~46, ~206) |
| `authType` | `ProjectManagedIdentity` |
| `useWorkspaceManagedIdentity` | `True` |
| `isSharedToAll` | `True` |
| `audience` | `https://search.azure.com` |
| `metadata` | `{ "ApiType": "Azure" }` |
| connection PUT api-version | `2025-04-01-preview` |

Note two distinct api-versions:
- The **connection resource** PUT uses `2025-04-01-preview` (matches bugs.md).
- The **target URL** embeds `2025-11-01-preview` (the KB MCP data-plane version). bugs.md referenced `2025-05-01-preview` for the KB itself — the live sample now uses `2025-11-01-preview` for both the KB and the MCP target (see `seed_knowledge_bases.py` line ~58 `KB_API_VERSION = "2025-11-01-preview"`).

Target URL shape (the `mcp` path is the KB MCP endpoint):
```
https://<search>.search.windows.net/knowledgebases/{kb_name}/mcp?api-version=2025-11-01-preview
```

### 1b. Authentication (control plane)

`DefaultAzureCredential` throughout (line ~24, instantiated in `main()` line ~170).

- The **connection PUT** uses an ARM token (lines 84–90):
  ```python
  def _get_management_headers(credential):
      token = credential.get_token("https://management.azure.com/.default")
      return {"Content-Type": "application/json", "Authorization": f"Bearer {token.token}"}
  ```
- The **project-resource-ID discovery** GET uses a Cognitive Services token (lines 100–113):
  ```python
  def _discover_project_resource_id(credential):
      token = credential.get_token("https://cognitiveservices.azure.com/.default")
      headers = {"Authorization": f"Bearer {token.token}", "Content-Type": "application/json"}
      url = f"{PROJECT_ENDPOINT}?api-version=2024-07-01-preview"
      resp = httpx.get(url, headers=headers, timeout=30)
      if resp.status_code == 200:
          return resp.json().get("id", "")
      return ""
  ```
- The caller (signed-in user during manual run) needs the **Azure AI User / "Foundry User"** role on the Foundry account. The bash wrapper assigns it explicitly (role-def GUID `53ca6127-db72-4b80-b1b0-d745d6d5456d`) and then sleeps 60s for propagation — see `ensure_role_assignments_for_kbmcp()` in post_deploy.sh (lines ~386–417). The script docstring says "caller needs Contributor on the AI project."

### 1c. How it discovers the KB names

`seed_kb_connections.py` imports the KB name set from its sibling `seed_knowledge_bases.py` (lines 42–60):

```python
try:
    from seed_knowledge_bases import KNOWLEDGE_BASES
    KB_NAMES = list(KNOWLEDGE_BASES.keys())
except ImportError:
    KB_NAMES = [
        "macae-retail-customer-kb", "macae-retail-orders-kb",
        "macae-content-gen-products-kb",
        "macae-contract-summary-kb", "macae-contract-risk-kb", "macae-contract-compliance-kb",
        "macae-rfp-summary-kb", "macae-rfp-risk-kb", "macae-rfp-compliance-kb",
    ]
```

`KNOWLEDGE_BASES` is a hardcoded `dict` literal in `seed_knowledge_bases.py` (line ~66+) — KB names are static per content pack, NOT discovered from Azure. A `--only kb1,kb2` CLI filter (parsed by `_parse_only_filter()`, lines 153–162) narrows the set; the wrapper passes the per-use-case CSV (see §2c `kb_map`).

### 1d. How it discovers the project / search endpoint

Two env vars, loaded from `src/backend/.env` with `override=False` (so wrapper-exported env wins) (lines 27–40):

```python
_backend_env = Path(__file__).parent.parent.parent.parent / "src" / "backend" / ".env"
load_dotenv(str(_backend_env), override=False)

SEARCH_ENDPOINT = os.environ.get("AZURE_AI_SEARCH_ENDPOINT", "").rstrip("/")
PROJECT_ENDPOINT = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "").rstrip("/")
```

The **project ARM resource ID** is NOT passed in — it is discovered at runtime (lines 172–195):
1. data-plane GET `{PROJECT_ENDPOINT}?api-version=2024-07-01-preview` → read `.id`.
2. Fallback: instantiate `AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=...)`, list connections, and parse the project resource ID by stripping the `/connections/...` suffix off any existing connection's `.id`.
3. If both fail → `sys.exit(1)`.

(`PROJECT_ENDPOINT` example shape in the comments: `https://aif-<SUFFIX>.services.ai.azure.com/api/projects/proj-<SUFFIX>`.)

### 1e. Idempotency

PUT (not POST) → create-or-update. `200`/`201`/`409` all treated as success (lines 143–150). Safe to re-run.

---

## 2. Deploy-time invocation

### 2a. The azd hook is a BANNER ONLY

data/sample_code/macae/azure.yaml `hooks.postdeploy` (lines 7–73) — and the identical block in data/sample_code/macae/azure_custom.yaml (lines 46–104) — does **not** run the seeder. It prints colored instructions:

```yaml
hooks:
  postdeploy:
    windows:
      run: |
        # ... Write-Host banner ...
        #   👉 infra\scripts\post-provision\post_deploy.ps1
      shell: pwsh
      interactive: true
    posix:
      run: |
        # ... printf banner ...
        #   👉 bash infra/scripts/post-provision/post_deploy.sh
      shell: sh
      interactive: true
```

So the actual seeding is an **operator-run manual step** after `azd up`. (The `post_deploy.sh` epilogue even suggests `azd hooks run postdeploy` to re-show the banner, plus the direct `bash ./infra/scripts/post-provision/post_deploy.sh` command.)

### 2b. The wrapper that actually calls the seeder

`post_deploy.sh` / `post_deploy.ps1` (the "real" post-deploy driver) →
- `post_deploy.ps1` mirrors `Selecting-Team-Config-And-Data.ps1`, which is the legacy driver that contains the explicit `Start-Process` call (data/sample_code/macae/infra/scripts/post-provision/Selecting-Team-Config-And-Data.ps1 lines 911–918):
  ```powershell
  # Create RemoteTool MCP connections in Foundry for each KB
  Write-Host "`nCreating KB MCP connections in Foundry..."
  $process = Start-Process -FilePath $pythonCmd -ArgumentList "infra/scripts/post-provision/seed_kb_connections.py" -Wait -NoNewWindow -PassThru
  if ($process.ExitCode -ne 0) {
      Write-Host "Warning: KB MCP connection provisioning failed. You can run 'python infra/scripts/post-provision/seed_kb_connections.py' manually after deployment."
  } else {
      Write-Host "KB MCP connections created successfully."
  }
  ```
- The modern bash driver `post_deploy.sh` calls it via the `run_python` helper (lines 380–384 + the seeding block lines 855–873):
  ```bash
  run_python() {
    local module="$1"; shift
    "$python_cmd" "$REPO_ROOT/$module" "$@"
  }
  # ...
  info "── Seeding Foundry IQ Knowledge Bases ──"
  run_python "scripts/post-provision/seed_knowledge_bases.py" "--only" "$selected_kbs"
  # ...
  info "── Creating KB MCP RemoteTool connections ──"
  run_python "scripts/post-provision/seed_kb_connections.py" "--only" "$selected_kbs"
  ```
  Note the **ordering**: KBs are seeded first, then connections (connections target the KB MCP endpoint, so the KB must exist).

### 2c. Working dir, venv, deps install

`post_deploy.sh` `activate_python_env()` (lines 599–642):
- picks a runnable `python3`/`python`,
- creates a venv at `$SCRIPT_DIR/scriptenv` (i.e. `infra/scripts/post-provision/scriptenv`) if absent,
- activates it,
- `pip install --quiet -r "$SCRIPT_DIR/requirements.txt"`.

`run_python` invokes `"$python_cmd" "$REPO_ROOT/<module>"` — so **cwd = repo root** and the module path is repo-root-relative. (`REPO_ROOT` = two levels up from `infra/scripts/post-provision`.)

### 2d. Per-use-case KB filter (the `--only` CSV)

post_deploy.sh lines 832–841:
```bash
declare -A kb_map
kb_map[1]="macae-rfp-summary-kb,macae-rfp-risk-kb,macae-rfp-compliance-kb"
kb_map[2]="macae-retail-customer-kb,macae-retail-orders-kb"
kb_map[5]="macae-contract-summary-kb,macae-contract-risk-kb,macae-contract-compliance-kb"
kb_map[6]="macae-content-gen-products-kb"
kb_map[7]="<all nine kb names>"
```
The selected CSV is passed as `--only` to both `seed_knowledge_bases.py` and `seed_kb_connections.py`.

---

## 3. Environment variables the hook/script read

| Env var | Read by | Source (post_deploy.sh) |
| --- | --- | --- |
| `AZURE_AI_SEARCH_ENDPOINT` | seed_kb_connections.py, seed_knowledge_bases.py | `export`ed from `$ai_search_endpoint`; that comes from `azd env get-value AZURE_SEARCH_ENDPOINT` (fallback `AZURE_AI_SEARCH_ENDPOINT`), else deployment outputs, else `https://$ai_search.search.windows.net` naming-convention fallback (lines 261–263, 750–754) |
| `AZURE_AI_PROJECT_ENDPOINT` | seed_kb_connections.py | `export`ed from `$project_endpoint` = `azd env get-value AZURE_AI_PROJECT_ENDPOINT` (fallback `AZURE_AI_AGENT_ENDPOINT`), else deployment output `azureAiProjectEndpoint` (lines 266–268, 744–748) |
| `AZURE_OPENAI_ENDPOINT` | seed_knowledge_bases.py (KB reasoning model) | `azd env get-value AZURE_OPENAI_ENDPOINT` (lines 265, 756–760) |

Other resource names the wrapper resolves (for blob upload / indexing / WAF toggling, not directly by the connection seeder): `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_AI_SEARCH_NAME`, `AZURE_RESOURCE_GROUP`, `AZURE_SUBSCRIPTION_ID`, `AI_FOUNDRY_RESOURCE_ID`, `AZURE_EXISTING_AI_PROJECT_RESOURCE_ID`, `BACKEND_URL`, `webSiteDefaultHostname`.

Resolution is a **3-tier fallback** (post_deploy.ps1 synopsis lines 10–13): (1) `azd env get-value` → (2) ARM deployment outputs → (3) resource naming convention from `SolutionSuffix` tag. The endpoints originate as **Bicep outputs** surfaced into the azd env.

The script itself also reads `src/backend/.env` (via `load_dotenv(..., override=False)`) as a developer-convenience fallback when run standalone.

---

## 4. Python deps for the script

Shipped requirements file: data/sample_code/macae/infra/scripts/post-provision/requirements.txt
```
azure-search-documents==11.5.3
azure-identity==1.24.0
azure-storage-blob==12.26.0
azure-cosmos==4.9.0
aiohttp
requests==2.33.0
httpx
azure-core
azure-ai-projects
PyPDF2
python-docx
python-dotenv
```

The connection seeder specifically needs: **`httpx`** (the PUT/GET), **`azure-identity`** (`DefaultAzureCredential`), **`python-dotenv`** (`load_dotenv`), and **`azure-ai-projects`** (`AIProjectClient` — only the resource-ID-discovery fallback). The rest of the file serves the other post-provision scripts (blob upload, indexing, cosmos).

---

## 5. Bicep vs script — confirmed BOTH connections exist

- **Bicep (base):** `module foundry_search_connection` in data/sample_code/macae/infra/bicep/main.bicep (lines 471–489) creates ONE `CognitiveSearch` / `AAD` connection:
  ```bicep
  // Base AI Search connection (CognitiveSearch / AAD).
  // Per-KB RemoteTool connections (ProjectManagedIdentity) are created by
  // infra/scripts/post-provision/seed_kb_connections.py at post-deploy time because the KB
  // names are dynamic and depend on selected content packs.
  module foundry_search_connection './modules/ai/ai-foundry-connection.bicep' = {
    params: {
      connectionName: aiSearchConnectionName
      useWorkspaceManagedIdentity: true
      category: 'CognitiveSearch'
      target: ai_search.outputs.endpoint
      authType: 'AAD'
      metadata: { ApiType: 'Azure', ResourceId: ai_search.outputs.resourceId }
    }
  }
  ```
  (Mirrored in the AVM variant data/sample_code/macae/infra/avm/main.bicep lines 921–939.)

- **Script (per-KB):** the N × `{kb}-mcp` `RemoteTool` / `ProjectManagedIdentity` connections, created by `seed_kb_connections.py` (§1).

Rationale captured in the Bicep comment: KB names are dynamic (depend on selected content packs) so they can't be enumerated at provision time → deferred to post-deploy script. The backend app is wired to default to the per-KB `-mcp` connection names; the env var `AZURE_AI_SEARCH_CONNECTION_NAME` is intentionally omitted from the backend container (main.bicep lines 601–605):
```bicep
// NOTE: AZURE_AI_SEARCH_CONNECTION_NAME intentionally omitted.
// The app defaults to per-KB RemoteTool connection names (e.g.
// "macae-retail-customer-kb-mcp") which carry ProjectManagedIdentity
// auth required by the KB MCP endpoint.
```

---

## 6. CWYD replication fit (existing post-deploy machinery)

### 6a. CWYD azure.yaml hooks (v2/azure.yaml lines 198–240)

CWYD already uses **real** azd hooks (not banners):
```yaml
hooks:
  postprovision:
    posix:   { shell: sh,   run: ./scripts/post-provision.sh,    continueOnError: false, interactive: true }
    windows: { shell: pwsh, run: ./scripts/post-provision.ps1,   continueOnError: false, interactive: true }
  postdeploy:
    posix:   { shell: sh,   run: ./scripts/upload-sample-data.sh,  continueOnError: true, interactive: true }
    windows: { shell: pwsh, run: ./scripts/upload-sample-data.ps1, continueOnError: true, interactive: true }
```

### 6b. CWYD wrapper style — thin `uv run python` shims

v2/scripts/upload-sample-data.sh (whole file):
```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run python "${SCRIPT_DIR}/upload_sample_data.py" "$@"
```

v2/scripts/upload-sample-data.ps1 (whole file):
```powershell
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& uv run python (Join-Path $scriptDir 'upload_sample_data.py') @args
exit $LASTEXITCODE
```

CWYD wrappers are **~10 lines** — no venv creation, no `pip install`, no `azd env get-value` plumbing. `uv run` resolves the project venv (declared in v2/pyproject.toml) and azd injects the env-var outputs into the hook process. This is the style a new KB-MCP seeder should mirror (NOT MACAE's heavyweight 900-line `post_deploy.sh`).

### 6c. CWYD Python uploader conventions (v2/scripts/upload_sample_data.py)

- Pillar/Phase docstring header (Hard Rule #3).
- `DefaultAzureCredential` (matches `post_provision.py`).
- Required env vars via `_require(name)` → exit `_EXIT_MISSING_ENV = 2` if missing: `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_DOCUMENTS_CONTAINER`, `AZURE_DOC_PROCESSING_QUEUE`; optional overrides `AZURE_STORAGE_BLOB_ENDPOINT`, `AZURE_INGESTION_TRIGGER`, `AZURE_ENV_SAMPLE_DATA`.
- `StrEnum` for closed-set selections (`SeedScope`), `argparse`, `--dry-run`, interactive menu with unattended override (`--set` / `AZURE_ENV_SAMPLE_DATA`), distinct exit codes including `_EXIT_SDK_FAILURE = 6`.
- Wraps Azure SDK calls in `azure.core.exceptions.AzureError` handling (Hard Rule #14).
- Idempotent (skip-if-present).

A CWYD KB-MCP seeder should: live at v2/scripts/seed_kb_connections.py, ship `seed-kb-connections.sh` + `seed-kb-connections.ps1` thin `uv run` shims, read endpoints from azd-output env vars, use `DefaultAzureCredential` + `httpx` PUT with the §1a payload, be idempotent (PUT, treat 200/201/409 as success), and emit structured logging per Hard Rule #14.

---

## Discrepancies vs CWYD bugs.md (BUG-0025 / BUG-0059)

1. **Path**: bugs.md says `infra/scripts/seed_kb_connections.py`; actual is `infra/scripts/post-provision/seed_kb_connections.py`.
2. **Target URL api-version**: bugs.md implies `2025-05-01-preview` for the KB; the live sample uses `2025-11-01-preview` for both the KB definition and the MCP target. The **connection PUT** api-version `2025-04-01-preview` matches bugs.md.
3. **Connection payload, audience, authType, category** all match bugs.md exactly (`RemoteTool` / `ProjectManagedIdentity` / `audience: https://search.azure.com`).
4. bugs.md frames the hook as auto-run; in MACAE the azd `postdeploy` hook is a **banner only** and the seeder is operator-invoked via `post_deploy.sh`/`.ps1`. CWYD, by contrast, already runs a real `postdeploy` hook — so a CWYD seeder could be genuinely automated.

---

## Gaps / clarifying questions for CWYD replication

1. **Where does CWYD get the KB name(s)?** MACAE hardcodes a static `KNOWLEDGE_BASES` dict per content pack. CWYD is single-tenant with a different scenario model (default / employee / contract). Decision needed: hardcode CWYD's KB name(s), derive from `AssistantType`, or read from an env var / azd output. Likely CWYD has **one** KB (not nine), simplifying the loop.
2. **postprovision vs postdeploy.** The RemoteTool connection depends on (a) the Foundry project existing (provision-time) and (b) the KB existing on the search service. In CWYD, does the KB get created at provision-time (Bicep / a postprovision seeder) or is there a separate KB-seed step? If the KB is provision-time, the connection seeder fits `postprovision`; if it depends on uploaded sample data being indexed, it must run after `postdeploy`. **Recommend confirming CWYD's KB lifecycle before choosing the hook.**
3. **Index-store mode.** CWYD supports `cosmosdb` (→ Azure AI Search) and `postgresql` (→ pgvector). The KB MCP / Foundry IQ RemoteTool connection only makes sense in the **Azure AI Search** path. The seeder must **no-op in postgresql mode** (gate on `AZURE_SEARCH_ENDPOINT` / `index_store`).
4. **Project resource-ID discovery.** MACAE discovers it at runtime (data-plane GET, then AIProjectClient fallback). CWYD could instead surface the project ARM resource ID directly as a Bicep output (cleaner, avoids the two-token dance). Decision: env-var the resource ID, or replicate runtime discovery?
5. **RBAC prerequisite.** The seeding identity needs **Azure AI User** (`53ca6127-db72-4b80-b1b0-d745d6d5456d`) on the Foundry account to PUT connections. Confirm CWYD's deployer/UAMI already holds an equivalent role, or the seeder will 403. MACAE assigns it in-wrapper + sleeps 60s for propagation.
6. **Base CognitiveSearch connection.** CWYD presumably keeps (or should keep) the Bicep-managed base `CognitiveSearch`/`AAD` connection AND add the script-managed `RemoteTool` connection — confirm CWYD wants the same two-connection split (the user's note says we're replacing a Bicep-resource approach with the script approach; clarify whether ONLY the RemoteTool moves to script, or the base one too).
7. **httpx dependency.** Confirm `httpx` + `azure-ai-projects` are in v2/pyproject.toml (CWYD's `upload_sample_data.py` uses azure SDK clients, not raw httpx). If the seeder uses raw ARM PUT like MACAE, `httpx` must be a declared dep.

---

## Key file references (workspace-relative)

- data/sample_code/macae/infra/scripts/post-provision/seed_kb_connections.py — the seeder (PUT payload lines 119–150; auth 84–113; KB names 42–60; env 31–40; idempotency 143–150; main 165–225).
- data/sample_code/macae/infra/scripts/post-provision/seed_knowledge_bases.py — `KNOWLEDGE_BASES` dict + `KB_API_VERSION = "2025-11-01-preview"` (line 58).
- data/sample_code/macae/infra/scripts/post-provision/post_deploy.sh — wrapper: venv (599–642), env export (740–760), seeding calls (855–873), kb_map (832–841), role assignment (386–417).
- data/sample_code/macae/infra/scripts/post-provision/Selecting-Team-Config-And-Data.ps1 — legacy driver `Start-Process` call (911–918).
- data/sample_code/macae/infra/scripts/post-provision/requirements.txt — script deps.
- data/sample_code/macae/azure.yaml — `postdeploy` banner hook (7–73).
- data/sample_code/macae/azure_custom.yaml — same banner hook (46–104).
- data/sample_code/macae/infra/bicep/main.bicep — base `foundry_search_connection` Bicep connection (467–489); backend env note (601–605).
- data/sample_code/macae/infra/bicep/modules/ai/ai-foundry-connection.bicep — parameterized connection module (category supports CognitiveSearch / AppInsights / RemoteTool).
- v2/azure.yaml — CWYD hooks block (198–240).
- v2/scripts/upload-sample-data.sh, v2/scripts/upload-sample-data.ps1 — CWYD thin `uv run python` shim style.
- v2/scripts/upload_sample_data.py — CWYD post-deploy uploader conventions (env `_require`, StrEnum, DefaultAzureCredential, idempotent, exit codes).
