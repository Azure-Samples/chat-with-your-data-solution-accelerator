<!-- markdownlint-disable-file -->
# WI-01 Research Spike — `cwyd-kb-mcp` Foundry Project Connection Schema (Phase 4 Step 4.1)

Status: Complete — Phase 4 Step 4.1 is UNBLOCKED (schema fully confirmed from three independent sources). One optional live-environment cross-check is noted under Remaining unknowns / risks; it is not a blocker.

Goal: give an implementer the EXACT Bicep resource schema for the `cwyd-kb-mcp` RemoteTool connection so they can author the durable bicep back-port that BUG-0059 left pending.

## Research topics / questions

1. What consumes `cwyd-kb-mcp` in v2 (backend env, agent_framework orchestrator, Foundry IQ KB wiring)?
2. The existing `CognitiveSearch` connection shape (ai-project-search-connection.bicep + ai-project.bicep).
3. The KB seed expectation (post_provision.py) — what connection name + shape does the KB/agent expect?
4. MACAE's KB-MCP connection pattern (seed_kb_connections.py + seed_knowledge_bases.py).
5. The authoritative ARM/Bicep schema for `Microsoft.CognitiveServices/accounts/projects/connections`.
6. ADR cross-check (KB MCP / Foundry IQ / RemoteTool connection design).

## Findings

### Topic 1 — What consumes `cwyd-kb-mcp` in v2

