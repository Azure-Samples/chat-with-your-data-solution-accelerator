<!-- markdownlint-disable-file -->
# MACAE Infra Research — Identity/RBAC, Env-Var Wiring, Conditional Deploy, Post-Provision Hooks, Outputs

Reference target: `data/sample_code/macae` (Multi-Agent Custom Automation Engine Solution Accelerator).
Purpose: reference for fixing CWYD v2 infra (missing role grants, env-var wiring, conditional AI Search deploy, post-provision sample-data upload).

Status: Complete.

## 0. Top-level infra topology (orientation)

MACAE `infra/` uses a **deployment-router** pattern. `data/sample_code/macae/infra/main.bicep` is a thin router that picks one of three flavors via the `deploymentFlavor` param (`'bicep' | 'avm' | 'avm-waf'`):

- `infra/main.bicep` lines 144-145 — derived flags `var isAvm = deploymentFlavor == 'avm' || deploymentFlavor == 'avm-waf'` and `var isBicep = deploymentFlavor == 'bicep'`.
- `infra/main.bicep` line 258 — `module avmDeployment './avm/main.bicep' = if (isAvm) {...}`.
- `infra/main.bicep` line 318 — `module bicepDeployment './bicep/main.bicep' = if (isBicep) {...}`.
- All outputs are coalesced: `output X = isAvm ? avmDeployment!.outputs.X : bicepDeployment!.outputs.X`.

This research documents the **vanilla bicep flavor** (`infra/bicep/`) because it is the simplest single-RG, UAMI-based, managed-identity-only path — the closest analog to what CWYD v2 needs. The `infra/avm/` flavor uses Azure Verified Modules and adds private-networking/WAF; not the focus here.

Vanilla bicep module tree (`infra/bicep/modules/`):
- `identity/` — `managed-identity.bicep`, `role-assignments.bicep`, `cross-scope-role-assignment.bicep`
- `compute/` — `container-app.bicep`, `container-app-environment.bicep`, `container-registry.bicep`, `app-service.bicep`, `app-service-plan.bicep`
- `data/` — `storage-account.bicep`, `cosmos-db-nosql.bicep`
- `ai/` — `ai-foundry-project.bicep`, `ai-foundry-model-deployment.bicep`, `ai-search.bicep`, `ai-foundry-connection.bicep`, `existing-project-setup.bicep`
- `monitoring/` — `log-analytics.bicep`, `app-insights.bicep`

---

## 1. Managed Identity + RBAC

### 1.1 Where the UAMI is created

A single user-assigned managed identity is created and shared by all workloads (backend container app, MCP container app, ACR pulls).

- Module: `infra/bicep/modules/identity/managed-identity.bicep` — resource `Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31` at line 23, named `id-${solutionName}`. Outputs `resourceId`, `principalId`, `clientId`, `name`.
- Instantiated in `infra/bicep/main.bicep` line 320:
  ```bicep
  module userAssignedIdentity './modules/identity/managed-identity.bicep' = {
    name: take('module.user-assigned-identity.${solutionSuffix}', 64)
    params: {
      solutionName: solutionSuffix
      identityName: 'id-${solutionSuffix}'
      location: solutionLocation
      tags: allTags
    }
  }
  ```
- NOTE: the module header docstring says "This module is NOT called from main.bicep by default" — that comment is stale; the **vanilla bicep flavor DOES call it** (line 320). The UAMI's `resourceId` is attached to both container apps via `managedIdentities: { userAssignedResourceIds: [userAssignedIdentity.outputs.resourceId] }`, and its `clientId` is injected as the `AZURE_CLIENT_ID` env var.

### 1.2 Centralized role-assignment module

All RBAC lives in one module for auditability: `infra/bicep/modules/identity/role-assignments.bicep`. It is wired once in `infra/bicep/main.bicep` line 831:
```bicep
module role_assignments './modules/identity/role-assignments.bicep' = {
  name: take('module.role-assignments.${solutionSuffix}', 64)
  params: {
    solutionName: solutionSuffix
    useExistingAIProject: useExistingAiFoundryAiProject
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    aiFoundryResourceId: aiFoundryAiServicesResourceId
    aiSearchResourceId: ai_search.outputs.resourceId
    storageAccountResourceId: storage_account.outputs.resourceId
    aiProjectPrincipalId: aiFoundryAiProjectPrincipalId
    aiSearchPrincipalId: ai_search.outputs.identityPrincipalId
    deployerPrincipalId: deployingUserPrincipalId
    deployerPrincipalType: deployerPrincipalType
    userAssignedManagedIdentityPrincipalId: userAssignedIdentity.outputs.principalId
    cosmosDbAccountName: cosmosDBModule.outputs.name
    containerRegistryResourceId: isCustom ? container_registry!.outputs.resourceId : ''
  }
}
```

