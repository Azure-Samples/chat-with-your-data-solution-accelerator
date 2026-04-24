// ========================================================================
// Pillar:  Stable Core
// Phase:   1 (Infrastructure + Project Skeleton)
// Purpose: Entry-point Bicep template for CWYD v2. Provisions a
//          Foundry-first AI footprint where a single `databaseType`
//          parameter selects BOTH the chat-history backend AND the
//          vector index store at deploy time:
//            cosmosdb   -> Cosmos DB + Azure AI Search
//            postgresql -> PostgreSQL Flexible (+ pgvector)
//          Both runtime-switchable orchestrators (Agent Framework and
//          LangGraph) bind to the same AI Services account + Foundry
//          Project; orchestrator selection is a runtime env var, never
//          a Bicep param.
//
// Notes:   - Modules are added in subsequent units; this file currently
//            declares only parameters, naming variables, and the resource
//            group tag stamp. `bicep build` must succeed at every commit.
//          - Adapted from Microsoft Multi-Agent Custom Automation Engine
//            and Content Generation solution accelerators (read-only
//            architectural references, per CWYD repo instructions).
// ========================================================================

targetScope = 'resourceGroup'

metadata name = 'Chat With Your Data v2'
metadata description = 'Foundry-first RAG accelerator. Single databaseType parameter selects chat history + vector index. Two orchestrators (Agent Framework, LangGraph) on a shared Foundry Project.'

// ===================== //
// Required parameters   //
// ===================== //

@minLength(3)
@maxLength(15)
@description('Required. Unique application/solution name. Drives every resource name. Cap is 15 chars to keep PostgreSQL Flexible Server names within limits.')
param solutionName string = 'cwyd'

@maxLength(5)
@description('Optional. Short unique suffix appended to global resource names. Defaults to a 5-char hash of subscription + RG + solution name.')
param solutionUniqueText string = take(uniqueString(subscription().id, resourceGroup().name, solutionName), 5)

@allowed([
  'australiaeast'
  'eastus2'
  'japaneast'
  'uksouth'
])
@metadata({ azd: { type: 'location' } })
@description('Required. Azure region for non-AI resources (Container Apps, App Service, Functions, Storage, Cosmos/Postgres). Restricted to the 4 regions where ALL three redundancy guarantees hold simultaneously: PostgreSQL Flexible Server ZoneRedundant HA (3 AZs), Cosmos DB automatic failover with paired-region replicas, and Storage GZRS. Independent of azureAiServiceLocation, which selects the model-availability region. Source: https://learn.microsoft.com/azure/reliability/regions-list and https://learn.microsoft.com/azure/postgresql/flexible-server/overview#azure-regions')
param location string

@allowed([
  'australiaeast'
  'canadaeast'
  'eastus2'
  'japaneast'
  'koreacentral'
  'polandcentral'
  'swedencentral'
  'switzerlandnorth'
  'uaenorth'
  'uksouth'
  'westus3'
])
@metadata({
  azd: {
    type: 'location'
    usageName: [
      'OpenAI.GlobalStandard.gpt-5.1,150'
      'OpenAI.GlobalStandard.o4-mini,50'
      'OpenAI.Standard.text-embedding-3-large,100'
    ]
  }
})
@description('Required. Region for AI Services / Foundry deployments. Restricted to regions with GPT-5.1 GlobalStandard availability.')
param azureAiServiceLocation string

// ===================== //
// Database selection    //
// ===================== //

@allowed([
  'cosmosdb'
  'postgresql'
])
@description('Required. Selects BOTH the chat-history backend AND the vector index store. cosmosdb: Cosmos DB + Azure AI Search. postgresql: PostgreSQL Flexible Server with pgvector (Azure AI Search is NOT deployed). Locked at deploy time.')
param databaseType string = 'cosmosdb'

// ===================== //
// AI model parameters   //
// ===================== //

@minLength(1)
@description('Optional. Primary chat model deployment name.')
param gptModelName string = 'gpt-5.1'

@description('Optional. Primary chat model version.')
param gptModelVersion string = '2025-11-13'

