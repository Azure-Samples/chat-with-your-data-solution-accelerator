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
@description('Required. Selects BOTH the chat-history backend AND the vector index store. CosmosDB: Cosmos DB + Azure AI Search. PostgreSQL: PostgreSQL Flexible Server with pgvector (Azure AI Search is NOT deployed). Locked at deploy time.')
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

@description('Optional. Foundry IQ knowledge base name the agent_framework orchestrator grounds on (cosmosdb mode). Must match the name seeded by post_provision.py and resolved through the Project-Search connection.')
param searchKnowledgeBaseName string = 'cwyd-kb'

@description('Optional. Foundry IQ knowledge source name backing the knowledge base (the search-index knowledge source seeded by post_provision.py).')
param searchKnowledgeSourceName string = 'cwyd-index-ks'

@description('Optional. Foundry IQ knowledge base / knowledge source REST API version (operator-tunable so the KB protocol can advance without a new image).')
param searchKnowledgeBaseApiVersion string = '2025-11-01-preview'

// ============================================================================
// Parameters — Compute
// ============================================================================

@description('Optional. The container registry login server/endpoint for the container images (for example, an Azure Container Registry endpoint).')
param containerRegistryEndpoint string = 'cwydcontainerreg.azurecr.io'

@description('Optional. The image tag for the container images.')
param imageTag string = 'latest'

@description('Optional. Hosting model for the web apps. This value is fixed as "container", which uses prebuilt containers for faster deployment.')
param hostingModel string = 'container'

// ===================== //
// WAF flags             //
// ===================== //

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

@secure()
@description('Optional. VM admin username (AVM-WAF only, when private networking is enabled).')
param vmAdminUsername string?

@secure()
@description('Optional. VM admin password (AVM-WAF only, when private networking is enabled).')
param vmAdminPassword string?

@description('Optional. VM size for jumpbox (AVM-WAF only). Defaults to Standard_D2s_v5.')
param vmSize string = 'Standard_D2s_v5'

@description('Optional. Existing Log Analytics Workspace Resource ID.')
param existingLogAnalyticsWorkspaceId string = ''

// ===================== //
// Tagging               //
// ===================== //

@description('Optional. Tags applied to every deployed resource.')
param tags object = {}

@description('Optional. Identifier of the user creating the deployment, recorded in the resource group tags.')
param createdBy string = contains(deployer(), 'userPrincipalName')
  ? split(deployer().userPrincipalName, '@')[0]
  : deployer().objectId

@description('Optional. Principal object for user or service principal to assign application roles. Format: {"id":"<object-id>", "name":"<name-or-upn>", "type":"User|Group|ServicePrincipal"}')
param principal object = {
  id: '' // Principal ID
  name: '' // Principal name
  type: 'User' // Principal type ('User', 'Group', or 'ServicePrincipal')
}

@allowed(['User', 'ServicePrincipal'])
@description('Optional. Principal type of the deploying user.')
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
    searchKnowledgeBaseApiVersion: searchKnowledgeBaseApiVersion
    containerRegistryEndpoint: containerRegistryEndpoint
    imageTag: imageTag
    hostingModel: hostingModel
    enableTelemetry: enableTelemetry
    enableMonitoring: enableMonitoring
    enableScalability: enableScalability
    enableRedundancy: enableRedundancy
    enablePrivateNetworking: enablePrivateNetworking
    vmAdminUsername: vmAdminUsername
    vmAdminPassword: vmAdminPassword
    vmSize: vmSize
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
    tags: tags
    createdBy: createdBy
    principal: principal
    deployingUserPrincipalType: deployingUserPrincipalType
  }
}

// ============================================================================
// Module: Vanilla Bicep Deployment (Docker)
// Activated when deploymentFlavor = 'bicep'
// ============================================================================

