# CWYD v2 — Infrastructure Guide

> Pillar: **Stable Core** · Phase: **1** (dev_plan §3.4 tasks #1–#19)
> Source files: [v2/infra/main.bicep](../infra/main.bicep), [v2/infra/modules/](../infra/modules/), [v2/infra/main.parameters.json](../infra/main.parameters.json), [v2/infra/main.waf.parameters.json](../infra/main.waf.parameters.json), [v2/scripts/post_provision.py](../scripts/post_provision.py)

This document explains **what the v2 Bicep deploys**, **how the pieces fit together**, and **how an operator runs it**. It is the single source of truth for the v2 substrate. v1 (`code/`, `infra/`) is reference-only — never imitated.

---

## 1. Design principles

1. **Foundry-first.** A single Cognitive Services account of `kind='AIServices'` with `allowProjectManagement: true` is the unified surface for both orchestrators (Microsoft Agent Framework + LangGraph). All chat / reasoning / embedding models are deployments of that account; the Foundry Project is a child resource.
2. **One database parameter, two modes.** `databaseType` (allowed: `cosmosdb` | `postgresql`) selects **both** chat-history storage **and** vector-index storage:
   - `cosmosdb` → Cosmos DB (chat) + Azure AI Search (vectors).
   - `postgresql` → PostgreSQL Flexible Server (chat **and** vectors via pgvector). AI Search is **not** deployed.
3. **AAD-only, no Key Vault.** Every workload binds a single User-Assigned Managed Identity (UAMI). Every data-plane resource has `disableLocalAuth` / `disableLocalAuthentication` / `allowSharedKeyAccess: false`. There are no connection strings or API keys to rotate.
4. **AVM-first.** Every primary resource is an Azure Verified Module from the public registry (`br/public:avm/res/…`). Custom modules live in [`v2/infra/modules/`](../infra/modules/) and only exist where AVM lacks coverage (Foundry Project + child connections, opinionated VNet wrapper).
5. **Plug-and-play preserved.** Backend (Container App), frontend (Web App), and indexing pipeline (Function App) are independent units behind their own ingress. The frontend reads only `VITE_BACKEND_URL`; the backend has no compile-time dependency on the SPA.
6. **Three WAF flags + one networking flag** drive cost / posture without changing topology:
   - `enableMonitoring` → Log Analytics + App Insights + diagnostic settings everywhere.
   - `enableScalability` → larger SKUs, higher autoscale ceilings.
   - `enableRedundancy` → zone-redundant HA, Cosmos failover, GZRS storage, multi-replica Search.
   - `enablePrivateNetworking` → VNet, private DNS, private endpoints, regional VNet integration, Bastion.

---

## 2. Resource topology

### 2.1 Always-on resources (both modes, both flag values)

| Resource | AVM module | Notes |
|---|---|---|
| User-Assigned Managed Identity | `managed-identity/user-assigned-identity:0.4.1` | Single workload identity. |
| AI Services account (`AIServices` kind) | `cognitive-services/account:0.13.0` | Hosts gpt / reasoning / embedding deployments + Foundry Project. |
| Foundry Project | custom: [`modules/ai-project.bicep`](../infra/modules/ai-project.bicep) | Child of AI Services. |
| Storage account | `storage/storage-account:0.32.0` | 3 blob containers (`documents`, `config`, `deployment-package`) + 4 queues (`doc-processing`, `add-url`, + poison). |
| Container Apps Environment + backend Container App | `app/managed-environment:0.13.2` + `app/container-app:0.22.1` | FastAPI backend on workload-profile Consumption. |
| App Service Plan + frontend Web App | `web/serverfarm:0.7.0` + `web/site:0.22.0` | Linux container app for the React/Vite SPA. |
| Function App (Flex Consumption) + Plan | `web/serverfarm:0.7.0` + `web/site:0.22.0` | Hosts the indexing pipeline. |
| Event Grid system topic | `event-grid/system-topic:0.6.4` | Storage `BlobCreated` → `doc-processing` queue. |

### 2.2 Database-conditional

| Mode | Resources |
|---|---|
| `cosmosdb` | Cosmos DB account (`document-db/database-account:0.19.0`) + AI Search service (`search/search-service:0.12.0`) + Foundry Project↔Search connection. |
| `postgresql` | PostgreSQL Flexible Server (`db-for-postgre-sql/flexible-server:0.15.3`) with `azure.extensions=VECTOR` allow-list. |

### 2.3 Monitoring-conditional (`enableMonitoring=true`)

| Resource | AVM module |
|---|---|
| Log Analytics workspace | `operational-insights/workspace:0.11.2` |
| Application Insights | `insights/component:0.6.0` |
| Diagnostic settings on every applicable resource | wired inline |

### 2.4 Private-networking-conditional (`enablePrivateNetworking=true`)

| Component | Module / source |
|---|---|
| VNet, NSGs, 5–6 subnets | custom: [`modules/virtualNetwork.bicep`](../infra/modules/virtualNetwork.bicep) |
| Private DNS zones (6 always-on + 1–2 db-mode-specific) | `network/private-dns-zone:0.8.1` (batched loop) |
| Private endpoints on AI Services / Storage (×3) / Cosmos / Search | inline `privateEndpoints: [...]` on each AVM data module |
| Postgres Flex VNet integration (delegated subnet, not a PE) | inline `delegatedSubnetResourceId` + `privateDnsZoneArmResourceId` |
| CAE wildcard DNS zone (`*.<defaultDomain>` → env staticIp) | `network/private-dns-zone:0.8.1` |
| Web App + Function App regional VNet integration | inline `virtualNetworkSubnetResourceId` + `vnetRouteAllEnabled` |
| Azure Bastion (Standard SKU) + static public IP | `network/bastion-host:0.8.2` |

---

## 3. Parameters at a glance

Two parameter files live alongside `main.bicep`:

| File | `enableMonitoring` | `enableScalability` | `enableRedundancy` | `enablePrivateNetworking` | When to use |
|---|---|---|---|---|---|
| [`main.parameters.json`](../infra/main.parameters.json) | `false` | `false` | `false` | `false` | Default `azd up` (fast, cheap, public). |
| [`main.waf.parameters.json`](../infra/main.waf.parameters.json) | `true` | `true` | `true` | `true` | Well-Architected baseline. |

Both files use azd-style substitutions (`${AZURE_ENV_…=default}`); every flag has an env-var override so you can toggle them per-environment with `azd env set`.

Other key parameters:

| Parameter | Default | Notes |
|---|---|---|
| `solutionName` | `cwyd` | 3–15 chars. Drives every resource name. |
| `location` | _(required)_ | Restricted to 4 regions where Postgres ZR-HA, Cosmos paired-region failover, and Storage GZRS all hold. |
| `azureAiServiceLocation` | _(required)_ | AI region. Defaults to `${AZURE_LOCATION}` if unset. Restricted to GPT-5.1 GlobalStandard regions. |
| `databaseType` | `cosmosdb` | Set to `postgresql` for the Postgres+pgvector mode. |
| `gpt/reasoning/embedding ModelName/Version/Sku/Capacity` | `gpt-5.1` / `o4-mini` / `text-embedding-3-large` etc. | All overridable via `AZURE_ENV_*` env vars. |
| `postgresAdminPrincipalId` | _deployer_ | Object ID of the Entra principal granted Postgres admin. |
| `postgresAdminPrincipalName` | _(required for `postgresql` mode)_ | UPN / group / app name. **No default** — wrong value silently locks you out. |
| `postgresAdminPrincipalType` | `User` | One of `User`, `Group`, `ServicePrincipal`. |

---

## 4. Networking deep-dive (private mode)

### 4.1 VNet layout

`10.0.0.0/20` by default. Subnets:

| Subnet | CIDR | Delegation | Notes |
|---|---|---|---|
| `web` | `10.0.0.0/24` | `Microsoft.Web/serverFarms` | Frontend Web App regional VNet integration. |
| `containerapps` | `10.0.2.0/23` | _none_ (CAE manages internally) | Workload-profile CAE infra subnet (≥/23 required). |
| `functions` | `10.0.4.0/24` | `Microsoft.Web/serverFarms` | Function App regional VNet integration. |
| `peps` | `10.0.6.0/23` | _none_, `privateEndpointNetworkPolicies: Disabled` | All private endpoints. |
| `AzureBastionSubnet` | `10.0.10.0/26` | _none_ (Azure-managed) | Fixed name + ≥/26 required by Bastion. |
| `postgres` | `10.0.12.0/24` | `Microsoft.DBforPostgreSQL/flexibleServers` | **Only created in `postgresql` mode.** |

NSGs are attached to every subnet (per-subnet NSG provisioned in a `@batchSize(1)` loop). Bastion gets the canonical 4-rule set (GatewayManager+Internet inbound on 443, SSH/RDP outbound to VirtualNetwork, AzureCloud outbound on 443). Web/Functions subnets get an `AllowHttpsInbound` + `AllowAzureLoadBalancer` baseline.

### 4.2 Private DNS zones

Wired in a single `@batchSize(5)` loop over a `concat()` array. Indices are tracked in a `dnsZoneIndex` map so PEs reference zones by name, not by magic number.

| Zone | Mode | Index |
|---|---|---|
| `privatelink.cognitiveservices.azure.com` | always | 0 |
| `privatelink.openai.azure.com` | always | 1 |
| `privatelink.services.ai.azure.com` | always | 2 |
| `privatelink.blob.<storage-suffix>` | always | 3 |
| `privatelink.queue.<storage-suffix>` | always | 4 |
| `privatelink.file.<storage-suffix>` | always | 5 |
| `privatelink.documents.azure.com` | `cosmosdb` only | 6 |
| `privatelink.search.windows.net` | `cosmosdb` only | 7 |
| `privatelink.postgres.database.azure.com` | `postgresql` only | 6 |
| `<cae-default-domain>` (wildcard A → CAE static IP) | always (private mode) | _separate `caeDnsZone` module_ |

> **Note** the actual zone names use the `privatelink.` prefix automatically — the variables in `main.bicep` set the bare zone names; AVM `network/private-dns-zone` resolves them as ARM-required.

Each zone is linked to the VNet (`registrationEnabled: false`).

### 4.3 Private endpoints (PE table)

| Resource | PE name | Group | DNS zone |
|---|---|---|---|
| AI Services | `pep-aisa-<suffix>` | `account` | cognitiveservices + openai + services.ai (3-in-1 group) |
| Storage (blob) | `pep-blob-<account>` | `blob` | blob |
| Storage (queue) | `pep-queue-<account>` | `queue` | queue |
| Storage (file) | `pep-file-<account>` | `file` | file (used by Function App host) |
| Cosmos DB | `pep-cosno-<suffix>` | `Sql` | documents (cosmosdb mode) |
| AI Search | `pep-srch-<suffix>` | `searchService` | search (cosmosdb mode) |
| Postgres Flex | _(no PE; uses delegated subnet + `privateDnsZoneArmResourceId`)_ | n/a | postgres (postgresql mode) |

### 4.4 Container Apps Environment in private mode

- `internal: true` and `infrastructureSubnetResourceId` → `containerapps` subnet.
- A **wildcard `caeDnsZone`** (`*.<defaultDomain>` A-record → env `staticIp`) makes any container app in this env resolvable from inside the VNet as `<app>.<defaultDomain>`.
- Backend Container App ingress flips to `external: false` automatically (`ingressExternal: !enablePrivateNetworking`).

### 4.5 Bastion

Standard SKU, static Standard public IP, lands in `AzureBastionSubnet`. No jumpbox VM. Operator access patterns:

```pwsh
# Tunnel kubectl / psql / arbitrary TCP
az network bastion tunnel `
  --resource-group $env:AZURE_RESOURCE_GROUP `
  --name $env:AZURE_BASTION_NAME `
  --target-resource-id (az postgres flexible-server show -g $env:AZURE_RESOURCE_GROUP -n $env:AZURE_POSTGRES_NAME --query id -o tsv) `
  --resource-port 5432 --port 5432

# In another terminal:
$env:PGHOST="localhost"; $env:PGUSER="$env:AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME"
psql -d postgres
```

---

## 5. Outputs

`azd` writes every `output AZURE_*` to `.azure/<env>/.env`. The most important ones:

| Output | Purpose |
|---|---|
| `AZURE_RESOURCE_GROUP`, `AZURE_LOCATION`, `AZURE_TENANT_ID`, `AZURE_SOLUTION_SUFFIX` | Identification. |
| `AZURE_UAMI_CLIENT_ID`, `AZURE_UAMI_PRINCIPAL_ID`, `AZURE_UAMI_RESOURCE_ID` | Workload identity wiring. |
| `AZURE_DB_TYPE`, `AZURE_INDEX_STORE` | Runtime branching for the orchestrators. |
| `AZURE_AI_SERVICES_ENDPOINT`, `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_OPENAI_API_VERSION`, `AZURE_AI_AGENT_API_VERSION` | Foundry data-plane. |
| `AZURE_OPENAI_GPT_DEPLOYMENT`, `AZURE_OPENAI_REASONING_DEPLOYMENT`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Model deployment names. |
| `AZURE_AI_SEARCH_ENDPOINT/NAME`, `AZURE_COSMOS_ENDPOINT/ACCOUNT_NAME` | Cosmosdb-mode data stores (empty in postgres mode). |
| `AZURE_POSTGRES_HOST/NAME/ADMIN_PRINCIPAL_NAME` | Postgres-mode data store (empty in cosmosdb mode). |
| `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_BLOB_ENDPOINT`, `AZURE_DOCUMENTS_CONTAINER`, `AZURE_DOC_PROCESSING_QUEUE` | Indexing-pipeline wiring. |
| `AZURE_BACKEND_URL`, `AZURE_FRONTEND_URL`, `AZURE_FUNCTION_APP_URL/NAME` | Hosting endpoints. |
| `AZURE_APP_INSIGHTS_CONNECTION_STRING` | Empty when monitoring disabled. |
| `AZURE_VNET_NAME/RESOURCE_ID`, `AZURE_BASTION_NAME` | Empty when private networking disabled. |

---

## 6. Post-provision

[v2/scripts/post_provision.py](../scripts/post_provision.py) runs automatically as the azd `postprovision` hook. Behaviour:

1. Validates `AZURE_DB_TYPE` against the allow-list.
2. **`postgresql` mode only:**
   - **Private-mode pre-flight:** if `AZURE_POSTGRES_HOST` contains `.private.postgres.database.azure.com`, exits **7** with a ready-to-paste `az network bastion tunnel` command. The deployer machine cannot resolve private DNS.
   - Acquires an Entra token for `https://ossrdbms-aad.database.windows.net/.default` via `DefaultAzureCredential`.
   - Connects as `AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME` and runs `CREATE EXTENSION IF NOT EXISTS vector`.
3. Prints a compact summary of the `AZURE_*` outputs.

Exit codes: `0` ok · `2` missing required env var · `3` missing pip deps · `4` token failure · `5` connect failure · `6` invalid `AZURE_DB_TYPE` · `7` private-mode unreachable.

---

## 7. How to deploy

### 7.1 Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) ≥ 1.10
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) ≥ 2.60 with `bicep` extension
- Python 3.12 + `uv` (for the post-provision hook). `uv sync` from the repo root installs `psycopg2-binary` and `azure-identity`.
- An Azure subscription with quota for: GPT-5.1 GlobalStandard (150K TPM), o4-mini GlobalStandard (50K TPM), text-embedding-3-large Standard (100K TPM) in `azureAiServiceLocation`.

