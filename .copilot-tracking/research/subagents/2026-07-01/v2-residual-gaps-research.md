<!-- markdownlint-disable-file -->
# v2 Residual Gaps — Focused Research (2026-07-01)

READ-ONLY research over `v2/`. Answers four focused questions with exact
file:line citations and quoted code.

## Scope / questions

- Q1 — cosmos-mode Foundry IQ knowledge-base connection (BUG-0059 residual).
- Q2 — sample-data upload on a fresh deploy.
- Q3 — exact model edit sites for the o4-mini → replacement swap.
- Q4 — image tagging on rebuild (does each build update the running code?).

Status: **Complete**.

---

## Q1 — cosmos-mode Foundry IQ knowledge-base connection

### One-line answer

`post_provision.py` **DOES** create the `cwyd-kb-mcp` connection — a
`RemoteTool` connection with `authType: "ProjectManagedIdentity"` and
`audience: "https://search.azure.com"`, PUT to the Foundry project via ARM.
Bicep's only Project↔Search connection is a *different* one
(`search-<searchServiceName>`, category `CognitiveSearch`, `authType: AAD`).
The 401 risk on a fresh cosmos deploy is **low but not zero**: the connection
and the Project's Search data-plane RBAC both exist, so as long as the
`postprovision` hook runs to completion the grounding path authenticates;
the residual risk is a *silent skip* (connection never created) if
`AZURE_AI_PROJECT_RESOURCE_ID` is absent from the hook env.

### Evidence

#### The backend references `cwyd-kb-mcp`, not the bicep connection

The backend Container App env binds `AZURE_AI_SEARCH_CONNECTION_NAME` to
`<searchKnowledgeBaseName>-mcp` in cosmosdb mode. `searchKnowledgeBaseName`
defaults to `cwyd-kb` (v2/infra/main.bicep line 202), so the value is
`cwyd-kb-mcp`.

v2/infra/main.bicep line 1912:

```bicep
{ name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: databaseType == 'cosmosdb' ? '${searchKnowledgeBaseName}-mcp' : '' }
```

v2/infra/main.bicep line 202:

```bicep
param searchKnowledgeBaseName string = 'cwyd-kb'
```

The inline comment at v2/infra/main.bicep lines 1908-1911 is slightly
misleading — it says the connection is "category CognitiveSearch" resolved
"through the Project-Search connection", but the *value it actually binds*
is the `-mcp` RemoteTool connection created by `post_provision.py`, not the
CognitiveSearch connection created by bicep.

#### Bicep's only Project↔Search connection is `search-<searchServiceName>` (CognitiveSearch/AAD)

The module `modules/ai-project-search-connection.bicep` creates exactly one
connection and it is **not** `cwyd-kb-mcp`.

v2/infra/modules/ai-project-search-connection.bicep lines 24-58:

```bicep
@description('Optional. Friendly name for the connection inside the Project. Lower-case, no spaces.')
param connectionName string = 'search-${searchServiceName}'
...
resource connection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: connectionName
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${searchServiceName}.search.windows.net'
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: searchService.id
      location: searchService.location
      KnowledgeBaseName: knowledgeBaseName
    }
  }
}
```

This connection has **no `audience` field**, **no `RemoteTool` category**,
and a name (`search-<searchServiceName>`) that does not match the
`cwyd-kb-mcp` the backend references. It is wired at v2/infra/main.bicep
lines 1072-1080:

```bicep
module aiProjectSearchConnection 'modules/ai-project-search-connection.bicep' = if (databaseType == 'cosmosdb') {
  name: take('module.ai-project-search-connection.${solutionSuffix}', 64)
  params: {
    aiServicesAccountName: aiServicesName
    projectName: aiProject.outputs.name
    searchServiceName: effectiveSearchName
    knowledgeBaseName: searchKnowledgeBaseName
  }
}
```

#### `post_provision.py` creates `cwyd-kb-mcp` (RemoteTool, ProjectManagedIdentity, audience search.azure.com)

