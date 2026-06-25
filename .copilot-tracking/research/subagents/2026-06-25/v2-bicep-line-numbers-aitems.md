# Research: v2 Bicep line numbers for A1–A12 remediation + frontend host change

Status: Complete

Scope: READ-ONLY location research grounding a plan that back-ports ~12 manual
`az`-override fixes (A1–A12) plus a frontend host change into durable Bicep.
No code proposed — only exact locations + current text + a one-line "must change" note.

Files examined (all under `v2/infra/`):

- `v2/infra/main.bicep` (2475+ lines)
- `v2/infra/modules/ai-project-search-connection.bicep`
- `v2/infra/modules/ai-project.bicep`
- `v2/infra/main.parameters.json`

Note on the ACR: there is NO `v2/infra/modules/container_registry.bicep`. The ACR is an
INLINE AVM module call inside `main.bicep` (`avm/res/container-registry/registry:0.12.1`).
`v2/infra/modules/` contains only `ai-project-search-connection.bicep`, `ai-project.bicep`,
and `virtualNetwork.bicep`.

---

## Key structural anchors (env arrays + module spans)

Backend Container App module `backendContainerApp` — `main.bicep`:

- Module call start: line 1695 (`module backendContainerApp 'br/public:avm/res/app/container-app:0.22.1' = {`)
- `managedIdentities.userAssignedResourceIds`: lines 1703–1707
- `containers[0].image`: line 1729
- `env: union(` open: line 1739
- Static env array `[ ... ]` body: lines 1740–1827 (closes `],` at line 1827)
- `enableMonitoring ? [...] : []` ternary tail: lines 1828–1842
- `union(...)` close `)`: line 1843; container `}` 1844; `containers ]` 1845; `params }` 1846; module `}` 1847
- NO `registries:` property anywhere in this module (confirmed by repo-wide grep — zero matches).

Function App module `functionApp` — `main.bicep`:

- Module call start: line 2023 (`module functionApp 'br/public:avm/res/web/site:0.22.0' = {`)
- `kind: 'functionapp,linux'`: line 2030
- `functionAppConfig:` open: line 2055
- `scaleAndConcurrency:` block: lines 2070–2073 (`maximumInstanceCount`, `instanceMemoryMB` only)
- `siteConfig:` open: line 2075
- `appSettings: union(` open: line 2089
- Static appSettings array `[ ... ]` body: lines 2090–2125 (closes `],` at line 2125)
- `enableMonitoring ? [...] : []` ternary tail: lines 2126–2134
- `union(...)` close `)`: line 2135; siteConfig `}` 2136; params `}` 2137; module `}` 2138

---

## A1 — AI Services endpoint env var + Cognitive Services User RBAC

`AZURE_AI_SERVICES_ENDPOINT` exists ONLY as a template OUTPUT — it is NOT bound as a
backend Container App env var nor a function appSetting.

- File `v2/infra/main.bicep` line 2359:
  ```bicep
  output AZURE_AI_SERVICES_ENDPOINT string = aiServices.outputs.endpoint
  ```
  (description on line 2358; the backend env block instead binds `AZURE_AI_PROJECT_ENDPOINT`
  at line 1782 and `AZURE_OPENAI_ENDPOINT` at line 1783 — there is NO `AZURE_AI_SERVICES_ENDPOINT`
  env entry in either the backend env array 1740–1827 or the function appSettings array 2090–2125).
  Must change: add an `AZURE_AI_SERVICES_ENDPOINT` env entry (value `aiServices.outputs.endpoint`)
  into the backend env array (and function appSettings if the indexing pipeline needs it).

AI Services / Foundry account RBAC — `aiServices` AVM module (`cognitive-services/account:0.13.0`,
module start line 511):

- `roleAssignments: [` for `aiServices`: line 582
- Line 587: `roleDefinitionIdOrName: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'` (Cognitive Services OpenAI User → UAMI)
- Line 593: `roleDefinitionIdOrName: '53ca6127-db72-4b80-b1b0-d745d6d5456d'` (Azure AI User → UAMI)
- The `Cognitive Services User` role `a97b65f3-24c7-4388-baec-2e87135dc908` is NOT assigned on the
  AI Services / Foundry account. Confirmed: `a97b65f3` appears exactly ONCE in the whole file.

