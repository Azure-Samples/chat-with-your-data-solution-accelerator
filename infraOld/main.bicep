// ========================================================================
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
      'OpenAI.Standard.text-embedding-3-large,100'
    ]
  }
})
@description('Required. Region for AI Services / Foundry deployments. Restricted to regions with GPT-5.1 GlobalStandard availability.')
param azureAiServiceLocation string

@description('Optional. Azure region for the Azure AI Search service. Empty (default) co-locates Search with the non-AI resources (the location parameter). Set this to a different region when the primary region has no Azure AI Search capacity (InsufficientResourcesAvailable). Search is reachable cross-region in the public profile (no private endpoints).')
param searchServiceLocation string = ''

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
// Ingestion trigger     //
// ===================== //

@allowed([
  'direct_enqueue'
  'event_grid'
])
@description('Optional. How an uploaded document is picked up for indexing. direct_enqueue: the backend admin upload enqueues the doc-processing message itself (works without an Event Grid subscription). event_grid: a storage Event Grid subscription fans BlobCreated/BlobDeleted to the blob-events queue and the blob_event Function translates each (create -> ingest, delete -> de-index), so the backend writes the blob only (no double-ingest). Flip to event_grid only after the blob_event Function blueprint is deployed.')
param ingestionTrigger string = 'direct_enqueue'

// ===================== //
// v1 resource reuse     //
// ===================== //
// When set, the corresponding AVM module is SKIPPED and a raw `existing`
// reference + minimal child resources + UAMI role assignments are
// created instead. Same RG only. Lets v2 coexist with a v1 deployment
// in the same resource group without provisioning duplicate accounts.

@description('Optional. Existing Azure AI Search service name to reuse. Same RG. When set, the new aiSearch module is skipped and only RBAC role assignments are added.')
param existingSearchName string = ''

@description('Optional. Existing Cosmos DB account name to reuse. Same RG. When set, the new cosmosDb module is skipped and only the new SQL database "cwyd" + container "conversations" + UAMI SQL role are added.')
param existingCosmosName string = ''

@description('Optional. Existing Storage Account name to reuse. Same RG. When set, the new storageAccount module is skipped and only missing containers/queues + UAMI role assignments are added.')
param existingStorageName string = ''

@description('Optional. When reusing v1 storage that already has an Event Grid system topic (Azure permits only one topic per source), set this to that topic name. The Bicep then adds a new event subscription to the existing topic instead of creating a new topic.')
param existingEventGridTopicName string = ''

@description('Optional. Existing Azure OpenAI (or AI Services) account name to reuse for chat + embedding deployments. Same RG. When set, the chat model deployment is placed on this account instead of the v2 Foundry account, and the v2 UAMI is granted Cognitive Services OpenAI User on it. Embedding is assumed to already exist on the reused account.')
param existingOpenAiName string = ''

var useExistingSearch = !empty(existingSearchName)
var useExistingCosmos = !empty(existingCosmosName)
var useExistingStorage = !empty(existingStorageName)
var useExistingEventGridTopic = !empty(existingEventGridTopicName)
var useExistingOpenAi = !empty(existingOpenAiName)

// Built-in role definition GUID: Cognitive Services OpenAI User --
// grants inference on Cognitive Services / OpenAI account deployments.
var cognitiveServicesOpenAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

var effectiveSearchLocation = empty(searchServiceLocation) ? location : searchServiceLocation

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

@description('Optional. Foundry IQ knowledge base name the agent_framework orchestrator grounds on (cosmosdb mode). Must match the name seeded by post_provision.py and resolved through the Project-Search connection.')
param searchKnowledgeBaseName string = 'cwyd-kb'

@description('Optional. Foundry IQ knowledge source name backing the knowledge base (the search-index knowledge source seeded by post_provision.py).')
param searchKnowledgeSourceName string = 'cwyd-index-ks'

@description('Optional. Chat index name the azure_search provider reads/writes and post_provision.py creates. Single-sourced so the backend env binding and the azd output (consumed by the postdeploy seed self-check) cannot diverge.')
param searchIndexName string = 'cwyd-index'

@description('Optional. Foundry IQ knowledge base / knowledge source REST API version (operator-tunable so the KB protocol can advance without a new image).')
param searchKnowledgeBaseApiVersion string = '2025-11-01-preview'

// Per ADR 0008 (lazy-foundry-agent-bootstrap), the Foundry agent
// identity is not an operator-supplied env value: the runtime resolves
// it lazily on first request and persists the id in the chat-history
// database (Cosmos in cosmosdb-mode, Postgres in postgresql-mode). Pin
// specific agents through the registry-backed agents provider instead.

// ===================== //
// WAF flags             //
// ===================== //

@description('Optional. Deploy Log Analytics + Application Insights and wire diagnostic settings on every applicable resource. Defaults to `true` for any deployed env (ADR-0018): observability is Stable Core, not a WAF opt-in. The `false` branch stays only for `bicep build` self-checks and unit tests.')
param enableMonitoring bool = true

@description('Optional. Higher SKUs and autoscaling on App Service Plan, Container Apps, Search, and PostgreSQL.')
param enableScalability bool = false

@description('Optional. Zone-redundant + paired-region failover on databases, App Service Plan, Container Apps, and Storage.')
param enableRedundancy bool = false

@description('Optional. Deploy a VNet, private endpoints, and disable public network access on data-plane resources. Wires the regional VNet (`modules/virtualNetwork.bicep`), private DNS zones, private endpoints for every data-plane resource, regional VNet integration for compute, and Bastion. Setting this to true is the WAF-aligned topology and requires no follow-up tasks; flipping it back to false re-enables public endpoints with default firewall rules.')
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
// below is provisioned with publicNetworkAccess='Disabled', the VNet
// + private DNS zones + private endpoints are wired in, and compute
// (Container Apps, Function App) connects via regional VNet
// integration. The flag is the supported WAF-aligned topology and
// requires no follow-up work to enable.

// Deployer identity -- used to grant the seed hook storage data-plane access.
var deployerPrincipalId = deployer().objectId
var deployerPrincipalType = contains(deployer(), 'userPrincipalName') ? 'User' : 'ServicePrincipal'


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
// Reference: reference-architecture pattern: managed-identity + RBAC +
// no Key Vault for app secrets.
var identityName = 'id-${solutionSuffix}'
module userAssignedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: take('avm.res.managed-identity.user-assigned-identity.${solutionSuffix}', 64)
  params: {
    name: identityName
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
    disableLocalAuth: false
    // Local auth is enabled so connection-string / instrumentation-key
    // ingestion is accepted. The `Monitoring Metrics Publisher` role
    // below is retained but unused.
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'Monitoring Metrics Publisher'
      }
    ]
  }
}

// ----------------------------------------------------------------------
// Virtual network (conditional). Wraps AVM
// `network/virtual-network:0.7.0` + per-subnet NSGs. Address plan and
// subnet roles documented in infra/modules/virtualNetwork.bicep.
//
// `databaseType` is forwarded so the wrapper only allocates the
// Postgres-delegated subnet in postgresql mode. Diagnostic logs are
// piped to Log Analytics when monitoring is enabled, otherwise the
// VNet ships without diagnostic settings (avoids a hard dependency on
// the optional workspace).
// ----------------------------------------------------------------------
module virtualNetwork 'modules/virtualNetwork.bicep' = if (enablePrivateNetworking) {
  name: take('module.virtual-network.${solutionSuffix}', 64)
  params: {
    name: 'vnet-${solutionSuffix}'
    location: location
    tags: allTags
    databaseType: databaseType
    resourceSuffix: solutionSuffix
    logAnalyticsWorkspaceId: enableMonitoring ? logAnalyticsWorkspace!.outputs.resourceId : ''
    enableTelemetry: false
  }
}

// ----------------------------------------------------------------------
// Private DNS zones (conditional). One AVM
// `network/private-dns-zone:0.8.1` deployment per zone, linked to the
// VNet. Zone selection is driven by `databaseType` so we only
// create zones we will actually wire to a private endpoint:
//
//   Always (when enablePrivateNetworking=true):
//     0  cognitiveservices.azure.com   - AI Services account
//     1  openai.azure.com              - OpenAI endpoint on AI Services
//     2  services.ai.azure.com         - Foundry Project
//     3  blob.<storage-suffix>         - Storage blob
//     4  queue.<storage-suffix>        - Storage queue
//     5  file.<storage-suffix>         - Storage file
//
//   cosmosdb mode only:
//     6  documents.azure.com           - Cosmos DB
//     7  search.windows.net            - AI Search
//
//   postgresql mode only:
//     6  postgres.database.azure.com   - Postgres Flexible Server
//                                        (used as `privateDnsZoneArmResourceId`
//                                        on the AVM module, NOT a private
//                                        endpoint - VNet-integrated Postgres
//                                        Flex has no PE model)
//
// Index constants are exposed via `dnsZoneIndex` so PE wiring stays
// readable. Indices >= 6 are mode-specific - the wrong mode reads
// `null` from the array, which the consuming module deals with by simply
// not deploying that PE in the wrong mode (gated by the same flag).
// ----------------------------------------------------------------------

var alwaysOnPrivateDnsZones = [
  'privatelink.cognitiveservices.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.services.ai.azure.com'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.queue.${environment().suffixes.storage}'
  'privatelink.file.${environment().suffixes.storage}'
]

var cosmosModePrivateDnsZones = [
  'privatelink.documents.azure.com'
  'privatelink.search.windows.net'
]

var postgresModePrivateDnsZones = [
  'privatelink.postgres.database.azure.com'
]

var privateDnsZones = concat(
  alwaysOnPrivateDnsZones,
  databaseType == 'postgresql' ? postgresModePrivateDnsZones : cosmosModePrivateDnsZones
)

// Named index map so PE wiring reads as
// `avmPrivateDnsZones[dnsZoneIndex.cognitiveServices]!.outputs.resourceId`
// instead of magic numbers. Postgres / Cosmos / Search share index 6+ but
// the consuming PE blocks are themselves gated on databaseType, so a
// cosmosdb-mode build will never read `dnsZoneIndex.postgres` and vice versa.
var dnsZoneIndex = {
  cognitiveServices: 0
  openAI: 1
  aiServicesProject: 2
  blob: 3
  queue: 4
  file: 5
  cosmosDb: 6
  search: 7
  postgres: 6
}