`_ensure_kb_mcp_connection` (v2/scripts/post_provision.py line 517) builds the
`{kb}-mcp` connection name and PUTs it to the project via the ARM control
plane.

Connection name + target — v2/scripts/post_provision.py lines 549-566:

```python
    kb_name = (
        os.environ.get("AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME", "").strip()
        or DEFAULT_KNOWLEDGE_BASE_NAME
    )
    kb_api_version = (
        os.environ.get("AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION", "").strip()
        or DEFAULT_KNOWLEDGE_BASE_API_VERSION
    )
    connection_name = f"{kb_name}-mcp"
    base = search_endpoint.rstrip("/")
    target = f"{base}/knowledgebases/{kb_name}/mcp?api-version={kb_api_version}"
    url = (
        f"https://management.azure.com{project_resource_id}/connections/"
        f"{connection_name}?api-version={KB_MCP_CONNECTION_API_VERSION}"
    )
```

Connection properties (type / audience / auth) — v2/scripts/post_provision.py
lines 577-586:

```python
    properties: dict[str, object] = {
        "category": "RemoteTool",
        "target": target,
        "authType": "ProjectManagedIdentity",
        "useWorkspaceManagedIdentity": True,
        "isSharedToAll": True,
        "audience": "https://search.azure.com",
        "metadata": {"ApiType": "Azure"},
    }
```

Answer to "what type / audience / auth":

- **type / category:** `RemoteTool`
- **audience:** `https://search.azure.com`
- **auth:** `ProjectManagedIdentity` (+ `useWorkspaceManagedIdentity: true`)
- **control plane:** ARM PUT to
  `management.azure.com/<AZURE_AI_PROJECT_RESOURCE_ID>/connections/cwyd-kb-mcp?api-version=2025-04-01-preview`
  (`KB_MCP_CONNECTION_API_VERSION` = `2025-04-01-preview`,
  v2/scripts/post_provision.py line 113).

#### The knowledge base (`cwyd-kb`) + knowledge source (`cwyd-index-ks`) are also created by post_provision

`_ensure_knowledge_base` (v2/scripts/post_provision.py line 391) builds and
PUTs both the knowledge source and the knowledge base via the Search data
plane. Defaults — v2/scripts/post_provision.py lines 92-94:

```python
DEFAULT_KNOWLEDGE_BASE_NAME = "cwyd-kb"
DEFAULT_KNOWLEDGE_SOURCE_NAME = "cwyd-index-ks"
DEFAULT_KNOWLEDGE_BASE_API_VERSION = "2025-11-01-preview"
```

The two PUTs (source first, base second — order matters) —
v2/scripts/post_provision.py inside `_ensure_knowledge_base` (the create-or-
update loop):

```python
        for url, body in (
            (f"{base}/knowledgesources('{knowledge_source_name}')", knowledge_source_body),
            (f"{base}/knowledgebases('{knowledge_base_name}')", knowledge_base_body),
        ):
            response = client.put(url, params=params, json=body)
            response.raise_for_status()
```

The KB uses the **chat** deployment (`AZURE_OPENAI_GPT_DEPLOYMENT`) for query
planning, not the reasoning deployment — Foundry IQ rejects o-series models
for the KB model (v2/scripts/post_provision.py `_build_knowledge_base_seed`
docstring + body, lines 331-390).

#### Hook wiring + call order

The `postprovision` hook runs `post-provision.sh` / `.ps1` which invoke
`post_provision.py`. v2/azure.yaml lines 207-217:

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

`main()` call order — v2/scripts/post_provision.py lines 655-660:

```python
    _ensure_search_index(dry_run=args.dry_run)
    _ensure_knowledge_base(dry_run=args.dry_run)
    ...
    _ensure_kb_mcp_connection(dry_run=args.dry_run)
```