`Cognitive Services User` (`a97b65f3-...`) is currently assigned ONLY on the Content Safety account:

- `cogContentSafety` AVM module (start line 817), `roleAssignments: [` line 841:
  - Line 847: `roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908'` (scope = Content Safety account,
    principal = UAMI). Comment at 845–846 ties it to the AnalyzeText data-plane call.
  Must change (if A1 needs it): add a `Cognitive Services User` (`a97b65f3-...`) role assignment for the
  UAMI on the AI Services / Foundry account `aiServices.roleAssignments` (line 582 array).

Side note (not A1 but adjacent): two standalone role assignments at lines 1008–1025 grant the SEARCH
service / reused-OpenAI system MI `Cognitive Services OpenAI User` (`5e0bd9bd-...`) on the AI Services
account for integrated vectorization. Distinct from the workload UAMI grants above.

---

## A2 — Function `scaleAndConcurrency` / `alwaysReady`

- File `v2/infra/main.bicep`, `functionApp` module (start 2023), `functionAppConfig` (line 2055):
  ```bicep
        scaleAndConcurrency: {          // line 2070
          maximumInstanceCount: enableScalability ? 100 : 40   // line 2071
          instanceMemoryMB: 2048                                // line 2072
        }                                                       // line 2073
  ```
  There is NO `alwaysReady: [...]` array inside `scaleAndConcurrency`. The plan SKU is Flex
  Consumption (`functionsPlanSkuName = 'FC1'`, var at line ~1998; `functionPlan` module start 2005).
  Must change: add an `alwaysReady` array (e.g. `[{ name: 'blob', instanceCount: 1 }]` or per-group)
  inside `scaleAndConcurrency` at line 2070.

---

## A3 — Function host.json / queue `messageEncoding` app setting

- File `v2/infra/main.bicep`, function `appSettings: union([ ... ])` (open line 2089).
- Present runtime knobs: `AzureWebJobsStorage__accountName/__credential/__clientId` (lines ~2091–2093),
  `FUNCTIONS_EXTENSION_VERSION` = `'~4'` (line ~2098).
- There is NO `AzureFunctionsJobHost__extensions__queues__messageEncoding` app setting anywhere
  (repo-wide grep for `messageEncoding` returned zero matches).
- No `host.json` reference is wired through Bicep; `host.json` ships in the function package
  (`v2/src/functions/`), not the infra.
  Must change: add `{ name: 'AzureFunctionsJobHost__extensions__queues__messageEncoding', value: 'base64' }`
  (or the desired value) into the static appSettings array (lines 2090–2125), OR set it via `host.json`
  in `v2/src/functions/` — confirm which surface the manual `az` fix used (app setting vs host.json).

---

## A4 — AI Search connection name env + CognitiveSearch connection + `cwyd-kb-mcp` RemoteTool + project Search Service Contributor

Backend env `AZURE_AI_SEARCH_CONNECTION_NAME` — `main.bicep`:

- Line 1792:
  ```bicep
  { name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: databaseType == 'cosmosdb' ? aiProjectSearchConnection!.outputs.name : '' }
  ```
  (No function-env equivalent — this env var is backend-only.)

Foundry Project ↔ Search `CognitiveSearch` connection:

- Declared in `v2/infra/modules/ai-project-search-connection.bicep`, resource `connection`
  (`Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview`), lines 39–57:
  - `category: 'CognitiveSearch'` (line 43), `authType: 'AAD'` (line 45), `isSharedToAll: true` (line 46),
    `target: 'https://${searchServiceName}.search.windows.net'` (line 44).
  - `connectionName` param default = `'search-${searchServiceName}'` (line 25).
- Invoked from `main.bicep` line 1037:
  ```bicep
  module aiProjectSearchConnection 'modules/ai-project-search-connection.bicep' = if (databaseType == 'cosmosdb') {
  ```
  (gated to cosmosdb mode; module call lines 1037–1045).