// module bicepDeployment './bicep/main.bicep' = if (isBicep) {
//   name: take('module.bicep.${solutionName}', 64)
//   params: {
//     solutionName: solutionName
//     solutionUniqueText: solutionUniqueText
//     location: location
//     tags: tags
//     azureAiServiceLocation: azureAiServiceLocation
//     deploymentType: deploymentType
//     gptModelName: gptModelName
//     gptModelVersion: gptModelVersion
//     gptDeploymentCapacity: gptDeploymentCapacity
//     embeddingModel: embeddingModel
//     embeddingDeploymentCapacity: embeddingDeploymentCapacity
//     azureOpenaiAPIVersion: azureOpenaiAPIVersion
//     azureAiAgentApiVersion: azureAiAgentApiVersion
//     imageTag: imageTag
//     containerRegistryName: containerRegistryName
//     backendRuntimeStack: backendRuntimeStack
//     appServicePlanSku: appServicePlanSku
//     useChatHistoryEnabled: useChatHistoryEnabled
//     useUserAccessToken: useUserAccessToken
//     existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
//     existingFoundryProjectResourceId: existingFoundryProjectResourceId
//     deployingUserPrincipalType: deployingUserPrincipalType
//     appTitlePrimary: appTitlePrimary
//     appTitleSecondary: appTitleSecondary
//     createFabricWorkspace: createFabricWorkspace
//     azureFabricCapacityName: azureFabricCapacityName
//     fabricCapacitySku: fabricCapacitySku
//     fabricAdminMembers: fabricAdminMembers
//   }
// }

// ============================================================================
// Outputs — Coalesced from whichever flavor was deployed
// ============================================================================

// @description('Solution suffix used for naming resources.')
// output SOLUTION_NAME string = isAvm ? avmDeployment!.outputs.SOLUTION_NAME : bicepDeployment!.outputs.SOLUTION_NAME

// @description('Lower-cased solution suffix used in every downstream resource name.')
// output AZURE_SOLUTION_SUFFIX string = solutionSuffix

// @description('Resource group containing the deployment.')
// output AZURE_RESOURCE_GROUP string = resourceGroup().name

// @description('Location of the non-AI resources (Container Apps, App Service, Functions, Storage, Cosmos/Postgres).')
// output AZURE_LOCATION string = location

// @description('Location of the AI Services account + model deployments (independent of AZURE_LOCATION).')
// output AZURE_AI_SERVICE_LOCATION string = azureAiServiceLocation

// @description('Tenant ID for the deployment subscription.')
// output AZURE_TENANT_ID string = subscription().tenantId

// @description('Client ID of the user-assigned managed identity shared by all v2 workloads.')
// output AZURE_UAMI_CLIENT_ID string = userAssignedIdentity.outputs.clientId

// @description('Principal (object) ID of the user-assigned managed identity.')
// output AZURE_UAMI_PRINCIPAL_ID string = userAssignedIdentity.outputs.principalId

// @description('Resource ID of the user-assigned managed identity.')
// output AZURE_UAMI_RESOURCE_ID string = userAssignedIdentity.outputs.resourceId

// // --- Database routing flag (mirrored as env on every workload) ---

// @description('Selected database engine for chat history + vector index (locked at deploy).')
// output AZURE_DB_TYPE string = databaseType

// @description('Logical name of the configured vector index store: "AzureSearch" (cosmosdb mode) or "pgvector" (postgresql mode).')
// output AZURE_INDEX_STORE string = indexStoreValue

// // --- Foundry substrate ---

// @description('Unified AI Services endpoint. Used by both orchestrators (LangGraph via OpenAI-compatible path; Agent Framework via the project endpoint below).')
// output AZURE_AI_SERVICES_ENDPOINT string = aiServices.outputs.endpoint

// @description('Effective Azure OpenAI endpoint backends call for chat + reasoning + embedding deployments. When `existingOpenAiName` is set this points at the reused v1 OpenAI account; otherwise it equals AZURE_AI_SERVICES_ENDPOINT (deployments live on the v2 Foundry account).')
// output AZURE_OPENAI_ENDPOINT string = effectiveOpenAiEndpoint