@allowed([
  'Standard'
  'GlobalStandard'
])
@description('Optional. SKU for the primary chat model deployment.')
param gptModelDeploymentType string = 'GlobalStandard'

@minValue(1)
@description('Optional. Token capacity (thousands of TPM) for the primary chat model.')
param gptModelCapacity int = 150

@minLength(1)
@description('Optional. Reasoning model deployment name (surfaced via the SSE reasoning channel).')
param reasoningModelName string = 'o4-mini'

@description('Optional. Reasoning model version.')
param reasoningModelVersion string = '2025-04-16'

@allowed([
  'Standard'
  'GlobalStandard'
])
@description('Optional. SKU for the reasoning model deployment.')
param reasoningModelDeploymentType string = 'GlobalStandard'

@minValue(1)
@description('Optional. Token capacity for the reasoning model.')
param reasoningModelCapacity int = 50

@minLength(1)
@description('Optional. Embedding model deployment name (used by Foundry IQ and the LangGraph indexer).')
param embeddingModelName string = 'text-embedding-3-large'

@description('Optional. Embedding model version.')
param embeddingModelVersion string = '1'

@allowed([
  'Standard'
  'GlobalStandard'
])
@description('Optional. SKU for the embedding model deployment.')
param embeddingModelDeploymentType string = 'Standard'

@minValue(1)
@description('Optional. Token capacity for the embedding model.')
param embeddingModelCapacity int = 100

@description('Optional. Azure OpenAI API version exposed via the OpenAI-compatible endpoint (used by the LangGraph orchestrator).')
param azureOpenAiApiVersion string = '2025-01-01-preview'

@description('Optional. Azure AI Agent API version (used by the Agent Framework orchestrator).')
param azureAiAgentApiVersion string = '2025-05-01'

// ===================== //
// WAF flags             //
// ===================== //

@description('Optional. Deploy Log Analytics + Application Insights and wire diagnostic settings on every applicable resource.')
param enableMonitoring bool = false

@description('Optional. Higher SKUs and autoscaling on App Service Plan, Container Apps, Search, and PostgreSQL.')
param enableScalability bool = false

@description('Optional. Zone-redundant + paired-region failover on databases, App Service Plan, Container Apps, and Storage.')
param enableRedundancy bool = false

@description('Optional. Deploy a VNet, private endpoints, and disable public network access on data-plane resources. NOTE: VNet/DNS modules land in dev_plan tasks #7-#8; flipping this to true today provisions resources with public access disabled but no VNet, making them unreachable. Set to true only after #7-#8 ship.')
param enablePrivateNetworking bool = false

// ===================== //
// Tagging               //
// ===================== //

@description('Optional. Tags applied to every deployed resource.')
param tags object = {}

@description('Optional. Identifier of the user creating the deployment, recorded in the resource group tags.')
param createdBy string = contains(deployer(), 'userPrincipalName')
  ? split(deployer().userPrincipalName, '@')[0]
  : deployer().objectId

// ===================== //
// Variables             //
// ===================== //

// NOTE: When enablePrivateNetworking=true, every data-plane resource
// below is provisioned with publicNetworkAccess='Disabled'. The
// matching VNet + private DNS zones land in dev_plan tasks #7-#8;
// until then, do not flip the flag. The parameter description above
// surfaces this warning in the `azd up` prompt.


// 15-char solution suffix used in every resource name. Lowercased and stripped
// of separators so it stays valid for resources with the strictest naming rules
// (PostgreSQL, Storage Account).
var solutionSuffix = toLower(trim(replace(
  replace(
    replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''),
    ' ',
    ''
  ),
  '*',
  '')))

var allTags = union(
  {
    'azd-env-name': solutionName
    TemplateName: 'CWYD-v2'
    Type: enablePrivateNetworking ? 'WAF' : 'Non-WAF'
    CreatedBy: createdBy
    DatabaseType: databaseType
  },
  tags
)

// ===================== //
// Resources             //
// ===================== //

// Stamp the resource group with the solution tags so downstream tooling can
// discover the deployment without parsing names.
resource resourceGroupTags 'Microsoft.Resources/tags@2024-03-01' = {
  name: 'default'
  properties: {
    tags: union(resourceGroup().tags ?? {}, allTags)
  }
}