Key design: the module accepts a `workloadPrincipalIds array` param (future SAMI support) and falls back to a single-element list wrapping the UAMI principal (`infra/bicep/modules/identity/role-assignments.bicep` line 73):
```bicep
var workloadPrincipals = !empty(workloadPrincipalIds) ? workloadPrincipalIds : (empty(userAssignedManagedIdentityPrincipalId) ? [] : [userAssignedManagedIdentityPrincipalId])
```
So every "workload" role assignment is a `[for principalId in workloadPrincipals: if (...) {...}]` loop. Today that loop has exactly one element: the shared UAMI.

### 1.3 Role-definition GUID table

Declared as a `var roleDefinitions` map in `infra/bicep/modules/identity/role-assignments.bicep` lines 79-90:

| Key in bicep | Role name | Role definition GUID |
| --- | --- | --- |
| `azureAiUser` | Azure AI User (Foundry User) | `53ca6127-db72-4b80-b1b0-d745d6d5456d` |
| `cognitiveServicesUser` | Cognitive Services User | `a97b65f3-24c7-4388-baec-2e87135dc908` |
| `cognitiveServicesOpenAIUser` | Cognitive Services OpenAI User | `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` |
| `cognitiveServicesOpenAIContributor` | Cognitive Services OpenAI Contributor | `a001fd3d-188f-4b5d-821b-7da978bf7442` |
| `searchIndexDataReader` | Search Index Data Reader | `1407120a-92aa-4202-b7e9-c0e197c71c8f` |
| `searchIndexDataContributor` | Search Index Data Contributor | `8ebe5a00-799e-43f5-93ac-243d3dce84a7` |
| `searchServiceContributor` | Search Service Contributor | `7ca78c08-252a-4471-8644-bb5ff32d4ba0` |
| `storageBlobDataContributor` | Storage Blob Data Contributor | `ba92f5b4-2d11-453d-a403-e96b0029c9fe` |
| `storageBlobDataReader` | Storage Blob Data Reader | `2a2b9908-6ea1-4ae2-8e65-a410df84e7d1` |
| `acrPull` | AcrPull | `7f951dda-4ed3-4680-a7ca-43fe172d538d` |

Cosmos DB uses a **data-plane** SQL role (not an ARM role assignment): the built-in `Cosmos DB Built-in Data Contributor` definition `00000000-0000-0000-0000-000000000002`, referenced as an existing child resource at `infra/bicep/modules/identity/role-assignments.bicep` line 114.

### 1.4 Full RBAC table — Role | Assignee | Scope

Every role assignment in `infra/bicep/modules/identity/role-assignments.bicep` (vanilla bicep, new-project path). "Workload UAMI" = the shared user-assigned managed identity (via the `workloadPrincipals` loop). "Deployer" = the signed-in user/SP running `azd up`.

| # | Role | Assignee | Scope resource | Bicep symbol / line |
| --- | --- | --- | --- | --- |
| 1 | Cognitive Services OpenAI User | AI Search service identity | AI Foundry account | `assignOpenAIRoleToAISearch` line 122 |
| 2 | Foundry User (Azure AI User) | Workload UAMI | AI Foundry account | `workloadAiUserAssignment` line 148 |
| 3 | Cognitive Services OpenAI Contributor | Workload UAMI | AI Foundry account | `workloadOpenAIContributor` line 160 |
| 4 | Search Index Data Reader | AI Foundry project identity | AI Search service | `projectSearchReader` line 204 |
| 5 | Search Service Contributor | AI Foundry project identity | AI Search service | `projectSearchContributor` line 215 |
| 6 | Search Index Data Contributor | Workload UAMI | AI Search service | `workloadSearchIndexContributor` line 228 |
| 7 | Search Service Contributor | Workload UAMI | AI Search service | `workloadSearchServiceContributor` line 240 |
| 8 | Storage Blob Data Contributor | Workload UAMI | Storage account | `workloadStorageContributor` line 258 |
| 9 | Cosmos DB Built-in Data Contributor (data-plane) | Workload UAMI | Cosmos DB account | `workloadCosmosRoleAssignment` line 275 |
| 10 | Cognitive Services User | Deployer (User/SP) | AI Foundry account | `deployerAiServicesAccess` line 291 |
| 11 | Foundry User (Azure AI User) | Deployer (User/SP) | AI Foundry account | `deployerAzureAIAccess` line 302 |
| 12 | Search Index Data Contributor | Deployer (User/SP) | AI Search service | `deployerSearchIndexContributor` line 332 |
| 13 | Search Service Contributor | Deployer (User/SP) | AI Search service | `deployerSearchServiceContributor` line 343 |
| 14 | Storage Blob Data Contributor | Deployer (User/SP) | Storage account | `deployerStorageBlobContributor` line 354 |
| 15 | Cosmos DB Built-in Data Contributor (data-plane) | Deployer (User/SP) | Cosmos DB account | `deployerCosmosRoleAssignment` line 365 |
| 16 | AcrPull | Workload UAMI | Container Registry (only when `isCustom`) | `workloadAcrPull` line 393 |