@batchSize(5)
module avmPrivateDnsZones 'br/public:avm/res/network/private-dns-zone:0.8.1' = [
  for (zone, i) in privateDnsZones: if (enablePrivateNetworking) {
    name: take('avm.res.network.private-dns-zone.${replace(zone, '.', '-')}.${solutionSuffix}', 64)
    params: {
      name: zone
      tags: allTags
      enableTelemetry: false
      virtualNetworkLinks: [
        {
          name: take('vnetlink-${solutionSuffix}-${replace(zone, '.', '-')}', 80)
          virtualNetworkResourceId: virtualNetwork!.outputs.resourceId
          registrationEnabled: false
        }
      ]
    }
  }
]

// ----------------------------------------------------------------------
// Azure Bastion (CONDITIONAL -- enablePrivateNetworking only).
//
// Operator access path into the private network. No jumpbox VM:
// operators connect via the Azure portal's browser-based Bastion
// experience, or use Bastion's `az network bastion tunnel` for kubectl
// / psql forwarded ports through the deployer's az session.
//
// Standard SKU is required for IP-based connect (no target NIC needed)
// and tunnelling. Deploys into the dedicated /26 `AzureBastionSubnet`
// (Azure requires that exact subnet name) defined in the VNet module.
// ----------------------------------------------------------------------
module bastion 'br/public:avm/res/network/bastion-host:0.8.2' = if (enablePrivateNetworking) {
  name: take('avm.res.network.bastion-host.${solutionSuffix}', 64)
  params: {
    name: 'bas-${solutionSuffix}'
    location: location
    tags: allTags
    enableTelemetry: false
    skuName: 'Standard'
    virtualNetworkResourceId: virtualNetwork!.outputs.resourceId
    publicIPAddressObject: {
      name: 'pip-bas-${solutionSuffix}'
      publicIPAllocationMethod: 'Static'
      skuName: 'Standard'
      skuTier: 'Regional'
      tags: allTags
    }
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
    // When `useExistingOpenAi` is true, all chat/embedding
    // deployments live on the reused v1 OpenAI account (see
    // `existingOpenAi` block below) and the Foundry account itself runs
    // with an empty deployments set; agents reach the model via the v1
    // OAI endpoint exported as AZURE_OPENAI_ENDPOINT. Otherwise Foundry
    // hosts the two deployments directly.
    deployments: useExistingOpenAi ? [] : [
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
        roleDefinitionIdOrName: cognitiveServicesOpenAiUserRoleId
      }
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Azure AI User (Foundry Project data-plane)
        roleDefinitionIdOrName: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
      }
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Cognitive Services User -- data-plane access for DocumentIntelligence
        // + Content Understanding calls against the AI Services account.
        roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908'
      }
    ]
    // Private endpoint into the `peps` subnet with three DNS zone configs:
    // cognitiveservices (account control plane), openai (model data plane),
    // and services.ai.azure.com (Foundry Project + Agents data plane).
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${aiServicesName}'
            customNetworkInterfaceName: 'nic-${aiServicesName}'
            subnetResourceId: virtualNetwork!.outputs.pepsSubnetResourceId
            service: 'account'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'cognitiveservices'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
                }
                {
                  name: 'openai'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.openAI]!.outputs.resourceId
                }
                {
                  name: 'aiServicesProject'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.aiServicesProject]!.outputs.resourceId
                }
              ]
            }
          }
        ]
      : []
  }
}

// ----------------------------------------------------------------------
// EXISTING Azure OpenAI account reuse (when `existingOpenAiName` is
// set). Single-tenant deployments place v2 alongside v1 in the same
// resource group and reuse v1's OpenAI account rather than provisioning
// a second one. The chat deployment is added as a child
// resource of the reused account; the embedding deployment is assumed
// to already exist on v1 (text-embedding-3-small). The v2 UAMI is
// granted Cognitive Services OpenAI User at the account scope so the
// backend + indexing pipeline can call inference.
// ----------------------------------------------------------------------
resource existingOpenAi 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (useExistingOpenAi) {
  name: existingOpenAiName
}

resource existingOpenAiGptDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (useExistingOpenAi) {
  parent: existingOpenAi
  name: gptModelName
  sku: {
    name: gptModelDeploymentType
    capacity: gptModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: gptModelName
      version: gptModelVersion
    }
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

resource existingOpenAiUamiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingOpenAi) {
  name: guid(existingOpenAi!.id, userAssignedIdentity.name, cognitiveServicesOpenAiUserRoleId)
  scope: existingOpenAi
  properties: {
    // Cognitive Services OpenAI User -- grants inference on every
    // deployment on the account (chat, embedding).
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUserRoleId)
    principalId: userAssignedIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Effective OpenAI endpoint consumed by the backend and indexing
// pipeline. When reusing v1 OAI, this points at the v1 account
// (`https://<name>.openai.azure.com/`); otherwise it falls back to the
// v2 Foundry account endpoint where the deployments live.
var effectiveOpenAiEndpoint = useExistingOpenAi ? 'https://${existingOpenAiName}.openai.azure.com/' : aiServices.outputs.endpoint

// Foundry Project -- child of the AI Services account. Hosts agents
// (Agent Framework orchestrator) and knowledge bases (Foundry IQ).
//
// NOTE on Foundry Tools: Document Intelligence and
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
// Azure Speech.
//
// Standalone `Microsoft.CognitiveServices/accounts` of kind
// `SpeechServices` powers the browser-side mic button on the chat
// composer (src/frontend/src/hooks/useSpeechRecognition.ts). The
// backend `mint_speech_token()` helper (src/backend/core/speech.py)
// exchanges the UAMI's AAD token for a 10-minute Speech authorization
// token via the regional `sts/v1.0/issueToken` endpoint, then the
// browser SDK talks to Speech directly -- no audio ever flows back
// through this backend.
//
// Local auth disabled (Hard Rule #2 -- no subscription keys, no Key
// Vault). The UAMI gets `Cognitive Services Speech User`
// (`f2dc8367-1007-4938-bd23-fe263f013447`) which is the data-plane
// role required by the issueToken STS exchange.
//
// Always-on (no `if` gate). S0 SKU has no per-resource cost; charges
// only on actual STT minutes.
// ----------------------------------------------------------------------
var speechServiceName = 'spch-${solutionSuffix}'

module speechService 'br/public:avm/res/cognitive-services/account:0.13.0' = {
  name: take('avm.res.cognitive-services.account.speech.${solutionSuffix}', 64)
  params: {
    name: speechServiceName
    location: azureAiServiceLocation
    tags: allTags
    enableTelemetry: false
    kind: 'SpeechServices'
    sku: 'S0'
    customSubDomainName: speechServiceName
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
        // Cognitive Services Speech User -- data-plane role for STS
        // issueToken + Speech recognition / synthesis.
        roleDefinitionIdOrName: 'f2dc8367-1007-4938-bd23-fe263f013447'
      }
    ]
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${speechServiceName}'
            customNetworkInterfaceName: 'nic-${speechServiceName}'
            subnetResourceId: virtualNetwork!.outputs.pepsSubnetResourceId
            service: 'account'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'cognitiveservices'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
                }
              ]
            }
          }
        ]
      : []
  }
}

// ----------------------------------------------------------------------
// Azure AI Content Safety.
//
// Standalone `Microsoft.CognitiveServices/accounts` of kind
// `ContentSafety` powers the prompt-shielding guard layered on top
// of the chat pipeline. The backend `ContentSafetyGuard`
// (src/backend/core/tools/content_safety.py) screens inbound user
// prompts via the AnalyzeText API; lifespan wiring in
// src/backend/app.py constructs the async client behind the
// `AZURE_CONTENT_SAFETY_ENABLED` + `AZURE_CONTENT_SAFETY_ENDPOINT`
// gate and stashes it on `app.state.content_safety_client`. The
// admin runtime toggle (`RuntimeConfig.content_safety_enabled`)
// flips the guard off per-request without rebuilding the client.
//
// Local auth disabled (no subscription keys, no Key Vault). The
// Cognitive Services User RBAC role assignment to the workload UAMI
// is wired alongside the backend container app env-var bindings.
//
// Always-on (no `if` gate). S0 SKU has no per-resource baseline
// cost; charges only on actual AnalyzeText calls.
// ----------------------------------------------------------------------
var contentSafetyServiceName = 'cs-${solutionSuffix}'

module cogContentSafety 'br/public:avm/res/cognitive-services/account:0.13.0' = {
  name: take('avm.res.cognitive-services.account.contentsafety.${solutionSuffix}', 64)
  params: {
    name: contentSafetyServiceName
    location: azureAiServiceLocation
    tags: allTags
    enableTelemetry: false
    kind: 'ContentSafety'
    sku: 'S0'
    customSubDomainName: contentSafetyServiceName
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
        // Cognitive Services User -- data-plane role for the AnalyzeText
        // call used by `ContentSafetyGuard.screen()`.
        roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908'
      }
    ]
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${contentSafetyServiceName}'
            customNetworkInterfaceName: 'nic-${contentSafetyServiceName}'
            subnetResourceId: virtualNetwork!.outputs.pepsSubnetResourceId
            service: 'account'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'cognitiveservices'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
                }
              ]
            }
          }
        ]
      : []
  }
}

// ----------------------------------------------------------------------
// Azure AI Search (CONDITIONAL -- cosmosdb mode only).
// In postgresql mode the index store is pgvector inside the Postgres
// Flexible Server, so Search is not deployed at all. RBAC grants the
// workload UAMI both data-plane (index read/write) and control-plane
// (manage indexers from the Function App) access. The Foundry Project
// connection to this Search service is wired by
// modules/ai-project-search-connection.bicep so Foundry IQ knowledge
// bases can resolve this Search service by friendly name.
// ----------------------------------------------------------------------
module aiSearch 'br/public:avm/res/search/search-service:0.12.0' = if (databaseType == 'cosmosdb' && !useExistingSearch) {
  name: take('avm.res.search.search-service.${solutionSuffix}', 64)
  params: {
    name: 'srch-${solutionSuffix}'
    location: effectiveSearchLocation
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
        // Search Index Data Reader -- lets the Foundry Project (and Foundry IQ) query indexes through the connection.
        roleDefinitionIdOrName: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
      }
      {
        principalId: aiProject.outputs.projectPrincipalId
        principalType: 'ServicePrincipal'
        // Search Service Contributor -- lets the Foundry Project (and Foundry IQ)
        // manage indexes/indexers/skillsets through the Project-Search connection.
        roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
      }
      {
        principalId: deployerPrincipalId
        principalType: deployerPrincipalType
        // Search Index Data Reader -- deployer reads the index document count during the post-deploy seed self-check (disableLocalAuth is on, so the data plane is RBAC-only).
        roleDefinitionIdOrName: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
      }
    ]
    // Private endpoint into the `peps` subnet, group `searchService`,
    // bound to the search.windows.net DNS zone.
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-srch-${solutionSuffix}'
            customNetworkInterfaceName: 'nic-srch-${solutionSuffix}'
            subnetResourceId: virtualNetwork!.outputs.pepsSubnetResourceId
            service: 'searchService'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'search'
                  // Search PE deploys in cosmosdb mode only. In postgresql mode the zone
                  // array is shorter and the literal `dnsZoneIndex.search` (7) is out of
                  // range for ARM's static index validation, so resolve to a valid in-range
                  // index. The value is never used because this PE is gated out in that mode.
                  privateDnsZoneResourceId: avmPrivateDnsZones[databaseType == 'cosmosdb' ? dnsZoneIndex.search : dnsZoneIndex.postgres]!.outputs.resourceId
                }
              ]
            }
          }
        ]
      : []
  }
}

