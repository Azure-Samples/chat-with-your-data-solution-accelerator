// ============================================================================
// main.bicep — Vanilla Bicep (Docker) flavor orchestrator
// Description: Functional twin of ./avm/main.bicep (Foundry-first v2) built from
//              the local native-resource modules under ./modules/*.
//              Frontend AND backend run on Azure Container Apps; the Functions
//              host runs as a code/zip Linux Function App.
//              Pure orchestrator: this file calls modules and declares only the
//              child resources / role assignments the native modules do not own
//              (storage queues, RBAC, Cosmos data-plane role).
//              Scope: simple Docker deploy + optional monitoring. No private
//              networking, scalability, redundancy, or VM/bastion (those live in
//              the avm-waf flavor only).
// ============================================================================
targetScope = 'resourceGroup'

// ============================================================================
// Parameters — Core
// ============================================================================

@minLength(3)
@maxLength(15)
@description('Required. Unique application/solution name. Drives every resource name. Cap is 15 chars to keep PostgreSQL Flexible Server names within limits.')
param solutionName string = 'cwyd'

@maxLength(5)
@description('Optional. Short unique suffix appended to global resource names. Defaults to a 5-char hash of subscription + RG + solution name.')
param solutionUniqueText string = take(uniqueString(subscription().id, resourceGroup().name, solutionName), 5)

@metadata({ azd: { type: 'location' } })
@description('Required. Azure region for non-AI resources (Container Apps, App Service, Functions, Storage, Cosmos/Postgres).')
param location string

@metadata({ azd: { type: 'location' } })
@description('Required. Region for AI Services / Foundry deployments.')
param azureAiServiceLocation string

// ===================== //
// Database selection    //
// ===================== //

@allowed([
  'cosmosdb'
  'postgresql'
])
@description('Required. Selects BOTH the chat-history backend AND the vector index store. CosmosDB: Cosmos DB + Azure AI Search. PostgreSQL: PostgreSQL Flexible Server with pgvector (Azure AI Search is NOT deployed).')
param databaseType string = 'cosmosdb'

// ===================== //
// Ingestion trigger     //
// ===================== //

@allowed([
  'direct_enqueue'
  'event_grid'
])
@description('Optional. How an uploaded document is picked up for indexing. direct_enqueue: the backend enqueues the doc-processing message itself. event_grid: a storage Event Grid subscription fans BlobCreated/BlobDeleted to the blob-events queue.')
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
@description('Optional. Embedding model deployment name.')
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

@description('Optional. Azure OpenAI API version exposed via the OpenAI-compatible endpoint.')
param azureOpenAiApiVersion string = '2025-01-01-preview'

@description('Optional. Azure AI Agent API version (used by the Agent Framework orchestrator).')
param azureAiAgentApiVersion string = '2025-05-01'

@description('Optional. Foundry IQ knowledge base name the agent_framework orchestrator grounds on (cosmosdb mode).')
param searchKnowledgeBaseName string = 'cwyd-kb'

@description('Optional. Foundry IQ knowledge source name backing the knowledge base.')
param searchKnowledgeSourceName string = 'cwyd-index-ks'

@description('Optional. Foundry IQ knowledge base / knowledge source REST API version.')
param searchKnowledgeBaseApiVersion string = '2025-11-01-preview'

// ============================================================================
// Parameters — Compute
// ============================================================================

@description('Optional. The container registry login server/endpoint for the container images.')
param containerRegistryEndpoint string = 'cwydcontainerreg.azurecr.io'

@description('Optional. The image tag for the container images.')
param imageTag string = 'latest'

@description('Optional. Hosting model for the web apps. Fixed as "container" for the Container App frontend/backend.')
#disable-next-line no-unused-params
param hostingModel string = 'container'

@description('Optional. Deploy Application Insights and wire diagnostics. Log Analytics is always deployed because the Container Apps Environment requires it.')
param enableMonitoring bool = false

@description('Optional. Existing Log Analytics Workspace Resource ID. When set, the workspace is reused instead of deploying a new one.')
param existingLogAnalyticsWorkspaceId string = ''

// ===================== //
// Tagging               //
// ===================== //

@description('Optional. Tags applied to every deployed resource.')
param tags object = {}

@description('Optional. Identifier of the user creating the deployment, recorded in the resource group tags.')
param createdBy string?

@allowed(['User', 'ServicePrincipal'])
@description('Optional. Principal type of the deploying user.')
param deployingUserPrincipalType string = 'User'

// ===================== //
// Variables             //
// ===================== //

var solutionSuffix = toLower(trim(replace(
  replace(
    replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''),
    ' ',
    ''
  ),
  '*',
  '')))

var deployingUserPrincipalId = deployer().objectId