Cross-scope variants (used only when reusing an existing AI Foundry project in another RG) go through the helper `infra/bicep/modules/identity/cross-scope-role-assignment.bicep` (a single `Microsoft.Authorization/roleAssignments@2022-04-01` scoped to an `existing` AI Services account in a `resourceGroup(sub, rg)`-scoped module). Examples: `assignOpenAIToSearchExisting` (line 135), `workloadAiUserExisting` (line 171), `workloadOpenAIContributorExisting` (line 184).

### 1.5 RBAC mapping → CWYD-relevant categories (for the comparison the user asked for)

| Service | Role granted to the runtime UAMI | Mechanism |
| --- | --- | --- |
| **Cosmos DB** | Cosmos DB Built-in Data Contributor (`00000000-...-000002`) | data-plane `Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2025-10-15` (parent = cosmos account), NOT an ARM role assignment |
| **Storage (blob)** | Storage Blob Data Contributor | ARM `roleAssignments` scoped to storage account |
| **AI Services / OpenAI** | Foundry User + Cognitive Services OpenAI Contributor | ARM `roleAssignments` scoped to AI Foundry (CognitiveServices) account |
| **Azure AI Search** | Search Index Data Contributor + Search Service Contributor | ARM `roleAssignments` scoped to the search service |
| **ACR pull** | AcrPull (only `isCustom`) | ARM `roleAssignments` scoped to the container registry |
| **App Insights / Monitor** | (none) | App Insights consumed via connection string / instrumentation key env vars; no RBAC role granted |

CWYD-relevant gap signal: MACAE grants the **runtime identity** all four data-plane roles (Cosmos data-contributor, Storage blob-contributor, Search index+service-contributor, Foundry/OpenAI) AND grants the **deployer** the same roles so the post-deploy seeding scripts (run as the signed-in user) can write blobs / build indexes. App Insights does NOT get an RBAC grant — it is wired purely through env vars.

---

## 2. Env-Var Wiring onto Runtimes

### 2.1 Backend Container App — env array

`infra/bicep/main.bicep` lines 528-678 — `module backend_container_app './modules/compute/container-app.bicep'`. The identity + ingress wiring:
```bicep
ingressTargetPort: 8000
managedIdentities: {
  userAssignedResourceIds: [userAssignedIdentity.outputs.resourceId]
}
registries: isCustom ? [
  {
    server: container_registry!.outputs.loginServer
    identity: userAssignedIdentity.outputs.resourceId
  }
] : []
```

Full `env: [ { name, value } ]` array (every value is a **plain `value:`** — no `secretRef`, no Key Vault). Key entries:
```bicep
env: [
  { name: 'COSMOSDB_ENDPOINT',  value: 'https://${cosmosDBModule.outputs.name}.documents.azure.com:443/' }
  { name: 'COSMOSDB_DATABASE',  value: cosmosDbDatabaseName }
  { name: 'COSMOSDB_CONTAINER', value: cosmosDbDatabaseMemoryContainerName }
  { name: 'AZURE_OPENAI_ENDPOINT',             value: aiFoundryOpenAIEndpoint }
  { name: 'AZURE_OPENAI_DEPLOYMENT_NAME',      value: gptModelName }
  { name: 'AZURE_OPENAI_RAI_DEPLOYMENT_NAME',  value: gpt4_1ModelName }
  { name: 'AZURE_OPENAI_API_VERSION',          value: azureOpenaiAPIVersion }
  { name: 'APPLICATIONINSIGHTS_INSTRUMENTATION_KEY', value: app_insights.outputs.instrumentationKey }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING',   value: app_insights.outputs.connectionString }
  { name: 'AZURE_AI_SUBSCRIPTION_ID',   value: aiFoundryAiServicesSubscriptionId }
  { name: 'AZURE_AI_RESOURCE_GROUP',    value: aiFoundryAiServicesResourceGroupName }
  { name: 'AZURE_AI_PROJECT_NAME',      value: aiFoundryAiProjectResourceName }
  { name: 'FRONTEND_SITE_NAME',         value: frontendAppUrl }
  { name: 'APP_ENV',                    value: 'Prod' }
  // NOTE in source: AZURE_AI_SEARCH_CONNECTION_NAME intentionally omitted
  // (app defaults to per-KB RemoteTool connection names w/ ProjectManagedIdentity auth)
  { name: 'AZURE_AI_SEARCH_ENDPOINT',   value: ai_search.outputs.endpoint }
  { name: 'AZURE_COGNITIVE_SERVICES',   value: 'https://cognitiveservices.azure.com/.default' }
  { name: 'ORCHESTRATOR_MODEL_NAME',    value: gptReasoningModelName }
  { name: 'AZURE_OPENAI_IMAGE_DEPLOYMENT', value: gptImageModelName }
  { name: 'MCP_SERVER_ENDPOINT',        value: 'https://${mcp_container_app.outputs.fqdn}/mcp' }
  { name: 'MCP_SERVER_NAME',            value: mcpServerName }
  { name: 'MCP_SERVER_DESCRIPTION',     value: mcpServerDescription }
  { name: 'AZURE_TENANT_ID',            value: tenant().tenantId }
  { name: 'AZURE_CLIENT_ID',            value: userAssignedIdentity.outputs.clientId }   // <-- MI auth handle
  { name: 'SUPPORTED_MODELS',           value: string(supportedModels) }
  { name: 'AZURE_STORAGE_BLOB_URL',     value: storage_account.outputs.blobEndpoint }
  { name: 'AZURE_AI_PROJECT_ENDPOINT',  value: aiFoundryAiProjectEndpoint }
  { name: 'AZURE_AI_AGENT_ENDPOINT',    value: aiFoundryAiProjectEndpoint }
  { name: 'AZURE_BASIC_LOGGING_LEVEL',  value: 'INFO' }
  { name: 'AZURE_PACKAGE_LOGGING_LEVEL',value: 'WARNING' }
  { name: 'AZURE_LOGGING_PACKAGES',     value: '' }
]
```