`continueOnError: false` on `postprovision` means any failure in these three
steps **aborts `azd up` loudly** rather than leaving a silent 401 at chat
time.

#### 401 risk analysis (residual)

The Project's managed identity **is** granted Search data-plane RBAC, so the
`ProjectManagedIdentity` + `audience: https://search.azure.com` token used by
the `cwyd-kb-mcp` RemoteTool connection should authenticate.

v2/infra/main.bicep lines 939-951 (on the `aiSearch` module role assignments):

```bicep
      {
        principalId: aiProject.outputs.projectPrincipalId
        principalType: 'ServicePrincipal'
        // Search Index Data Reader — lets the Foundry Project (and Foundry IQ) query indexes through the connection.
        roleDefinitionIdOrName: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
      }
      {
        principalId: aiProject.outputs.projectPrincipalId
        principalType: 'ServicePrincipal'
        // Search Service Contributor — lets the Foundry Project (and Foundry IQ)
        // manage indexes/indexers/skillsets through the Project-Search connection.
        roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
      }
```

`AZURE_AI_PROJECT_RESOURCE_ID` (required by `_ensure_kb_mcp_connection`) is a
declared bicep output, so azd surfaces it to the hook —
v2/infra/main.bicep line 2570:

```bicep
@description('Foundry Project ARM resource id. Consumed by post_provision.py to seed the KB-MCP RemoteTool connection at the control plane.')
output AZURE_AI_PROJECT_RESOURCE_ID string = aiProject.outputs.resourceId
```

**Residual risk vectors (why "low but not zero"):**

1. **Silent skip.** `_ensure_kb_mcp_connection` returns `"skipped"` (no error)
   if either `AZURE_AI_SEARCH_ENDPOINT` or `AZURE_AI_PROJECT_RESOURCE_ID` is
   missing from the hook env (v2/scripts/post_provision.py lines 538-547). If
   that happens, `cwyd-kb-mcp` is never created, the backend references a
   non-existent connection, and agent_framework KB grounding fails at runtime
   (the connection lookup fails, not strictly a 401). This depends entirely on
   azd exporting the bicep outputs to the hook — which it normally does.
2. **KB API-version availability.** `_ensure_knowledge_base` uses
   `2025-11-01-preview` and `_ensure_kb_mcp_connection` embeds the same
   version in the RemoteTool `target`. If that preview API is unavailable in
   the deployed region, the KB/connection PUT fails — but because
   `continueOnError: false`, this aborts `azd up` loudly (fail-fast), it does
   not produce a silent chat-time 401.
3. **Naming confusion (latent, not a 401).** Bicep creates
   `search-<searchServiceName>` (CognitiveSearch) but the backend binds
   `cwyd-kb-mcp`. Reading the bicep alone would mislead — the functional
   connection is the post_provision one. Not a runtime failure as long as
   post_provision runs.

**Conclusion:** On a fresh cosmos-mode `azd up`, the `cwyd-kb-mcp` connection
IS created (by post_provision, not bicep) and the Project MI HAS the Search
RBAC to use it — so no 401 in the happy path. The realistic failure mode is a
loud postprovision abort (bad API version / RBAC propagation) or a silent
skip if the project-resource-id env var never reaches the hook.

---

## Q2 — sample-data upload on a fresh deploy

### One-line answer

**Yes** — a script uploads sample documents into the `documents` blob
container on a fresh `azd up`, and it is **wired into an azd hook so it runs
automatically**. `v2/scripts/upload_sample_data.py` (invoked via
`upload-sample-data.sh` / `.ps1`) is the project-level `postdeploy` hook.

### Evidence

#### The postdeploy hook

v2/azure.yaml lines 218-228:

```yaml
  postdeploy:
    posix:
      shell: sh
      run: ./scripts/upload-sample-data.sh
      continueOnError: true
      interactive: true
    windows:
      shell: pwsh
      run: ./scripts/upload-sample-data.ps1
      continueOnError: true
      interactive: true
```