// User-Assigned Managed Identity used by every workload (backend Container
// App, frontend Web App, Function App). All RBAC role assignments target
// this single principal so there is one identity to audit and rotate.
// Reference: MACAE solution accelerator (managed-identity + RBAC + no Key
// Vault for app secrets).
module userAssignedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: take('avm.res.managed-identity.user-assigned-identity.${solutionSuffix}', 64)
  params: {
    name: 'id-${solutionSuffix}'
    location: location
    tags: allTags
    enableTelemetry: false
  }
}

// ----------------------------------------------------------------------
// Monitoring (conditional). Gated on enableMonitoring so non-WAF deploys
// stay cheap. Log Analytics is the sink for Application Insights and for
// every diagnostic setting wired by downstream modules.
// ----------------------------------------------------------------------
module logAnalyticsWorkspace 'br/public:avm/res/operational-insights/workspace:0.11.2' = if (enableMonitoring) {
  name: take('avm.res.operational-insights.workspace.${solutionSuffix}', 64)
  params: {
    name: 'log-${solutionSuffix}'
    location: location
    tags: allTags
    enableTelemetry: false
    skuName: 'PerGB2018'
    dataRetention: enableRedundancy ? 90 : 30
  }
}

module applicationInsights 'br/public:avm/res/insights/component:0.6.0' = if (enableMonitoring) {
  name: take('avm.res.insights.component.${solutionSuffix}', 64)
  params: {
    name: 'appi-${solutionSuffix}'
    location: location
    tags: allTags
    enableTelemetry: false
    workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId
    applicationType: 'web'
    kind: 'web'
    disableLocalAuth: true
  }
}

// ----------------------------------------------------------------------
// Microsoft Foundry substrate. ONE Cognitive Services account of
// kind='AIServices' with allowProjectManagement=true is the unified
// surface for BOTH orchestrators:
//   - Agent Framework binds via the Foundry Project endpoint.
//   - LangGraph binds via the OpenAI-compatible endpoint on the same
//     account (chat completions + embeddings).
// Local auth is disabled; every caller authenticates with the UAMI via
// the Cognitive Services OpenAI User + Azure AI User roles assigned
// below.
// ----------------------------------------------------------------------
var aiServicesName = 'aisa-${solutionSuffix}'

module aiServices 'br/public:avm/res/cognitive-services/account:0.13.0' = {
  name: take('avm.res.cognitive-services.account.${solutionSuffix}', 64)
  params: {
    name: aiServicesName
    location: azureAiServiceLocation
    tags: allTags
    enableTelemetry: false
    kind: 'AIServices'
    sku: 'S0'
    customSubDomainName: aiServicesName
    allowProjectManagement: true
    disableLocalAuth: true
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    managedIdentities: {
      systemAssigned: true
    }
    diagnosticSettings: enableMonitoring
      ? [
          {
            workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId
          }
        ]
      : []
    deployments: [
      {
        name: gptModelName
        model: {
          format: 'OpenAI'
          name: gptModelName
          version: gptModelVersion
        }
        sku: {
          name: gptModelDeploymentType
          capacity: gptModelCapacity
        }
        raiPolicyName: 'Microsoft.DefaultV2'
      }
      {
        name: reasoningModelName
        model: {
          format: 'OpenAI'
          name: reasoningModelName
          version: reasoningModelVersion
        }
        sku: {
          name: reasoningModelDeploymentType
          capacity: reasoningModelCapacity
        }
        raiPolicyName: 'Microsoft.DefaultV2'
      }
      {
        name: embeddingModelName
        model: {
          format: 'OpenAI'
          name: embeddingModelName
          version: embeddingModelVersion
        }
        sku: {
          name: embeddingModelDeploymentType
          capacity: embeddingModelCapacity
        }
      }
    ]
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Cognitive Services OpenAI User
        roleDefinitionIdOrName: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
      }
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Azure AI User (Foundry Project data-plane)
        roleDefinitionIdOrName: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
      }
    ]
  }
}