### 7.2 First deploy (default profile, public)

```pwsh
cd v2
azd auth login
azd env new cwyd-dev
azd env set AZURE_LOCATION eastus2
azd env set AZURE_ENV_AI_SERVICE_LOCATION eastus2
azd env set AZURE_ENV_DATABASE_TYPE cosmosdb   # or postgresql
azd up
```

For postgres mode also set:

```pwsh
azd env set AZURE_ENV_POSTGRES_ADMIN_PRINCIPAL_NAME (az ad signed-in-user show --query userPrincipalName -o tsv)
```

### 7.3 WAF profile (private + monitored + redundant)

```pwsh
azd env new cwyd-waf
azd env set AZURE_LOCATION eastus2
azd env set AZURE_ENV_AI_SERVICE_LOCATION eastus2
azd env set AZURE_ENV_DATABASE_TYPE postgresql
azd env set AZURE_ENV_POSTGRES_ADMIN_PRINCIPAL_NAME (az ad signed-in-user show --query userPrincipalName -o tsv)
# Tell azd to use the WAF parameter file
azd env set AZURE_PARAMETERS_FILE main.waf.parameters.json
azd up
```

In private mode the post-provision step **will exit 7** because the deployer is outside the VNet. Open a Bastion tunnel as instructed and re-run:

```pwsh
azd hooks run postprovision
```

### 7.4 Tear down

```pwsh
azd down --purge
```

`--purge` removes soft-deleted Cognitive Services, Key Vault (none here), and App Configuration so the names are immediately reusable.

---

## 8. Validation

`bicep build` is run on every change. From the repo root:

```pwsh
az bicep build --file v2/infra/main.bicep --outdir v2/infra/.build
```

Expect exit `0` and only `BCP081` warnings (AVM resource types that lack metadata in the current Bicep CLI). Any other warning or error is a regression.

---

## 9. Naming conventions

Per repo rule §11:

- **Bicep symbols** — `camelCase` (`virtualNetwork`, `aiServicesName`).
- **Azure resource names** — `<type-abbrev>-<solutionSuffix>` driven by [`abbreviations.json`](../infra/abbreviations.json) (e.g. `id-cwyd-abc12`, `srch-cwyd-abc12`, `cosno-cwyd-abc12`, `psql-cwyd-abc12`, `bas-cwyd-abc12`).
- **Storage account** is the one exception (no hyphens, ≤ 24 chars): `take(replace('st${solutionSuffix}', '-', ''), 24)`.
- **Env vars** — `UPPER_SNAKE_CASE`, prefixed `AZURE_` (or `AZURE_ENV_` for azd substitutions, `VITE_` for the frontend build).
- **Public APIs** — once an `output AZURE_*` ships, do not rename without explicit confirmation.