// @description('Foundry Project endpoint (https://<account>.services.ai.azure.com/api/projects/<project>). Required by the Microsoft Agent Framework SDK.')
// output AZURE_AI_PROJECT_ENDPOINT string = aiProject.outputs.projectEndpoint

// @description('OpenAI-compatible API version pinned for the GPT + reasoning deployments.')
// output AZURE_OPENAI_API_VERSION string = azureOpenAiApiVersion

// @description('Azure AI Agents API version pinned for the Foundry Project endpoint.')
// output AZURE_AI_AGENT_API_VERSION string = azureAiAgentApiVersion

// @description('Deployment name of the chat-completions GPT model.')
// output AZURE_OPENAI_GPT_DEPLOYMENT string = gptModelName

// @description('Deployment name of the o-series reasoning model (output flows on the SSE `reasoning` channel).')
// output AZURE_OPENAI_REASONING_DEPLOYMENT string = reasoningModelName

// @description('Deployment name of the embedding model used by the indexing pipeline.')
// output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = embeddingModelName

// // --- Speech (S1 / SPEECH-MVP) ---

// @description('Speech account name (kind=SpeechServices). Backend reads via SpeechSettings.service_name; not used directly by the SDK.')
// output AZURE_SPEECH_SERVICE_NAME string = speechService.outputs.name

// @description('Speech account region. Browser SDK passes this to SpeechConfig.fromAuthorizationToken(token, region) and the backend uses it to build the regional sts/v1.0/issueToken URL.')
// output AZURE_SPEECH_SERVICE_REGION string = azureAiServiceLocation

// @description('Speech account ARM resource id. Required as the x-ms-cognitiveservices-resource-id header on the AAD-bearer STS issueToken POST.')
// output AZURE_SPEECH_ACCOUNT_RESOURCE_ID string = speechService.outputs.resourceId

// // --- Content Safety ---

// @description('Content Safety account endpoint. Backend reads via ContentSafetySettings.endpoint; lifespan gates client construction on this + AZURE_CONTENT_SAFETY_ENABLED.')
// output AZURE_CONTENT_SAFETY_ENDPOINT string = cogContentSafety.outputs.endpoint

// @description('Content Safety account name (kind=ContentSafety). Diagnostic surface only — backend builds the client from the endpoint.')
// output AZURE_CONTENT_SAFETY_NAME string = cogContentSafety.outputs.name

// // --- Conditional: Azure AI Search (cosmosdb mode only) ---

// @description('AI Search service endpoint. Empty in postgresql mode.')
// output AZURE_AI_SEARCH_ENDPOINT string = databaseType == 'cosmosdb' ? effectiveSearchEndpoint : ''

// @description('AI Search service name. Empty in postgresql mode.')
// output AZURE_AI_SEARCH_NAME string = databaseType == 'cosmosdb' ? effectiveSearchName : ''

// // --- Conditional: Cosmos DB (cosmosdb mode only) ---

// @description('Cosmos DB account endpoint (DocumentEndpoint). Empty in postgresql mode.')
// output AZURE_COSMOS_ENDPOINT string = databaseType == 'cosmosdb' ? effectiveCosmosEndpoint : ''

// @description('Cosmos DB account name. Empty in postgresql mode.')
// output AZURE_COSMOS_ACCOUNT_NAME string = databaseType == 'cosmosdb' ? effectiveCosmosName : ''

// // --- Conditional: PostgreSQL Flexible Server (postgresql mode only) ---

// @description('PostgreSQL Flexible Server FQDN (clients add :5432 themselves). Empty in cosmosdb mode.')
// output AZURE_POSTGRES_HOST string = databaseType == 'postgresql' ? postgresServer!.outputs.fqdn! : ''

// @description('Full libpq connection URI for the PostgreSQL Flexible Server (no credentials — the workload supplies an Entra token; the user comes from AZURE_UAMI_CLIENT_ID). Mirrors AZURE_COSMOS_ENDPOINT shape so AzurePostgresSettings reads one var. Empty in cosmosdb mode.')
// output AZURE_POSTGRES_ENDPOINT string = postgresLibpqUri

