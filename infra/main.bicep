// ============================================================================
// main.bicep — Deployment Router
// Description: Routes deployment to the appropriate infrastructure flavor.
//   - 'bicep'   → Vanilla Bicep modules (Docker deployment)
//   - 'avm'     → AVM-based modules (non-WAF)
//   - 'avm-waf' → AVM-based modules with WAF-aligned features
//              (monitoring, private networking, scalability, redundancy)
// ============================================================================
targetScope = 'resourceGroup'

metadata name = 'Chat With Your Data v2'
metadata description = 'Foundry-first RAG accelerator. Single databaseType parameter selects chat history + vector index. Two orchestrators (Agent Framework, LangGraph) on a shared Foundry Project.'

// ============================================================================
// Routing Parameter
// ============================================================================

@allowed(['bicep', 'avm', 'avm-waf'])
@description('Required. Deployment flavor: bicep (vanilla Docker), avm (AVM non-WAF), or avm-waf (AVM WAF-aligned).')
param deploymentFlavor string

// ============================================================================
// Parameters — Core (shared across all flavors)
// ============================================================================

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
      'OpenAI.GlobalStandard.gpt-5.4-mini,50'
      'OpenAI.GlobalStandard.gpt-5-mini,50'
      'OpenAI.Standard.text-embedding-3-small,100'
    ]
  }
})
@description('Required. Region for AI Services / Foundry deployments. Restricted to regions with GPT-5.1 GlobalStandard availability.')
param azureAiServiceLocation string

// ============================================================================
// Parameters — Database & Ingestion
// ============================================================================

@allowed([
  'cosmosdb'
  'postgresql'
])
@description('Required. Selects BOTH the chat-history backend AND the vector index store. CosmosDB: Cosmos DB + Azure AI Search. PostgreSQL: PostgreSQL Flexible Server with pgvector (Azure AI Search is NOT deployed). Locked at deploy time.')
param databaseType string = 'cosmosdb'

@allowed([
  'direct_enqueue'
  'event_grid'
])
@description('Optional. How an uploaded document is picked up for indexing. direct_enqueue: the backend admin upload enqueues the doc-processing message itself (works without an Event Grid subscription). event_grid: a storage Event Grid subscription fans BlobCreated/BlobDeleted to the blob-events queue and the blob_event Function translates each (create -> ingest, delete -> de-index), so the backend writes the blob only (no double-ingest). Flip to event_grid only after the blob_event Function blueprint is deployed.')
param ingestionTrigger string = 'direct_enqueue'

// ============================================================================
// Parameters — AI Configuration
// ============================================================================

@minLength(1)
@description('Optional. Primary chat model deployment name.')
param gptModelName string = 'gpt-5.4-mini'

@description('Optional. Primary chat model version.')
param gptModelVersion string = '2026-03-17'

@allowed([
  'Standard'
  'GlobalStandard'
])
@description('Optional. SKU for the primary chat model deployment.')
param gptModelDeploymentType string = 'GlobalStandard'

@minValue(1)
@description('Optional. Token capacity (thousands of TPM) for the primary chat model.')
param gptModelCapacity int = 50

@minLength(1)
@description('Optional. Reasoning model deployment name (surfaced via the SSE reasoning channel).')
param reasoningModelName string = 'gpt-5-mini'

@description('Optional. Reasoning model version.')
param reasoningModelVersion string = '2025-08-07'

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
param embeddingModelName string = 'text-embedding-3-small'

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

// ============================================================================
// Parameters — Existing Resources
// ============================================================================

@description('Optional. Resource ID of an existing Log Analytics workspace. Empty creates a new one.')
param existingLogAnalyticsWorkspaceId string = ''

@description('Optional. Resource ID of an existing AI Foundry project. Empty creates a new one.')
param existingFoundryProjectResourceId string = ''

// ============================================================================
// Parameters — WAF Flags
// ============================================================================

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Optional. Deploy Log Analytics + Application Insights and wire diagnostic settings on every applicable resource.')
param enableMonitoring bool = false

@description('Optional. Higher SKUs and autoscaling on App Service Plan, Container Apps, Search, and PostgreSQL.')
param enableScalability bool = false

@description('Optional. Zone-redundant + paired-region failover on databases, App Service Plan, Container Apps, and Storage.')
param enableRedundancy bool = false