### 2.2 How each connection type is passed

- **DB connection info (Cosmos):** NOT a connection string. The bicep passes only the **endpoint URL + database name + container name** as plain env vars (`COSMOSDB_ENDPOINT`, `COSMOSDB_DATABASE`, `COSMOSDB_CONTAINER`). The backend authenticates with the UAMI (`AZURE_CLIENT_ID`) against the Cosmos data-plane RBAC role. No account key, no connection string.
- **Storage account:** passed as the **blob endpoint URL** (`AZURE_STORAGE_BLOB_URL = storage_account.outputs.blobEndpoint`). Again MI auth, no key.
- **AI Services / OpenAI endpoint:** `AZURE_OPENAI_ENDPOINT` (`https://${aiFoundryAiServicesResourceName}.openai.azure.com/`) and `AZURE_AI_PROJECT_ENDPOINT`. MI auth via `AZURE_CLIENT_ID` + `AZURE_COGNITIVE_SERVICES` token scope.
- **Search:** `AZURE_AI_SEARCH_ENDPOINT = ai_search.outputs.endpoint`. There is **no** `AZURE_AI_SEARCH_KEY` and the search "connection name" env var is intentionally omitted (commented in source) because MACAE uses per-KB RemoteTool connections seeded post-deploy. Search local auth is disabled (`disableLocalAuth: true`, `infra/bicep/main.bicep` line 380).

### 2.3 Secrets vs plain values — the model

- **No Azure Key Vault anywhere** in the vanilla bicep flavor. The container-app module (`infra/bicep/modules/compute/container-app.bicep`) does have an optional `secrets array?` param (line 38) and an unused `secretRef` capability, but the backend/MCP module calls **do not pass `secrets`** and **no env entry uses `secretRef`** — every value is inline.
- The single auth primitive is the **UAMI clientId** injected as `AZURE_CLIENT_ID`; the runtime's SDK (`DefaultAzureCredential` / `ManagedIdentityCredential`) uses it to obtain AAD tokens for Cosmos, Storage, Search, and OpenAI. This is the MACAE/CWYD "managed-identity + RBAC + no-Key-Vault env-var" pattern.
- App Insights is the only "secret-ish" value and it is passed in the clear as `APPLICATIONINSIGHTS_CONNECTION_STRING` / `APPLICATIONINSIGHTS_INSTRUMENTATION_KEY` env vars (sourced from `app_insights.outputs.*`).

### 2.4 MCP Container App — env array

`infra/bicep/main.bicep` lines 680-787. Same UAMI attach + `registries: isCustom ? [...] : []`. Env includes `HOST`, `PORT=9000`, `SERVER_NAME`, `ENABLE_AUTH='false'`, `TENANT_ID`, `CLIENT_ID = userAssignedIdentity.outputs.clientId`, `JWKS_URI`, `ISSUER`, `AUDIENCE = 'api://${userAssignedIdentity.outputs.clientId}'`, `AZURE_CLIENT_ID`, `AZURE_OPENAI_ENDPOINT`, `AZURE_STORAGE_BLOB_URL`, `BACKEND_URL`. All plain `value:`.

### 2.5 Frontend — App Service (not a container app)

`infra/bicep/main.bicep` lines 799-829 — `module frontend_app './modules/compute/app-service.bicep'`. The frontend is an **App Service** (Linux), not a container app, with `appSettings` map (object, not array). It conditionally runs as Python code (`isCustom`) or as a Docker image. Settings: `BACKEND_API_URL = 'https://${backend_container_app.outputs.fqdn}'`, `AUTH_ENABLED='false'`, `PROXY_API_REQUESTS='false'`, `APPLICATIONINSIGHTS_CONNECTION_STRING`, `WEBSITES_PORT`. There is **no Azure Function app** in MACAE (no function app in the bicep tree).

---

## 3. Conditional Resource Deployment

**Yes — MACAE uses conditional module deployment extensively.** The canonical idiom is `module <name> '<path>' = if (<condition>) {...}`, consumed with the `!` non-null assertion operator on the conditional module's outputs.