// ----------------------------------------------------------------------
// EXISTING Azure AI Search service reuse (when existingSearchName is
// set). Adds the same RBAC role grants the new aiSearch module would,
// but on the v1 service instead. v2 creates its own index name (e.g.
// `cwyd-index`) inside the shared service alongside v1's index.
// ----------------------------------------------------------------------
resource existingSearch 'Microsoft.Search/searchServices@2024-06-01-preview' existing = if (databaseType == 'cosmosdb' && useExistingSearch) {
  name: existingSearchName
}

resource existingSearchUamiIndexContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (databaseType == 'cosmosdb' && useExistingSearch) {
  name: guid(existingSearch!.id, userAssignedIdentity.name, '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  scope: existingSearch
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
    principalId: userAssignedIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

resource existingSearchUamiServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (databaseType == 'cosmosdb' && useExistingSearch) {
  name: guid(existingSearch!.id, userAssignedIdentity.name, '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
  scope: existingSearch
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
    principalId: userAssignedIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

resource existingSearchProjectIndexReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (databaseType == 'cosmosdb' && useExistingSearch) {
  name: guid(existingSearch!.id, aiProject.name, '1407120a-92aa-4202-b7e9-c0e197c71c8f')
  scope: existingSearch
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
    principalId: aiProject.outputs.projectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Foundry IQ knowledge bases call their query-planning chat model with
// the Search service's system-assigned managed identity (the knowledge
// base model `authIdentity` is null, which defaults to the Search MI).
// That identity therefore needs Cognitive Services OpenAI User on the
// account hosting the chat deployment, or the model call 401s and
// knowledge-base retrieval returns nothing. The chat model lives on the
// new Foundry account (default) or a reused v1 OpenAI account
// (`useExistingOpenAi`); the principal is the new Search service's
// system MI. Reusing an existing Search service (`useExistingSearch`)
// is not covered here because v2 does not own that service's identity
// configuration -- grant Cognitive Services OpenAI User to the reused
// Search service's identity on the chat-model account manually.
resource aiServicesAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (databaseType == 'cosmosdb' && !useExistingSearch && !useExistingOpenAi) {
  name: aiServicesName
}

resource searchOpenAiUserOnFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (databaseType == 'cosmosdb' && !useExistingSearch && !useExistingOpenAi) {
  name: guid(aiServicesAccount.id, 'srch-${solutionSuffix}', subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUserRoleId))
  scope: aiServicesAccount
  properties: {
    // Cognitive Services OpenAI User -- lets the Search MI call the KB
    // query-planning chat deployment on the Foundry account.
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUserRoleId)
    principalId: aiSearch!.outputs.systemAssignedMIPrincipalId!
    principalType: 'ServicePrincipal'
  }
}

resource searchOpenAiUserOnReusedOpenAi 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (databaseType == 'cosmosdb' && !useExistingSearch && useExistingOpenAi) {
  name: guid(existingOpenAi!.id, 'srch-${solutionSuffix}', subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUserRoleId))
  scope: existingOpenAi
  properties: {
    // Cognitive Services OpenAI User -- lets the Search MI call the KB
    // query-planning chat deployment on the reused v1 OpenAI account.
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUserRoleId)
    principalId: aiSearch!.outputs.systemAssignedMIPrincipalId!
    principalType: 'ServicePrincipal'
  }
}

var effectiveSearchName = useExistingSearch ? existingSearchName : (databaseType == 'cosmosdb' ? aiSearch!.outputs.name : '')
var effectiveSearchEndpoint = useExistingSearch ? 'https://${existingSearchName}.search.windows.net' : (databaseType == 'cosmosdb' ? aiSearch!.outputs.endpoint : '')

// Foundry Project ↔ Search connection (cosmosdb mode only). Lets Foundry
// IQ knowledge bases resolve this Search service by friendly name and
// authenticate via the Project's system-assigned identity (no API keys).
module aiProjectSearchConnection 'modules/ai-project-search-connection.bicep' = if (databaseType == 'cosmosdb') {
  name: take('module.ai-project-search-connection.${solutionSuffix}', 64)
  params: {
    aiServicesAccountName: aiServicesName
    projectName: aiProject.outputs.name
    searchServiceName: effectiveSearchName
    knowledgeBaseName: searchKnowledgeBaseName
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

module storageAccount 'br/public:avm/res/storage/storage-account:0.32.0' = if (!useExistingStorage) {
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
    // AVM storage defaults networkAcls.defaultAction to Deny.
    // With private networking off (no private endpoints) that firewall
    // blocks the Flex Consumption package upload and Event Grid queue
    // delivery. Allow public access on the no-private-net profile; the
    // private-networking profile keeps Deny (the private endpoints cover
    // internal access). AzureServices bypass lets first-party services
    // (Event Grid, the Function host) reach the account regardless.
    networkAcls: {
      defaultAction: enablePrivateNetworking ? 'Deny' : 'Allow'
      bypass: 'AzureServices'
    }
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
        { name: 'blob-events' }
        { name: 'blob-events-poison' }
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
      {
        principalId: deployerPrincipalId
        principalType: deployerPrincipalType
        // Storage Blob Data Contributor (deployer seeds sample documents)
        roleDefinitionIdOrName: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
      }
      {
        principalId: deployerPrincipalId
        principalType: deployerPrincipalType
        // Storage Queue Data Message Sender (deployer enqueues seed doc-processing messages)
        roleDefinitionIdOrName: 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a'
      }
    ]
    // Three private endpoints (blob, queue, file) into the `peps` subnet.
    // Each binds to its matching private DNS zone so internal callers
    // resolve `<account>.blob.<storage-suffix>` etc. to a private IP.
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-blob-${storageAccountName}'
            customNetworkInterfaceName: 'nic-blob-${storageAccountName}'
            subnetResourceId: virtualNetwork!.outputs.pepsSubnetResourceId
            service: 'blob'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'blob'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.blob]!.outputs.resourceId
                }
              ]
            }
          }
          {
            name: 'pep-queue-${storageAccountName}'
            customNetworkInterfaceName: 'nic-queue-${storageAccountName}'
            subnetResourceId: virtualNetwork!.outputs.pepsSubnetResourceId
            service: 'queue'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'queue'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.queue]!.outputs.resourceId
                }
              ]
            }
          }
          {
            name: 'pep-file-${storageAccountName}'
            customNetworkInterfaceName: 'nic-file-${storageAccountName}'
            subnetResourceId: virtualNetwork!.outputs.pepsSubnetResourceId
            service: 'file'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'file'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.file]!.outputs.resourceId
                }
              ]
            }
          }
        ]
      : []
  }
}

// ----------------------------------------------------------------------
// EXISTING Storage account reuse (when existingStorageName is set).
// Creates missing blob containers + queues + UAMI role assignments on
// v1's storage. PUT-on-PUT is idempotent for child resources, so this
// safely co-exists with v1's own containers/queues. The parent symbol
// `storageAccountExisting` is declared once later in this file (just
// before the Event Grid system topic) and resolves to either the new or
// the v1 storage account based on useExistingStorage.
// ----------------------------------------------------------------------
resource existingStorageBlobServices 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' existing = if (useExistingStorage) {
  parent: storageAccountExisting
  name: 'default'
}

resource existingStorageDocumentsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = if (useExistingStorage) {
  parent: existingStorageBlobServices
  name: 'documents'
  properties: { publicAccess: 'None' }
}

resource existingStorageConfigContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = if (useExistingStorage) {
  parent: existingStorageBlobServices
  name: 'config'
  properties: { publicAccess: 'None' }
}

resource existingStorageQueueServices 'Microsoft.Storage/storageAccounts/queueServices@2024-01-01' existing = if (useExistingStorage) {
  parent: storageAccountExisting
  name: 'default'
}

resource existingStorageQueueDocProcessing 'Microsoft.Storage/storageAccounts/queueServices/queues@2024-01-01' = if (useExistingStorage) {
  parent: existingStorageQueueServices
  name: 'doc-processing'
  properties: {}
}

resource existingStorageQueueDocProcessingPoison 'Microsoft.Storage/storageAccounts/queueServices/queues@2024-01-01' = if (useExistingStorage) {
  parent: existingStorageQueueServices
  name: 'doc-processing-poison'
  properties: {}
}

resource existingStorageQueueBlobEvents 'Microsoft.Storage/storageAccounts/queueServices/queues@2024-01-01' = if (useExistingStorage) {
  parent: existingStorageQueueServices
  name: 'blob-events'
  properties: {}
}

resource existingStorageQueueBlobEventsPoison 'Microsoft.Storage/storageAccounts/queueServices/queues@2024-01-01' = if (useExistingStorage) {
  parent: existingStorageQueueServices
  name: 'blob-events-poison'
  properties: {}
}

resource existingStorageQueueAddUrl 'Microsoft.Storage/storageAccounts/queueServices/queues@2024-01-01' = if (useExistingStorage) {
  parent: existingStorageQueueServices
  name: 'add-url'
  properties: {}
}

resource existingStorageQueueAddUrlPoison 'Microsoft.Storage/storageAccounts/queueServices/queues@2024-01-01' = if (useExistingStorage) {
  parent: existingStorageQueueServices
  name: 'add-url-poison'
  properties: {}
}