@description('Optional. Deploy a VNet, private endpoints, and disable public network access on data-plane resources. Wires the regional VNet (`modules/virtualNetwork.bicep`), private DNS zones, private endpoints for every data-plane resource, regional VNet integration for compute, and Bastion. Setting this to true is the WAF-aligned topology and requires no follow-up tasks; flipping it back to false re-enables public endpoints with default firewall rules.')
param enablePrivateNetworking bool = false

// ============================================================================
// Parameters — AVM-specific (ignored when deploymentFlavor = 'bicep')
// ============================================================================

@secure()
@description('Optional. VM admin username (AVM-WAF only, when private networking is enabled).')
param vmAdminUsername string?

@secure()
@description('Optional. VM admin password (AVM-WAF only, when private networking is enabled).')
param vmAdminPassword string?

@description('Optional. VM size for jumpbox (AVM-WAF only). Defaults to Standard_D2s_v5.')
param vmSize string = 'Standard_D2s_v5'

// ============================================================================
// Parameters — Identity & Tagging
// ============================================================================

@description('Optional. Tags applied to every deployed resource.')
param tags object = {}

@description('Optional. Identifier of the user creating the deployment, recorded in the resource group tags.')
param createdBy string = contains(deployer(), 'userPrincipalName')
  ? split(deployer().userPrincipalName, '@')[0]
  : deployer().objectId

@allowed(['User', 'ServicePrincipal'])
@description('Optional. Principal type of the deploying user. Use ServicePrincipal for CI/CD pipelines with OIDC.')
param deployingUserPrincipalType string = 'User'

// ============================================================================
// Derived Variables
// ============================================================================

var isAvm = deploymentFlavor == 'avm' || deploymentFlavor == 'avm-waf'
var isBicep = deploymentFlavor == 'bicep'

// ============================================================================
// Module: AVM Deployment (non-WAF and WAF)
// Activated when deploymentFlavor = 'avm' or 'avm-waf'
// WAF features (monitoring, private networking, scalability, redundancy)
// are enabled automatically for 'avm-waf'.
// ============================================================================

module avmDeployment './avm/main.bicep' = if (isAvm) {
  name: take('module.avm.${solutionName}', 64)
  params: {
    solutionName: solutionName
    solutionUniqueText: solutionUniqueText
    location: location
    azureAiServiceLocation: azureAiServiceLocation
    databaseType: databaseType
    ingestionTrigger: ingestionTrigger
    gptModelName: gptModelName
    gptModelVersion: gptModelVersion
    gptModelDeploymentType: gptModelDeploymentType
    gptModelCapacity: gptModelCapacity
    reasoningModelName: reasoningModelName
    reasoningModelVersion: reasoningModelVersion
    reasoningModelDeploymentType: reasoningModelDeploymentType
    reasoningModelCapacity: reasoningModelCapacity
    embeddingModelName: embeddingModelName
    embeddingModelVersion: embeddingModelVersion
    embeddingModelDeploymentType: embeddingModelDeploymentType
    embeddingModelCapacity: embeddingModelCapacity
    azureOpenAiApiVersion: azureOpenAiApiVersion
    azureAiAgentApiVersion: azureAiAgentApiVersion
    searchKnowledgeBaseName: searchKnowledgeBaseName
    searchKnowledgeSourceName: searchKnowledgeSourceName
    searchIndexName: searchIndexName
    searchKnowledgeBaseApiVersion: searchKnowledgeBaseApiVersion
    enableTelemetry: enableTelemetry
    enableMonitoring: enableMonitoring
    enableScalability: enableScalability
    enableRedundancy: enableRedundancy
    enablePrivateNetworking: enablePrivateNetworking
    vmAdminUsername: vmAdminUsername
    vmAdminPassword: vmAdminPassword
    vmSize: vmSize
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    tags: tags
    createdBy: createdBy
    deployingUserPrincipalType: deployingUserPrincipalType
  }
}

// ============================================================================
// Module: Vanilla Bicep Deployment (Docker)
// Activated when deploymentFlavor = 'bicep'
// ============================================================================