var docProcessingQueueName = 'doc-processing'
var blobEventsQueueName = 'blob-events'
var documentsContainerName = 'documents'

var storageQueueNames = [
  'doc-processing'
  'doc-processing-poison'
  'blob-events'
  'blob-events-poison'
  'add-url'
  'add-url-poison'
]

var allTags = union(
  {
    'azd-env-name': solutionName
    TemplateName: 'CWYD-v2'
    Type: 'Non-WAF'
    CreatedBy: createdBy
    DatabaseType: databaseType
  },
  tags
)

var isCosmos = databaseType == 'cosmosdb'
var indexStoreValue = isCosmos ? 'AzureSearch' : 'pgvector'

var postgresLibpqUri = databaseType == 'postgresql'
  ? 'postgresql://${postgresServer!.outputs.serverFqdn}:5432/cwyd?sslmode=require'
  : ''

var defaultOpenAiDeployments = [
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
    raiPolicyName: 'Microsoft.DefaultV2'
  }
]

// ----- Role definition GUIDs (built-in roles) -----
var roleIds = {
  cognitiveServicesOpenAIUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  azureAiUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
  cognitiveServicesSpeechUser: 'f2dc8367-1007-4938-bd23-fe263f013447'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  storageBlobDataOwner: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  storageQueueDataContributor: '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  storageAccountContributor: '17d1049b-9a84-46fb-8f53-869881c3d3ab'
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
}
var cosmosDataContributorRoleId = '00000000-0000-0000-0000-000000000002'

// ----- Deterministic resource names (mirror each module's naming rule) -----
// Used by `existing` references whose .id must be calculable at the start of
// deployment (role assignment / child-resource name + scope cannot depend on a
// runtime module output). Ordering is enforced with explicit dependsOn.
var uamiName = 'id-${solutionSuffix}'
var aiFoundryName = 'aif-${solutionSuffix}'
var aiFoundryProjectName = 'proj-${solutionSuffix}'
var aiSearchName = 'srch-${solutionSuffix}'
var storageName = take('st${solutionSuffix}', 24)
var containerRegistryName = 'cr${solutionSuffix}'
var cosmosDbName = 'cosmos-${solutionSuffix}'

// ===================== //
// Resources             //
// ===================== //

resource resourceGroupTags 'Microsoft.Resources/tags@2025-04-01' = {
  name: 'default'
  properties: {
    tags: union(resourceGroup().tags ?? {}, allTags)
  }
}

// ========== Managed Identity ========== //
module userAssignedIdentity './modules/identity/managed-identity.bicep' = {
  name: take('module.managed-identity.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
  }
}

// ============================================================================
// Module: Monitoring
// Log Analytics is ALWAYS provisioned (the Container Apps Environment requires a
// workspace). Application Insights is gated on enableMonitoring.
// ============================================================================

var useExistingLogAnalytics = !empty(existingLogAnalyticsWorkspaceId)

resource existingLogAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2025-07-01' existing = if (useExistingLogAnalytics) {
  name: split(existingLogAnalyticsWorkspaceId, '/')[8]
  scope: resourceGroup(split(existingLogAnalyticsWorkspaceId, '/')[2], split(existingLogAnalyticsWorkspaceId, '/')[4])
}

module logAnalyticsWorkspace './modules/monitoring/log-analytics.bicep' = if (!useExistingLogAnalytics) {
  name: take('module.log-analytics.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
  }
}

var logAnalyticsWorkspaceResourceId = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspace.id
  : logAnalyticsWorkspace!.outputs.resourceId

module applicationInsights './modules/monitoring/app-insights.bicep' = if (enableMonitoring) {
  name: take('module.app-insights.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    workspaceResourceId: logAnalyticsWorkspaceResourceId
  }
}

var appInsightsConnectionString = enableMonitoring ? applicationInsights!.outputs.connectionString : ''

// ============================================================================
// Module: AI Foundry (account + project)
// ============================================================================