This is **project-scoped** `postdeploy`, so it runs after every successful
`azd deploy` / `azd up`. `continueOnError: true` means a seed hiccup never
fails an otherwise-successful deployment. `interactive: true` lets it prompt.

#### What the script does

The wrapper `.sh` / `.ps1` shell out to `v2/scripts/upload_sample_data.py`.
Its module docstring (v2/scripts/upload_sample_data.py lines 1-31) states it
uploads sample documents into the documents container and enqueues ingestion:

```python
"""Post-deploy seed: upload sample documents and enqueue ingestion.
...
Runs after a successful ``azd deploy`` / ``azd up`` so chat grounds
out-of-the-box without an operator manually uploading documents. The
operator chooses which assistant scenario to seed -- ``default`` /
``employee assistant`` (benefits / HR documents) or ``contract
assistant`` (contract documents) -- or ``all`` to seed every sample
document. The scope is taken from ``--set``, then the
``AZURE_ENV_SAMPLE_DATA`` env override, then an interactive menu when the
hook runs in a terminal; a non-interactive shell with no override seeds
the default PDF document set so chat grounds out-of-the-box (set
``AZURE_ENV_SAMPLE_DATA=none`` to opt out). Files resolve from the
repo-root ``data/`` folder; no binary documents are committed.
"""
```

Key behavior:

- **Default on non-interactive CI:** seeds the default PDF set (not "none")
  unless `AZURE_ENV_SAMPLE_DATA=none`.
- **Target container:** env var `AZURE_DOCUMENTS_CONTAINER`
  (`_ENV_CONTAINER = "AZURE_DOCUMENTS_CONTAINER"`,
  v2/scripts/upload_sample_data.py line ~106). Confirmed this resolves to the
  literal `documents` container: v2/infra/main.bicep line 2157
  (`var documentsContainerName = 'documents'`) → output at line 2657
  (`output AZURE_DOCUMENTS_CONTAINER string = documentsContainerName`). The
  container itself is created at v2/infra/main.bicep line 1134
  (`name: 'documents'`).
- **Source:** repo-root `data/` folder (benefits set + `contract_data/`),
  v2/scripts/upload_sample_data.py lines 60-84.
- **Idempotent:** blobs already present are skipped (no re-upload,
  no re-enqueue).
- **Enqueue only in direct-enqueue mode:** under event-grid ingestion the
  blob upload alone triggers processing, so enqueue is suppressed.

**Conclusion:** Sample data upload is automatic on `azd up` via the
`postdeploy` hook — not manual-only.

---

## Q3 — exact model edit sites for the o4-mini → replacement swap

### One-line answer

Three model deployments (chat `gpt-5.1`, reasoning `o4-mini`, embedding
`text-embedding-3-large`) are declared as bicep params (v2/infra/main.bicep
lines 143-176) and consumed in a single deployments array (lines 557-595) plus
the reused-OpenAI child resources (lines 660-700). Both parameter JSON files
carry identical `${AZURE_ENV_*}` bindings at the same line numbers. The three
backend deployment env-var names default to empty strings in
`v2/src/backend/core/settings.py` (infra-pinned).

### Exact model params — v2/infra/main.bicep

Chat / GPT — lines 142-157:

```bicep
@minLength(1)
@description('Optional. Primary chat model deployment name.')
param gptModelName string = 'gpt-5.1'            // line 143

@description('Optional. Primary chat model version.')
param gptModelVersion string = '2025-11-13'      // line 146
...
param gptModelDeploymentType string = 'GlobalStandard'   // line 153
...
param gptModelCapacity int = 150                 // line 157
```

Reasoning / o-series — lines 160-175:

```bicep
@minLength(1)
@description('Optional. Reasoning model deployment name (surfaced via the SSE reasoning channel).')
param reasoningModelName string = 'o4-mini'      // line 161

@description('Optional. Reasoning model version.')
param reasoningModelVersion string = '2025-04-16'   // line 164
...
param reasoningModelDeploymentType string = 'GlobalStandard'   // line 171
...
param reasoningModelCapacity int = 50            // line 175
```