module bicepDeployment './bicep/main.bicep' = if (isBicep) {
  name: take('module.bicep.${solutionName}', 64)
  params: {
    solutionName: solutionName
    solutionUniqueText: solutionUniqueText
    location: location
    azureAiServiceLocation: azureAiServiceLocation
    databaseType: databaseType
    ingestionTrigger: ingestionTrigger
    gptModelName: gptModelName
    gptModelVersion: gptModelVersion
    gptModelDeploymentType: gptModelDeploymentType
    gptModelCapacity: gptModelCapacity
    reasoningModelName: reasoningModelName
    reasoningModelVersion: reasoningModelVersion
    reasoningModelDeploymentType: reasoningModelDeploymentType
    reasoningModelCapacity: reasoningModelCapacity
    embeddingModelName: embeddingModelName
    embeddingModelVersion: embeddingModelVersion
    embeddingModelDeploymentType: embeddingModelDeploymentType
    embeddingModelCapacity: embeddingModelCapacity
    azureOpenAiApiVersion: azureOpenAiApiVersion
    azureAiAgentApiVersion: azureAiAgentApiVersion
    searchKnowledgeBaseName: searchKnowledgeBaseName
    searchKnowledgeSourceName: searchKnowledgeSourceName
    searchIndexName: searchIndexName
    searchKnowledgeBaseApiVersion: searchKnowledgeBaseApiVersion
    enableMonitoring: enableMonitoring
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    tags: tags
    createdBy: createdBy
    deployingUserPrincipalType: deployingUserPrincipalType
  }
}

// ============================================================================
// Outputs — Forwarded from whichever flavor was deployed
// ============================================================================

@description('Lower-cased solution suffix used in every downstream resource name.')
output AZURE_SOLUTION_SUFFIX string = isAvm ? avmDeployment!.outputs.AZURE_SOLUTION_SUFFIX : bicepDeployment!.outputs.AZURE_SOLUTION_SUFFIX

@description('Resource group containing the deployment.')
output AZURE_RESOURCE_GROUP string = resourceGroup().name

@description('Location of the non-AI resources.')
output AZURE_LOCATION string = location

@description('Location of the AI Services account + model deployments.')
output AZURE_AI_SERVICE_LOCATION string = azureAiServiceLocation

@description('Tenant ID for the deployment subscription.')
output AZURE_TENANT_ID string = subscription().tenantId

@description('Client ID of the user-assigned managed identity shared by all v2 workloads.')
output AZURE_UAMI_CLIENT_ID string = isAvm ? avmDeployment!.outputs.AZURE_UAMI_CLIENT_ID : bicepDeployment!.outputs.AZURE_UAMI_CLIENT_ID

@description('Principal (object) ID of the user-assigned managed identity.')
output AZURE_UAMI_PRINCIPAL_ID string = isAvm ? avmDeployment!.outputs.AZURE_UAMI_PRINCIPAL_ID : bicepDeployment!.outputs.AZURE_UAMI_PRINCIPAL_ID

@description('Resource ID of the user-assigned managed identity.')
output AZURE_UAMI_RESOURCE_ID string = isAvm ? avmDeployment!.outputs.AZURE_UAMI_RESOURCE_ID : bicepDeployment!.outputs.AZURE_UAMI_RESOURCE_ID

// --- Database routing flag ---

@description('Selected database engine for chat history + vector index (locked at deploy).')
output AZURE_DB_TYPE string = databaseType

@description('Logical name of the configured vector index store.')
output AZURE_INDEX_STORE string = isAvm ? avmDeployment!.outputs.AZURE_INDEX_STORE : bicepDeployment!.outputs.AZURE_INDEX_STORE

// --- Foundry substrate ---

@description('Unified AI Services endpoint.')
output AZURE_AI_SERVICES_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_AI_SERVICES_ENDPOINT : bicepDeployment!.outputs.AZURE_AI_SERVICES_ENDPOINT

@description('Effective Azure OpenAI endpoint for chat + reasoning + embedding deployments.')
output AZURE_OPENAI_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_OPENAI_ENDPOINT : bicepDeployment!.outputs.AZURE_OPENAI_ENDPOINT

@description('Foundry Project endpoint. Required by the Microsoft Agent Framework SDK.')
output AZURE_AI_PROJECT_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_AI_PROJECT_ENDPOINT : bicepDeployment!.outputs.AZURE_AI_PROJECT_ENDPOINT

@description('OpenAI-compatible API version pinned for the GPT + reasoning deployments.')
output AZURE_OPENAI_API_VERSION string = azureOpenAiApiVersion