module aiProject './modules/ai/ai-foundry-project.bicep' = {
  name: take('module.ai-foundry-project.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: azureAiServiceLocation
    tags: allTags
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

// Model deployments — serial (@batchSize(1)) to avoid Cognitive Services
// deployment throttling, since the native module owns a single deployment each.
@batchSize(1)
module aiModelDeployments './modules/ai/ai-foundry-model-deployment.bicep' = [
  for deployment in defaultOpenAiDeployments: {
    name: take('module.model-deployment.${deployment.name}.${solutionSuffix}', 64)
    params: {
      aiServicesAccountName: aiProject.outputs.name
      deploymentName: deployment.name
      modelFormat: deployment.model.format
      modelName: deployment.model.name
      modelVersion: deployment.model.version
      raiPolicyName: deployment.raiPolicyName
      skuName: deployment.sku.name
      skuCapacity: deployment.sku.capacity
    }
  }
]

var speechServiceName = 'spch-${solutionSuffix}'
module speechService './modules/ai/ai-services.bicep' = {
  name: take('module.ai-services.SpeechServices.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    namePrefix: 'spch'
    name: speechServiceName
    location: azureAiServiceLocation
    tags: allTags
    kind: 'SpeechServices'
    customSubDomainName: speechServiceName
    publicNetworkAccess: 'Enabled'
  }
}

var contentSafetyServiceName = 'cs-${solutionSuffix}'
module contentSafety './modules/ai/ai-services.bicep' = {
  name: take('module.ai-services.ContentSafety.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    namePrefix: 'cs'
    name: contentSafetyServiceName
    location: azureAiServiceLocation
    tags: allTags
    kind: 'ContentSafety'
    customSubDomainName: contentSafetyServiceName
    publicNetworkAccess: 'Enabled'
  }
}

// ============================================================================
// Module: Azure AI Search (cosmosdb mode only) + Foundry connection
// ============================================================================

module aiSearch './modules/ai/ai-search.bicep' = if (isCosmos) {
  name: take('module.ai-search.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    skuName: 'basic'
    publicNetworkAccess: 'Enabled'
  }
}

module aiProjectSearchConnection './modules/ai/ai-foundry-connection.bicep' = if (isCosmos) {
  name: take('module.foundry-search-conn.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    aiServicesAccountName: aiProject.outputs.name
    projectName: aiProject.outputs.projectName
    target: aiSearch!.outputs.endpoint
    category: 'CognitiveSearch'
    authType: 'AAD'
    useWorkspaceManagedIdentity: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: aiSearch!.outputs.resourceId
      knowledgeBaseName: searchKnowledgeBaseName
    }
  }
}

// ============================================================================
// Module: Storage Account
// allowSharedKeyAccess=true so the code/zip Function App host can authenticate
// to AzureWebJobsStorage with the account key (key-based, per the native
// function-app module).
// ============================================================================

module storageAccount './modules/data/storage-account.bicep' = {
  name: take('module.storage-account.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    kind: 'StorageV2'
    skuName: 'Standard_LRS'
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true
    containers: [
      { name: documentsContainerName, publicAccess: 'None' }
      { name: 'config', publicAccess: 'None' }
      { name: 'deployment-package', publicAccess: 'None' }
    ]
  }
}

// Storage queues — the native storage-account module creates blob containers
// only, so the v2 ingestion queues are declared here against the deployed
// account (deterministic existing ref + explicit dependsOn for ordering).
resource storageAccountResource 'Microsoft.Storage/storageAccounts@2025-08-01' existing = {
  #disable-next-line BCP334
  name: storageName
}

resource storageQueueService 'Microsoft.Storage/storageAccounts/queueServices@2025-08-01' = {
  parent: storageAccountResource
  name: 'default'
  dependsOn: [
    storageAccount
  ]
}

resource storageQueues 'Microsoft.Storage/storageAccounts/queueServices/queues@2025-08-01' = [
  for queueName in storageQueueNames: {
    parent: storageQueueService
    name: queueName
  }
]

// ============================================================================
// Module: Data (chat history + vector store)
// ============================================================================

module cosmosDb './modules/data/cosmos-db-nosql.bicep' = if (isCosmos) {
  name: take('module.cosmos-db.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    databaseName: 'cwyd'
  }
}

module postgresServer './modules/data/postgresql-flexible-server.bicep' = if (databaseType == 'postgresql') {
  name: take('module.postgresql.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    skuName: 'Standard_B2s'
    skuTier: 'Burstable'
    administrators: union(
      [
        {
          objectId: userAssignedIdentity.outputs.principalId
          principalName: userAssignedIdentity.outputs.name
          principalType: 'ServicePrincipal'
        }
      ],
      contains(deployer(), 'userPrincipalName')
        ? [
            {
              objectId: deployingUserPrincipalId
              principalName: deployer().userPrincipalName
              principalType: deployingUserPrincipalType
            }
          ]
        : []
    )
    databases: [
      { name: 'cwyd', charset: 'UTF8', collation: 'en_US.utf8' }
    ]
    configurations: [
      { name: 'azure.extensions', value: 'VECTOR', source: 'user-override' }
    ]
  }
}

// ========== Container Registry ========== //
module containerRegistry './modules/compute/container-registry.bicep' = {
  name: take('module.container-registry.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    sku: 'Basic'
    publicNetworkAccess: 'Enabled'
  }
}

// ========== Container App Environment ========== //
module containerAppsEnv './modules/compute/container-app-environment.bicep' = {
  name: take('module.container-app-environment.${solutionSuffix}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    logAnalyticsWorkspaceResourceId: logAnalyticsWorkspaceResourceId
  }
}

// ========== Backend Container App ========== //
var backendContainerEnv = concat(
  [
    { name: 'AZURE_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
    { name: 'AZURE_UAMI_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
    { name: 'AZURE_TENANT_ID', value: subscription().tenantId }
    { name: 'AZURE_ENVIRONMENT', value: 'production' }
    { name: 'AZURE_AI_PROJECT_ENDPOINT', value: aiProject.outputs.projectEndpoint }
    { name: 'AZURE_OPENAI_ENDPOINT', value: aiProject.outputs.endpoint }
    { name: 'AZURE_AI_SERVICES_ENDPOINT', value: aiProject.outputs.endpoint }
    { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
    { name: 'AZURE_AI_AGENT_API_VERSION', value: azureAiAgentApiVersion }
    { name: 'AZURE_OPENAI_GPT_DEPLOYMENT', value: gptModelName }
    { name: 'AZURE_OPENAI_REASONING_DEPLOYMENT', value: reasoningModelName }
    { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
    { name: 'AZURE_DB_TYPE', value: databaseType }
    { name: 'AZURE_INDEX_STORE', value: indexStoreValue }
    { name: 'AZURE_COSMOS_ENDPOINT', value: isCosmos ? cosmosDb!.outputs.endpoint : '' }
    { name: 'AZURE_AI_SEARCH_ENDPOINT', value: isCosmos ? aiSearch!.outputs.endpoint : '' }
    { name: 'AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME', value: searchKnowledgeBaseName }
    { name: 'AZURE_AI_SEARCH_KNOWLEDGE_SOURCE_NAME', value: searchKnowledgeSourceName }
    { name: 'AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION', value: searchKnowledgeBaseApiVersion }
    { name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: isCosmos ? aiProjectSearchConnection!.outputs.connectionName : '' }
    { name: 'AZURE_POSTGRES_ENDPOINT', value: postgresLibpqUri }
    { name: 'AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME', value: databaseType == 'postgresql' ? userAssignedIdentity.outputs.name : '' }
    { name: 'AZURE_SPEECH_SERVICE_NAME', value: speechService.outputs.name }
    { name: 'AZURE_SPEECH_SERVICE_REGION', value: azureAiServiceLocation }
    { name: 'AZURE_SPEECH_ACCOUNT_RESOURCE_ID', value: speechService.outputs.resourceId }
    { name: 'AZURE_CONTENT_SAFETY_ENABLED', value: 'true' }
    { name: 'AZURE_CONTENT_SAFETY_ENDPOINT', value: contentSafety.outputs.endpoint }
    { name: 'ORCHESTRATOR', value: 'agent_framework' }
    { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storageAccount.outputs.name }
    { name: 'AZURE_DOCUMENTS_CONTAINER', value: documentsContainerName }
    { name: 'AZURE_DOC_PROCESSING_QUEUE', value: docProcessingQueueName }
    { name: 'AZURE_INGESTION_TRIGGER', value: ingestionTrigger }
  ],
  enableMonitoring
    ? [ { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString } ]
    : []
)

module backendContainerApp './modules/compute/container-app.bicep' = {
  name: take('module.container-app-backend.${solutionSuffix}', 64)
  params: {
    name: 'ca-backend-${solutionSuffix}'
    location: location
    tags: union(allTags, { 'azd-service-name': 'backend' })
    environmentResourceId: containerAppsEnv.outputs.resourceId
    identity: {
      type: 'SystemAssigned, UserAssigned'
      userAssignedIdentities: {
        '${userAssignedIdentity.outputs.resourceId}': {}
      }
    }
    workloadProfileName: 'Consumption'
    ingressTargetPort: 8000
    ingressExternal: true
    scaleSettings: {
      minReplicas: 0
      maxReplicas: 3
    }
    containers: [
      {
        name: 'backend'
        image: '${containerRegistryEndpoint}/rag-backend:${imageTag}'
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: backendContainerEnv
      }
    ]
  }
}

// ========== App Service Plan (hosts the code/zip Function App) ========== //
module appServicePlan './modules/compute/app-service-plan.bicep' = {
  name: take('module.app-service-plan.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    skuName: 'B3'
    skuCapacity: 1
  }
}

// ========== Frontend Container App ========== //
var frontendContainerEnv = concat(
  [
    { name: 'VITE_BACKEND_URL', value: 'https://${backendContainerApp.outputs.fqdn}' }
  ],
  enableMonitoring
    ? [ { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString } ]
    : []
)

module frontendContainerApp './modules/compute/container-app.bicep' = {
  name: take('module.container-app-frontend.${solutionSuffix}', 64)
  params: {
    name: 'ca-frontend-${solutionSuffix}'
    location: location
    tags: union(allTags, { 'azd-service-name': 'frontend' })
    environmentResourceId: containerAppsEnv.outputs.resourceId
    identity: {
      type: 'SystemAssigned, UserAssigned'
      userAssignedIdentities: {
        '${userAssignedIdentity.outputs.resourceId}': {}
      }
    }
    workloadProfileName: 'Consumption'
    ingressTargetPort: 80
    ingressExternal: true
    scaleSettings: {
      minReplicas: 1
      maxReplicas: 3
    }
    containers: [
      {
        name: 'frontend'
        image: '${containerRegistryEndpoint}/rag-frontend:${imageTag}'
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: frontendContainerEnv
      }
    ]
  }
}

// ========== Function App (code/zip, Linux) ========== //
var functionAppSettings = concat(
  [
    { name: 'AZURE_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
    { name: 'AZURE_UAMI_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
    { name: 'AZURE_TENANT_ID', value: subscription().tenantId }
    { name: 'AZURE_ENVIRONMENT', value: 'production' }
    { name: 'AZURE_AI_PROJECT_ENDPOINT', value: aiProject.outputs.projectEndpoint }
    { name: 'AZURE_OPENAI_ENDPOINT', value: aiProject.outputs.endpoint }
    { name: 'AZURE_AI_SERVICES_ENDPOINT', value: aiProject.outputs.endpoint }
    { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
    { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
    { name: 'AZURE_DB_TYPE', value: databaseType }
    { name: 'AZURE_INDEX_STORE', value: indexStoreValue }
    { name: 'AZURE_COSMOS_ENDPOINT', value: isCosmos ? cosmosDb!.outputs.endpoint : '' }
    { name: 'AZURE_AI_SEARCH_ENDPOINT', value: isCosmos ? aiSearch!.outputs.endpoint : '' }
    { name: 'AZURE_POSTGRES_ENDPOINT', value: postgresLibpqUri }
    { name: 'AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME', value: databaseType == 'postgresql' ? userAssignedIdentity.outputs.name : '' }
    { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storageAccount.outputs.name }
    { name: 'AZURE_DOCUMENTS_CONTAINER', value: documentsContainerName }
    { name: 'AZURE_DOC_PROCESSING_QUEUE', value: docProcessingQueueName }
    { name: 'AZURE_INGESTION_TRIGGER', value: ingestionTrigger }
  ],
  enableMonitoring
    ? [ { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString } ]
    : []
)

var functionName = 'func-${solutionSuffix}'
module functionApp './modules/compute/function-app.bicep' = {
  name: take('module.function-app.${solutionName}', 64)
  params: {
    name: functionName
    location: location
    tags: union(allTags, { 'azd-service-name': 'function' })
    serverFarmResourceId: appServicePlan.outputs.resourceId
    storageAccountResourceId: storageAccount.outputs.resourceId
    storageAccountName: storageAccount.outputs.name
    identity: {
      type: 'SystemAssigned, UserAssigned'
      userAssignedIdentities: {
        '${userAssignedIdentity.outputs.resourceId}': {}
      }
    }
    runtimeStack: 'python'
    runtimeVersion: '3.11'
    appSettings: functionAppSettings
  }
}

// ========== Event Grid (storage blob events -> blob-events queue) ========== //
module eventGridSystemTopic './modules/data/event-grid.bicep' = {
  name: take('module.event-grid.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    source: storageAccount.outputs.resourceId
    topicType: 'Microsoft.Storage.StorageAccounts'
    eventSubscriptions: [
      {
        name: 'blob-created-to-blob-events'
        destination: {
          endpointType: 'StorageQueue'
          properties: {
            resourceId: storageAccount.outputs.resourceId
            queueName: blobEventsQueueName
          }
        }
        filter: {
          includedEventTypes: [
            'Microsoft.Storage.BlobCreated'
            'Microsoft.Storage.BlobDeleted'
          ]
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
  dependsOn: [
    storageQueues
  ]
}

// ============================================================================
// Role Assignments (native — the local resource modules do not own RBAC).
// Mirrors avm/main.bicep. Existing references use DETERMINISTIC resource names
// so the assignment name/scope are calculable at the start of deployment;
// ordering against the creating modules is enforced with explicit dependsOn.
// ============================================================================

resource uamiResource 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: uamiName
}

resource aiFoundryAccountResource 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: aiFoundryName
}

resource aiFoundryProjectResource 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' existing = {
  parent: aiFoundryAccountResource
  name: aiFoundryProjectName
}

resource speechServiceResource 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: speechServiceName
}

resource contentSafetyResource 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: contentSafetyServiceName
}

resource searchServiceResource 'Microsoft.Search/searchServices@2025-05-01' existing = if (isCosmos) {
  name: aiSearchName
}

resource containerRegistryResource 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  #disable-next-line BCP334
  name: containerRegistryName
}

resource functionAppResource 'Microsoft.Web/sites@2024-04-01' existing = {
  name: functionName
}

// ----- UAMI -> AI Foundry account -----
var uamiFoundryRoleIds = [
  roleIds.cognitiveServicesOpenAIUser
  roleIds.cognitiveServicesUser
  roleIds.azureAiUser
]
resource uamiFoundryRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleId in uamiFoundryRoleIds: {
    name: guid(aiFoundryAccountResource.id, uamiResource.id, roleId)
    scope: aiFoundryAccountResource
    properties: {
      principalId: uamiResource.properties.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleId)
      principalType: 'ServicePrincipal'
    }
    dependsOn: [
      aiProject
      userAssignedIdentity
    ]
  }
]

// ----- UAMI -> Speech -----
resource uamiSpeechRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(speechServiceResource.id, uamiResource.id, roleIds.cognitiveServicesSpeechUser)
  scope: speechServiceResource
  properties: {
    principalId: uamiResource.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.cognitiveServicesSpeechUser)
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    speechService
    userAssignedIdentity
  ]
}

// ----- UAMI -> Content Safety -----
resource uamiContentSafetyRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(contentSafetyResource.id, uamiResource.id, roleIds.cognitiveServicesUser)
  scope: contentSafetyResource
  properties: {
    principalId: uamiResource.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.cognitiveServicesUser)
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    contentSafety
    userAssignedIdentity
  ]
}

// ----- UAMI -> Container Registry (AcrPull) -----
resource uamiAcrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistryResource.id, uamiResource.id, roleIds.acrPull)
  scope: containerRegistryResource
  properties: {
    principalId: uamiResource.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.acrPull)
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    containerRegistry
    userAssignedIdentity
  ]
}