// @description('PostgreSQL Flexible Server resource name. Empty in cosmosdb mode.')
// output AZURE_POSTGRES_NAME string = databaseType == 'postgresql' ? postgresServer!.outputs.name : ''

// @description('Configured Entra admin principal name for the Postgres Flex server (used as the `user` in AAD-token connections by the post-provision hook). Empty in cosmosdb mode.')
// output AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME string = databaseType == 'postgresql' ? postgresAdminPrincipalName : ''

// // --- Storage (blobs + queues + Function deployment package) ---

// @description('Storage account name (shared by RAG document store, indexing queues, and the Function App deployment package).')
// output AZURE_STORAGE_ACCOUNT_NAME string = effectiveStorageName

// @description('Primary blob endpoint of the shared storage account (https URL ending in /). Hostname follows the storage cloud-specific suffix.')
// output AZURE_STORAGE_BLOB_ENDPOINT string = effectiveStorageBlobEndpoint

// @description('Container holding documents to be indexed (Event Grid filter + batch_start source).')
// output AZURE_DOCUMENTS_CONTAINER string = documentsContainerName

// @description('Storage Queue name fed by Event Grid BlobCreated and consumed by the batch_push Function blueprint.')
// output AZURE_DOC_PROCESSING_QUEUE string = docProcessingQueueName

// // --- Hosting endpoints (consumed by azd hooks, Vite build, smoke tests) ---

// @description('Public URL of the backend Container App (FastAPI + LangGraph/Agent Framework).')
// output AZURE_BACKEND_URL string = 'https://${backendContainerApp.outputs.fqdn}'

// @description('Public URL of the frontend Web App (React/Vite SPA). Backend CORS must allow this origin.')
// output AZURE_FRONTEND_URL string = 'https://${frontendWebApp.outputs.defaultHostname}'

// @description('Public URL of the Function App hosting the indexing pipeline.')
// output AZURE_FUNCTION_APP_URL string = 'https://${functionApp.outputs.defaultHostname}'

// @description('Function App resource name (used by azd to deploy the function package).')
// output AZURE_FUNCTION_APP_NAME string = functionApp.outputs.name

// @description('Container Registry login server (e.g. cr<SUFFIX>.azurecr.io). `azd deploy` reads this to discover the push target for backend + function images.')
// output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer

// @description('Container Registry resource name. Diagnostic surface only — azd uses the login server above.')
// output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.name

// // --- Conditional: monitoring ---

// @description('Application Insights connection string. Empty when enableMonitoring=false.')
// output AZURE_APP_INSIGHTS_CONNECTION_STRING string = enableMonitoring ? applicationInsights!.outputs.connectionString : ''

// // --- Conditional: private networking (enablePrivateNetworking only) ---

// @description('VNet name. Empty when enablePrivateNetworking=false.')
// output AZURE_VNET_NAME string = enablePrivateNetworking ? virtualNetwork!.outputs.name : ''

// @description('VNet resource ID. Empty when enablePrivateNetworking=false.')
// output AZURE_VNET_RESOURCE_ID string = enablePrivateNetworking ? virtualNetwork!.outputs.resourceId : ''

// @description('Bastion host name (for `az network bastion tunnel`). Empty when enablePrivateNetworking=false.')
// output AZURE_BASTION_NAME string = enablePrivateNetworking ? bastion!.outputs.name : ''

@description('Selected database engine for chat history + vector index (locked at deploy).')
output AZURE_DB_TYPE string = databaseType

@description('PostgreSQL Flexible Server FQDN (clients add :5432 themselves). Empty in cosmosdb mode.')
output AZURE_POSTGRES_HOST string = databaseType == 'postgresql' ? avmDeployment!.outputs.AZURE_POSTGRES_HOST : ''

@description('AI Search service endpoint. Empty in PostgreSQL mode.')
output AZURE_AI_SEARCH_ENDPOINT string = databaseType == 'cosmosdb' ? avmDeployment!.outputs.AZURE_AI_SEARCH_ENDPOINT : ''