// Foundry Project — child of the AI Services account. Hosts agents
// (Agent Framework orchestrator) and knowledge bases (Foundry IQ).
//
// NOTE on Foundry Tools (dev_plan task #9b): Document Intelligence and
// Content Understanding are intentionally NOT deployed as separate
// Cognitive Services accounts. The unified `kind=AIServices` account
// above (with allowProjectManagement=true) exposes both APIs on the
// same endpoint and bills under the same SKU. Code references them via
// https://<account>.services.ai.azure.com/{documentintelligence|contentunderstanding}/...
module aiProject 'modules/ai-project.bicep' = {
  name: take('module.ai-project.${solutionSuffix}', 64)
  params: {
    aiServicesAccountName: aiServicesName
    projectName: 'proj-${solutionSuffix}'
    location: azureAiServiceLocation
    tags: allTags
    uamiPrincipalId: userAssignedIdentity.outputs.principalId
  }
  dependsOn: [
    aiServices
  ]
}

// ----------------------------------------------------------------------
// Azure AI Search (CONDITIONAL — cosmosdb mode only).
// In postgresql mode the index store is pgvector inside the Postgres
// Flexible Server, so Search is not deployed at all. RBAC grants the
// workload UAMI both data-plane (index read/write) and control-plane
// (manage indexers from the Function App) access. The Foundry Project
// connection to this Search service is wired in the next unit
// (modules/ai-project-search-connection.bicep) so Foundry IQ knowledge
// bases can resolve this Search service by friendly name.
// ----------------------------------------------------------------------
module aiSearch 'br/public:avm/res/search/search-service:0.12.0' = if (databaseType == 'cosmosdb') {
  name: take('avm.res.search.search-service.${solutionSuffix}', 64)
  params: {
    name: 'srch-${solutionSuffix}'
    location: location
    tags: allTags
    enableTelemetry: false
    sku: enableScalability ? 'standard' : 'basic'
    replicaCount: enableRedundancy ? 3 : 1
    partitionCount: 1
    semanticSearch: 'free'
    disableLocalAuth: true
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    managedIdentities: {
      systemAssigned: true
    }
    diagnosticSettings: enableMonitoring
      ? [
          {
            workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId
          }
        ]
      : []
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Search Index Data Contributor (data-plane CRUD on docs)
        roleDefinitionIdOrName: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
      }
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Search Service Contributor (control-plane: indexes, indexers, skillsets)
        roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
      }
      {
        principalId: aiProject.outputs.projectPrincipalId
        principalType: 'ServicePrincipal'
        // Search Index Data Reader — lets the Foundry Project (and Foundry IQ) query indexes through the connection.
        roleDefinitionIdOrName: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
      }
    ]
  }
}

// Foundry Project ↔ Search connection (cosmosdb mode only). Lets Foundry
// IQ knowledge bases resolve this Search service by friendly name and
// authenticate via the Project's system-assigned identity (no API keys).
module aiProjectSearchConnection 'modules/ai-project-search-connection.bicep' = if (databaseType == 'cosmosdb') {
  name: take('module.ai-project-search-connection.${solutionSuffix}', 64)
  params: {
    aiServicesAccountName: aiServicesName
    projectName: aiProject.outputs.name
    searchServiceName: aiSearch!.outputs.name
  }
}

// ----------------------------------------------------------------------
// Storage account. Triple-purpose:
//   - WebJobsStorage / content share for the Function App.
//   - Source bucket for uploaded documents (`documents` container).
//   - Queue backbone for the indexing pipeline (one queue per trigger:
//     batch_start, batch_push, add_url).
// Storage account names must be 3-24 chars, lower-case alphanumeric.
// We strip dashes from the suffix and fall back to a uniqueString-derived
// short name when the solution suffix is too long.
// ----------------------------------------------------------------------
var storageAccountName = take(replace('st${solutionSuffix}', '-', ''), 24)