// ----- UAMI -> Storage -----
var uamiStorageRoleIds = [
  roleIds.storageBlobDataContributor
  roleIds.storageQueueDataContributor
  roleIds.storageAccountContributor
]
resource uamiStorageRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleId in uamiStorageRoleIds: {
    name: guid(storageAccountResource.id, uamiResource.id, roleId)
    scope: storageAccountResource
    properties: {
      principalId: uamiResource.properties.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleId)
      principalType: 'ServicePrincipal'
    }
    dependsOn: [
      storageAccount
      userAssignedIdentity
    ]
  }
]

// ----- AI Project (project identity) -> Storage Blob Data Contributor -----
resource projectStorageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountResource.id, aiFoundryProjectResource.id, roleIds.storageBlobDataContributor)
  scope: storageAccountResource
  properties: {
    principalId: aiFoundryProjectResource.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.storageBlobDataContributor)
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    storageAccount
    aiProject
  ]
}

// ----- Function App (system identity) -> Storage (host lock + queue triggers) -----
var functionStorageRoleIds = [
  roleIds.storageBlobDataOwner
  roleIds.storageQueueDataContributor
  roleIds.storageAccountContributor
]
resource functionStorageRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleId in functionStorageRoleIds: {
    name: guid(storageAccountResource.id, functionAppResource.id, roleId)
    scope: storageAccountResource
    properties: {
      principalId: functionAppResource.identity.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleId)
      principalType: 'ServicePrincipal'
    }
    dependsOn: [
      storageAccount
      functionApp
    ]
  }
]