Embedding — lines 178-192:

```bicep
@minLength(1)
@description('Optional. Embedding model deployment name (used by Foundry IQ and the LangGraph indexer).')
param embeddingModelName string = 'text-embedding-3-large'   // line 179

@description('Optional. Embedding model version.')
param embeddingModelVersion string = '1'         // line 182
...
param embeddingModelDeploymentType string = 'Standard'   // line 189
...
param embeddingModelCapacity int = 100           // line 192

@description('Optional. Azure OpenAI API version exposed via the OpenAI-compatible endpoint (used by the LangGraph orchestrator).')
param azureOpenAiApiVersion string = '2025-01-01-preview'   // line 195

@description('Optional. Azure AI Agent API version (used by the Agent Framework orchestrator).')
param azureAiAgentApiVersion string = '2025-05-01'          // line 198
```

### `usageName` capacity hints — v2/infra/main.bicep lines 67-71

```bicep
    usageName: [
      'OpenAI.GlobalStandard.gpt-5.1,150'
      'OpenAI.GlobalStandard.o4-mini,50'
      'OpenAI.Standard.text-embedding-3-large,100'
    ]
```

(Line 69 = `o4-mini` occurrence #1 in the quota usageName hints — must be
updated when swapping the reasoning model.)

### Model-deployment resource blocks — v2/infra/main.bicep

Primary Foundry account deployments array — lines 557-595 (the `deployments:`
consumed by the AI Services / Foundry account module):

```bicep
    deployments: useExistingOpenAi ? [] : [
      {
        name: gptModelName
        model: { format: 'OpenAI', name: gptModelName, version: gptModelVersion }
        sku: { name: gptModelDeploymentType, capacity: gptModelCapacity }
        raiPolicyName: 'Microsoft.DefaultV2'
      }
      {
        name: reasoningModelName
        model: { format: 'OpenAI', name: reasoningModelName, version: reasoningModelVersion }
        sku: { name: reasoningModelDeploymentType, capacity: reasoningModelCapacity }
        raiPolicyName: 'Microsoft.DefaultV2'
      }
      {
        name: embeddingModelName
        model: { format: 'OpenAI', name: embeddingModelName, version: embeddingModelVersion }
        sku: { name: embeddingModelDeploymentType, capacity: embeddingModelCapacity }
      }
    ]
```

Reused-v1-OpenAI child deployments (only when `existingOpenAiName` is set) —
lines 664-700:

- `existingOpenAiGptDeployment` — parent name `gptModelName` (line 666),
  model name `gptModelName` (line 674).
- `existingOpenAiReasoningDeployment` — parent name `reasoningModelName`
  (line 683), model name `reasoningModelName` (line 691).

(These two child resources re-declare the chat + reasoning deployments on the
reused account; the swap must touch both the array *and* these when the
`existingOpenAiName` path is in play.)

### Backend env binding — v2/infra/main.bicep lines 1880-1882

```bicep
            { name: 'AZURE_OPENAI_GPT_DEPLOYMENT', value: gptModelName }
            { name: 'AZURE_OPENAI_REASONING_DEPLOYMENT', value: reasoningModelName }
            { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
```

Function App also binds embedding — v2/infra/main.bicep line 2278:

```bicep
          { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
```

### Parameter files — EXACT line numbers (both files identical)

Both `v2/infra/main.parameters.json` and `v2/infra/main.waf.parameters.json`
have **byte-identical** model blocks at the **same line numbers**. Pinned
exactly (correcting the earlier "~36/~40" estimate — the reasoning block is
lines 35-46):