// Storage Blob Data Contributor -- read/write uploaded documents
resource existingStorageBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingStorage) {
  name: guid(storageAccountExisting.id, userAssignedIdentity.name, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: storageAccountExisting
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: userAssignedIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Queue Data Contributor -- enqueue + consume indexing messages
resource existingStorageQueueContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingStorage) {
  name: guid(storageAccountExisting.id, userAssignedIdentity.name, '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
  scope: storageAccountExisting
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
    principalId: userAssignedIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Account Contributor -- Function App host storage management
resource existingStorageAccountContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingStorage) {
  name: guid(storageAccountExisting.id, userAssignedIdentity.name, '17d1049b-9a84-46fb-8f53-869881c3d3ab')
  scope: storageAccountExisting
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '17d1049b-9a84-46fb-8f53-869881c3d3ab')
    principalId: userAssignedIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

var effectiveStorageName = useExistingStorage ? existingStorageName : storageAccount!.outputs.name
var effectiveStorageResourceId = useExistingStorage ? storageAccountExisting.id : storageAccount!.outputs.resourceId
var effectiveStorageBlobEndpoint = useExistingStorage ? storageAccountExisting.properties.primaryEndpoints.blob : storageAccount!.outputs.primaryBlobEndpoint

// ----------------------------------------------------------------------
// Cosmos DB (CONDITIONAL -- cosmosdb mode only).
// Stores chat history, one item per message. Partitioned on `userId`
// for high-cardinality even distribution; query patterns are
// "all messages for user X in conversation Y" so userId is the hot path.
// AAD-only (disableLocalAuth) -- workload UAMI gets the built-in
// Cosmos DB Built-in Data Contributor role at data-plane scope.
//
// Capacity model: Serverless by default (cheap, scale-to-zero). When
// enableRedundancy=true we switch to provisioned throughput so we can
// turn on automatic failover + zone redundancy, which serverless
// rejects.
// ----------------------------------------------------------------------
module cosmosDb 'br/public:avm/res/document-db/database-account:0.19.0' = if (databaseType == 'cosmosdb' && !useExistingCosmos) {
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
      networkAclBypass: 'None'
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
    // Private endpoint into the `peps` subnet, group `Sql` (the SQL/NoSQL
    // API surface). Bound to the documents.azure.com private DNS zone.
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-cosno-${solutionSuffix}'
            customNetworkInterfaceName: 'nic-cosno-${solutionSuffix}'
            subnetResourceId: virtualNetwork!.outputs.pepsSubnetResourceId
            service: 'Sql'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'cosmosdb'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.cosmosDb]!.outputs.resourceId
                }
              ]
            }
          }
        ]
      : []
  }
}

// ----------------------------------------------------------------------
// EXISTING Cosmos DB account reuse (when existingCosmosName is set).
// Adds a new SQL database `cwyd` + container `conversations` on the v1
// account, plus a UAMI SQL role assignment. v1's existing databases are
// untouched.
// ----------------------------------------------------------------------
resource existingCosmos 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = if (databaseType == 'cosmosdb' && useExistingCosmos) {
  name: existingCosmosName
}

resource existingCosmosCwydDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = if (databaseType == 'cosmosdb' && useExistingCosmos) {
  parent: existingCosmos
  name: 'cwyd'
  properties: {
    resource: {
      id: 'cwyd'
    }
  }
}

resource existingCosmosConversations 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = if (databaseType == 'cosmosdb' && useExistingCosmos) {
  parent: existingCosmosCwydDb
  name: 'conversations'
  properties: {
    resource: {
      id: 'conversations'
      partitionKey: {
        paths: [ '/userId' ]
        kind: 'Hash'
      }
    }
  }
}