// ----- UAMI -> AI Search (cosmosdb mode) -----
var uamiSearchRoleIds = [
  roleIds.searchIndexDataContributor
  roleIds.searchServiceContributor
]
resource uamiSearchRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleId in uamiSearchRoleIds: if (isCosmos) {
    name: guid(searchServiceResource.id, uamiResource.id, roleId)
    scope: searchServiceResource
    properties: {
      principalId: uamiResource.properties.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleId)
      principalType: 'ServicePrincipal'
    }
    dependsOn: [
      aiSearch
      userAssignedIdentity
    ]
  }
]

// ----- AI Project (project identity) -> AI Search (cosmosdb mode) -----
var projectSearchRoleIds = [
  roleIds.searchIndexDataReader
  roleIds.searchIndexDataContributor
  roleIds.searchServiceContributor
]
resource projectSearchRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleId in projectSearchRoleIds: if (isCosmos) {
    name: guid(searchServiceResource.id, aiFoundryProjectResource.id, roleId)
    scope: searchServiceResource
    properties: {
      principalId: aiFoundryProjectResource.identity.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleId)
      principalType: 'ServicePrincipal'
    }
    dependsOn: [
      aiSearch
      aiProject
    ]
  }
]

// ----- AI Services account identity -> AI Search (cosmosdb mode) -----
var accountSearchRoleIds = [
  roleIds.searchIndexDataContributor
  roleIds.searchIndexDataReader
  roleIds.searchServiceContributor
]
resource accountSearchRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleId in accountSearchRoleIds: if (isCosmos) {
    name: guid(searchServiceResource.id, aiFoundryAccountResource.id, roleId)
    scope: searchServiceResource
    properties: {
      principalId: aiFoundryAccountResource.identity.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleId)
      principalType: 'ServicePrincipal'
    }
    dependsOn: [
      aiSearch
      aiProject
    ]
  }
]