| Param | Key line | Value line | Value |
|---|---|---|---|
| `gptModelName` | 23 | 24 | `${AZURE_ENV_GPT_MODEL_NAME=gpt-5.1}` |
| `gptModelVersion` | 26 | 27 | `${AZURE_ENV_GPT_MODEL_VERSION=2025-11-13}` |
| `gptModelDeploymentType` | 29 | 30 | `${AZURE_ENV_GPT_MODEL_SKU=GlobalStandard}` |
| `gptModelCapacity` | 32 | 33 | `${AZURE_ENV_GPT_MODEL_CAPACITY=150}` |
| `reasoningModelName` | 35 | **36** | `${AZURE_ENV_REASONING_MODEL_NAME=o4-mini}` |
| `reasoningModelVersion` | 38 | **39** | `${AZURE_ENV_REASONING_MODEL_VERSION=2025-04-16}` |
| `reasoningModelDeploymentType` | 41 | 42 | `${AZURE_ENV_REASONING_MODEL_SKU=GlobalStandard}` |
| `reasoningModelCapacity` | 44 | 45 | `${AZURE_ENV_REASONING_MODEL_CAPACITY=50}` |
| `embeddingModelName` | 47 | 48 | `${AZURE_ENV_EMBEDDING_MODEL_NAME=text-embedding-3-large}` |
| `embeddingModelVersion` | 50 | 51 | `${AZURE_ENV_EMBEDDING_MODEL_VERSION=1}` |
| `embeddingModelDeploymentType` | 53 | 54 | `${AZURE_ENV_EMBEDDING_MODEL_SKU=Standard}` |
| `embeddingModelCapacity` | 56 | 57 | `${AZURE_ENV_EMBEDDING_MODEL_CAPACITY=100}` |
| `azureOpenAiApiVersion` | 59 | 60 | `${AZURE_ENV_OPENAI_API_VERSION=2025-01-01-preview}` |

**Every `reasoningModel*` / `o4-mini` occurrence across the three files:**

- v2/infra/main.bicep:
  - line 69 — `'OpenAI.GlobalStandard.o4-mini,50'` (usageName hint)
  - line 161 — `param reasoningModelName string = 'o4-mini'` (default)
  - line 164 — `param reasoningModelVersion string = '2025-04-16'`
  - line 171 — `param reasoningModelDeploymentType string = 'GlobalStandard'`
  - line 175 — `param reasoningModelCapacity int = 50`
  - lines 572, 575 — `reasoningModelName` in the primary deployments array
  - lines 683, 691 — `reasoningModelName` in the reused-OpenAI child resource
  - line 1881 — `AZURE_OPENAI_REASONING_DEPLOYMENT` backend env binding
- v2/infra/main.parameters.json:
  - line 35 — `"reasoningModelName": {`
  - line 36 — `"value": "${AZURE_ENV_REASONING_MODEL_NAME=o4-mini}"`
  - line 38 — `"reasoningModelVersion": {`
  - line 39 — `"value": "${AZURE_ENV_REASONING_MODEL_VERSION=2025-04-16}"`
  - line 41 — `"reasoningModelDeploymentType": {`
  - line 42 — `"value": "${AZURE_ENV_REASONING_MODEL_SKU=GlobalStandard}"`
  - line 44 — `"reasoningModelCapacity": {`
  - line 45 — `"value": "${AZURE_ENV_REASONING_MODEL_CAPACITY=50}"`
- v2/infra/main.waf.parameters.json:
  - **identical to main.parameters.json — same line numbers 35-46**
    (line 36 = `o4-mini`, line 39 = `2025-04-16`, line 42 = `GlobalStandard`,
    line 45 = `50`).

### Backend settings defaults — v2/src/backend/core/settings.py

`OpenAISettings` (env_prefix `AZURE_OPENAI_`) — v2/src/backend/core/settings.py
lines 167-179:

```python
class OpenAISettings(BaseSettings):
    """Azure OpenAI deployments routed through the Foundry account."""

    model_config = SettingsConfigDict(env_prefix="AZURE_OPENAI_", extra="ignore")

    api_version: str = ""            # env: AZURE_OPENAI_API_VERSION (default "")
    gpt_deployment: str = ""         # env: AZURE_OPENAI_GPT_DEPLOYMENT (default "")
    reasoning_deployment: str = ""   # env: AZURE_OPENAI_REASONING_DEPLOYMENT (default "")
    embedding_deployment: str = ""   # env: AZURE_OPENAI_EMBEDDING_DEPLOYMENT (default "")
    embedding_dimensions: int = 1536
    temperature: float = 0.0
    max_tokens: int = 1000
```

Env-var name / default summary:

- `AZURE_OPENAI_GPT_DEPLOYMENT` → `gpt_deployment`, default `""`
- `AZURE_OPENAI_REASONING_DEPLOYMENT` → `reasoning_deployment`, default `""`
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` → `embedding_deployment`, default `""`
- `AZURE_OPENAI_API_VERSION` → `api_version`, default `""`

All three deployment names default to empty strings — the settings are
**infra-pinned** (the real values come from the bicep env bindings at
main.bicep lines 1880-1882). The bicep API-version defaults are
`azureOpenAiApiVersion = '2025-01-01-preview'` (main.bicep line 195) and
`azureAiAgentApiVersion = '2025-05-01'` (main.bicep line 198). Foundry
substrate API version lives in `FoundrySettings.agent_api_version`
(env `AZURE_AI_AGENT_API_VERSION`, default `""`,
v2/src/backend/core/settings.py line 164).

**Swap footprint for o4-mini → replacement:** at minimum update
main.bicep lines 69, 161, 164 (and 171/175 if SKU/capacity change), plus the
identical `reasoningModel*` value lines 36/39 (and 42/45) in **both**
parameter JSON files. The `settings.py` reasoning field needs no change (it
reads whatever `AZURE_OPENAI_REASONING_DEPLOYMENT` resolves to). Note the KB
query-planning model uses the **chat** deployment, not the reasoning one
(Q1), so a reasoning swap does not touch the Foundry IQ KB seed.

---

## Q4 — image tagging on rebuild

### One-line answer

The backend Container App is an azd-managed containerapp target (tag
`azd-service-name: backend`) with a **remote ACR build** (`remoteBuild: true`).
The bicep `image:` line is only a **placeholder** — azd overrides it at
`azd deploy` time with a **unique per-build tag** (azd's `azd-deploy-<timestamp>`
convention) and patches the Container App to reference it, which creates a new
revision. So a rebuild **does** reliably roll the running code forward.

### Evidence

#### azure.yaml backend service — remote build

v2/azure.yaml lines 116-126:

```yaml
services:
  backend:
    project: ./src/backend
    language: py
    host: containerapp
    docker:
      path: ../../docker/Dockerfile.backend
      context: ../..
      # Build the backend image in ACR (remote) instead of the local
      # Docker daemon, so `azd deploy` works without a local Docker
      # install and pushes straight to the registry the UAMI pulls from.
      remoteBuild: true
```

`remoteBuild: true` → azd runs `az acr build` (ACR Tasks) rather than a local
`docker build`; the image is built and pushed inside ACR.

#### Container App resource — tag + placeholder image

The `azd-service-name: backend` tag is what binds the azd service to the
Container App resource — v2/infra/main.bicep line 1781:

```bicep
    tags: union(allTags, { 'azd-service-name': 'backend' })
```

The bicep `image:` is a placeholder / fallback, not the deployed code —
v2/infra/main.bicep lines 1829-1831:

```bicep
        image: empty(backendContainerRegistryHostname)
          ? 'mcr.microsoft.com/k8se/quickstart:latest'
          : '${backendContainerRegistryHostname}/${backendContainerImageName}:${backendContainerImageTag}'
```

The bicep params default to a **fixed** tag `latest` (v2/infra/main.bicep
lines 1638-1641):

```bicep
@description('Optional. Repository (image) name of the backend container image within the registry.')
param backendContainerImageName string = 'cwyd-backend'