`cwyd-kb-mcp` RemoteTool connection: NOT FOUND. Repo-wide grep across `v2/infra/**` for
`cwyd-kb-mcp`, `RemoteTool`/`remoteTool`, `McpTool` returned zero matches in Bicep. The only
Project connection declared is the `CognitiveSearch` one above. This is a gap the plan must fill
(declare a `RemoteTool`/MCP-category project connection named `cwyd-kb-mcp`, likely a sibling
resource in `ai-project-search-connection.bicep` or a new module).

Project-MI roles on the Search service — `aiSearch` AVM module (`search/search-service:0.12.0`,
start line 881), `roleAssignments: [` line 904:

- Line 909: `'8ebe5a00-799e-43f5-93ac-243d3dce84a7'` — Search Index Data Contributor → UAMI
- Line 914: `'7ca78c08-252a-4471-8644-bb5ff32d4ba0'` — Search Service Contributor → UAMI (UAMI only)
- Line ~927: `'1407120a-92aa-4202-b7e9-c0e197c71c8f'` — Search Index Data Reader → `aiProject.outputs.projectPrincipalId`
  (the Project system MI). This is the ONLY role the Project MI gets on Search.
- The Project MI does NOT currently get `Search Service Contributor` (`7ca78c08-...`).
  Must change (if A4 requires it): add a `Search Service Contributor` (and/or `Search Index Data
  Contributor`) role assignment for `aiProject.outputs.projectPrincipalId` inside the `aiSearch`
  `roleAssignments` array (line 904) so Foundry IQ / the Project can build/manage the KB + index.

`projectPrincipalId` is produced by `v2/infra/modules/ai-project.bicep` output `projectPrincipalId`
(`project.identity.principalId`). The Project MI's only other grant is `Azure AI User` on the
project scope (ai-project.bicep `projectAiUserRole`, lines ~64–78).

---

## A5 — Event Grid system topic + subscription + queue-sender role

`main.bicep`:

- Event Grid system-topic AVM module (`event-grid/system-topic:0.6.4`):
  ```bicep
  module eventGridSystemTopic 'br/public:avm/res/event-grid/system-topic:0.6.4' = if (!useExistingEventGridTopic) {   // line 2180
    name: take('avm.res.event-grid.system-topic.${solutionSuffix}', 64)                                              // line 2181
  ```
  Module call body: lines 2180–2227.
- The `blob-created-to-doc-processing` subscription is declared INSIDE the AVM module's
  `eventSubscriptions:` array (NOT a standalone `Microsoft.EventGrid/systemTopics/eventSubscriptions`
  resource for the new-topic path):
  - `eventSubscriptions: [` open: line 2192
  - `name: 'blob-created-to-doc-processing'`: line 2198
  - Delivery: `deliveryWithResourceIdentity` (SystemAssigned) → `StorageQueue` `blob-events` (lines ~2201–2213).
  - Filter `BlobCreated`+`BlobDeleted`, `subjectBeginsWith` documents container, retry 30/1440 (lines ~2214–2225).
- `eventGridQueueSenderRole` (Storage Queue Data Message Sender):
  ```bicep
  resource eventGridQueueSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingEventGridTopic) {   // line 2234
  ```
  Body lines 2234–2247. Role GUID via var `storageQueueDataMessageSenderRoleId =
  'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a'` (var declared line ~2003). Scope = storage account
  (`storageAccountExisting`); principal = topic system MI (`eventGridSystemTopic!.outputs.systemAssignedMIPrincipalId`).

`useExistingEventGridTopic` branch (v1-reuse path) — present:

- `existingEventGridTopic` existing ref: line ~2268 (`if (useExistingEventGridTopic)`).
- `existingQueueMessageSenderRole` (account-scope Queue Data Message Sender → UAMI): line ~2256.
- STANDALONE subscription resource on the existing topic:
  ```bicep
  resource existingEventGridSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2024-12-15-preview' = if (useExistingEventGridTopic) {   // line 2274
    parent: existingEventGridTopic
    name: 'cwyd2-blob-created-doc-processing'
  ```
  Uses `deliveryWithResourceIdentity` UserAssigned (UAMI), same filter/retry as the new-topic sub.