The connection NAME flows: bicep env var -> backend `SearchSettings.connection_name` -> agent_framework orchestrator -> `MCPTool.project_connection_id`. Foundry runs the KB retrieval server-side under the connection's identity, so the connection's auth config (not the backend's) is what mints the bearer against the KB MCP endpoint.

- v2/src/backend/core/settings.py — `SearchSettings` (env_prefix `AZURE_AI_SEARCH_`): `connection_name: str = ""` (from `AZURE_AI_SEARCH_CONNECTION_NAME`), `knowledge_base_name = "cwyd-kb"`, `knowledge_base_api_version = "2025-11-01-preview"`.
- v2/src/backend/core/providers/orchestrators/agent_framework.py:
  - L65 `from azure.ai.projects.models import MCPTool`.
  - L99 `KB_RETRIEVE_TOOL_NAME = "knowledge_base_retrieve"`.
  - `self._connection_name = search_settings.connection_name`.
  - `_build_kb_tool()` returns `None` when `not endpoint or not self._kb_name or not self._connection_name`; otherwise builds:
    `url = f"{endpoint}/knowledgebases/{self._kb_name}/mcp?api-version={self._kb_api_version}"`
    `MCPTool(server_label=self._kb_name, server_url=url, require_approval="never", allowed_tools=[KB_RETRIEVE_TOOL_NAME], project_connection_id=self._connection_name)`.
- v2/.env line 52 `AZURE_AI_SEARCH_CONNECTION_NAME=cwyd-kb-mcp`; line 50 comment: "Created live as cwyd-kb-mcp per MACAE's seed_kb_connections.py payload."

Conclusion: the env value MUST be the friendly name of a connection whose category/authType/audience can authenticate to the KB MCP path. Today in bicep it resolves to the `CognitiveSearch`/`AAD` connection name (`search-<svc>`), which 401s (BUG-0025 / BUG-0059).

### Topic 2 — Existing `CognitiveSearch` connection shape (the one that 401s)

v2/infra/modules/ai-project-search-connection.bicep (verbatim properties; resource + parent both at `2025-04-01-preview`):

```bicep
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  name: '${aiServicesAccountName}/${projectName}'
}

resource connection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: connectionName            // default 'search-${searchServiceName}'
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${searchServiceName}.search.windows.net'
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: searchService.id
      location: searchService.location
      KnowledgeBaseName: knowledgeBaseName   // default 'cwyd-kb'
    }
  }
}
```

Key differences from the working KB MCP connection: `category` is `CognitiveSearch` (not `RemoteTool`), `authType` is bare `AAD` (not `ProjectManagedIdentity`), there is no `useWorkspaceManagedIdentity: true`, and no `audience`. Per BUG-0025 these gaps mean the server-side MCP path gets no usable bearer -> 401. The module is NOT wrapped in `any(...)` because every property it uses is in the typed schema.

v2/infra/modules/ai-project.bicep — the Project is `Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview` with `identity: SystemAssigned`; output `projectPrincipalId = project.identity.principalId`. This system-assigned identity is the principal the RemoteTool connection authenticates as.

### Topic 3 — KB seed expectation (post_provision.py)

v2/scripts/post_provision.py seeds the knowledge SOURCE and knowledge BASE via Search REST PUT (`_build_knowledge_base_seed` L321, `_ensure_knowledge_base` L381 -> `knowledgesources` / `knowledgebases`). There is NO `_ensure_*_connection` function — post_provision does NOT create the `cwyd-kb-mcp` project connection. So today CWYD has no automated path (neither bicep nor post_provision) that creates the connection; the working one was created live/manually. This is the gap WI-01 / Step 4.1 closes.

Important ordering fact: the connection is just a target-URL string + auth config; Foundry validates the KB lazily at tool-call time. The KB (`cwyd-kb`) does not need to exist when the connection is created, so bicep MAY declare the connection at provision time even though the KB is seeded later by post_provision.

### Topic 4 — MACAE's KB-MCP connection pattern (authoritative payload)

data/sample_code/macae/infra/scripts/post-provision/seed_kb_connections.py — module docstring: "Create RemoteTool connections in the AI Foundry project for each Knowledge Base ... so that MCPTool can authenticate to the KB MCP endpoint using the project's managed identity (ProjectManagedIdentity auth type). Connection naming convention: '{kb_name}-mcp'. Target URL pattern: '{search_endpoint}/knowledgebases/{kb_name}/mcp?api-version=2025-11-01-preview'."

- `KB_API_VERSION = "2025-11-01-preview"` (embedded in target URL).
- ARM PUT URL: `https://management.azure.com{resource_id}/connections/{connection_name}?api-version=2025-04-01-preview` (management-plane token scope `https://management.azure.com/.default`; idempotent: 200/201/409 = success).
- Connection name `f"{kb_name}-mcp"` -> for `cwyd-kb` that is `cwyd-kb-mcp` (matches CWYD's `.env`).
- EXACT REST body (`_create_connection_via_arm`):

```python
body = {
    "properties": {
        "category": "RemoteTool",
        "target": target_url,   # f"{SEARCH_ENDPOINT}/knowledgebases/{kb_name}/mcp?api-version={KB_API_VERSION}"
        "authType": "ProjectManagedIdentity",
        "useWorkspaceManagedIdentity": True,
        "isSharedToAll": True,
        "audience": "https://search.azure.com",
        "metadata": {
            "ApiType": "Azure",
        },
    }
}
```

data/sample_code/macae/infra/bicep/modules/ai/ai-foundry-connection.bicep — generic reusable connection module. Resource `Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01`, parent `aiProject@2025-12-01`. `baseProperties = { category, target, authType, isSharedToAll, metadata, useWorkspaceManagedIdentity }` and `properties: any(union(baseProperties, optionalDefault, optionalCredentials))`. Note: the bicep module does NOT pass `audience` — `audience` is set ONLY in the REST seed body. Outputs `connectionName`, `connectionId`.

data/sample_code/macae/infra/bicep/main.bicep L466-490 — bicep declares ONLY the base `CognitiveSearch`/`AAD` connection (`foundry_search_connection`); the per-KB `RemoteTool` connections are created by the post-provision script. The comment (L467-470) gives the reason: "Per-KB RemoteTool connections (ProjectManagedIdentity) are created by infra/scripts/post-provision/seed_kb_connections.py at post-deploy time because the KB names are dynamic and depend on selected content packs."

CWYD insight: CWYD has a SINGLE STATIC KB (`cwyd-kb`), single-tenant — there is no dynamic-name dependency, so CWYD CAN and SHOULD declare `cwyd-kb-mcp` in bicep at provision time rather than via a script. This is the cleaner choice and is why CWYD diverges from MACAE here.

### Topic 5 — Authoritative ARM/Bicep schema (`...projects/connections@2025-04-01-preview`)

Fetched the strongly-typed Bicep schema for `Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview`. Findings (token presence in the schema, by offset):

- `name` pattern: `^[a-zA-Z0-9][a-zA-Z0-9_-]{2,32}$` — `cwyd-kb-mcp` (11 chars) is VALID.
- `properties` -> `ConnectionPropertiesV2`. Typed top-level members present: `isSharedToAll` (bool), `metadata` (free-form user metadata object), `target` (string), `useWorkspaceManagedIdentity` (bool), plus `expiryTime`, `peRequirement`, `peStatus`, `sharedUserList`.
- `authType` is a discriminated `oneOf`; the const branches are exactly: AAD, AccessKey, AccountKey, ApiKey, ManagedIdentity, None, OAuth2, PAT, SAS, ServicePrincipal, UsernamePassword. There is NO `ProjectManagedIdentity` branch at this api version.
- `category` is `anyOf: [ { enum: [ ...big closed list... ] }, { type: string } ]` — i.e. it ACCEPTS any string. `RemoteTool` is NOT in the explicit enum, but the trailing `{type: string}` branch means an arbitrary string is schema-valid.
- `audience` is NOT a recognized top-level property at `2025-04-01-preview` (token absent).
- `useWorkspaceManagedIdentity` IS a recognized typed bool — good.

Implication for bicep authoring: because `authType: 'ProjectManagedIdentity'` matches no `oneOf` branch AND `audience` is not a typed property, a strongly-typed `properties: { ... }` literal would produce Bicep type warnings/errors. The fix is the SAME pattern MACAE already uses in its reusable module: wrap the property bag in `any(...)` so Bicep skips the discriminated-union/closed-property validation and passes the bag straight to ARM. The ARM control plane DOES accept `RemoteTool` / `ProjectManagedIdentity` / top-level `audience` at `2025-04-01-preview` — that is exactly the api-version MACAE's live seed PUTs against, and CWYD's own working `cwyd-kb-mcp` connection was created from that payload (BUG-0025 / BUG-0059).

### Topic 6 — ADR / bugs cross-check

v2/docs/bugs.md:

- BUG-0025 (2026-06-12, fixed): KB tool pointed at the wrong connection category (`CognitiveSearch` / bare `AAD`, `useWorkspaceManagedIdentity: false`, no `audience`) -> server-side MCP path got no usable bearer -> 401. Fixed by creating a dedicated `cwyd-kb-mcp` `RemoteTool` / `ProjectManagedIdentity` connection (`audience: https://search.azure.com`).
- BUG-0059 (2026-06-16, fixed live, durable bicep back-port PENDING): deployed backend `AZURE_AI_SEARCH_CONNECTION_NAME` held the bicep default `search-srch-<DATA_SUFFIX>` -> 401. The correct `cwyd-kb-mcp` RemoteTool / ProjectManagedIdentity connection (`audience: https://search.azure.com`, `useWorkspaceManagedIdentity: true`, `target` = the KB MCP URL) already exists live, and the Project MI already holds BOTH `Search Index Data Reader` and `Search Service Contributor`. Fixed live via `az containerapp update --set-env-vars AZURE_AI_SEARCH_CONNECTION_NAME=cwyd-kb-mcp`. The note explicitly says the durable bicep back-port (create the connection + point the env at it + Project-MI `Search Service Contributor` in `infra/`) is still pending. THIS pending back-port is exactly WI-01 / Phase 4 Step 4.1.
- BUG-0020 (KB MCP connect unauthenticated 401) and BUG-0030 (citation divergence) — related but distinct; not part of this schema spike.

No dedicated ADR defines the connection schema; bugs.md BUG-0025/0059 is the authoritative CWYD-side record and it agrees field-for-field with MACAE's `seed_kb_connections.py` payload.

## Confirmed schema

The `cwyd-kb-mcp` connection is a Project sub-resource `Microsoft.CognitiveServices/accounts/projects/connections`. Confirmed working property bag (agreed by MACAE seed payload + CWYD BUG-0025/0059):

| Property | Value | Schema status at `2025-04-01-preview` |
| --- | --- | --- |
| `category` | `RemoteTool` | accepted (anyOf string fallback) |
| `target` | `https://<search>.search.windows.net/knowledgebases/cwyd-kb/mcp?api-version=2025-11-01-preview` | typed string |
| `authType` | `ProjectManagedIdentity` | NOT in oneOf -> needs `any()` |
| `useWorkspaceManagedIdentity` | `true` | typed bool |
| `isSharedToAll` | `true` | typed bool |
| `audience` | `https://search.azure.com` | NOT typed -> needs `any()` |
| `metadata` | `{ ApiType: 'Azure' }` | free-form object |
| `name` | `cwyd-kb-mcp` (or `${knowledgeBaseName}-mcp`) | matches name regex |

Recommendation: a NEW dedicated module `v2/infra/modules/ai-project-kb-mcp-connection.bicep`, sibling to `ai-project-search-connection.bicep`, cosmosdb-gated. Keep the existing `CognitiveSearch` connection (it is the base AI-Search registration; harmless and mirrors MACAE keeping both). Wrap `properties` in `any(...)` exactly like MACAE's reusable module, because `authType: 'ProjectManagedIdentity'` and top-level `audience` are not in the typed schema. Pin the resource at CWYD's existing `2025-04-01-preview` (same version the live seed PUTs against — no reason to jump to MACAE's `2025-12-01`).

Ready-to-adapt Bicep snippet (the new module's core):

```bicep
// ========================================================================
// Pillar:  Stable Core
// Phase:   4 (MACAE infra-parity)
// Purpose: Foundry Project RemoteTool connection 'cwyd-kb-mcp'. This is
//          the connection MCPTool.project_connection_id points at; Foundry
//          runs KB retrieval server-side under the Project MI using this
//          connection's ProjectManagedIdentity auth + search.azure.com
//          audience. Replaces the CognitiveSearch connection for the KB
//          MCP path (the latter 401s -- BUG-0025 / BUG-0059).
//          Deployed only in databaseType=='cosmosdb' mode.
// ========================================================================

targetScope = 'resourceGroup'

@description('Required. Name of the parent AI Services account.')
param aiServicesAccountName string

@description('Required. Name of the Foundry Project (sub-resource of the account).')
param projectName string

@description('Required. Azure AI Search endpoint, e.g. https://<svc>.search.windows.net (no trailing slash).')
param searchEndpoint string

@description('Optional. Foundry IQ knowledge base name (matches SearchSettings.knowledge_base_name).')
param knowledgeBaseName string = 'cwyd-kb'

@description('Optional. KB MCP API version embedded in the connection target URL.')
param knowledgeBaseApiVersion string = '2025-11-01-preview'

@description('Optional. Friendly connection name. MUST match AZURE_AI_SEARCH_CONNECTION_NAME. Lower-case, 3-33 chars.')
param connectionName string = '${knowledgeBaseName}-mcp'   // -> 'cwyd-kb-mcp'

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  name: '${aiServicesAccountName}/${projectName}'
}

resource kbMcpConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: connectionName
  // any() is required: authType 'ProjectManagedIdentity' and top-level
  // 'audience' are accepted by ARM but are not in the typed Bicep schema
  // at 2025-04-01-preview (mirrors MACAE ai-foundry-connection.bicep).
  properties: any({
    category: 'RemoteTool'
    target: '${searchEndpoint}/knowledgebases/${knowledgeBaseName}/mcp?api-version=${knowledgeBaseApiVersion}'
    authType: 'ProjectManagedIdentity'
    useWorkspaceManagedIdentity: true
    isSharedToAll: true
    audience: 'https://search.azure.com'
    metadata: {
      ApiType: 'Azure'
    }
  })
}

@description('Friendly name of the KB MCP connection. Flows to AZURE_AI_SEARCH_CONNECTION_NAME.')
output name string = kbMcpConnection.name

@description('Resource ID of the KB MCP connection.')
output resourceId string = kbMcpConnection.id
```

Note: `searchEndpoint` maps directly to the existing `effectiveSearchEndpoint` var in main.bicep (L1046), so the target URL the connection carries is byte-identical to the URL the backend builds in `_build_kb_tool` and to MACAE's seed target pattern.

## main.bicep change

Two edits in v2/infra/main.bicep (both cosmosdb-gated, mirroring the existing `aiProjectSearchConnection` module).

1. Add a new module instantiation next to `aiProjectSearchConnection` (currently L1051-1059). All inputs already exist as vars/params:

```bicep
// Foundry Project RemoteTool connection for the KB MCP path (cosmosdb
// mode only). This is what AZURE_AI_SEARCH_CONNECTION_NAME must resolve
// to; the CognitiveSearch connection 401s on the MCP path (BUG-0025/0059).
module aiProjectKbMcpConnection 'modules/ai-project-kb-mcp-connection.bicep' = if (databaseType == 'cosmosdb') {
  name: take('module.ai-project-kb-mcp-connection.${solutionSuffix}', 64)
  params: {
    aiServicesAccountName: aiServicesName
    projectName: aiProject.outputs.name
    searchEndpoint: effectiveSearchEndpoint            // L1046
    knowledgeBaseName: searchKnowledgeBaseName         // L193 = 'cwyd-kb'
    knowledgeBaseApiVersion: searchKnowledgeBaseApiVersion  // L199 = '2025-11-01-preview'
  }
}
```

2. Re-point the env var at the new connection. Change L1864 from:

```bicep
{ name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: databaseType == 'cosmosdb' ? aiProjectSearchConnection!.outputs.name : '' }
```

to:

```bicep
{ name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: databaseType == 'cosmosdb' ? aiProjectKbMcpConnection!.outputs.name : '' }
```

Result: in cosmosdb mode the backend env resolves to `cwyd-kb-mcp` (the RemoteTool connection's name) instead of `search-<svc>` (the CognitiveSearch connection). In postgresql mode it stays `''` (pgvector path, unchanged).

Out of scope for this spike but called out by BUG-0059 as part of the same back-port: ensure the Project MI `Search Service Contributor` grant lives in `infra/` (per the WI-01 prompt, Phase 3.5 already added it). No change to the existing `aiProjectSearchConnection` module is required — keep both connections.

## Remaining unknowns / risks

1. Bicep-level `audience` + `authType: 'ProjectManagedIdentity'` are not in the typed schema at `2025-04-01-preview`. RESOLVED in approach, not a blocker: wrap `properties` in `any(...)` (MACAE precedent). The control plane accepts these — MACAE's live seed PUTs the identical bag at this exact api-version, and CWYD's working live connection was created from it. Residual risk is only a Bicep linter warning if `any()` is omitted; the snippet includes `any()`.
2. Does ARM persist `audience` as a top-level connection property at `2025-04-01-preview`, or silently drop it? MACAE's working KBs and CWYD's working live `cwyd-kb-mcp` (both carry top-level `audience`) indicate it is honored. OPTIONAL live cross-check: `az rest --method get --url "https://management.azure.com/subscriptions/<AZURE_SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>/connections/cwyd-kb-mcp?api-version=2025-04-01-preview"` and confirm `properties.audience == 'https://search.azure.com'` and `properties.authType == 'ProjectManagedIdentity'`. Not required to author Step 4.1.
3. API version choice: CWYD pins `2025-04-01-preview`; MACAE's reusable bicep module uses `2025-12-01`. Recommend staying on `2025-04-01-preview` for consistency with the existing CognitiveSearch module and because the live seed proves RemoteTool/ProjectManagedIdentity work there. If a future Bicep build flags the `any()` bag, bumping the connection resource to a newer version that types `ProjectManagedIdentity`/`audience` is a fallback — but unnecessary today.
4. RBAC sufficiency: BUG-0059 confirms the Project MI already holds BOTH `Search Index Data Reader` and `Search Service Contributor`, and the WI-01 prompt states Phase 3.5 added `Search Service Contributor` in infra. Confirm the role assignment is the Project's SYSTEM-assigned identity (the connection authenticates as `useWorkspaceManagedIdentity: true` = the Project MI), not a UAMI. `ai-project.bicep` outputs `projectPrincipalId = project.identity.principalId` (system-assigned) — that is the principal to grant.
5. Keep-both vs consolidate: recommendation keeps the CognitiveSearch connection AND adds the RemoteTool one (MACAE keeps both). If a later cleanup shows nothing reads the CognitiveSearch connection in CWYD's cosmosdb path, it could be removed — out of scope for Step 4.1; do not remove in this unit.
6. Name-length/regex: `cwyd-kb-mcp` (11 chars, lower-case, hyphens) satisfies `^[a-zA-Z0-9][a-zA-Z0-9_-]{2,32}$`. If `knowledgeBaseName` is ever lengthened, `${knowledgeBaseName}-mcp` must stay <= 33 chars.

## Citations

Workspace files (plain-text paths, line refs where exact):

- v2/src/backend/core/providers/orchestrators/agent_framework.py — L65 MCPTool import, L99 KB_RETRIEVE_TOOL_NAME, `_build_kb_tool()` URL + project_connection_id.
- v2/src/backend/core/settings.py — SearchSettings (connection_name, knowledge_base_name, knowledge_base_api_version).
- v2/infra/modules/ai-project-search-connection.bicep — existing CognitiveSearch/AAD connection (the one that 401s); resource + parent at 2025-04-01-preview.
- v2/infra/modules/ai-project.bicep — Project resource (SystemAssigned identity), output projectPrincipalId.
- v2/infra/main.bicep — L193 searchKnowledgeBaseName='cwyd-kb', L199 searchKnowledgeBaseApiVersion='2025-11-01-preview', L1045-1046 effectiveSearchName/effectiveSearchEndpoint, L1051-1059 aiProjectSearchConnection module, L1859 KB_API_VERSION env, L1864 AZURE_AI_SEARCH_CONNECTION_NAME env.
- v2/scripts/post_provision.py — L321 _build_knowledge_base_seed, L381 _ensure_knowledge_base (KB source/base seeding; no connection creation).
- v2/.env — L50 comment, L52 AZURE_AI_SEARCH_CONNECTION_NAME=cwyd-kb-mcp.
- v2/docs/bugs.md — BUG-0025, BUG-0059 (authoritative CWYD connection-shape record + pending bicep back-port), BUG-0020, BUG-0030.
- data/sample_code/macae/infra/scripts/post-provision/seed_kb_connections.py — RemoteTool REST payload (category/target/authType/useWorkspaceManagedIdentity/isSharedToAll/audience/metadata), KB_API_VERSION, ARM PUT api-version 2025-04-01-preview, naming convention {kb}-mcp.
- data/sample_code/macae/infra/bicep/modules/ai/ai-foundry-connection.bicep — reusable connection module using `properties: any(union(...))`; resource @2025-12-01; baseProperties omit audience.
- data/sample_code/macae/infra/bicep/main.bicep — L466-490 base CognitiveSearch connection in bicep + comment (L467-470) explaining per-KB RemoteTool connections are script-seeded because KB names are dynamic.
- data/sample_code/macae/infra/scripts/post-provision/seed_knowledge_bases.py — _SEARCH_SCOPE https://search.azure.com/.default, KB_API_VERSION 2025-11-01-preview.

Authoritative schema (fetched this session):

- `Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview` Bicep resource schema — name regex `^[a-zA-Z0-9][a-zA-Z0-9_-]{2,32}$`; ConnectionPropertiesV2 typed members include isSharedToAll, metadata, target, useWorkspaceManagedIdentity; authType oneOf = {AAD, AccessKey, AccountKey, ApiKey, ManagedIdentity, None, OAuth2, PAT, SAS, ServicePrincipal, UsernamePassword} (no ProjectManagedIdentity); category anyOf has a string fallback (RemoteTool accepted); no top-level `audience`.

Azure documentation:

- ARM template reference — [Microsoft.CognitiveServices accounts/projects/connections](https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/accounts/projects/connections)
- [Azure AI Foundry connections](https://learn.microsoft.com/azure/ai-foundry/concepts/connections)
- [Foundry IQ / knowledge bases (agentic retrieval)](https://learn.microsoft.com/azure/search/search-agentic-retrieval-concept)