module storageAccount 'br/public:avm/res/storage/storage-account:0.32.0' = {
  name: take('avm.res.storage.storage-account.${solutionSuffix}', 64)
  params: {
    name: storageAccountName
    location: location
    tags: allTags
    enableTelemetry: false
    kind: 'StorageV2'
    skuName: enableRedundancy ? 'Standard_ZRS' : 'Standard_LRS'
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    managedIdentities: {
      systemAssigned: true
    }
    diagnosticSettings: enableMonitoring
      ? [
          {
            workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId
          }
        ]
      : []
    blobServices: {
      containers: [
        {
          name: 'documents'
          publicAccess: 'None'
        }
        {
          name: 'config'
          publicAccess: 'None'
        }
      ]
    }
    queueServices: {
      queues: [
        { name: 'doc-processing' }
        { name: 'doc-processing-poison' }
        { name: 'add-url' }
        { name: 'add-url-poison' }
      ]
    }
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Storage Blob Data Contributor (read/write uploaded documents)
        roleDefinitionIdOrName: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
      }
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Storage Queue Data Contributor (enqueue + consume indexing messages)
        roleDefinitionIdOrName: '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
      }
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Storage Account Contributor (Function App host storage management)
        roleDefinitionIdOrName: '17d1049b-9a84-46fb-8f53-869881c3d3ab'
      }
    ]
  }
}

// ----------------------------------------------------------------------
// Cosmos DB (CONDITIONAL — cosmosdb mode only).
// Stores chat history, one item per message. Partitioned on `userId`
// for high-cardinality even distribution; query patterns are
// "all messages for user X in conversation Y" so userId is the hot path.
// AAD-only (disableLocalAuth) — workload UAMI gets the built-in
// Cosmos DB Built-in Data Contributor role at data-plane scope.
//
// Capacity model: Serverless by default (cheap, scale-to-zero). When
// enableRedundancy=true we switch to provisioned throughput so we can
// turn on automatic failover + zone redundancy, which serverless
// rejects.
// ----------------------------------------------------------------------
module cosmosDb 'br/public:avm/res/document-db/database-account:0.19.0' = if (databaseType == 'cosmosdb') {
  name: take('avm.res.document-db.database-account.${solutionSuffix}', 64)
  params: {
    name: 'cosno-${solutionSuffix}'
    location: location
    tags: allTags
    enableTelemetry: false
    disableLocalAuthentication: true
    enableAutomaticFailover: enableRedundancy
    zoneRedundant: enableRedundancy
    capabilitiesToAdd: enableRedundancy ? [] : [
      'EnableServerless'
    ]
    networkRestrictions: {
      publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    }
    diagnosticSettings: enableMonitoring
      ? [
          {
            workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId
          }
        ]
      : []
    sqlDatabases: [
      {
        name: 'cwyd'
        containers: [
          {
            name: 'conversations'
            paths: [
              '/userId'
            ]
          }
        ]
      }
    ]
    sqlRoleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        // Cosmos DB Built-in Data Contributor (data-plane CRUD)
        roleDefinitionId: '00000000-0000-0000-0000-000000000002'
      }
    ]
  }
}

// ----------------------------------------------------------------------
// PostgreSQL Flexible Server + pgvector (CONDITIONAL — postgresql mode).
// Single server hosts BOTH chat history (relational tables) AND the
// vector index (pgvector extension). Auth is Entra-only — the workload
// UAMI is the Entra admin, and the post-provision script
// (`v2/scripts/post-provision.sh`, task #19) connects via `psql` with
// the deployer's az token to:
//   1. CREATE EXTENSION vector;
//   2. Create the chat_history + document_chunks schema.
//
// `azure.extensions=VECTOR` in the configurations block adds vector to
// the allow-list so step 1 succeeds. Without it, CREATE EXTENSION fails
// even if the binary is installed.
// ----------------------------------------------------------------------
@description('Optional. Object ID of the Entra principal (user/group) to grant Postgres admin access to. Defaults to the deploying principal so the post-provision script can run schema-init via az AAD token.')
param postgresAdminPrincipalId string = ''

@description('Optional. Display name (UPN, group name, or app name) of the Entra principal above. Surfaced in pg_hba.')
param postgresAdminPrincipalName string = 'cwyd-deployer'