// ----- AI Search identity -> Storage + AI Foundry (cosmosdb mode) -----
resource searchStorageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isCosmos) {
  name: guid(storageAccountResource.id, searchServiceResource.id, roleIds.storageBlobDataContributor)
  scope: storageAccountResource
  properties: {
    principalId: searchServiceResource!.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.storageBlobDataContributor)
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    storageAccount
    aiSearch
  ]
}

var searchFoundryRoleIds = [
  roleIds.cognitiveServicesUser
  roleIds.cognitiveServicesOpenAIUser
]
resource searchFoundryRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleId in searchFoundryRoleIds: if (isCosmos) {
    name: guid(aiFoundryAccountResource.id, searchServiceResource.id, roleId)
    scope: aiFoundryAccountResource
    properties: {
      principalId: searchServiceResource!.identity.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleId)
      principalType: 'ServicePrincipal'
    }
    dependsOn: [
      aiProject
      aiSearch
    ]
  }
]

// ----- UAMI -> Cosmos DB (data-plane SQL role, cosmosdb mode) -----
resource cosmosAccountResource 'Microsoft.DocumentDB/databaseAccounts@2025-10-15' existing = if (isCosmos) {
  name: cosmosDbName
}

resource cosmosDataContributorRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2025-10-15' existing = if (isCosmos) {
  parent: cosmosAccountResource
  name: cosmosDataContributorRoleId
}