@description('Azure AI Agents API version.')
output AZURE_AI_AGENT_API_VERSION string = isAvm ? avmDeployment!.outputs.AZURE_AI_AGENT_API_VERSION : bicepDeployment!.outputs.AZURE_AI_AGENT_API_VERSION

@description('Deployment name of the chat-completions GPT model.')
output AZURE_OPENAI_GPT_DEPLOYMENT string = gptModelName

@description('Deployment name of the o-series reasoning model.')
output AZURE_OPENAI_REASONING_DEPLOYMENT string = isAvm ? avmDeployment!.outputs.AZURE_OPENAI_REASONING_DEPLOYMENT : bicepDeployment!.outputs.AZURE_OPENAI_REASONING_DEPLOYMENT

@description('Deployment name of the embedding model.')
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = isAvm ? avmDeployment!.outputs.AZURE_OPENAI_EMBEDDING_DEPLOYMENT : bicepDeployment!.outputs.AZURE_OPENAI_EMBEDDING_DEPLOYMENT

// --- Speech ---

@description('Speech account name.')
output AZURE_SPEECH_SERVICE_NAME string = isAvm ? avmDeployment!.outputs.AZURE_SPEECH_SERVICE_NAME : bicepDeployment!.outputs.AZURE_SPEECH_SERVICE_NAME

@description('Speech account region.')
output AZURE_SPEECH_SERVICE_REGION string = azureAiServiceLocation

@description('Speech account ARM resource ID.')
output AZURE_SPEECH_ACCOUNT_RESOURCE_ID string = isAvm ? avmDeployment!.outputs.AZURE_SPEECH_ACCOUNT_RESOURCE_ID : bicepDeployment!.outputs.AZURE_SPEECH_ACCOUNT_RESOURCE_ID

// --- Content Safety ---

@description('Content Safety account endpoint.')
output AZURE_CONTENT_SAFETY_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_CONTENT_SAFETY_ENDPOINT : bicepDeployment!.outputs.AZURE_CONTENT_SAFETY_ENDPOINT

@description('Content Safety account name.')
output AZURE_CONTENT_SAFETY_NAME string = isAvm ? avmDeployment!.outputs.AZURE_CONTENT_SAFETY_NAME : bicepDeployment!.outputs.AZURE_CONTENT_SAFETY_NAME

// --- Azure AI Search (cosmosdb mode only) ---

@description('AI Search service endpoint. Empty in postgresql mode.')
output AZURE_AI_SEARCH_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_AI_SEARCH_ENDPOINT : bicepDeployment!.outputs.AZURE_AI_SEARCH_ENDPOINT

@description('AI Search service name. Empty in postgresql mode.')
output AZURE_AI_SEARCH_NAME string = isAvm ? avmDeployment!.outputs.AZURE_AI_SEARCH_NAME : bicepDeployment!.outputs.AZURE_AI_SEARCH_NAME

@description('Chat index name. Exported so the postdeploy seed hook can run its index-population self-check; empty in postgresql mode (no AI Search).')
output AZURE_AI_SEARCH_INDEX string = isAvm ? avmDeployment!.outputs.AZURE_AI_SEARCH_INDEX : bicepDeployment!.outputs.AZURE_AI_SEARCH_INDEX

// --- Cosmos DB (cosmosdb mode only) ---

@description('Cosmos DB account endpoint. Empty in postgresql mode.')
output AZURE_COSMOS_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_COSMOS_ENDPOINT : bicepDeployment!.outputs.AZURE_COSMOS_ENDPOINT

@description('Cosmos DB account name. Empty in postgresql mode.')
output AZURE_COSMOS_ACCOUNT_NAME string = isAvm ? avmDeployment!.outputs.AZURE_COSMOS_ACCOUNT_NAME : bicepDeployment!.outputs.AZURE_COSMOS_ACCOUNT_NAME

// --- PostgreSQL (postgresql mode only) ---

@description('PostgreSQL Flexible Server FQDN. Empty in cosmosdb mode.')
output AZURE_POSTGRES_HOST string = isAvm ? avmDeployment!.outputs.AZURE_POSTGRES_HOST : bicepDeployment!.outputs.AZURE_POSTGRES_HOST

@description('Full libpq connection URI. Empty in cosmosdb mode.')
output AZURE_POSTGRES_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_POSTGRES_ENDPOINT : bicepDeployment!.outputs.AZURE_POSTGRES_ENDPOINT