---

## 10. Where things live (file map)

```
v2/infra/
├── main.bicep                    # Entry point. All `module` calls.
├── main.parameters.json          # Default profile (public, cheap).
├── main.waf.parameters.json      # WAF profile (private, monitored, redundant).
├── abbreviations.json            # Resource-type prefix table.
└── modules/
    ├── virtualNetwork.bicep              # Custom VNet wrapper (subnets + per-subnet NSGs).
    ├── ai-project.bicep                  # Foundry Project (child of AI Services).
    └── ai-project-search-connection.bicep  # Foundry Project ↔ Search connection (cosmosdb mode).

v2/scripts/
├── post_provision.py             # azd postprovision hook (Python).
├── post-provision.sh             # POSIX wrapper.
└── post-provision.ps1            # PowerShell wrapper.

v2/azure.yaml                     # azd service map (backend/frontend/function).
```

---

## 11. References

- Microsoft Multi-Agent Custom Automation Engine (MACAE) — managed-identity + RBAC + no-Key-Vault patterns. Read-only architectural reference.
- Microsoft Content Generation Solution Accelerator (CGSA) — frontend/backend plug-and-play surface. Read-only architectural reference.
- [Azure Verified Modules public registry](https://aka.ms/avm) — every `br/public:avm/res/…` reference in `main.bicep`.
- [`v2/docs/development_plan.md`](development_plan.md) — phase ordering and §3.4 task list.
- [`v2/docs/pillars_of_development.md`](pillars_of_development.md) — Stable Core / Scenario Pack / Configuration Layer / Customization Layer classification.