resource uamiCosmosSqlRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2025-10-15' = if (isCosmos) {
  parent: cosmosAccountResource
  name: guid(cosmosDbName, uamiResource.id, cosmosDataContributorRoleId)
  properties: {
    principalId: uamiResource.properties.principalId
    roleDefinitionId: cosmosDataContributorRoleDefinition.id
    scope: cosmosAccountResource.id
  }
  dependsOn: [
    cosmosDb
    userAssignedIdentity
  ]
}

// ----- Deploying user (Bicep-only convenience roles for post-provision) -----
var deployerFoundryRoleIds = [
  roleIds.cognitiveServicesUser
  roleIds.azureAiUser
]
resource deployerFoundryRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleId in deployerFoundryRoleIds: {
    name: guid(aiFoundryAccountResource.id, deployingUserPrincipalId, roleId)
    scope: aiFoundryAccountResource
    properties: {
      principalId: deployingUserPrincipalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleId)
      principalType: deployingUserPrincipalType
    }
    dependsOn: [
      aiProject
    ]
  }
]

var deployerSearchRoleIds = [
  roleIds.searchIndexDataContributor
  roleIds.searchServiceContributor
]
resource deployerSearchRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleId in deployerSearchRoleIds: if (isCosmos) {
    name: guid(searchServiceResource.id, deployingUserPrincipalId, roleId)
    scope: searchServiceResource
    properties: {
      principalId: deployingUserPrincipalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleId)
      principalType: deployingUserPrincipalType
    }
    dependsOn: [
      aiSearch
    ]
  }
]

resource deployerStorageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountResource.id, deployingUserPrincipalId, roleIds.storageBlobDataContributor)
  scope: storageAccountResource
  properties: {
    principalId: deployingUserPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.storageBlobDataContributor)
    principalType: deployingUserPrincipalType
  }
  dependsOn: [
    storageAccount
  ]
}

// ===================== //
// Outputs               //
// ===================== //

@description('Lower-cased solution suffix used in every downstream resource name.')
output AZURE_SOLUTION_SUFFIX string = solutionSuffix

@description('Resource group containing the deployment.')
output AZURE_RESOURCE_GROUP string = resourceGroup().name

@description('Deployment location for non-AI resources.')
output AZURE_LOCATION string = location

@description('Deployment location for AI Services / Foundry.')
output AZURE_AI_SERVICE_LOCATION string = azureAiServiceLocation

@description('Tenant ID of the deployment.')
output AZURE_TENANT_ID string = subscription().tenantId

@description('Client ID of the user-assigned managed identity.')
output AZURE_UAMI_CLIENT_ID string = userAssignedIdentity.outputs.clientId

@description('Principal ID of the user-assigned managed identity.')
output AZURE_UAMI_PRINCIPAL_ID string = userAssignedIdentity.outputs.principalId

@description('Resource ID of the user-assigned managed identity.')
output AZURE_UAMI_RESOURCE_ID string = userAssignedIdentity.outputs.resourceId

@description('Selected database backend.')
output AZURE_DB_TYPE string = databaseType

