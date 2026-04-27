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
var deploymentContainerName = 'deployment-package'

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
        {
          // Flex Consumption Function App pulls its zipped runtime from
          // this container via the UAMI assigned below. Created here so
          // the function app deployment never has to provision storage.
          name: deploymentContainerName
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

// ----------------------------------------------------------------------
// App Service Plan + frontend Web App.
// Frontend (React/Vite static SPA served by an nginx container) runs on
// App Service rather than ACA because:
//   - Static SPA workload doesn't benefit from scale-to-zero (negligible
//     cold-start matters more for the user-facing landing page).
//   - App Service exposes a stable *.azurewebsites.net hostname suitable
//     for branding / custom-domain CNAME.
//   - Mixed hosting (ACA backend + App Service frontend) follows MACAE's
//     reference layout for plug-and-play deployments.
//
// Phase 1 deploys a placeholder image; the real image is wired in
// azure.yaml `services.frontend` once the frontend Dockerfile ships in
// Phase 2.
// ----------------------------------------------------------------------
var appServicePlanName = 'asp-${solutionSuffix}'
var frontendAppName = 'app-frontend-${solutionSuffix}'
// SKU ladder hoisted per naming-stability rule §11:
//   default            → B1 / 1 worker  (cheapest Linux container plan)
//   enableScalability  → P1v3 / 1 worker (autoscale, faster cold start)
//   enableRedundancy   → P1v3 / 3 workers + zoneRedundant (Premium v3 is
//                        the minimum tier supporting AZ spread; B1 does
//                        NOT support zone redundancy and would fail at
//                        deploy time — the && guard below makes that
//                        guarantee explicit, not coincidental).
var appServicePlanSkuName = enableRedundancy || enableScalability ? 'P1v3' : 'B1'
var appServicePlanSkuCapacity = enableRedundancy ? 3 : 1

module appServicePlan 'br/public:avm/res/web/serverfarm:0.7.0' = {
  name: take('avm.res.web.serverfarm.${solutionSuffix}', 64)
  params: {
    name: appServicePlanName
    location: location
    tags: allTags
    enableTelemetry: false
    kind: 'linux'
    reserved: true
    skuName: appServicePlanSkuName
    skuCapacity: appServicePlanSkuCapacity
    zoneRedundant: enableRedundancy && appServicePlanSkuName == 'P1v3'
  }
}

module frontendWebApp 'br/public:avm/res/web/site:0.22.0' = {
  name: take('avm.res.web.site.frontend.${solutionSuffix}', 64)
  params: {
    name: frontendAppName
    location: location
    tags: union(allTags, { 'azd-service-name': 'frontend' })
    enableTelemetry: false
    kind: 'app,linux,container'
    serverFarmResourceId: appServicePlan.outputs.resourceId
    httpsOnly: true
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    clientAffinityEnabled: false
    managedIdentities: {
      userAssignedResourceIds: [
        userAssignedIdentity.outputs.resourceId
      ]
    }
    diagnosticSettings: enableMonitoring
      ? [
          {
            workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId
          }
        ]
      : []
    siteConfig: {
      // Placeholder image. Replaced by `azd deploy` once the real
      // frontend Dockerfile ships in Phase 2 and is referenced from
      // azure.yaml `services.frontend`.
      linuxFxVersion: 'DOCKER|mcr.microsoft.com/appsvc/staticsite:latest'
      ftpsState: 'FtpsOnly'
      minTlsVersion: '1.2'
      http20Enabled: true
      // App Insights env entry is included only when monitoring is on,
      // so SDKs don't auto-init against an empty connection string.
      appSettings: union(
        [
          // VITE_BACKEND_URL is consumed by the Vite build step (see
          // azd post-provision hook + frontend Dockerfile in Phase 2)
          // via `azd env get-values`. It is set here for parity and
          // diagnostics only — the running container does NOT read it,
          // since the SPA is fully static once built.
          {
            name: 'VITE_BACKEND_URL'
            value: 'https://${backendContainerApp.outputs.fqdn}'
          }
          // Tell App Service to pull the image from MCR (no ACR creds).
          // (No AZURE_CLIENT_ID here — the SPA does not call Azure
          // directly. All Azure calls go through the FastAPI backend per
          // plug-and-play rule §4. UAMI on the site is for ACR pull only.)
          { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false' }
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
  }
}

// ----------------------------------------------------------------------
// Function App (Flex Consumption) + Event Grid system topic.
// The Function App hosts the modular RAG indexing pipeline:
//   - batch_start  — list blobs in /documents/, enqueue per-blob messages
//   - batch_push   — Storage Queue trigger; parse, chunk, embed, push to
//                    the configured vector index (AI Search OR Postgres)
//   - add_url      — HTTP trigger; fetch URL content, parse, embed
// Event Grid system topic on the Storage Account fans out BlobCreated
// notifications under /documents/ to the doc-processing queue, which
// triggers batch_push.
//
// Flex Consumption (FC1) chosen over Premium because:
//   - sub-second cold start, scale-to-zero (cheap when idle)
//   - native AAD-only AzureWebJobsStorage (no shared keys)
//   - built-in always-ready instance support if scale matters later
//
// Identity / no-keys posture: Storage has allowSharedKeyAccess=false,
// so Event Grid → Storage Queue MUST use deliveryWithResourceIdentity
// with the system topic's system-assigned MI, plus a Storage Queue Data
// Message Sender role on that MI. AzureWebJobsStorage uses the function
// app's UAMI via the `AzureWebJobsStorage__credential=managedidentity`
// + `__clientId` pattern.
// ----------------------------------------------------------------------
var functionPlanName = 'plan-func-${solutionSuffix}'
var functionAppName = 'func-${solutionSuffix}'
var eventGridSystemTopicName = 'evgt-${solutionSuffix}'
var functionsPlanSkuName = 'FC1'
var functionsRuntimeName = 'python'
var functionsRuntimeVersion = '3.11'
var docProcessingQueueName = 'doc-processing'
var documentsContainerName = 'documents'
// Built-in role definition GUIDs used by this section.
//   Storage Queue Data Message Sender — for Event Grid → Storage Queue
//   Storage Blob Data Owner           — for AzureWebJobsStorage Flex pkg
var storageQueueDataMessageSenderRoleId = 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a'
var storageBlobDataOwnerRoleId = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'

module functionPlan 'br/public:avm/res/web/serverfarm:0.7.0' = {
  name: take('avm.res.web.serverfarm.func.${solutionSuffix}', 64)
  params: {
    name: functionPlanName
    location: location
    tags: allTags
    enableTelemetry: false
    // `kind: 'functionapp'` (NOT 'linux') is the documented value for
    // Linux Function App plans. `reserved: true` is what actually flips
    // the Linux bit; `kind` is a hint used by the portal. The frontend
    // App Service Plan above uses `kind: 'linux'` because it hosts a
    // generic Web App, not a Function App.
    kind: 'functionapp'
    reserved: true
    skuName: functionsPlanSkuName
    skuCapacity: 0
  }
}

module functionApp 'br/public:avm/res/web/site:0.22.0' = {
  name: take('avm.res.web.site.func.${solutionSuffix}', 64)
  params: {
    name: functionAppName
    location: location
    tags: union(allTags, { 'azd-service-name': 'function' })
    enableTelemetry: false
    kind: 'functionapp,linux'
    serverFarmResourceId: functionPlan.outputs.resourceId
    httpsOnly: true
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    clientAffinityEnabled: false
    managedIdentities: {
      userAssignedResourceIds: [
        userAssignedIdentity.outputs.resourceId
      ]
    }
    diagnosticSettings: enableMonitoring
      ? [
          {
            workspaceResourceId: logAnalyticsWorkspace!.outputs.resourceId
          }
        ]
      : []
    // Flex Consumption-specific runtime + deployment storage. The package
    // is pulled from the deployment-package container on the same storage
    // account using the function's UAMI (UserAssignedIdentity auth).
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storageAccount.outputs.primaryBlobEndpoint}${deploymentContainerName}'
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: userAssignedIdentity.outputs.resourceId
          }
        }
      }
      runtime: {
        name: functionsRuntimeName
        version: functionsRuntimeVersion
      }
      scaleAndConcurrency: {
        maximumInstanceCount: enableScalability ? 100 : 40
        instanceMemoryMB: 2048
      }
    }
    siteConfig: {
      // App Insights env entry is included only when monitoring is on,
      // so the SDK doesn't auto-init against an empty connection string.
      appSettings: union(
        [
          // AAD-only AzureWebJobsStorage — no connection string, UAMI auth.
          { name: 'AzureWebJobsStorage__accountName', value: storageAccount.outputs.name }
          { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
          { name: 'AzureWebJobsStorage__clientId', value: userAssignedIdentity.outputs.clientId }
          // Functions runtime knobs.
          { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
          { name: 'FUNCTIONS_WORKER_RUNTIME', value: functionsRuntimeName }
          // Identity + Foundry endpoints (mirrors backend env so the
          // indexing pipeline can call the embedding model + write to
          // the configured vector index).
          { name: 'AZURE_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
          { name: 'AZURE_TENANT_ID', value: subscription().tenantId }
          { name: 'AZURE_AI_PROJECT_ENDPOINT', value: aiProject.outputs.projectEndpoint }
          { name: 'AZURE_OPENAI_ENDPOINT', value: aiServices.outputs.endpoint }
          { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
          { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
          // Database routing — same flag the backend reads.
          { name: 'AZURE_DB_TYPE', value: databaseType }
          // Storage wiring used by batch_start / batch_push / add_url.
          { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storageAccount.outputs.name }
          { name: 'AZURE_DOCUMENTS_CONTAINER', value: documentsContainerName }
          { name: 'AZURE_DOC_PROCESSING_QUEUE', value: docProcessingQueueName }
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
  }
}

// Function App needs Storage Blob Data Owner on the deployment container
// to upload its package via Flex Consumption's UserAssignedIdentity auth.
// Scoped to the storage account because the AVM module assigns at the
// account level (sub-scoping requires a separate inline child resource,
// not worth it for a deployment-only role).
// `existing` uses the *variable* (compile-time known), not the module
// output (runtime-only) — required for roleAssignment scope/name to
// satisfy BCP120.
resource storageAccountExisting 'Microsoft.Storage/storageAccounts@2024-01-01' existing = {
  // BCP334: take(...) returns string 0..24 chars; storage account name
  // requires min 3. solutionSuffix is generated by MACAE pattern as 8+
  // chars in main.bicep, so the actual value is always 10..24. Suppress
  // the static-analysis warning rather than add a runtime guard.
  #disable-next-line BCP334
  name: storageAccountName
  dependsOn: [ storageAccount ]
}

resource flexDeploymentRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountExisting.id, userAssignedIdentity.name, storageBlobDataOwnerRoleId)
  scope: storageAccountExisting
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataOwnerRoleId)
    principalId: userAssignedIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Event Grid system topic on the Storage Account. Single subscription
// for now: BlobCreated under /documents/ → doc-processing queue. The
// add_url path is HTTP-triggered, not blob-triggered, so it does not
// need an Event Grid subscription.
module eventGridSystemTopic 'br/public:avm/res/event-grid/system-topic:0.6.4' = {
  name: take('avm.res.event-grid.system-topic.${solutionSuffix}', 64)
  params: {
    name: eventGridSystemTopicName
    location: location
    tags: allTags
    enableTelemetry: false
    source: storageAccount.outputs.resourceId
    topicType: 'Microsoft.Storage.StorageAccounts'
    managedIdentities: {
      systemAssigned: true
    }
    eventSubscriptions: [
      {
        name: 'blob-created-to-doc-processing'
        // deliveryWithResourceIdentity (NOT plain destination) is required
        // because storage has allowSharedKeyAccess=false. The system
        // topic's system-assigned MI authenticates to Storage Queue.
        deliveryWithResourceIdentity: {
          identity: {
            type: 'SystemAssigned'
          }
          destination: {
            endpointType: 'StorageQueue'
            properties: {
              resourceId: storageAccount.outputs.resourceId
              queueName: docProcessingQueueName
            }
          }
        }
        filter: {
          includedEventTypes: [ 'Microsoft.Storage.BlobCreated' ]
          subjectBeginsWith: '/blobServices/default/containers/${documentsContainerName}/'
          enableAdvancedFilteringOnArrays: true
        }
        eventDeliverySchema: 'EventGridSchema'
        retryPolicy: {
          maxDeliveryAttempts: 30
          eventTimeToLiveInMinutes: 1440
        }
      }
    ]
  }
}

// Grant the Event Grid system topic's system-assigned MI permission to
// enqueue messages on the storage account's queues.
resource eventGridQueueSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountExisting.id, eventGridSystemTopicName, storageQueueDataMessageSenderRoleId)
  scope: storageAccountExisting
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageQueueDataMessageSenderRoleId)
    // managedIdentities.systemAssigned: true is set unconditionally on
    // the topic above, so this output is always populated. The non-null
    // assertion satisfies Bicep's nullable-output type without the
    // empty-string fallback (which would fail the GUID min-length check).
    principalId: eventGridSystemTopic.outputs.systemAssignedMIPrincipalId!
    principalType: 'ServicePrincipal'
  }
}

// ===================== //
// Outputs               //
// ===================== //
// Every AZURE_* output is consumed by either:
//   - azd post-provision hooks (v2/scripts/post-provision.{sh,ps1}, #19)
//   - the backend / function / frontend at build or run time
//   - operator inspection via `azd env get-values`
// Conditional outputs (cosmosdb-only / postgresql-only / monitoring-only)
// emit empty strings when their gate is off so downstream consumers can
// treat them as "not configured" without null-checks.

// --- Identity / region / suffix ---

@description('Lower-cased solution suffix used in every downstream resource name.')
output AZURE_SOLUTION_SUFFIX string = solutionSuffix

@description('Resource group containing the deployment.')
output AZURE_RESOURCE_GROUP string = resourceGroup().name

@description('Location of the non-AI resources (Container Apps, App Service, Functions, Storage, Cosmos/Postgres).')
output AZURE_LOCATION string = location

@description('Location of the AI Services account + model deployments (independent of AZURE_LOCATION).')
output AZURE_AI_SERVICE_LOCATION string = azureAiServiceLocation

@description('Tenant ID for the deployment subscription.')
output AZURE_TENANT_ID string = subscription().tenantId

@description('Client ID of the user-assigned managed identity shared by all v2 workloads.')
output AZURE_UAMI_CLIENT_ID string = userAssignedIdentity.outputs.clientId

@description('Principal (object) ID of the user-assigned managed identity.')
output AZURE_UAMI_PRINCIPAL_ID string = userAssignedIdentity.outputs.principalId

@description('Resource ID of the user-assigned managed identity.')
output AZURE_UAMI_RESOURCE_ID string = userAssignedIdentity.outputs.resourceId

// --- Database routing flag (mirrored as env on every workload) ---

@description('Selected database engine for chat history + vector index (locked at deploy).')
output AZURE_DB_TYPE string = databaseType

@description('Logical name of the configured vector index store: "AzureSearch" (cosmosdb mode) or "pgvector" (postgresql mode).')
output AZURE_INDEX_STORE string = databaseType == 'cosmosdb' ? 'AzureSearch' : 'pgvector'

// --- Foundry substrate ---

@description('Unified AI Services endpoint. Used by both orchestrators (LangGraph via OpenAI-compatible path; Agent Framework via the project endpoint below).')
output AZURE_AI_SERVICES_ENDPOINT string = aiServices.outputs.endpoint

@description('Foundry Project endpoint (https://<account>.services.ai.azure.com/api/projects/<project>). Required by the Microsoft Agent Framework SDK.')
output AZURE_AI_PROJECT_ENDPOINT string = aiProject.outputs.projectEndpoint

@description('OpenAI-compatible API version pinned for the GPT + reasoning deployments.')
output AZURE_OPENAI_API_VERSION string = azureOpenAiApiVersion

@description('Azure AI Agents API version pinned for the Foundry Project endpoint.')
output AZURE_AI_AGENT_API_VERSION string = azureAiAgentApiVersion

@description('Deployment name of the chat-completions GPT model.')
output AZURE_OPENAI_GPT_DEPLOYMENT string = gptModelName

@description('Deployment name of the o-series reasoning model (output flows on the SSE `reasoning` channel).')
output AZURE_OPENAI_REASONING_DEPLOYMENT string = reasoningModelName

@description('Deployment name of the embedding model used by the indexing pipeline.')
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = embeddingModelName

// --- Conditional: Azure AI Search (cosmosdb mode only) ---

@description('AI Search service endpoint. Empty in postgresql mode.')
output AZURE_AI_SEARCH_ENDPOINT string = databaseType == 'cosmosdb' ? aiSearch!.outputs.endpoint : ''

@description('AI Search service name. Empty in postgresql mode.')
output AZURE_AI_SEARCH_NAME string = databaseType == 'cosmosdb' ? aiSearch!.outputs.name : ''

// --- Conditional: Cosmos DB (cosmosdb mode only) ---

@description('Cosmos DB account endpoint (DocumentEndpoint). Empty in postgresql mode.')
output AZURE_COSMOS_ENDPOINT string = databaseType == 'cosmosdb' ? cosmosDb!.outputs.endpoint : ''

@description('Cosmos DB account name. Empty in postgresql mode.')
output AZURE_COSMOS_ACCOUNT_NAME string = databaseType == 'cosmosdb' ? cosmosDb!.outputs.name : ''

// --- Conditional: PostgreSQL Flexible Server (postgresql mode only) ---

@description('PostgreSQL Flexible Server FQDN (clients add :5432 themselves). Empty in cosmosdb mode.')
output AZURE_POSTGRES_HOST string = databaseType == 'postgresql' ? postgresServer!.outputs.fqdn! : ''

@description('PostgreSQL Flexible Server resource name. Empty in cosmosdb mode.')
output AZURE_POSTGRES_NAME string = databaseType == 'postgresql' ? postgresServer!.outputs.name : ''

@description('Configured Entra admin principal name for the Postgres Flex server (used as the `user` in AAD-token connections by the post-provision hook). Empty in cosmosdb mode.')
output AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME string = databaseType == 'postgresql' ? postgresAdminPrincipalName : ''

// --- Storage (blobs + queues + Function deployment package) ---

@description('Storage account name (shared by RAG document store, indexing queues, and the Function App deployment package).')
output AZURE_STORAGE_ACCOUNT_NAME string = storageAccount.outputs.name

@description('Primary blob endpoint of the shared storage account (https URL ending in /). Hostname follows the storage cloud-specific suffix.')
output AZURE_STORAGE_BLOB_ENDPOINT string = storageAccount.outputs.primaryBlobEndpoint

@description('Container holding documents to be indexed (Event Grid filter + batch_start source).')
output AZURE_DOCUMENTS_CONTAINER string = documentsContainerName

@description('Storage Queue name fed by Event Grid BlobCreated and consumed by the batch_push Function blueprint.')
output AZURE_DOC_PROCESSING_QUEUE string = docProcessingQueueName

// --- Hosting endpoints (consumed by azd hooks, Vite build, smoke tests) ---

@description('Public URL of the backend Container App (FastAPI + LangGraph/Agent Framework).')
output AZURE_BACKEND_URL string = 'https://${backendContainerApp.outputs.fqdn}'

@description('Public URL of the frontend Web App (React/Vite SPA). Backend CORS must allow this origin.')
output AZURE_FRONTEND_URL string = 'https://${frontendWebApp.outputs.defaultHostname}'

@description('Public URL of the Function App hosting the indexing pipeline.')
output AZURE_FUNCTION_APP_URL string = 'https://${functionApp.outputs.defaultHostname}'

@description('Function App resource name (used by azd to deploy the function package).')
output AZURE_FUNCTION_APP_NAME string = functionApp.outputs.name

// --- Conditional: monitoring ---

@description('Application Insights connection string. Empty when enableMonitoring=false.')
output AZURE_APP_INSIGHTS_CONNECTION_STRING string = enableMonitoring ? applicationInsights!.outputs.connectionString : ''