@allowed([
  'User'
  'Group'
  'ServicePrincipal'
])
@description('Optional. Type of the Entra principal above. Auto-detected from the deployer (User vs ServicePrincipal) when left at the default.')
param postgresAdminPrincipalType string = contains(deployer(), 'userPrincipalName') ? 'User' : 'ServicePrincipal'

module postgresServer 'br/public:avm/res/db-for-postgre-sql/flexible-server:0.15.3' = if (databaseType == 'postgresql') {
  name: take('avm.res.db-for-postgre-sql.flexible-server.${solutionSuffix}', 64)
  params: {
    name: 'psql-${solutionSuffix}'
    location: location
    tags: allTags
    enableTelemetry: false
    skuName: enableScalability ? 'Standard_D4ds_v5' : 'Standard_B2s'
    tier: enableScalability ? 'GeneralPurpose' : 'Burstable'
    version: '16'
    storageSizeGB: 32
    availabilityZone: enableRedundancy ? 1 : -1
    highAvailability: enableRedundancy ? 'ZoneRedundant' : 'Disabled'
    highAvailabilityZone: enableRedundancy ? 2 : -1
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
      tenantId: subscription().tenantId
    }
    administrators: union(
      [
        {
          objectId: userAssignedIdentity.outputs.principalId
          principalName: 'id-${solutionSuffix}'
          principalType: 'ServicePrincipal'
        }
      ],
      empty(postgresAdminPrincipalId)
        ? []
        : [
            {
              objectId: postgresAdminPrincipalId
              principalName: postgresAdminPrincipalName
              principalType: postgresAdminPrincipalType
            }
          ]
    )
    databases: [
      {
        name: 'cwyd'
        charset: 'UTF8'
        collation: 'en_US.utf8'
      }
    ]
    configurations: [
      {
        name: 'azure.extensions'
        value: 'VECTOR'
        source: 'user-override'
      }
    ]
    firewallRules: enablePrivateNetworking
      ? []
      : [
          {
            // Allow connections from Azure-internal services (Function App,
            // Container Apps) without enumerating egress IPs. Tightened by
            // private endpoints when enablePrivateNetworking=true.
            name: 'AllowAzureServices'
            startIpAddress: '0.0.0.0'
            endIpAddress: '0.0.0.0'
          }
        ]
    diagnosticSettings: enableMonitoring
      ? [
          {
            workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId
          }
        ]
      : []
  }
}

// ----------------------------------------------------------------------
// Container Apps Environment + backend Container App.
// The backend (FastAPI + LangGraph/Agent Framework) runs here. ACA was
// chosen over App Service for the backend because:
//   - scale-to-zero (SSE workloads idle most of the time)
//   - native UAMI-based ACR pull (no managed-identity glue code)
//   - first-class HTTP/SSE streaming with no buffering
// The Web App (frontend) lands in #15 on a separate App Service Plan,
// matching the MACAE mixed-hosting pattern.
//
// Phase 1 deploys a placeholder image so the resources exist; the real
// image is wired in azure.yaml `services.backend` once the backend
// Dockerfile (v2/docker/Dockerfile.backend) ships in Phase 2.
// ----------------------------------------------------------------------
var containerAppsEnvName = 'cae-${solutionSuffix}'
var backendAppName = 'ca-backend-${solutionSuffix}'
var acaWorkloadProfileName = 'Consumption'

module containerAppsEnv 'br/public:avm/res/app/managed-environment:0.13.2' = {
  name: take('avm.res.app.managed-environment.${solutionSuffix}', 64)
  params: {
    name: containerAppsEnvName
    location: location
    tags: allTags
    enableTelemetry: false
    zoneRedundant: enableRedundancy
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    // Workload Profile Consumption (NOT classic Consumption). Required
    // for full VNet integration in #7-#8 and to allow mixing Dedicated
    // profiles (e.g. GPU) later without re-creating the env. Idle cost
    // for the Consumption profile is the same as classic Consumption.
    workloadProfiles: [
      {
        name: acaWorkloadProfileName
        workloadProfileType: acaWorkloadProfileName
      }
    ]
    // ACA env app logs: 'azure-monitor' destination routes logs through
    // an explicit Microsoft.Insights/diagnosticSettings resource (added
    // below when monitoring is on). Using 'log-analytics' here would
    // require passing the workspace's primarySharedKey (a secure output),
    // which Bicep disallows across conditional module references
    // (BCP426). The AVM module does not expose `diagnosticSettings`.
    appLogsConfiguration: {
      destination: 'azure-monitor'
    }
  }
}