### 3.1 The canonical conditional-module idiom

- Router level — `infra/main.bicep` line 258 & 318:
  ```bicep
  module avmDeployment   './avm/main.bicep'   = if (isAvm)  { ... }
  module bicepDeployment './bicep/main.bicep' = if (isBicep){ ... }
  ```
- "New-vs-existing" toggle pair — `infra/bicep/main.bicep` lines 330 & 341 (the most reusable idiom):
  ```bicep
  module ai_foundry_project   './modules/ai/ai-foundry-project.bicep'  = if (!useExistingAiFoundryAiProject) { ... }
  module existing_project_setup './modules/ai/existing-project-setup.bicep' = if (useExistingAiFoundryAiProject) { ... }

  // consume with ternary + non-null assertion (!):
  var aiFoundryAiProjectPrincipalId = useExistingAiFoundryAiProject
    ? existing_project_setup!.outputs.projectIdentityPrincipalId
    : ai_foundry_project!.outputs.projectIdentityPrincipalId
  ```
- Skip-when-reusing — `infra/bicep/main.bicep` line 298:
  ```bicep
  module log_analytics './modules/monitoring/log-analytics.bicep' = if (!useExistingLogAnalytics) { ... }
  ```
- Deploy-only-for-a-flag — `infra/bicep/main.bicep` line 734 (closest analog to CWYD's need):
  ```bicep
  module container_registry './modules/compute/container-registry.bicep' = if (isCustom) { ... }
  ```

### 3.2 Consuming a conditional module's outputs

Three patterns appear:
1. **Non-null assertion** inside a ternary that already gates on the same condition (safe):
   ```bicep
   containerRegistryResourceId: isCustom ? container_registry!.outputs.resourceId : ''
   ```
2. **Conditional array build** — pass `[]` when the resource was skipped:
   ```bicep
   registries: isCustom ? [
     { server: container_registry!.outputs.loginServer, identity: userAssignedIdentity.outputs.resourceId }
   ] : []
   ```
3. **Nullable conditional output**:
   ```bicep
   output AZURE_CONTAINER_REGISTRY_ENDPOINT string? = isCustom ? container_registry!.outputs.loginServer : null
   output AZURE_CONTAINER_REGISTRY_NAME     string? = isCustom ? container_registry!.outputs.name : null
   ```

### 3.3 Conditional role-assignment loops (array + per-item `if`)

`infra/bicep/modules/identity/role-assignments.bicep` builds role assignments as a filtered loop — the idiom for "assign only when the target resource and principal exist":
```bicep
resource workloadStorageContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in workloadPrincipals: if (!empty(storageAccountResourceId) && !empty(principalId)) {
  name: guid(solutionName, storageAccountResourceId, principalId, roleDefinitions.storageBlobDataContributor)
  scope: storageAccount
  properties: { ... }
}]
```
The referenced resources are declared with `existing = if (!empty(<id>))`:
```bicep
resource storageAccount 'Microsoft.Storage/storageAccounts@2025-08-01' existing = if (!empty(storageAccountResourceId)) {
  name: last(split(storageAccountResourceId, '/'))
}
```

### 3.4 IMPORTANT caveat for the CWYD use case

**MACAE does NOT conditionally deploy Azure AI Search.** The `ai_search` module (`infra/bicep/main.bicep` line 370) is **unconditional** — MACAE always deploys both Cosmos DB and AI Search. So MACAE has no direct "deploy Search only when `databaseType == cosmosdb`" precedent.

However, the **idiom CWYD v2 needs is exactly the `isCustom` container-registry pattern** above (§3.1 line 734) — a single `module ai_search '...' = if (databaseType == 'cosmosdb') { ... }`, then consume its outputs with `databaseType == 'cosmosdb' ? ai_search!.outputs.endpoint : ''` and emit nullable outputs `string? = databaseType == 'cosmosdb' ? ai_search!.outputs.endpoint : null`. The Search-related role assignments would naturally drop out because `aiSearchResourceId` would be `''` and the `existing = if (!empty(aiSearchResourceId))` + per-item `if (!empty(aiSearchResourceId) ...)` guards already short-circuit (the role-assignments module is built to tolerate empty resource IDs).

Azure/AVM convention note: the `string?` nullable-output + `module = if (...)` + `<module>!.outputs.<x>` non-null-assertion trio is the standard Bicep idiom for optional resources; AVM modules follow the same pattern. The per-resource `existing = if (!empty(id))` guard plus filtered `[for x in arr: if (cond) {...}]` loops are the idiomatic way to make a shared RBAC module tolerate optional/absent target resources.

---

## 4. Post-Provision / Post-Deploy Hooks

### 4.1 `azure.yaml` hooks (exact inventory)

`data/sample_code/macae/azure.yaml` declares **exactly one hook: `postdeploy`** (lines 7-70). There is **no** `postprovision`, `predeploy`, or `prepackage` hook. Both OS variants are present:
- `hooks.postdeploy.windows` — `shell: pwsh`, `interactive: true` (lines 8-49). It does **not run the seeding itself** — it detects Git-Bash vs PowerShell and **prints instructions** telling the user to manually run `infra/scripts/post-provision/post_deploy.sh` (bash) or `infra\scripts\post-provision\post_deploy.ps1` (pwsh), then prints the frontend URL `https://$env:webSiteDefaultHostname`.
- `hooks.postdeploy.posix` — `shell: sh`, `interactive: true` (lines 50-70). Same — prints the bash command + frontend URL.

So the data-seeding is **manual/interactive** in MACAE (the azd hook only advertises the command). The frontend hostname comes from the `webSiteDefaultHostname` deployment output exported into the hook env (`$env:webSiteDefaultHostname` / `$webSiteDefaultHostname`).

There is also a sibling `data/sample_code/macae/azure_custom.yaml` (the `isCustom` build-from-source variant) — not the default; not analyzed in depth here.

### 4.2 The actual seeding script — `post_deploy.sh` / `post_deploy.ps1`

`infra/scripts/post-provision/post_deploy.sh` (cross-OS twin: `post_deploy.ps1`). This is the real data-upload + index + KB-creation engine. Flow of `main()` (lines 643-908):

1. **Auth + subscription** — `az account show` / `az login`; `select_subscription()` resolves `AZURE_SUBSCRIPTION_ID` from `azd env get-value`.
2. **Resolve resource values** — `get_values_from_azd_env` → fallback `get_values_from_az_deployment` → fallback `get_values_using_solution_suffix` (naming convention). Resolves `backend_url`, `storage_account`, `ai_search`, `ai_search_endpoint`, `openai_endpoint`, `project_endpoint`, `ai_foundry_resource_id`.
3. **`select_use_case()`** — interactive menu (1=RFP, 2=Retail, 3=HR, 4=Marketing, 5=Contract, 6=Content-Gen, 7=All).
4. **WAF/private-networking routing** — if the backend container app has internal ingress / IP restrictions / `PROXY_API_REQUESTS=true`, it routes API calls through the frontend App Service proxy instead of the backend FQDN.
5. **`ensure_role_assignments_for_kbmcp()`** (lines 386-417) — grants the **signed-in user** the Foundry User role (`53ca6127-...`) on the AI Foundry resource via `az role assignment create`, then `sleep 60` for propagation. This is a **runtime RBAC grant performed by the script** (needed for KB MCP connection creation).
6. **`enable_public_access_if_waf()`** — for WAF deployments, temporarily flips Storage / Search / Foundry `publicNetworkAccess` to Enabled (with retry polling), and an `EXIT` trap `restore_network_access` flips them back. Lets the developer machine reach private resources during seeding.
7. **`activate_python_env()`** — creates/uses a venv at `infra/scripts/post-provision/scriptenv`, `pip install -r requirements.txt`.
8. **Per-use-case seeding** (lines 764-880).

### 4.3 Data-upload mechanism (the part CWYD v2 needs)

This is the canonical "upload sample data + build index" approach:

- **Content packs** live under `content_packs/<usecase>/` (e.g. `content_packs/rfp_evaluation`, `content_packs/retail_customer`, `content_packs/contract_compliance`, `content_packs/content_gen`). Each pack has a `pack.json` manifest with three list types: `blob_indexes`, `blob_uploads`, `search_indexes`.
- **`deploy_content_pack()`** (lines 419-520) parses `pack.json` with an inline Python snippet, then for each item:
  - `BLOB_INDEX` / `BLOB_UPLOAD`: `az storage container create ... --auth-mode login` then **`az storage blob upload-batch --account-name "$storage_account_name" --destination "$container" --source "$pack_path/$source" --auth-mode login --pattern "$pattern" --overwrite`**. (Uses AAD/MI auth — `--auth-mode login` — relying on the deployer's Storage Blob Data Contributor role from §1.4 #14.)
  - `BLOB_INDEX` / `SEARCH_INDEX`: builds the AI Search index with **`run_python "scripts/post-provision/index_datasets.py" <storage_account> <container> <ai_search_name> <index_name>`**.
- **`upload_team_config()`** (lines 522-535) → `run_python "scripts/post-provision/upload_team_config.py" <backend_url> <team_config_dir> <user_principal_id> <team_id>` — POSTs agent-team JSON configs to the backend REST API (`/api/v4/team_configs/{team_id}`) with retry/backoff for cold starts.
- **Vector stores + Foundry IQ Knowledge Bases** (lines 826-878), only when the use case `uses_data`:
  - `run_python "scripts/post-provision/seed_vector_stores.py" --only "<csv>"`
  - `run_python "scripts/post-provision/seed_knowledge_bases.py" --only "<csv>"`
  - `run_python "scripts/post-provision/seed_kb_connections.py" --only "<csv>"`
  - The KB/vector-store names are hard-coded per use case in `vector_store_map` / `kb_map` bash assoc-arrays (lines 833-846).

### 4.4 Seed-script summaries (what each Python helper does)

- `infra/scripts/post-provision/index_datasets.py` — uses `AzureCliCredential` + `azure.search.documents` (`SearchIndexClient`, `SearchClient`) + `azure.storage.blob.BlobServiceClient`. Reads blobs from a container, extracts text (PDF via PyPDF2, DOCX via python-docx), creates an AI Search index (`SearchIndex` with `SimpleField`/`SearchableField`), and uploads documents. Auth = AAD (no admin key).
- `infra/scripts/post-provision/upload_team_config.py` — pure `requests`-based REST client. `check_team_exists()` GETs `/api/v4/team_configs/{team_id}`; uploads agent-team JSON to the backend. Retry/backoff (`request_with_retry`, status 408/429/5xx).
- `infra/scripts/post-provision/seed_knowledge_bases.py` — creates Foundry IQ Knowledge Bases on Azure AI Search via `httpx` + `DefaultAzureCredential` (token scope `https://search.azure.com/.default`). Idempotent (PUT semantic configs; create knowledge sources + KB only on 409-skip). Requires indexes to already exist and the search MI to have Cognitive Services OpenAI User on AI Services. Reads `AZURE_AI_SEARCH_ENDPOINT` / `AZURE_OPENAI_ENDPOINT` from env (exported by `post_deploy.sh`) or `src/backend/.env`.
- `infra/scripts/post-provision/seed_vector_stores.py`, `seed_kb_connections.py` — companion seeders for vector stores and per-KB RemoteTool MCP connections (ProjectManagedIdentity auth).

**Takeaway for CWYD v2:** MACAE's data-upload pattern = (a) ship sample files in-repo under `content_packs/`, (b) a cross-OS post-provision script (`.sh` + `.ps1`) that `az storage blob upload-batch --auth-mode login` uploads them, then (c) a Python indexer that builds the AI Search index with AAD auth, relying on the **deployer** having Storage Blob Data Contributor + Search Service/Index Contributor roles (granted in bicep §1.4 rows 12-14). MACAE advertises this through the azd `postdeploy` hook but runs it interactively/manually rather than fully automating it.

---

## 5. Main Outputs (azd → `.env`)

These are the coalesced outputs from `infra/main.bicep` (router) which mirror `infra/bicep/main.bicep` lines 849-998. azd writes each `output AZURE_* string` to `.azure/<env>/.env` and the app consumes them.

```bicep
// infra/main.bicep (router) — coalesced; values shown are the bicep-flavor source
output resourceGroupName string                  // resourceGroup().name
output webSiteDefaultHostname string             // frontend host (https stripped)

// Storage
output AZURE_STORAGE_BLOB_URL string             // storage_account.outputs.blobEndpoint
output AZURE_STORAGE_ACCOUNT_NAME string         // storageAccountName

// Azure AI Search
output AZURE_AI_SEARCH_ENDPOINT string           // ai_search.outputs.endpoint
output AZURE_AI_SEARCH_NAME string               // aiSearchServiceName
output AZURE_SEARCH_ENDPOINT string              // alias of AZURE_AI_SEARCH_ENDPOINT (back-compat)

// Cosmos DB
output COSMOSDB_ENDPOINT string                  // https://${cosmosDbResourceName}.documents.azure.com:443/
output COSMOSDB_DATABASE string                  // cosmosDbDatabaseName ('macae')
output COSMOSDB_CONTAINER string                 // cosmosDbDatabaseMemoryContainerName ('memory')
output COSMOSDB_ACCOUNT_NAME string              // cosmosDbResourceName

// Azure OpenAI / Foundry
output AZURE_OPENAI_ENDPOINT string              // aiFoundryOpenAIEndpoint
output AZURE_OPENAI_DEPLOYMENT_NAME string       // gptModelName
output AZURE_OPENAI_RAI_DEPLOYMENT_NAME string   // gpt4_1ModelName
output AZURE_OPENAI_API_VERSION string           // azureOpenaiAPIVersion
output AZURE_AI_SUBSCRIPTION_ID string           // subscription().subscriptionId
output AZURE_AI_RESOURCE_GROUP string            // resourceGroup().name
output AZURE_AI_PROJECT_NAME string              // aiFoundryAiProjectResourceName
output AI_FOUNDRY_RESOURCE_ID string             // existing-or-new project resourceId
output AZURE_AI_PROJECT_ENDPOINT string          // aiFoundryAiProjectEndpoint
output AZURE_AI_AGENT_ENDPOINT string            // alias of project endpoint (agent SDK back-compat)
output AI_SERVICE_NAME string                    // aiFoundryAiServicesResourceName
output ORCHESTRATOR_MODEL_NAME string            // gptReasoningModelName
output SUPPORTED_MODELS string                   // string(supportedModels) (JSON list)

// Identity / auth
output AZURE_CLIENT_ID string                    // userAssignedIdentity.outputs.clientId  (UAMI auth handle)
output AZURE_TENANT_ID string                    // tenant().tenantId
output AZURE_COGNITIVE_SERVICES string           // 'https://cognitiveservices.azure.com/.default'

// App / runtime
output APP_ENV string                            // 'Prod'
output BACKEND_URL string                        // 'https://${backend_container_app.outputs.fqdn}'

// MCP server
output MCP_SERVER_NAME string                    // mcpServerName ('MacaeMcpServer')
output MCP_SERVER_DESCRIPTION string             // mcpServerDescription

// Per-dataset container + index names (bicep flavor only; not all surfaced by router)
output AZURE_STORAGE_CONTAINER_NAME_* string     // retail/RFP/contract container names
output AZURE_AI_SEARCH_INDEX_NAME_* string       // retail/RFP/contract index names

// Container Registry (nullable — only when isCustom)
output AZURE_CONTAINER_REGISTRY_ENDPOINT string? // isCustom ? container_registry!.outputs.loginServer : null
output AZURE_CONTAINER_REGISTRY_NAME     string? // isCustom ? container_registry!.outputs.name : null
```

The seed scripts specifically consume: `AZURE_SUBSCRIPTION_ID`, `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_OPENAI_ENDPOINT`, `AZURE_AI_PROJECT_ENDPOINT`, `webSiteDefaultHostname`, `BACKEND_URL` (via `azd env get-value`).

---

## 6. Key takeaways for fixing CWYD v2 infra

1. **Grant the runtime identity all data-plane roles it needs**, mirroring MACAE §1.4 rows 2,3,6,7,8,9,16: Foundry User + OpenAI Contributor (AI Foundry), Search Index Data Contributor + Search Service Contributor (Search), Storage Blob Data Contributor (Storage), Cosmos Built-in Data Contributor (data-plane SQL role), AcrPull (registry). **Also grant the deployer** the same Storage/Search/Cosmos roles if a post-provision script will seed data as the signed-in user.
2. **Env-var wiring = endpoints + names + `AZURE_CLIENT_ID`, all plain `value:`** — no Key Vault, no connection strings, no `secretRef`. Pass `COSMOSDB_ENDPOINT`/`COSMOSDB_DATABASE`/`COSMOSDB_CONTAINER`, `AZURE_STORAGE_BLOB_URL`, `AZURE_OPENAI_ENDPOINT`, `AZURE_AI_SEARCH_ENDPOINT`, and the UAMI `clientId` as `AZURE_CLIENT_ID`.
3. **Conditional AI Search** → use `module ai_search '...' = if (databaseType == 'cosmosdb') { ... }`, consume with `databaseType == 'cosmosdb' ? ai_search!.outputs.endpoint : ''`, emit `string?` nullable outputs, and let the existing `existing = if (!empty(id))` + filtered `[for ...: if (!empty(id) ...)]` RBAC guards drop the Search role assignments automatically. (MACAE's `isCustom` container-registry block at `infra/bicep/main.bicep` line 734 is the exact template.)
4. **Post-provision sample-data upload** → ship files in-repo, add a cross-OS `.sh`+`.ps1` that `az storage blob upload-batch --auth-mode login` uploads + a Python indexer that builds the index with `AzureCliCredential`/`DefaultAzureCredential`. MACAE wires it via the azd `postdeploy` hook but runs it interactively; CWYD can choose to fully automate it inside the hook instead of just printing the command.

---

## 7. Clarifying questions

- CWYD v2 needs Search deployed **only when `databaseType == cosmosdb`** — confirm the inverse case (pgvector) should deploy **no** AI Search resource at all (so all Search role-assignments + Search outputs must be conditional/nullable). MACAE always deploys Search, so there is no exact precedent for the "skip Search entirely" branch; the idiom in §3 is the closest reference.
- Should CWYD's post-provision data upload be **fully automated inside the azd `postprovision`/`postdeploy` hook** (run the script), or follow MACAE's **print-the-command, run-manually** convention? MACAE chose manual/interactive (use-case menu + WAF network toggling). CWYD's stated need ("a post-provision step that uploads sample data files") suggests full automation is preferred.

## 8. Recommended next research (not completed here)

- [ ] Read CWYD v2's current `v2/infra/main.bicep` + module tree to diff against this MACAE baseline (which exact role grants / outputs are missing).
- [ ] Inspect `infra/avm/main.bicep` (AVM flavor) if CWYD v2 standardizes on AVM modules — the conditional/RBAC idioms differ slightly (AVM modules expose `roleAssignments` params).
- [ ] Read a sample `content_packs/*/pack.json` to capture the exact manifest schema (`blob_indexes`/`blob_uploads`/`search_indexes` fields) if CWYD adopts the same content-pack format.
- [ ] Read `infra/bicep/modules/data/storage-account.bicep` + `ai-search.bicep` to confirm `allowSharedKeyAccess=false` / `disableLocalAuth=true` posture if CWYD wants to match the keyless stance.