@description('Vector index store implementation.')
output AZURE_INDEX_STORE string = indexStoreValue

@description('AI Services endpoint.')
output AZURE_AI_SERVICES_ENDPOINT string = aiProject.outputs.endpoint

@description('Azure OpenAI endpoint.')
output AZURE_OPENAI_ENDPOINT string = aiProject.outputs.endpoint

@description('AI Foundry project endpoint.')
output AZURE_AI_PROJECT_ENDPOINT string = aiProject.outputs.projectEndpoint

@description('Azure OpenAI API version.')
output AZURE_OPENAI_API_VERSION string = azureOpenAiApiVersion

@description('Azure AI Agent API version.')
output AZURE_AI_AGENT_API_VERSION string = azureAiAgentApiVersion

@description('Primary chat model deployment name.')
output AZURE_OPENAI_GPT_DEPLOYMENT string = gptModelName

@description('Reasoning model deployment name.')
output AZURE_OPENAI_REASONING_DEPLOYMENT string = reasoningModelName

@description('Embedding model deployment name.')
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = embeddingModelName

@description('Speech service account name.')
output AZURE_SPEECH_SERVICE_NAME string = speechService.outputs.name

@description('Speech service region.')
output AZURE_SPEECH_SERVICE_REGION string = azureAiServiceLocation

@description('Speech service account resource ID.')
output AZURE_SPEECH_ACCOUNT_RESOURCE_ID string = speechService.outputs.resourceId

@description('Content Safety endpoint.')
output AZURE_CONTENT_SAFETY_ENDPOINT string = contentSafety.outputs.endpoint

@description('Content Safety account name.')
output AZURE_CONTENT_SAFETY_NAME string = contentSafety.outputs.name

@description('AI Search endpoint (cosmosdb mode only).')
output AZURE_AI_SEARCH_ENDPOINT string = isCosmos ? aiSearch!.outputs.endpoint : ''

@description('AI Search service name (cosmosdb mode only).')
output AZURE_AI_SEARCH_NAME string = isCosmos ? aiSearch!.outputs.name : ''

@description('Cosmos DB endpoint (cosmosdb mode only).')
output AZURE_COSMOS_ENDPOINT string = isCosmos ? cosmosDb!.outputs.endpoint : ''

@description('Cosmos DB account name (cosmosdb mode only).')
output AZURE_COSMOS_ACCOUNT_NAME string = isCosmos ? cosmosDb!.outputs.name : ''

@description('PostgreSQL server FQDN (postgresql mode only).')
output AZURE_POSTGRES_HOST string = databaseType == 'postgresql' ? postgresServer!.outputs.serverFqdn : ''

@description('PostgreSQL libpq URI (postgresql mode only).')
output AZURE_POSTGRES_ENDPOINT string = postgresLibpqUri

@description('PostgreSQL server name (postgresql mode only).')
output AZURE_POSTGRES_NAME string = databaseType == 'postgresql' ? postgresServer!.outputs.name : ''

@description('PostgreSQL admin principal name (postgresql mode only).')
output AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME string = databaseType == 'postgresql' ? userAssignedIdentity.outputs.name : ''

@description('PostgreSQL deploying-user principal name (postgresql mode only).')
output AZURE_POSTGRES_DEPLOYER_PRINCIPAL_NAME string = databaseType == 'postgresql' && contains(deployer(), 'userPrincipalName') ? deployer().userPrincipalName : ''

@description('Storage account name.')
output AZURE_STORAGE_ACCOUNT_NAME string = storageAccount.outputs.name

@description('Storage blob endpoint.')
output AZURE_STORAGE_BLOB_ENDPOINT string = storageAccount.outputs.blobEndpoint

@description('Documents blob container name.')
output AZURE_DOCUMENTS_CONTAINER string = documentsContainerName

@description('Document-processing queue name.')
output AZURE_DOC_PROCESSING_QUEUE string = docProcessingQueueName

@description('Ingestion trigger mode.')
output AZURE_INGESTION_TRIGGER string = ingestionTrigger

@description('Backend Container App URL.')
output AZURE_BACKEND_URL string = 'https://${backendContainerApp.outputs.fqdn}'

@description('Frontend Container App URL.')
output AZURE_FRONTEND_URL string = 'https://${frontendContainerApp.outputs.fqdn}'

@description('Function App URL.')
output AZURE_FUNCTION_APP_URL string = 'https://${functionApp.outputs.defaultHostName}'

@description('Function App name.')
output AZURE_FUNCTION_APP_NAME string = functionApp.outputs.name

@description('Container registry login server.')
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer

@description('Container registry name.')
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.name

@description('Application Insights connection string (empty when monitoring disabled).')
output AZURE_APP_INSIGHTS_CONNECTION_STRING string = appInsightsConnectionString