@description('PostgreSQL Flexible Server resource name. Empty in cosmosdb mode.')
output AZURE_POSTGRES_NAME string = isAvm ? avmDeployment!.outputs.AZURE_POSTGRES_NAME : bicepDeployment!.outputs.AZURE_POSTGRES_NAME

@description('Entra admin principal name for the Postgres Flex server. Empty in cosmosdb mode.')
output AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME string = isAvm ? avmDeployment!.outputs.AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME : bicepDeployment!.outputs.AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME

@description('Deployer principal name registered as Postgres Entra admin (for post_provision.py). Empty in cosmosdb mode.')
output AZURE_POSTGRES_DEPLOYER_PRINCIPAL_NAME string = isAvm ? avmDeployment!.outputs.AZURE_POSTGRES_DEPLOYER_PRINCIPAL_NAME : bicepDeployment!.outputs.AZURE_POSTGRES_DEPLOYER_PRINCIPAL_NAME

// --- Storage ---

@description('Storage account name.')
output AZURE_STORAGE_ACCOUNT_NAME string = isAvm ? avmDeployment!.outputs.AZURE_STORAGE_ACCOUNT_NAME : bicepDeployment!.outputs.AZURE_STORAGE_ACCOUNT_NAME

@description('Primary blob endpoint.')
output AZURE_STORAGE_BLOB_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_STORAGE_BLOB_ENDPOINT : bicepDeployment!.outputs.AZURE_STORAGE_BLOB_ENDPOINT

@description('Container holding documents to be indexed.')
output AZURE_DOCUMENTS_CONTAINER string = isAvm ? avmDeployment!.outputs.AZURE_DOCUMENTS_CONTAINER : bicepDeployment!.outputs.AZURE_DOCUMENTS_CONTAINER

@description('Storage Queue name for doc processing.')
output AZURE_DOC_PROCESSING_QUEUE string = isAvm ? avmDeployment!.outputs.AZURE_DOC_PROCESSING_QUEUE : bicepDeployment!.outputs.AZURE_DOC_PROCESSING_QUEUE

@description('Ingestion trigger mode.')
output AZURE_INGESTION_TRIGGER string = isAvm ? avmDeployment!.outputs.AZURE_INGESTION_TRIGGER : bicepDeployment!.outputs.AZURE_INGESTION_TRIGGER

// --- Hosting endpoints ---

@description('Public URL of the backend Container App.')
output AZURE_BACKEND_URL string = isAvm ? avmDeployment!.outputs.AZURE_BACKEND_URL : bicepDeployment!.outputs.AZURE_BACKEND_URL

@description('Public URL of the frontend Container App.')
output AZURE_FRONTEND_URL string = isAvm ? avmDeployment!.outputs.AZURE_FRONTEND_URL : bicepDeployment!.outputs.AZURE_FRONTEND_URL

@description('Public URL of the Function App.')
output AZURE_FUNCTION_APP_URL string = isAvm ? avmDeployment!.outputs.AZURE_FUNCTION_APP_URL : bicepDeployment!.outputs.AZURE_FUNCTION_APP_URL

@description('Function App resource name.')
output AZURE_FUNCTION_APP_NAME string = isAvm ? avmDeployment!.outputs.AZURE_FUNCTION_APP_NAME : bicepDeployment!.outputs.AZURE_FUNCTION_APP_NAME

@description('Container Registry login server.')
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = isAvm ? avmDeployment!.outputs.AZURE_CONTAINER_REGISTRY_ENDPOINT : bicepDeployment!.outputs.AZURE_CONTAINER_REGISTRY_ENDPOINT

@description('Container Registry resource name.')
output AZURE_CONTAINER_REGISTRY_NAME string = isAvm ? avmDeployment!.outputs.AZURE_CONTAINER_REGISTRY_NAME : bicepDeployment!.outputs.AZURE_CONTAINER_REGISTRY_NAME

// --- Conditional: monitoring ---

@description('Application Insights connection string. Empty when enableMonitoring=false.')
output AZURE_APP_INSIGHTS_CONNECTION_STRING string = isAvm ? avmDeployment!.outputs.AZURE_APP_INSIGHTS_CONNECTION_STRING : bicepDeployment!.outputs.AZURE_APP_INSIGHTS_CONNECTION_STRING