// Existing reference to the deployed env so we can attach diagnostic
// settings to it without round-tripping through a module output.
resource containerAppsEnvResource 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: containerAppsEnvName
  dependsOn: [ containerAppsEnv ]
}

resource containerAppsEnvDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableMonitoring) {
  name: 'send-to-log-analytics'
  scope: containerAppsEnvResource
  properties: {
    workspaceId: logAnalyticsWorkspace!.outputs.resourceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
  }
}

module backendContainerApp 'br/public:avm/res/app/container-app:0.22.1' = {
  name: take('avm.res.app.container-app.backend.${solutionSuffix}', 64)
  params: {
    name: backendAppName
    location: location
    tags: union(allTags, { 'azd-service-name': 'backend' })
    enableTelemetry: false
    environmentResourceId: containerAppsEnv.outputs.resourceId
    managedIdentities: {
      userAssignedResourceIds: [
        userAssignedIdentity.outputs.resourceId
      ]
    }
    workloadProfileName: acaWorkloadProfileName
    ingressTargetPort: 8000
    ingressExternal: true
    ingressAllowInsecure: false
    ingressTransport: 'auto'
    scaleSettings: {
      minReplicas: enableScalability ? 1 : 0
      maxReplicas: enableScalability ? 10 : 3
    }
    containers: [
      {
        name: 'backend'
        // Placeholder image. Replaced by `azd deploy` once the real
        // backend Dockerfile ships in Phase 2 and is referenced from
        // azure.yaml `services.backend`.
        image: 'mcr.microsoft.com/k8se/quickstart:latest'
        resources: {
          cpu: enableScalability ? '1.0' : '0.5'
          memory: enableScalability ? '2.0Gi' : '1.0Gi'
        }
        // App Insights env entry is included only when monitoring is on,
        // so SDKs don't auto-init against an empty connection string.
        env: union(
          [
            // Identity + region
            { name: 'AZURE_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
            { name: 'AZURE_TENANT_ID', value: subscription().tenantId }
            // Foundry endpoints (consumed by both orchestrators)
            { name: 'AZURE_AI_PROJECT_ENDPOINT', value: aiProject.outputs.projectEndpoint }
            { name: 'AZURE_OPENAI_ENDPOINT', value: aiServices.outputs.endpoint }
            { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
            { name: 'AZURE_AI_AGENT_API_VERSION', value: azureAiAgentApiVersion }
            // Model deployment names
            { name: 'AZURE_OPENAI_GPT_DEPLOYMENT', value: gptModelName }
            { name: 'AZURE_OPENAI_REASONING_DEPLOYMENT', value: reasoningModelName }
            { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
            // Database routing
            { name: 'AZURE_DB_TYPE', value: databaseType }
            // Default orchestrator (runtime-switchable per request)
            { name: 'ORCHESTRATOR', value: 'agent_framework' }
          ],
          enableMonitoring
            ? [
                {
                  name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
                  value: applicationInsights!.outputs.connectionString
                }
              ]
            : []
        )
      }
    ]
  }
}

// ===================== //
// Outputs               //
// ===================== //
// Outputs are wired in the Phase 1E unit (#17) once every module exists.
// A single placeholder is emitted now so `azd env get-values` returns at least
// the suffix needed by post-provision scripts.
// Outputs are wired in the Phase 1E unit (#17) once every module exists.
// A single placeholder is emitted now so `azd env get-values` returns at least
// the suffix needed by post-provision scripts.

@description('Lower-cased solution suffix used in every downstream resource name.')
output AZURE_SOLUTION_SUFFIX string = solutionSuffix

@description('Selected database engine for chat history + vector index (locked at deploy).')
output AZURE_DB_TYPE string = databaseType

@description('Resource group containing the deployment.')
output AZURE_RESOURCE_GROUP string = resourceGroup().name