@description('Optional. Tag of the backend container image to deploy.')
param backendContainerImageTag string = 'latest'
```

#### How the swap actually happens (the authoritative comment)

The bicep comment block explains that bicep only sets a bootable placeholder,
and `azd deploy`'s deploy-time `azd-service-name: backend` tag swap patches the
live revision — v2/infra/main.bicep lines 1624-1632:

```bicep
// Backend image coordinates (azd-driven). On a clean first `azd up` the
// AZURE_CONTAINER_REGISTRY_ENDPOINT output does not exist yet, so
// `backendContainerRegistryHostname` is empty and the Container App boots
// from a pullable public placeholder image so the first provision can
// pull. `azd deploy` then builds + pushes the real image and the
// deploy-time `azd-service-name: backend` tag swap patches the live
// revision; later provisions compose the real ACR image reference from
// these params.
```

And again at the container definition — v2/infra/main.bicep lines 1820-1828:

```bicep
        // When `backendContainerRegistryHostname` is empty (clean first
        // provision -- the AZURE_CONTAINER_REGISTRY_ENDPOINT output does
        // not exist yet) the container boots from a pullable public
        // placeholder so provisioning succeeds before any image is
        // pushed. Once the real backend image is built + pushed, azd's
        // deploy-time `azd-service-name: backend` tag swap patches the
        // live revision, and subsequent provisions compose the real ACR
        // image reference from the backendContainerImage* params.
```

#### Managed-identity pull

The Container App pulls from ACR with the UAMI (AcrPull), no admin creds —
v2/infra/main.bicep lines 1793-1798:

```bicep
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: userAssignedIdentity.outputs.resourceId
      }
    ]
```

#### Interpretation of "unique tag per build"

azd's containerapp deploy target does **not** reuse the bicep `latest` tag for
the deployed revision. azd tags each built image with a unique
`azd-deploy-<unix-timestamp>` tag, pushes it, and then updates the Container
App's `image` on the target revision to that unique reference (this is azd's
standard containerapp behavior — the bicep `image:`/`backendContainerImageTag`
placeholder is superseded at deploy time). Because the image reference changes
on every deploy, the Container App creates a **new revision** and rolls traffic
to the new code — a rebuild reliably updates the running app.

**Caveat / thing to verify against azd version:** the repo pins
`requiredVersions: azd: ">= 1.18.0 != 1.23.9"` (v2/azure.yaml line 27). The
unique-tag-per-deploy behavior is azd-version-dependent; the bicep's own
`backendContainerImageTag = 'latest'` is only used by `azd provision` (infra
re-apply), not by `azd deploy` (which supplies its own unique tag). If a
future azd release changed to reuse a fixed tag, the placeholder-vs-deployed
split documented in the bicep comments would still hold, but revision rollover
would depend on the image digest changing. As written today, `azd deploy`
rolls a new revision per build.

---

## Clarifying questions

None strictly blocking. Two notes the caller may want to confirm downstream:

1. Q4 relies on azd's documented containerapp unique-tag-per-deploy behavior.
   Confirming against the operator's actual azd version (`azd version`) would
   remove the only inference in this document — every other answer is pinned to
   quoted source.
2. Q1's "low but not zero" 401 verdict assumes azd exports bicep outputs
   (notably `AZURE_AI_PROJECT_RESOURCE_ID`) into the `postprovision` hook env.
   That is azd's normal behavior; a live `azd env get-values` after provision
   would confirm the var is present before the hook runs.

## Recommended next research (not done this session)

- [ ] Confirm azd version behavior for containerapp deploy tag (Q4 inference).
- [ ] Trace how the backend `agent_framework` orchestrator consumes
      `AZURE_AI_SEARCH_CONNECTION_NAME` (`cwyd-kb-mcp`) at runtime to verify the
      KB MCP tool wiring end-to-end (beyond infra/seed).