resource existingCosmosUamiRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = if (databaseType == 'cosmosdb' && useExistingCosmos) {
  parent: existingCosmos
  name: guid(existingCosmos!.id, userAssignedIdentity.name, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${existingCosmos!.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: userAssignedIdentity.outputs.principalId
    scope: existingCosmos!.id
  }
}

var effectiveCosmosName = useExistingCosmos ? existingCosmosName : (databaseType == 'cosmosdb' ? cosmosDb!.outputs.name : '')
var effectiveCosmosEndpoint = useExistingCosmos ? existingCosmos!.properties.documentEndpoint : (databaseType == 'cosmosdb' ? cosmosDb!.outputs.endpoint : '')

// ----------------------------------------------------------------------
// PostgreSQL Flexible Server + pgvector (CONDITIONAL -- postgresql mode).
// Single server hosts BOTH chat history (relational tables) AND the
// vector index (pgvector extension). Auth is Entra-only -- the workload
// UAMI is the Entra admin, and the post-provision script
// (`scripts/post-provision.sh`) connects via `psql` with
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

@description('Required when databaseType=postgresql. Display name (UPN, group name, or app name) of the Entra principal above. Surfaced in pg_hba and used by the post-provision script to log in over AAD. No default: a wrong value silently locks the deployer out of the new server.')
param postgresAdminPrincipalName string = ''

// Fail-fast guard: postgresAdminPrincipalName is REQUIRED when
// databaseType=postgresql. Without it, the post-provision script
// cannot acquire an AAD token for the deployer and the new server
// becomes unreachable for schema init. Indexing past the end of an
// empty array aborts ARM template expansion with a clear, named error
// before any resource is provisioned, so the user sees the failure at
// `azd provision` time rather than after the Postgres server stands
// up. Cosmosdb mode is unaffected.
#disable-next-line no-unused-vars
var _validatePostgresAdminPrincipalName = (databaseType == 'postgresql' && empty(postgresAdminPrincipalName))
  ? array([])[0]
  : ''

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
    // Postgres Flex private model = VNet integration via a delegated
    // subnet (Microsoft.DBforPostgreSQL/flexibleServers), NOT a private
    // endpoint. The DNS zone is bound at the server level, not in a PE
    // group. Public access is mutually exclusive with delegation; the
    // AVM module flips it off automatically when delegatedSubnetResourceId
    // is set.
    delegatedSubnetResourceId: enablePrivateNetworking ? virtualNetwork!.outputs.postgresSubnetResourceId : null
    privateDnsZoneArmResourceId: enablePrivateNetworking ? avmPrivateDnsZones[dnsZoneIndex.postgres]!.outputs.resourceId : null
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
// ----------------------------------------------------------------------
var containerAppsEnvName = 'cae-${solutionSuffix}'
var backendAppName = 'ca-backend-${solutionSuffix}'
var frontendContainerAppName = 'ca-frontend-${solutionSuffix}'
var functionContainerAppName = 'ca-func-${solutionSuffix}'
var acaWorkloadProfileName = 'Consumption'
// ACR name must be globally unique, 5-50 alphanumeric (no dashes).
var containerRegistryName = take('cr${replace(solutionSuffix, '-', '')}', 50)

// ----------------------------------------------------------------------
// Backend image coordinates (azd-driven). On a clean first `azd up` the
// AZURE_CONTAINER_REGISTRY_ENDPOINT output does not exist yet, so
// `backendContainerRegistryHostname` is empty and the Container App boots
// from a pullable public placeholder image so the first provision can
// pull. `azd deploy` then builds + pushes the real image and the
// deploy-time `azd-service-name: backend` tag swap patches the live
// revision; later provisions compose the real ACR image reference from
// these params.
// ----------------------------------------------------------------------
@description('Optional. Login server of the registry hosting the backend + frontend images (e.g. cr<suffix>.azurecr.io). Empty until the first provision publishes AZURE_CONTAINER_REGISTRY_ENDPOINT; empty selects a public placeholder image so the first provision can pull.')
param backendContainerRegistryHostname string = ''

@description('Optional. Repository (image) name of the backend container image within the registry.')
param backendContainerImageName string = 'cwyd-backend'

@description('Optional. Tag of the backend container image to deploy.')
param backendContainerImageTag string = 'latest'

@description('Optional. Repository (image) name of the frontend container image within the registry.')
param frontendContainerImageName string = 'cwyd-frontend'

@description('Optional. Tag of the frontend container image to deploy.')
param frontendContainerImageTag string = 'latest'

@description('Optional. Repository (image) name of the function container image within the registry.')
param functionContainerImageName string = 'cwyd-functions'

@description('Optional. Tag of the function container image to deploy.')
param functionContainerImageTag string = 'latest'

// Single source of truth for the Postgres libpq URI so the output, the
// backend ACA env, and the Function App appSettings can't drift.
// Empty in cosmosdb mode (the `!` non-null operators are guarded by the
// ternary -- evaluated only when `databaseType == 'postgresql'`).
// Hard Rule #11 (Bicep): hoist literals repeated 2+ times to a `var`.
var postgresLibpqUri = databaseType == 'postgresql'
  ? 'postgresql://${postgresServer!.outputs.fqdn!}:5432/cwyd?sslmode=require'
  : ''
var indexStoreValue = databaseType == 'cosmosdb' ? 'AzureSearch' : 'pgvector'

module containerAppsEnv 'br/public:avm/res/app/managed-environment:0.13.2' = {
  name: take('avm.res.app.managed-environment.${solutionSuffix}', 64)
  params: {
    name: containerAppsEnvName
    location: location
    tags: allTags
    enableTelemetry: false
    zoneRedundant: enableRedundancy
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    // Private mode: env joins the `containerapps` /23 subnet and ingress
    // gets an internal IP only. The wildcard DNS zone below makes
    // `<app>.<defaultDomain>` resolve to that internal IP from inside
    // the VNet (frontend Web App, Function App, Bastion clients).
    internal: enablePrivateNetworking
    infrastructureSubnetResourceId: enablePrivateNetworking ? virtualNetwork!.outputs.containerAppsSubnetResourceId : null
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

// Private DNS zone for the CAE internal default domain. The env emits
// a per-deployment domain like `purpleforest-1234abcd.<region>.azurecontainerapps.io`;
// in `internal: true` mode that domain only resolves publicly to a
// 404 page and the real ingress is the env's static internal IP.
// We register the zone as `<defaultDomain>` and put a single wildcard
// A-record (`*`) pointing at the static IP, so any container app in
// this env (backend now, more later) becomes reachable as
// `<app>.<defaultDomain>` from inside the VNet without per-app records.
module caeDnsZone 'br/public:avm/res/network/private-dns-zone:0.8.1' = if (enablePrivateNetworking) {
  name: take('avm.res.network.private-dns-zone.cae.${solutionSuffix}', 64)
  params: {
    name: containerAppsEnv.outputs.defaultDomain
    location: 'global'
    tags: allTags
    enableTelemetry: false
    a: [
      {
        name: '*'
        ttl: 3600
        aRecords: [
          {
            ipv4Address: containerAppsEnv.outputs.staticIp
          }
        ]
      }
    ]
    virtualNetworkLinks: [
      {
        name: take('vnetlink-${solutionSuffix}-cae', 80)
        virtualNetworkResourceId: virtualNetwork!.outputs.resourceId
        registrationEnabled: false
      }
    ]
  }
}

// Container Registry -- azd pushes backend + function images here.
// AcrPull is granted to the v2 UAMI so the Container App pulls without
// admin credentials. Output `AZURE_CONTAINER_REGISTRY_ENDPOINT` is read
// by `azd deploy` to discover the push target.
module containerRegistry 'br/public:avm/res/container-registry/registry:0.12.1' = {
  name: take('avm.res.container-registry.registry.${solutionSuffix}', 64)
  params: {
    name: containerRegistryName
    location: location
    tags: allTags
    enableTelemetry: false
    acrSku: 'Basic'
    acrAdminUserEnabled: false
    publicNetworkAccess: 'Enabled'
    networkRuleSetDefaultAction: 'Allow'
    // Basic-SKU ACR ships this policy disabled, which 401s the
    // App Service / Container App managed-identity -> ACR token exchange
    // even with correct AcrPull RBAC. Enable it durably.
    azureADAuthenticationAsArmPolicyStatus: 'enabled'
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        roleDefinitionIdOrName: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
        principalType: 'ServicePrincipal'
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
    // Authenticate the ACR image pull with the UAMI that holds AcrPull on
    // the registry (granted by the containerRegistry roleAssignments
    // above), so the Container App pulls without admin credentials
    // (reference-architecture managed-identity pull pattern). `server` is the same
    // loginServer surfaced as AZURE_CONTAINER_REGISTRY_ENDPOINT; `identity`
    // is the UAMI resource id. Harmless while the placeholder public image
    // is in use (public pull ignores the credential) and active once the
    // real backend image is pushed to ACR.
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: userAssignedIdentity.outputs.resourceId
      }
    ]
    workloadProfileName: acaWorkloadProfileName
    ingressTargetPort: 8000
    // In private mode the CAE itself is `internal: true`, so ingress
    // can only be internal. Setting external=true would either fail
    // ARM validation or silently produce an unroutable FQDN that the
    // wildcard `caeDnsZone` A-record cannot intercept. Frontend +
    // Function App reach the backend via `<app>.<defaultDomain>` resolved
    // by the private DNS link inside the VNet.
    ingressExternal: !enablePrivateNetworking
    ingressAllowInsecure: false
    ingressTransport: 'auto'
    scaleSettings: {
      minReplicas: enableScalability ? 1 : 0
      maxReplicas: enableScalability ? 10 : 3
    }
    containers: [
      {
        name: 'backend'
        // When `backendContainerRegistryHostname` is empty (clean first
        // provision -- the AZURE_CONTAINER_REGISTRY_ENDPOINT output does
        // not exist yet) the container boots from a pullable public
        // placeholder so provisioning succeeds before any image is
        // pushed. Once the real backend image is built + pushed, azd's
        // deploy-time `azd-service-name: backend` tag swap patches the
        // live revision, and subsequent provisions compose the real ACR
        // image reference from the backendContainerImage* params.
        image: empty(backendContainerRegistryHostname)
          ? 'mcr.microsoft.com/k8se/quickstart:latest'
          : '${backendContainerRegistryHostname}/${backendContainerImageName}:${backendContainerImageTag}'
        resources: {
          // AVM v0.22.1 declares `cpu: int | null`, but ACA accepts
          // fractional CPU. `any()` bypasses the over-strict type so
          // we can keep the cheaper 0.5-core default for non-scaled runs.
          cpu: any(enableScalability ? '1.0' : '0.5')
          memory: enableScalability ? '2.0Gi' : '1.0Gi'
        }
        // App Insights env entry is included only when monitoring is on,
        // so SDKs don't auto-init against an empty connection string.
        env: union(
          [
            // Identity + region
            { name: 'AZURE_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
            { name: 'AZURE_UAMI_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
            { name: 'AZURE_TENANT_ID', value: subscription().tenantId }
            // Runtime mode: sets AppSettings.environment, surfaced by
            // GET /api/admin/status. It no longer governs any auth behavior.
            { name: 'AZURE_ENVIRONMENT', value: 'production' }
            // Foundry endpoints (consumed by both orchestrators)
            { name: 'AZURE_AI_PROJECT_ENDPOINT', value: aiProject.outputs.projectEndpoint }
            { name: 'AZURE_OPENAI_ENDPOINT', value: effectiveOpenAiEndpoint }
            // AI Services / Foundry account endpoint -- the data-plane base
            // for DocumentIntelligence + Content Understanding calls.
            { name: 'AZURE_AI_SERVICES_ENDPOINT', value: aiServices.outputs.endpoint }
            { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
            { name: 'AZURE_AI_AGENT_API_VERSION', value: azureAiAgentApiVersion }
            // Foundry agent id is intentionally NOT bound here. The
            // runtime resolves CWYD + RAI agent ids lazily on first
            // request and caches them in the chat-history DB (see
            // ADR 0008 -- lazy-foundry-agent-bootstrap).
            // Model deployment names
            { name: 'AZURE_OPENAI_GPT_DEPLOYMENT', value: gptModelName }
            { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
            // Database routing -- AppSettings.DatabaseSettings reads
            // these to dispatch `databases.create(db_type, ...)` and
            // `search.create(index_store, ...)` (Hard Rule #4). The
            // endpoint vars per mode are conditionally non-empty in the
            // Bicep outputs (lines ~1606-1661); binding both sides
            // unconditionally lets one image deploy to either mode
            // without rebuild.
            { name: 'AZURE_DB_TYPE', value: databaseType }
            { name: 'AZURE_INDEX_STORE', value: indexStoreValue }
            { name: 'AZURE_COSMOS_ENDPOINT', value: effectiveCosmosEndpoint }
            { name: 'AZURE_AI_SEARCH_ENDPOINT', value: effectiveSearchEndpoint }
            // Chat index name the azure_search provider reads/writes. Pinned
            // explicitly so an infra rename can't silently diverge from the
            // index post_provision.py creates (retrieval would break only at
            // query time, not deploy time).
            { name: 'AZURE_AI_SEARCH_INDEX', value: searchIndexName }
            // Foundry IQ knowledge base config (agent_framework orchestrator).
            // The agent grounds on the KB via the Search MCP endpoint
            // ({search}/knowledgebases/{kb}/mcp?api-version=<ver>); the
            // api-version is operator-tunable so the KB protocol can advance
            // without a new image. Defaults match the names post_provision.py
            // seeds; resolved through the Project-Search connection.
            { name: 'AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME', value: searchKnowledgeBaseName }
            { name: 'AZURE_AI_SEARCH_KNOWLEDGE_SOURCE_NAME', value: searchKnowledgeSourceName }
            { name: 'AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION', value: searchKnowledgeBaseApiVersion }
            // Foundry Project ↔ Search connection name (category CognitiveSearch).
            // The agent_framework orchestrator passes this as the KB MCP tool's
            // project_connection_id so Foundry IQ executes retrieval server-side
            // under the Project identity. Empty in postgresql mode (no connection).
            { name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: databaseType == 'cosmosdb' ? '${searchKnowledgeBaseName}-mcp' : '' }
            { name: 'AZURE_POSTGRES_ENDPOINT', value: postgresLibpqUri }
            { name: 'AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME', value: databaseType == 'postgresql' ? 'id-${solutionSuffix}' : '' }
            // Speech: backend mints a 10-min AAD-bearer Speech token for
            // the browser SDK. UAMI holds Cognitive Services Speech User
            // on the spch-* account; resource-id header is required by the
            // STS issueToken exchange.
            { name: 'AZURE_SPEECH_SERVICE_NAME', value: speechService.outputs.name }
            { name: 'AZURE_SPEECH_SERVICE_REGION', value: azureAiServiceLocation }
            { name: 'AZURE_SPEECH_ACCOUNT_RESOURCE_ID', value: speechService.outputs.resourceId }
            // Content Safety -- backend prompt-shielding guard. The
            // Cognitive Services account is always deployed, so ENABLED
            // is statically true at infra level; operators flip the guard
            // OFF per-request via the admin runtime override
            // (RuntimeConfig.content_safety_enabled).
            { name: 'AZURE_CONTENT_SAFETY_ENABLED', value: 'true' }
            { name: 'AZURE_CONTENT_SAFETY_ENDPOINT', value: cogContentSafety.outputs.endpoint }
            // Default orchestrator (runtime-switchable per request). Key matches
            // OrchestratorSettings (env_prefix CWYD_ORCHESTRATOR_ + field `name`).
            // pgvector deployments must ground app-side via langgraph;
            // agent_framework is the cosmosdb/Foundry-IQ default.
            { name: 'CWYD_ORCHESTRATOR_NAME', value: databaseType == 'postgresql' ? 'langgraph' : 'agent_framework' }
            // Storage -- the admin surface writes uploaded documents to the
            // blob container and enqueues each onto the doc-processing queue
            // for the ingestion pipeline; the files route streams blobs back
            // from the same container. The UAMI holds Storage Blob Data Owner
            // + Storage Queue Data Contributor on the account; the blob and
            // queue endpoints are derived from the account name. Mirrors the
            // function app's storage wiring so both runtimes share one
            // container + queue.
            { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: effectiveStorageName }
            { name: 'AZURE_DOCUMENTS_CONTAINER', value: documentsContainerName }
            { name: 'AZURE_DOC_PROCESSING_QUEUE', value: docProcessingQueueName }
            // Ingestion trigger -- direct_enqueue keeps the backend
            // enqueueing the push message on upload; event_grid makes the
            // backend write the blob only and lets the Event Grid -> blob-events
            // -> blob_event Function own the push (no double-ingest).
            { name: 'AZURE_INGESTION_TRIGGER', value: ingestionTrigger }
            // Allowed browser origin for the frontend Container App. Built
            // inline from the app name + the shared Container Apps
            // Environment default domain (not the frontend module output)
            // so there is no frontend<->backend dependency cycle; the
            // backend CORSMiddleware allows this single origin with
            // credentials.
            { name: 'BACKEND_CORS_ORIGINS', value: 'https://${frontendContainerAppName}.${containerAppsEnv.outputs.defaultDomain}' }
          ],
          enableMonitoring
            ? [
                {
                  // Backend ACA is a plain container with no host-level App
                  // Insights agent, so its Python lifespan calls
                  // configure_azure_monitor with the connection string read
                  // from the AZURE_-prefixed typed setting
                  // (ObservabilitySettings, env_prefix=AZURE_). The Function
                  // app keeps the standard APPLICATIONINSIGHTS_CONNECTION_STRING
                  // that its host reads natively. (ADR-0018.)
                  name: 'AZURE_APP_INSIGHTS_CONNECTION_STRING'
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
// Frontend Container App.
// The React/Vite SPA is served by a single-runtime uvicorn container on
// the shared Container Apps Environment (cae-<suffix>), mirroring the
// backend so both services build to the same registry, share the same
// UAMI + AcrPull grant, and reach each other over the CAE default
// domain. External ingress on port 80 (the Dockerfile.frontend `prod`
// stage) so the SPA is publicly reachable in the non-private profile; in
// private mode the CAE is internal and the wildcard caeDnsZone A-record
// resolves it like the backend. The backend origin is injected at
// runtime via the BACKEND_API_URL env var (the SPA fetches it from
// /config on boot), so nothing is baked at build time. Easy Auth stays
// off -- the SPA is anonymous and the FastAPI backend owns auth.
//
// A placeholder image boots the resource on a clean first provision
// (before any image is pushed); `azd deploy` then builds + pushes the
// real image and the deploy-time `azd-service-name: frontend` tag swap
// patches the live revision.
// ----------------------------------------------------------------------
module frontendContainerApp 'br/public:avm/res/app/container-app:0.22.1' = {
  name: take('avm.res.app.container-app.frontend.${solutionSuffix}', 64)
  params: {
    name: frontendContainerAppName
    location: location
    tags: union(allTags, { 'azd-service-name': 'frontend' })
    enableTelemetry: false
    environmentResourceId: containerAppsEnv.outputs.resourceId
    managedIdentities: {
      userAssignedResourceIds: [
        userAssignedIdentity.outputs.resourceId
      ]
    }
    // Pull the image with the shared UAMI that holds AcrPull on the
    // registry (granted by the containerRegistry roleAssignments above),
    // so no admin credentials are needed. Harmless while the public
    // placeholder image is in use and active once the real frontend
    // image is pushed to ACR.
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: userAssignedIdentity.outputs.resourceId
      }
    ]
    workloadProfileName: acaWorkloadProfileName
    // The Dockerfile.frontend `prod` stage serves the SPA on port 80.
    ingressTargetPort: 80
    // Public in the non-private profile so the SPA is reachable; in
    // private mode the CAE is internal, so ingress is internal and
    // resolves via the wildcard caeDnsZone A-record like the backend.
    ingressExternal: !enablePrivateNetworking
    ingressAllowInsecure: false
    ingressTransport: 'auto'
    scaleSettings: {
      minReplicas: enableScalability ? 1 : 0
      maxReplicas: enableScalability ? 10 : 3
    }
    containers: [
      {
        name: 'frontend'
        // When `backendContainerRegistryHostname` is empty (clean first
        // provision -- the AZURE_CONTAINER_REGISTRY_ENDPOINT output does
        // not exist yet) the container boots from a pullable public
        // placeholder so provisioning succeeds before any image is
        // pushed. Once the real frontend image is built + pushed, azd's
        // deploy-time `azd-service-name: frontend` tag swap patches the
        // live revision, and subsequent provisions compose the real ACR
        // image reference from the frontendContainerImage* params.
        image: empty(backendContainerRegistryHostname)
          ? 'mcr.microsoft.com/k8se/quickstart:latest'
          : '${backendContainerRegistryHostname}/${frontendContainerImageName}:${frontendContainerImageTag}'
        resources: {
          // Static SPA server -- smaller footprint than the backend.
          // AVM v0.22.1 declares `cpu: int | null`, but ACA accepts
          // fractional CPU, so `any()` bypasses the over-strict type.
          cpu: any(enableScalability ? '0.5' : '0.25')
          memory: enableScalability ? '1.0Gi' : '0.5Gi'
        }
        env: [
          // The only runtime env the SPA needs: the backend origin the
          // frontend_app.py /config endpoint returns, which the SPA
          // fetches once at boot. Bound to the backend Container App FQDN.
          {
            name: 'BACKEND_API_URL'
            value: 'https://${backendContainerApp.outputs.fqdn}'
          }
        ]
      }
    ]
  }
}

// ----------------------------------------------------------------------
// Function container app (Azure Functions on Azure Container Apps) +
// Event Grid system topic.
// The function hosts the modular RAG indexing pipeline:
//   - batch_start  -- list blobs in /documents/, enqueue per-blob messages
//   - batch_push   -- Storage Queue trigger; parse, chunk, embed, push to
//                    the configured vector index (AI Search OR Postgres)
//   - add_url      -- HTTP trigger; fetch URL content, parse, embed
// Event Grid system topic on the Storage Account fans out BlobCreated
// and BlobDeleted notifications under /documents/ to the blob-events
// queue; the blob_event trigger turns a create into a doc-processing
// ingestion job (batch_push) and a delete into a de-index.
//
// Azure Functions on Container Apps (a Microsoft.App/containerApps
// resource, kind=functionapp) chosen so the function ships as a container
// image on the shared registry + environment like the backend and
// frontend:
//   - custom container image built + pushed to the shared ACR by azd
//   - KEDA event-driven scale for the HTTP + Storage Queue triggers
//   - AAD-only AzureWebJobsStorage (no shared keys) via the shared UAMI
//
// Identity / no-keys posture: Storage has allowSharedKeyAccess=false,
// so Event Grid → Storage Queue MUST use deliveryWithResourceIdentity
// with the system topic's system-assigned MI, plus a Storage Queue Data
// Message Sender role on that MI. AzureWebJobsStorage uses the function
// app's UAMI via the `AzureWebJobsStorage__credential=managedidentity`
// + `__clientId` pattern.
// ----------------------------------------------------------------------
var eventGridSystemTopicName = 'evgt-${solutionSuffix}'
var docProcessingQueueName = 'doc-processing'
// Event Grid delivers BlobCreated / BlobDeleted events here; the
// blob_event queue trigger translates a create into a doc-processing
// ingestion envelope and a delete into a de-index.
var blobEventsQueueName = 'blob-events'
var documentsContainerName = 'documents'
// Built-in role definition GUID used by this section.
//   Storage Queue Data Message Sender -- for Event Grid → Storage Queue
var storageQueueDataMessageSenderRoleId = 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a'

// ----------------------------------------------------------------------
// Function container app (Azure Functions on Azure Container Apps).
// A raw Microsoft.App/containerApps resource with kind=functionapp on the
// shared Container Apps Environment (cae-<suffix>), tagged
// azd-service-name: function, pulling its image from the shared ACR with
// the shared UAMI's AcrPull grant. Authored as a raw resource (not the
// avm/res/app/container-app module the backend + frontend use) because the
// module version pinned for those services does not expose kind=functionapp;
// a raw resource keeps the function isolated so the backend + frontend stay
// on their validated module version.
//
// Three host-specific settings differ from the backend container app:
//   - FUNCTIONS_WORKER_RUNTIME=python is REQUIRED on Container Apps (Flex
//     Consumption forbade it); the runtime version comes from the base image.
//   - targetPort 80 -- the Functions Python base image listens on 80.
//   - minReplicas 1 keeps the batch_push + blob_event queue consumers warm;
//     maxReplicas maps from the former Flex maximumInstanceCount (40 / 100).
//
// A placeholder image boots the resource on a clean first provision (before
// any image is pushed); azd deploy then builds + pushes the real image and
// the deploy-time azd-service-name: function tag swap patches the live
// revision.
// ----------------------------------------------------------------------
resource functionContainerApp 'Microsoft.App/containerApps@2024-10-02-preview' = {
  name: functionContainerAppName
  location: location
  kind: 'functionapp'
  tags: union(allTags, { 'azd-service-name': 'function' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      // The identity dictionary key on a raw containerApps resource must be a
      // compile-time-resolvable resource id, so it is built from the UAMI name
      // (identityName) rather than the module's runtime resourceId output.
      '${resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', identityName)}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnv.outputs.resourceId
    workloadProfileName: acaWorkloadProfileName
    configuration: {
      activeRevisionsMode: 'Single'
      // HTTP triggers (batch_start / add_url / search_skill) must be
      // reachable -- the AI Search indexer calls search_skill -- and ingress
      // is also required for KEDA scaling. Internal in the private profile,
      // resolved via the wildcard caeDnsZone A-record like the backend.
      ingress: {
        external: !enablePrivateNetworking
        targetPort: 80
        allowInsecure: false
        transport: 'auto'
      }
      // Pull the image with the shared UAMI that holds AcrPull on the
      // registry (granted by the containerRegistry roleAssignments above).
      // Harmless while the public placeholder image is in use and active
      // once the real function image is pushed to ACR.
      registries: [
        {
          server: containerRegistry.outputs.loginServer
          identity: userAssignedIdentity.outputs.resourceId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'function'
          // When `backendContainerRegistryHostname` is empty (clean first
          // provision) the container boots from a pullable public
          // placeholder so provisioning succeeds before any image is
          // pushed. Once the real function image is built + pushed, azd's
          // deploy-time `azd-service-name: function` tag swap patches the
          // live revision, and subsequent provisions compose the real ACR
          // image reference from the functionContainerImage* params.
          image: empty(backendContainerRegistryHostname)
            ? 'mcr.microsoft.com/k8se/quickstart:latest'
            : '${backendContainerRegistryHostname}/${functionContainerImageName}:${functionContainerImageTag}'
          // json() yields the numeric cpu the raw ACA schema expects while
          // still allowing fractional cores (0.5). cpu:memory ratios follow
          // the Consumption profile (0.5→1.0Gi, 1.0→2.0Gi).
          resources: {
            cpu: json(enableScalability ? '1.0' : '0.5')
            memory: enableScalability ? '2.0Gi' : '1.0Gi'
          }
          env: union(
            [
              // AAD-only AzureWebJobsStorage -- no connection string, UAMI auth.
              { name: 'AzureWebJobsStorage__accountName', value: effectiveStorageName }
              { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
              { name: 'AzureWebJobsStorage__clientId', value: userAssignedIdentity.outputs.clientId }
              // Functions runtime knobs. FUNCTIONS_WORKER_RUNTIME is REQUIRED
              // on Container Apps (Flex Consumption forbade it as an app
              // setting); the runtime version comes from the container base
              // image, so no functionAppConfig.runtime block is needed.
              { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
              { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
              // Identity + Foundry endpoints (mirrors backend env so the
              // indexing pipeline can call the embedding model + write to
              // the configured vector index).
              { name: 'AZURE_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
              { name: 'AZURE_UAMI_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
              { name: 'AZURE_TENANT_ID', value: subscription().tenantId }
              // Runtime mode (AppSettings.environment) -- pin 'production' so the
              // deployed config reports production, parity with the backend.
              { name: 'AZURE_ENVIRONMENT', value: 'production' }
              { name: 'AZURE_AI_PROJECT_ENDPOINT', value: aiProject.outputs.projectEndpoint }
              { name: 'AZURE_OPENAI_ENDPOINT', value: effectiveOpenAiEndpoint }
              // AI Services / Foundry account endpoint -- the data-plane base
              // for DocumentIntelligence + Content Understanding calls.
              { name: 'AZURE_AI_SERVICES_ENDPOINT', value: aiServices.outputs.endpoint }
              { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
              { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
              // Database routing -- same flags the backend reads. The
              // indexing pipeline writes vectors into AzureSearch (cosmosdb
              // mode) or pgvector (postgresql mode), so it needs the
              // active-mode endpoint(s). AZURE_COSMOS_ENDPOINT is also
              // bound because DatabaseSettings cross-validates
              // AZURE_DB_TYPE=cosmosdb against a non-empty endpoint at
              // AppSettings() construction time; the function worker
              // fails to start (Pydantic ValidationError during settings
              // load) otherwise, even though the function host performs
              // no chat-history writes.
              { name: 'AZURE_DB_TYPE', value: databaseType }
              { name: 'AZURE_INDEX_STORE', value: indexStoreValue }
              { name: 'AZURE_COSMOS_ENDPOINT', value: effectiveCosmosEndpoint }
              { name: 'AZURE_AI_SEARCH_ENDPOINT', value: effectiveSearchEndpoint }
              { name: 'AZURE_POSTGRES_ENDPOINT', value: postgresLibpqUri }
              { name: 'AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME', value: databaseType == 'postgresql' ? 'id-${solutionSuffix}' : '' }
              // Storage wiring used by batch_start / batch_push / add_url.
              { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: effectiveStorageName }
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
      ]
      scale: {
        // minReplicas 1 keeps the batch_push + blob_event queue consumers
        // warm (mirrors the former Flex alwaysReady). maxReplicas maps from
        // the former Flex maximumInstanceCount.
        minReplicas: 1
        maxReplicas: enableScalability ? 100 : 40
      }
    }
  }
}

// Existing-reference to the effective storage account (new or reused v1),
// used as the scope for the Event Grid queue-sender role assignments below.
// `existing` uses the *variable* (compile-time known), not the module
// output (runtime-only) -- required for roleAssignment scope/name to
// satisfy BCP120.
resource storageAccountExisting 'Microsoft.Storage/storageAccounts@2024-01-01' existing = {
  // BCP334: take(...) returns string 0..24 chars; storage account name
  // requires min 3. solutionSuffix is generated by reference-architecture pattern as 8+
  // chars in main.bicep, so the actual value is always 10..24. Suppress
  // the static-analysis warning rather than add a runtime guard.
  #disable-next-line BCP334
  name: useExistingStorage ? existingStorageName : storageAccountName
  dependsOn: [ storageAccount ]
}

// Event Grid system topic on the Storage Account. Single subscription:
// BlobCreated / BlobDeleted under /documents/ → blob-events queue, which
// the blob_event queue trigger translates into the right action (create
// → doc-processing ingestion envelope consumed by batch_push; delete →
// de-index) (ADR 0028). A queue destination --
// not an Event Grid AzureFunction trigger -- keeps managed-identity
// delivery and deploys at provision time (the queue exists; a function
// would not yet). The add_url path is HTTP-triggered, not
// blob-triggered, so it needs no subscription. When reusing v1's
// storage that already has a system topic, the AVM module is skipped
// and a sibling `existingEventGridSubscription` resource adds our
// subscription to the v1 topic (Azure permits only one system topic
// per source).
module eventGridSystemTopic 'br/public:avm/res/event-grid/system-topic:0.6.4' = if (!useExistingEventGridTopic) {
  name: take('avm.res.event-grid.system-topic.${solutionSuffix}', 64)
  params: {
    name: eventGridSystemTopicName
    location: location
    tags: allTags
    enableTelemetry: false
    source: effectiveStorageResourceId
    topicType: 'Microsoft.Storage.StorageAccounts'
    managedIdentities: {
      // Deliver events as the shared UAMI (id-<suffix>) rather than the
      // topic's system-assigned MI. The UAMI exists from t=0, so its
      // Storage Queue Data Message Sender grant (eventGridQueueSenderRole)
      // is authored with NO dependency on this topic and replicates during
      // the whole provisioning tail -- closing the delivery-preflight
      // replication race a system-assigned MI cannot. Mirrors
      // the existing-topic reuse path, which already delivers as the UAMI.
      userAssignedResourceIds: [ userAssignedIdentity.outputs.resourceId ]
    }
    // The blob subscription is NOT nested here. It is created as a
    // standalone sibling (blobCreatedSubscription, below) that dependsOn
    // eventGridQueueSenderRole, so the UAMI holds Storage Queue Data Message
    // Sender BEFORE Event Grid runs its delivery-authorization preflight.
    // A nested subscription preflights inside this module, before the
    // role exists, and fails on a fresh provision.
  }
}

// Grant the shared UAMI (id-<suffix>) permission to enqueue messages on
// the storage account's queues, so Event Grid can deliver blob events to
// the blob-events queue as that identity. Authored with NO dependency on
// the Event Grid topic -- the UAMI exists from the start of the
// deployment, so ARM creates this grant early and it replicates during the
// multi-minute provisioning tail, BEFORE Event Grid runs its synchronous
// delivery-authorization preflight at subscription-create time.
// Account-scope is required: the EG MI validator walks the storage account
// hierarchy and does not recognize queue-scope alone. Skipped when reusing
// v1's topic (existingQueueMessageSenderRole below grants the same role to
// the same UAMI under the same deterministic name).
resource eventGridQueueSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingEventGridTopic) {
  name: guid(storageAccountExisting.id, userAssignedIdentity.name, storageQueueDataMessageSenderRoleId)
  scope: storageAccountExisting
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageQueueDataMessageSenderRoleId)
    principalId: userAssignedIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Standalone subscription on the new system topic. Lifted out of the AVM
// module's eventSubscriptions array so it can dependsOn
// eventGridQueueSenderRole and only run its delivery-authorization
// preflight AFTER the shared UAMI is granted Storage Queue Data Message
// Sender. The `parent` is an `existing` reference to the
// AVM-created topic -- the same mechanism the reuse path uses
// (existingEventGridTopic → existingEventGridSubscription), because an AVM
// module is not a resource symbol usable as `parent`.
resource newEventGridTopic 'Microsoft.EventGrid/systemTopics@2024-12-15-preview' existing = if (!useExistingEventGridTopic) {
  name: eventGridSystemTopicName
}

resource blobCreatedSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2024-12-15-preview' = if (!useExistingEventGridTopic) {
  parent: newEventGridTopic
  // Name retained (not 'blob-created-to-blob-events') so the destination
  // repoint is an in-place update; renaming under azd incremental mode
  // would orphan the prior subscription, leaving it delivering to
  // doc-processing.
  name: 'blob-created-to-doc-processing'
  properties: {
    // deliveryWithResourceIdentity (NOT plain destination) is required
    // because storage has allowSharedKeyAccess=false. The shared UAMI
    // (id-<suffix>, assigned to the topic above) authenticates to Storage
    // Queue -- mirrors the existing-topic reuse path.
    deliveryWithResourceIdentity: {
      identity: {
        type: 'UserAssigned'
        userAssignedIdentity: userAssignedIdentity.outputs.resourceId
      }
      destination: {
        endpointType: 'StorageQueue'
        properties: {
          resourceId: effectiveStorageResourceId
          queueName: blobEventsQueueName
        }
      }
    }
    filter: {
      includedEventTypes: [ 'Microsoft.Storage.BlobCreated', 'Microsoft.Storage.BlobDeleted' ]
      subjectBeginsWith: '/blobServices/default/containers/${documentsContainerName}/'
      enableAdvancedFilteringOnArrays: true
    }
    eventDeliverySchema: 'EventGridSchema'
    retryPolicy: {
      maxDeliveryAttempts: 30
      eventTimeToLiveInMinutes: 1440
    }
  }
  // Role-before-subscription: the queue-sender grant must land before the
  // Event Grid delivery-authorization preflight runs. Depend on
  // the topic module too so the topic (with the UAMI assigned) exists -- the
  // `parent` existing-ref alone does not enforce module completion.
  dependsOn: [
    eventGridSystemTopic
    eventGridQueueSenderRole
  ]
}

// EXISTING Event Grid system topic reuse. Adds a new subscription on
// v1's topic that routes BlobCreated / BlobDeleted events from the
// documents/ prefix to our blob-events queue (the blob_event trigger
// translates a create to doc-processing and a delete to a de-index).
// Delivery uses v2's UAMI (granted both Queue Data Contributor AND
// Queue Data Message Sender on the storage account -- EG's synchronous
// preflight validates delivery authorization at account scope, not
// queue scope; see existingQueueMessageSenderRole below).
//
// MANAGED resource (an idempotent in-place PUT on v1's topic), NOT an
// `existing` read-only reference. deliveryWithResourceIdentity on the
// subscription below can only deliver as the UAMI if the UAMI is
// assigned to the TOPIC -- and an `existing` reference cannot carry an
// identity block, so a reuse deployment would fail EG's delivery
// preflight. Azure permits only one system topic per storage source, so
// we cannot create a second topic; instead we re-declare v1's topic with
// its immutable source/topicType unchanged (source == effectiveStorageResourceId,
// the reused storage) plus the UAMI identity. ARM updates the topic in
// place, adding the identity -- mirroring the new-topic path's
// managedIdentities assignment. The `parent` relationship on the
// subscription orders this identity update before the delivery-authorization
// preflight runs.
resource existingEventGridTopic 'Microsoft.EventGrid/systemTopics@2024-12-15-preview' = if (useExistingEventGridTopic) {
  name: existingEventGridTopicName
  location: location
  tags: allTags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      // The identity dictionary key on a raw systemTopics resource must be a
      // compile-time-resolvable resource id, so it is built from the UAMI name
      // (identityName) rather than the module's runtime resourceId output.
      '${resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', identityName)}': {}
    }
  }
  properties: {
    source: effectiveStorageResourceId
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

// Message Sender grant scoped to the storage account. EG's MI preflight
// validator walks the storage account hierarchy when checking delivery
// authorization for StorageQueue destinations; queue-scope alone is not
// recognized by the synchronous validator. Account-scope is required.
resource existingQueueMessageSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingEventGridTopic) {
  name: guid(storageAccountExisting.id, userAssignedIdentity.name, 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a')
  scope: storageAccountExisting
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a')
    principalId: userAssignedIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

resource existingEventGridSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2024-12-15-preview' = if (useExistingEventGridTopic) {
  parent: existingEventGridTopic
  // Name retained (see the new-topic subscription above): an in-place
  // destination repoint, not a rename that would orphan the prior sub.
  name: 'cwyd2-blob-created-doc-processing'
  properties: {
    deliveryWithResourceIdentity: {
      identity: {
        type: 'UserAssigned'
        userAssignedIdentity: userAssignedIdentity.outputs.resourceId
      }
      destination: {
        endpointType: 'StorageQueue'
        properties: {
          resourceId: effectiveStorageResourceId
          queueName: blobEventsQueueName
        }
      }
    }
    filter: {
      includedEventTypes: [ 'Microsoft.Storage.BlobCreated', 'Microsoft.Storage.BlobDeleted' ]
      subjectBeginsWith: '/blobServices/default/containers/${documentsContainerName}/'
      enableAdvancedFilteringOnArrays: true
    }
    eventDeliverySchema: 'EventGridSchema'
    retryPolicy: {
      maxDeliveryAttempts: 30
      eventTimeToLiveInMinutes: 1440
    }
  }
  dependsOn: [
    existingStorageQueueBlobEvents
    existingStorageQueueContributor
    existingQueueMessageSenderRole
  ]
}

// ===================== //
// Outputs               //
// ===================== //
// Every AZURE_* output is consumed by either:
//   - azd post-provision hooks (scripts/post-provision.{sh,ps1})
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
output AZURE_INDEX_STORE string = indexStoreValue

// --- Foundry substrate ---

@description('Unified AI Services endpoint. Used by both orchestrators (LangGraph via OpenAI-compatible path; Agent Framework via the project endpoint below).')
output AZURE_AI_SERVICES_ENDPOINT string = aiServices.outputs.endpoint

@description('Effective Azure OpenAI endpoint backends call for chat + embedding deployments. When `existingOpenAiName` is set this points at the reused v1 OpenAI account; otherwise it equals AZURE_AI_SERVICES_ENDPOINT (deployments live on the v2 Foundry account).')
output AZURE_OPENAI_ENDPOINT string = effectiveOpenAiEndpoint

@description('Foundry Project endpoint (https://<account>.services.ai.azure.com/api/projects/<project>). Required by the Microsoft Agent Framework SDK.')
output AZURE_AI_PROJECT_ENDPOINT string = aiProject.outputs.projectEndpoint

@description('Foundry Project ARM resource id. Consumed by post_provision.py to seed the KB-MCP RemoteTool connection at the control plane.')
output AZURE_AI_PROJECT_RESOURCE_ID string = aiProject.outputs.resourceId

@description('OpenAI-compatible API version pinned for the GPT chat deployment.')
output AZURE_OPENAI_API_VERSION string = azureOpenAiApiVersion

@description('Azure AI Agents API version pinned for the Foundry Project endpoint.')
output AZURE_AI_AGENT_API_VERSION string = azureAiAgentApiVersion

@description('Deployment name of the chat-completions GPT model.')
output AZURE_OPENAI_GPT_DEPLOYMENT string = gptModelName

@description('Deployment name of the embedding model used by the indexing pipeline.')
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = embeddingModelName

// --- Speech ---

@description('Speech account name (kind=SpeechServices). Backend reads via SpeechSettings.service_name; not used directly by the SDK.')
output AZURE_SPEECH_SERVICE_NAME string = speechService.outputs.name

@description('Speech account region. Browser SDK passes this to SpeechConfig.fromAuthorizationToken(token, region) and the backend uses it to build the regional sts/v1.0/issueToken URL.')
output AZURE_SPEECH_SERVICE_REGION string = azureAiServiceLocation

@description('Speech account ARM resource id. Required as the x-ms-cognitiveservices-resource-id header on the AAD-bearer STS issueToken POST.')
output AZURE_SPEECH_ACCOUNT_RESOURCE_ID string = speechService.outputs.resourceId

// --- Content Safety ---

@description('Content Safety account endpoint. Backend reads via ContentSafetySettings.endpoint; lifespan gates client construction on this + AZURE_CONTENT_SAFETY_ENABLED.')
output AZURE_CONTENT_SAFETY_ENDPOINT string = cogContentSafety.outputs.endpoint

@description('Content Safety account name (kind=ContentSafety). Diagnostic surface only — backend builds the client from the endpoint.')
output AZURE_CONTENT_SAFETY_NAME string = cogContentSafety.outputs.name

// --- Conditional: Azure AI Search (cosmosdb mode only) ---

@description('AI Search service endpoint. Empty in postgresql mode.')
output AZURE_AI_SEARCH_ENDPOINT string = databaseType == 'cosmosdb' ? effectiveSearchEndpoint : ''

@description('AI Search service name. Empty in postgresql mode.')
output AZURE_AI_SEARCH_NAME string = databaseType == 'cosmosdb' ? effectiveSearchName : ''

@description('Chat index name. Exported so the postdeploy seed hook can run its index-population self-check; empty in postgresql mode (no AI Search).')
output AZURE_AI_SEARCH_INDEX string = databaseType == 'cosmosdb' ? searchIndexName : ''

@description('Foundry IQ knowledge base name. Backend grounds the agent_framework orchestrator on it; post_provision.py seeds it. Carries the configured name in both modes (post_provision skips seeding when the Search endpoint is empty).')
output AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME string = searchKnowledgeBaseName

@description('Foundry IQ knowledge source name backing the knowledge base. Seeded by post_provision.py before the knowledge base (the base references it).')
output AZURE_AI_SEARCH_KNOWLEDGE_SOURCE_NAME string = searchKnowledgeSourceName

@description('Foundry IQ knowledge base / knowledge source REST API version (operator-tunable). Used by post_provision.py to seed and by the backend to build the MCP retrieval URL.')
output AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION string = searchKnowledgeBaseApiVersion

// --- Conditional: Cosmos DB (cosmosdb mode only) ---

@description('Cosmos DB account endpoint (DocumentEndpoint). Empty in postgresql mode.')
output AZURE_COSMOS_ENDPOINT string = databaseType == 'cosmosdb' ? effectiveCosmosEndpoint : ''

@description('Cosmos DB account name. Empty in postgresql mode.')
output AZURE_COSMOS_ACCOUNT_NAME string = databaseType == 'cosmosdb' ? effectiveCosmosName : ''

// --- Conditional: PostgreSQL Flexible Server (postgresql mode only) ---

@description('PostgreSQL Flexible Server FQDN (clients add :5432 themselves). Empty in cosmosdb mode.')
output AZURE_POSTGRES_HOST string = databaseType == 'postgresql' ? postgresServer!.outputs.fqdn! : ''

@description('Full libpq connection URI for the PostgreSQL Flexible Server (no credentials — the workload supplies an Entra token; the user comes from AZURE_UAMI_CLIENT_ID). Mirrors AZURE_COSMOS_ENDPOINT shape so AzurePostgresSettings reads one var. Empty in cosmosdb mode.')
output AZURE_POSTGRES_ENDPOINT string = postgresLibpqUri

@description('PostgreSQL Flexible Server resource name. Empty in cosmosdb mode.')
output AZURE_POSTGRES_NAME string = databaseType == 'postgresql' ? postgresServer!.outputs.name : ''

@description('Configured Entra admin principal name for the Postgres Flex server (used as the `user` in AAD-token connections by the post-provision hook). Empty in cosmosdb mode.')
output AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME string = databaseType == 'postgresql' ? postgresAdminPrincipalName : ''

// --- Storage (blobs + queues + Function deployment package) ---

@description('Storage account name (shared by RAG document store and the indexing queues).')
output AZURE_STORAGE_ACCOUNT_NAME string = effectiveStorageName

@description('Primary blob endpoint of the shared storage account (https URL ending in /). Hostname follows the storage cloud-specific suffix.')
output AZURE_STORAGE_BLOB_ENDPOINT string = effectiveStorageBlobEndpoint

@description('Container holding documents to be indexed (Event Grid filter + batch_start source).')
output AZURE_DOCUMENTS_CONTAINER string = documentsContainerName

@description('Storage Queue name fed by Event Grid BlobCreated and consumed by the batch_push Function blueprint.')
output AZURE_DOC_PROCESSING_QUEUE string = docProcessingQueueName

@description('Ingestion trigger mode for the backend admin upload path: direct_enqueue (backend enqueues) or event_grid (Event Grid + blob_event Function own the push).')
output AZURE_INGESTION_TRIGGER string = ingestionTrigger

// --- Hosting endpoints (consumed by azd hooks, Vite build, smoke tests) ---

@description('Public URL of the backend Container App (FastAPI + LangGraph/Agent Framework).')
output AZURE_BACKEND_URL string = 'https://${backendContainerApp.outputs.fqdn}'

@description('Public URL of the frontend Container App (React/Vite SPA). Backend CORS must allow this origin.')
output AZURE_FRONTEND_URL string = 'https://${frontendContainerApp.outputs.fqdn}'

@description('Public URL of the Function App hosting the indexing pipeline.')
output AZURE_FUNCTION_APP_URL string = 'https://${functionContainerApp.properties.configuration.ingress.fqdn}'

@description('Function App resource name (used by azd to deploy the function image).')
output AZURE_FUNCTION_APP_NAME string = functionContainerApp.name

@description('Container Registry login server (e.g. cr<SUFFIX>.azurecr.io). `azd deploy` reads this to discover the push target for backend + function images.')
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer

@description('Container Registry resource name. Diagnostic surface only — azd uses the login server above.')
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.name

// --- Conditional: monitoring ---

@description('Application Insights connection string. Empty when enableMonitoring=false.')
output AZURE_APP_INSIGHTS_CONNECTION_STRING string = enableMonitoring ? applicationInsights!.outputs.connectionString : ''

// --- Conditional: private networking (enablePrivateNetworking only) ---

@description('VNet name. Empty when enablePrivateNetworking=false.')
output AZURE_VNET_NAME string = enablePrivateNetworking ? virtualNetwork!.outputs.name : ''

@description('VNet resource ID. Empty when enablePrivateNetworking=false.')
output AZURE_VNET_RESOURCE_ID string = enablePrivateNetworking ? virtualNetwork!.outputs.resourceId : ''

@description('Bastion host name (for `az network bastion tunnel`). Empty when enablePrivateNetworking=false.')
output AZURE_BASTION_NAME string = enablePrivateNetworking ? bastion!.outputs.name : ''