Must change: depends on what the manual A5 fix corrected (e.g. event types, subjectBeginsWith
prefix, queue target, retry policy, or the role principal). All edit points are the
`eventSubscriptions[0]` block (line 2192) for the new-topic path, the `existingEventGridSubscription`
resource (line 2274) for the reuse path, and the two queue-sender role resources (2234 / 2256).

---

## A6 — Function storage account public network access / networkRuleSet

There is ONE shared storage account (`st<suffix>`) used for Function WebJobs storage + documents
container + indexing queues. No separate function-only storage account.

`main.bicep`:

- Storage account var name: `storageAccountName = take(replace('st${solutionSuffix}', '-', ''), 24)` (line ~1056)
- Module:
  ```bicep
  module storageAccount 'br/public:avm/res/storage/storage-account:0.32.0' = if (!useExistingStorage) {   // line 1060
  ```
  - `allowBlobPublicAccess: false` (line 1070)
  - `allowSharedKeyAccess: false` (line 1071)
  - `publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'` (line 1072)
- There is NO `networkAcls` / `networkRuleSet` / `defaultAction` property in this module call
  (repo-wide grep for `networkAcls` returned zero matches in `main.bicep`). Public network access
  is governed solely by `publicNetworkAccess` gated on `enablePrivateNetworking`.
- `enablePrivateNetworking` param: line 224 (`param enablePrivateNetworking bool = false`), default `false`
  → so by default `publicNetworkAccess = 'Enabled'`.

Must change: if A6 added a `networkAcls`/`networkRuleSet` with `defaultAction` (or flipped
`publicNetworkAccess`), add the corresponding property to the `storageAccount` module params
(lines 1062–1110). Confirm whether the manual fix opened access (defaultAction `Allow` / bypass
`AzureServices`) or restricted it.

---

## A7 — `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` env on backend + function

`main.bicep`:

- Backend env, line 1794:
  ```bicep
  { name: 'AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME', value: databaseType == 'postgresql' ? postgresAdminPrincipalName : '' }
  ```
- Function env, line 2120 (identical expression):
  ```bicep
  { name: 'AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME', value: databaseType == 'postgresql' ? postgresAdminPrincipalName : '' }
  ```
- Output, line 2438 (same expression).

Current VALUE source = the `postgresAdminPrincipalName` PARAM (the deploying Entra principal's
display name / UPN):

- `param postgresAdminPrincipalName string = ''` — line 1441 (description: "Display name (UPN, group
  name, or app name) of the Entra principal … used by the post-provision script to log in over AAD").
- Mapped in `main.parameters.json` to `${AZURE_ENV_POSTGRES_ADMIN_PRINCIPAL_NAME}` (no default).

It is NOT `id-${solutionSuffix}`. However, the Postgres server's `administrators` array
UNCONDITIONALLY registers the workload UAMI as an admin with `principalName: 'id-${solutionSuffix}'`
(`postgresServer` module, line 1497) — and the runtime (backend + function) authenticates to
Postgres AS the UAMI. So the env var the RUNTIME logs in with should be the UAMI principal name
(`id-${solutionSuffix}`), not the deployer's UPN.

Must change: set the backend (1794) and function (2120) `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME`
values to `'id-${solutionSuffix}'` (the UAMI principal name the runtime connects as) rather than
the deployer `postgresAdminPrincipalName`. (This matches the manual `az` override pattern of
pointing the runtime login user at the UAMI.)

---

## A8 — `ORCHESTRATOR` env var

`main.bicep`:

- Backend env, line 1810:
  ```bicep
  { name: 'ORCHESTRATOR', value: 'agent_framework' }
  ```
  (preceded by comment "// Default orchestrator (runtime-switchable per request)" line 1809).
- There is NO `CWYD_ORCHESTRATOR_NAME` env var anywhere (repo-wide grep returned zero matches).
- This env var is backend-only (no function-env equivalent).

Must change: if the backend now reads `CWYD_ORCHESTRATOR_NAME` (per the `CWYD_*` prefix convention),
rename the env key at line 1810 from `ORCHESTRATOR` to `CWYD_ORCHESTRATOR_NAME` (value unchanged
`agent_framework`). Confirm which key the backend settings class actually reads.

---

## A9 — `AZURE_ENVIRONMENT` env var (backend + function)

`main.bicep`:

- Backend env, line 1753: `{ name: 'AZURE_ENVIRONMENT', value: 'production' }` (comment block 1746–1752
  explains the fail-closed admin-auth rationale).
- Function env, line 2100: `{ name: 'AZURE_ENVIRONMENT', value: 'production' }` (comment 2099).

Value `'production'` IS already wired on BOTH runtimes. A9 appears ALREADY SATISFIED in Bicep — no
change needed unless the plan wants to template it (note: per the user memory directive, the code
DEFAULT must stay dev/local and only the deployed env var flips to production — which is exactly
the current pattern: settings default `local`, Bicep pins `production`).

---

## A10 — ACR `azureADAuthenticationAsArmPolicy`

The ACR is the inline AVM module in `main.bicep` (there is no `container_registry.bicep` module file):

```bicep
module containerRegistry 'br/public:avm/res/container-registry/registry:0.12.1' = {   // line 1674
  name: take('avm.res.container-registry.registry.${solutionSuffix}', 64)              // line 1675
  params: {
    name: containerRegistryName
    location: location
    tags: allTags
    enableTelemetry: false
    acrSku: 'Basic'                          // line 1681
    acrAdminUserEnabled: false               // line 1682
    publicNetworkAccess: 'Enabled'           // line 1683
    networkRuleSetDefaultAction: 'Allow'     // line 1684
    roleAssignments: [                       // line 1685  (AcrPull 7f951dda → UAMI, line 1688)
      ...
    ]
  }
}
```

- There is NO `policies:` property in this module call (repo-wide grep for `policies:` and
  `azureADAuthenticationAsArmPolicy` returned zero matches in `main.bicep`).
- The AVM `container-registry/registry:0.12.1` module exposes an optional `policies` object param.
  To enable AAD-as-ARM auth, the plan adds (inside `params`, alongside lines 1681–1684):
  `policies: { azureADAuthenticationAsArmPolicy: { status: 'enabled' } }`.
  VERIFY the exact nested key/shape against AVM `container-registry/registry` v0.12.1 docs during
  planning (the param is `policies`; the documented nested key is `azureADAuthenticationAsArmPolicy.status`
  with allowed values `'enabled' | 'disabled'`).

Must change: add the `policies.azureADAuthenticationAsArmPolicy.status = 'enabled'` param to the
`containerRegistry` module (line 1674), so token-based ARM auth is enabled durably.

---

## A11 — `backendContainerApp` `registries:` property + acrPull wiring

`main.bicep`, `backendContainerApp` AVM module (`app/container-app:0.22.1`):

- Module call: lines 1695–1847.
- `managedIdentities.userAssignedResourceIds` → UAMI: lines 1703–1707.
- NO `registries:` property is present (repo-wide grep for `registries:` returned zero matches).
- ACR pull authorization: the UAMI is granted `AcrPull` (`7f951dda-4ed3-4680-a7ca-43fe172d538d`) on
  the registry via `containerRegistry.roleAssignments` (line 1685, role GUID line 1688). But without
  a `registries:` block on the Container App, ACA does not know to authenticate the pull with that
  UAMI — it falls back to anonymous/MCR.

Must change: add a `registries: [{ server: containerRegistry.outputs.loginServer, identity:
userAssignedIdentity.outputs.resourceId }]` property to the `backendContainerApp` module params
(inside the module body 1695–1847) so the Container App pulls the real backend image from ACR using
the UAMI. (Pairs with the backend-image change below.)

---

## Backend image reference

`main.bicep`:

- `containers[0].image`, line 1729:
  ```bicep
  image: 'mcr.microsoft.com/k8se/quickstart:latest'
  ```
  (comment 1726–1728: "Placeholder image. Replaced by `azd deploy` …"). This is the MCR placeholder.

Must change: point to the ACR-hosted backend image (e.g. `'${containerRegistry.outputs.loginServer}/backend:latest'`)
so the deployed app runs the real backend rather than the k8se quickstart placeholder — coupled with
the A11 `registries:` block.

---

## Frontend `Microsoft.Web/sites` resource + `linuxFxVersion` (frontend host change)

`main.bicep`, `frontendWebApp` AVM module (`web/site:0.22.0`):

- Module call: line 1892 (`module frontendWebApp 'br/public:avm/res/web/site:0.22.0' = {`)
- `kind: 'app,linux,container'`: line 1898
- `serverFarmResourceId: appServicePlan.outputs.resourceId` (App Service Plan `asp-<suffix>`,
  `appServicePlan` module start ~1875, plan var `appServicePlanName` line 1864).
- `siteConfig:` open: line 1921
- `linuxFxVersion`, line 1925:
  ```bicep
  linuxFxVersion: 'DOCKER|mcr.microsoft.com/appsvc/staticsite:latest'
  ```
  (comment 1922–1924: "Placeholder image …"). This is the DOCKER placeholder.
- `appSettings: union([...])` open line ~1935; sets `VITE_BACKEND_URL` (line ~1942) and
  `WEBSITES_ENABLE_APP_SERVICE_STORAGE='false'` (line ~1950).

Must change: per the "frontend host change" goal — either (a) repoint `linuxFxVersion` (line 1925)
to the ACR-hosted frontend image (`'DOCKER|${containerRegistry.outputs.loginServer}/frontend:latest'`)
and add ACR-pull/registry wiring, OR (b) move the frontend off App Service onto a second ACA
Container App (matching the backend hosting model). Confirm the intended target host with the plan
owner — this is a structural decision (Hard Rule #10).

---

## ACR module + `AZURE_CONTAINER_REGISTRY_ENDPOINT` output + `databaseType` param

- `databaseType` param: line 88 (`param databaseType string = 'cosmosdb'`, `@allowed['cosmosdb','postgresql']`).
- ACR module: `containerRegistry` inline AVM `container-registry/registry:0.12.1`, line 1674 (see A10).
- `AZURE_CONTAINER_REGISTRY_ENDPOINT` output, line 2472:
  ```bicep
  output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
  ```
  (plus `AZURE_CONTAINER_REGISTRY_NAME` output line ~2475 — diagnostic).

---

## `main.parameters.json` — current params + image/registry presence

All params are azd env-var mapped (`${AZURE_ENV_*}` with inline defaults). Full list:

`solutionName`, `solutionUniqueText`, `location`, `azureAiServiceLocation`, `databaseType`
(`=cosmosdb`), `ingestionTrigger` (`=direct_enqueue`), `gptModelName/Version/DeploymentType/Capacity`,
`reasoningModelName/Version/DeploymentType/Capacity`, `embeddingModelName/Version/DeploymentType/Capacity`,
`azureOpenAiApiVersion`, `azureAiAgentApiVersion`, `enableMonitoring` (`=false`), `enableScalability`
(`=false`), `enableRedundancy` (`=false`), `enablePrivateNetworking` (`=false`), `tags`, `createdBy`,
`postgresAdminPrincipalId` (`=${AZURE_PRINCIPAL_ID}`), `postgresAdminPrincipalName` (no default),
`postgresAdminPrincipalType` (`=User`), `existingSearchName`, `existingCosmosName`,
`existingStorageName`, `existingEventGridTopicName`, `existingOpenAiName` (all `=` empty).

- NO image params, NO registry/ACR params, NO container-tag params exist. Images are placeholders in
  Bicep and overridden by `azd deploy` via `azure.yaml` `services.*` (the registry endpoint flows out
  as the `AZURE_CONTAINER_REGISTRY_ENDPOINT` output, not in as a param).

---

## Line-number summary table (A1–A12 + backend image + frontend site + ACR + function-app)

| Item | File | Line(s) | Symbol / current text | One-line "must change" |
|------|------|---------|-----------------------|------------------------|
| A1 endpoint env | main.bicep | 2359 (output only); backend env 1740–1827, fn env 2090–2125 | `output AZURE_AI_SERVICES_ENDPOINT = aiServices.outputs.endpoint` — NOT an env var | Add `AZURE_AI_SERVICES_ENDPOINT` env entry to backend env (and fn if needed) |
| A1 Cog Svc User RBAC | main.bicep | aiServices roleAssignments 582 (587/593 only); a97b65f3 ONLY at 847 (Content Safety) | `a97b65f3-...` not on AI Services account | Add `Cognitive Services User` (`a97b65f3-...`) for UAMI to `aiServices.roleAssignments` (582) |
| A2 alwaysReady | main.bicep | 2070–2073 (`scaleAndConcurrency`) | `maximumInstanceCount`, `instanceMemoryMB` only — no `alwaysReady` | Add `alwaysReady` array inside `scaleAndConcurrency` (2070) |
| A3 messageEncoding | main.bicep | fn appSettings 2089–2125 | `FUNCTIONS_EXTENSION_VERSION='~4'` present; no `…queues__messageEncoding` | Add the queue `messageEncoding` app setting (or set in `host.json`) |
| A4 search conn name | main.bicep | 1792 | `AZURE_AI_SEARCH_CONNECTION_NAME = …aiProjectSearchConnection.outputs.name` | (Likely OK) verify; depends on `cwyd-kb-mcp` addition |
| A4 CognitiveSearch conn | modules/ai-project-search-connection.bicep | 39–57 (called main.bicep 1037) | `connection` resource, `category: 'CognitiveSearch'` | Present; basis for adding the MCP RemoteTool conn |
| A4 cwyd-kb-mcp RemoteTool | — | NOT FOUND | no MCP/RemoteTool project connection in Bicep | Declare a `cwyd-kb-mcp` RemoteTool/MCP project connection |
| A4 project Search Service Contributor | main.bicep | aiSearch roleAssignments 904 (project gets Reader 1407120a ~927) | project MI has Search Index Data Reader only | Add `Search Service Contributor` (`7ca78c08-...`) for `projectPrincipalId` |
| A5 EG system topic | main.bicep | 2180 (AVM module, gated `!useExistingEventGridTopic`) | `event-grid/system-topic:0.6.4` | Edit per manual fix (filter/target/retry) |
| A5 subscription | main.bicep | inside AVM `eventSubscriptions:` array 2192; name 2198 | `blob-created-to-doc-processing` (NOT standalone for new-topic path) | Adjust subscription block (2192) / reuse path 2274 |
| A5 queue sender role | main.bicep | 2234 (`eventGridQueueSenderRole`) | `Storage Queue Data Message Sender` `c6a89b2d-...`, scope storage acct | Verify principal/scope per fix |
| A5 useExistingEventGridTopic | main.bicep | branch: 2274 (`existingEventGridSubscription`), role 2256 | standalone `…/eventSubscriptions@2024-12-15-preview` | Mirror changes on reuse path |
| A6 storage public access | main.bicep | storageAccount module 1060; `publicNetworkAccess` 1072; `allowSharedKeyAccess:false` 1071 | NO `networkAcls`/`networkRuleSet` block | Add `networkAcls`/`defaultAction` (or adjust `publicNetworkAccess`) per fix |
| A6 enablePrivateNetworking | main.bicep | 224 (`param … = false`) | gates `publicNetworkAccess` ternary | (context only) |
| A7 postgres principal (backend) | main.bicep | 1794 | value = `postgresAdminPrincipalName` (deployer UPN, param 1441) | Change to `'id-${solutionSuffix}'` (UAMI login name) |
| A7 postgres principal (fn) | main.bicep | 2120 | same expression | Change to `'id-${solutionSuffix}'` |
| A8 ORCHESTRATOR | main.bicep | 1810 | `{ name: 'ORCHESTRATOR', value: 'agent_framework' }`; no `CWYD_ORCHESTRATOR_NAME` | Rename key → `CWYD_ORCHESTRATOR_NAME` (value unchanged) if backend reads that |
| A9 AZURE_ENVIRONMENT | main.bicep | backend 1753, fn 2100 | both `value: 'production'` | ALREADY wired on both — likely no change |
| A10 ACR AAD policy | main.bicep | containerRegistry module 1674 (no `policies:`) | `acrSku/acrAdminUserEnabled/publicNetworkAccess/networkRuleSetDefaultAction` only | Add `policies.azureADAuthenticationAsArmPolicy.status='enabled'` |
| A11 backend registries | main.bicep | backendContainerApp module 1695–1847 (no `registries:`); UAMI MI 1703–1707; AcrPull role 1685/1688 | Container App has no `registries:` block | Add `registries:[{ server, identity: UAMI }]` |
| Backend image | main.bicep | 1729 | `image: 'mcr.microsoft.com/k8se/quickstart:latest'` (placeholder) | Point to ACR backend image |
| Frontend site | main.bicep | frontendWebApp module 1892; kind 1898; siteConfig 1921; `linuxFxVersion` 1925 | `'DOCKER|mcr.microsoft.com/appsvc/staticsite:latest'` (placeholder) | Repoint to ACR frontend image OR move to ACA (structural — confirm) |
| ACR module | main.bicep | 1674 (inline AVM); endpoint output 2472 | `container-registry/registry:0.12.1`; `AZURE_CONTAINER_REGISTRY_ENDPOINT` | A10 policies + feed backend/frontend image refs |
| Function app | main.bicep | functionApp module 2023; kind 2030; functionPlan FC1 2005 | `web/site:0.22.0`, `kind:'functionapp,linux'`, Flex Consumption | A2 alwaysReady + A3 messageEncoding |
| databaseType param | main.bicep | 88 | `param databaseType string = 'cosmosdb'` | (context only) |

---

## Items explicitly NOT found

- `AZURE_AI_SERVICES_ENDPOINT` as an env var (only an output) — A1.
- `Cognitive Services User` (`a97b65f3-...`) on the AI Services/Foundry account (only on Content Safety) — A1.
- `alwaysReady` array in function `scaleAndConcurrency` — A2.
- `AzureFunctionsJobHost__extensions__queues__messageEncoding` app setting (and no host.json wired in Bicep) — A3.
- `cwyd-kb-mcp` RemoteTool / MCP-category project connection (only `CognitiveSearch` exists) — A4.
- `Search Service Contributor` for the Project MI on Search (Project MI gets Reader only) — A4.
- `networkAcls` / `networkRuleSet` / `defaultAction` on the storage account — A6.
- `CWYD_ORCHESTRATOR_NAME` env var (key is `ORCHESTRATOR`) — A8.
- `policies` / `azureADAuthenticationAsArmPolicy` on the ACR module — A10.
- `registries:` property on the backend Container App — A11.
- Any image / registry / container-tag param in `main.parameters.json`.
- A standalone `v2/infra/modules/container_registry.bicep` (ACR is inline in main.bicep).

---

## Recommended next research (not done here)

- [ ] Confirm the EXACT manual `az` override commands behind A1–A12 (the `.azure/` env or a runbook),
      to know precisely what each fix set (values, scopes) vs. inferred-from-Bicep gaps above —
      especially A5 (what property), A6 (open vs restrict), A8 (exact new key name), A10 (exact AVM param shape).
- [ ] Verify the backend settings class reads `CWYD_ORCHESTRATOR_NAME` vs `ORCHESTRATOR` (A8) in
      `v2/src/backend/core/settings*.py`.
- [ ] Verify AVM `container-registry/registry:0.12.1` `policies` param schema (A10) and AVM
      `app/container-app:0.22.1` `registries` param schema (A11) against the published module versions.
- [ ] Confirm the intended frontend target host (ACR-on-App-Service vs second ACA app) — structural,
      requires user confirmation per Hard Rule #10.
- [ ] Confirm whether A7's runtime Postgres user should be `id-${solutionSuffix}` or the UAMI client-id
      form by checking how `AzurePostgresSettings` builds the libpq `user` in `v2/src/backend/core/`.

## Clarifying questions

- A5: Which specific property did the manual fix change (event types, subjectBeginsWith, queue target,
  retry, or the delivery identity/role)? The Bicep block is internally consistent today.
- A6: Did the manual fix OPEN storage public access (defaultAction Allow / bypass AzureServices) or
  RESTRICT it? Bicep currently has only `publicNetworkAccess` (Enabled when not private) and no networkAcls.
- A8: Is the new env key exactly `CWYD_ORCHESTRATOR_NAME`, and does the value stay `agent_framework`?
- Frontend host: target ACR image on the existing App Service, or migrate to a second ACA Container App?
