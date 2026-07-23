// ============================================================================
// main.bicep — Orchestrator
// Description: Pure orchestrator for Chat With Your Data V2.
//              All resource names are derived from params — no hardcoded names.
//              This file only calls modules; no inline resource definitions.
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

@description('Required. Azure region for non-AI resources (Container Apps, App Service, Functions, Storage, Cosmos/Postgres). Restricted to the 4 regions where ALL three redundancy guarantees hold simultaneously: PostgreSQL Flexible Server ZoneRedundant HA (3 AZs), Cosmos DB automatic failover with paired-region replicas, and Storage GZRS. Independent of azureAiServiceLocation, which selects the model-availability region. Source: https://learn.microsoft.com/azure/reliability/regions-list and https://learn.microsoft.com/azure/postgresql/flexible-server/overview#azure-regions')
param location string

@description('Required. Region for AI Services / Foundry deployments. Restricted to regions with GPT-5.1 GlobalStandard availability.')
param azureAiServiceLocation string

// ============================================================================
// Parameters — Database & Ingestion
// ============================================================================

@description('Required. Selects BOTH the chat-history backend AND the vector index store. CosmosDB: Cosmos DB + Azure AI Search. PostgreSQL: PostgreSQL Flexible Server with pgvector (Azure AI Search is NOT deployed). Locked at deploy time.')
param databaseType string = 'cosmosdb'

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

@description('Optional. Deploy Application Insights and wire diagnostics. Log Analytics is always deployed because the Container Apps Environment requires it.')
param enableMonitoring bool = false

// ============================================================================
// Parameters — Existing Resources
// ============================================================================

@description('Optional. Resource ID of an existing Log Analytics workspace. Empty creates a new one.')
param existingLogAnalyticsWorkspaceId string = ''

@description('Optional. Resource ID of an existing AI Foundry project. Empty creates a new one.')
param existingFoundryProjectResourceId string = ''

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
var sampleContainerImage = 'mcr.microsoft.com/k8se/quickstart:latest'

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

// ----- Deterministic resource names (mirror each module's naming rule) -----
var useExistingAIProject = !empty(existingFoundryProjectResourceId)
var aiFoundrySubscriptionId = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[2] : subscription().subscriptionId
var aiFoundryResourceGroupName = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[4] : resourceGroup().name
var aiFoundryResourceName = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[8] : 'aif-${solutionSuffix}'
var aiProjectResourceName = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[10] : ''

var aiSearchName = 'srch-${solutionSuffix}'
var storageName = take('st${solutionSuffix}', 24)
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

module existingAIProject './modules/ai/existing-project-setup.bicep' = if (useExistingAIProject) {
  name: take('module.existing-project-setup.${solutionName}', 64)
  scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
  params: {
    name: aiFoundryResourceName
    projectName: aiProjectResourceName
  }
}

module aiProject './modules/ai/ai-foundry-project.bicep' = if (!useExistingAIProject) {
  name: take('module.ai-foundry-project.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: azureAiServiceLocation
    tags: allTags
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

var aiFoundryEndpoint = useExistingAIProject ? existingAIProject!.outputs.endpoint : aiProject!.outputs.endpoint
var projectEndpoint = useExistingAIProject ? existingAIProject!.outputs.projectEndpoint : aiProject!.outputs.projectEndpoint
var foundryProjectName = useExistingAIProject ? existingAIProject!.outputs.projectName : aiProject!.outputs.projectName

// Model deployments — serial (@batchSize(1)) to avoid Cognitive Services
// deployment throttling, since the native module owns a single deployment each.
@batchSize(1)
module aiModelDeployments './modules/ai/ai-foundry-model-deployment.bicep' = [
  for deployment in defaultOpenAiDeployments: {
    name: take('module.model-deployment.${deployment.name}.${solutionSuffix}', 64)
    scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
    params: {
      aiServicesAccountName: aiFoundryResourceName
      deploymentName: deployment.name
      modelFormat: deployment.model.format
      modelName: deployment.model.name
      modelVersion: deployment.model.version
      raiPolicyName: deployment.raiPolicyName
      skuName: deployment.sku.name
      skuCapacity: deployment.sku.capacity
    }
    dependsOn: [
      aiProject
      existingAIProject
    ]
  }
]

module speechService './modules/ai/ai-services.bicep' = {
  name: take('module.ai-services.SpeechServices.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    namePrefix: 'spch'
    location: azureAiServiceLocation
    tags: allTags
    kind: 'SpeechServices'
    customSubDomainName: 'spch${uniqueString(resourceGroup().id, solutionSuffix, 'SpeechServices')}'
  }
}

module contentSafety './modules/ai/ai-services.bicep' = {
  name: take('module.ai-services.ContentSafety.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    namePrefix: 'cs'
    location: azureAiServiceLocation
    tags: allTags
    kind: 'ContentSafety'
    customSubDomainName: 'cs${uniqueString(resourceGroup().id, solutionSuffix, 'ContentSafety')}'
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
  }
}

module aiProjectSearchConnection './modules/ai/ai-foundry-connection.bicep' = if (isCosmos) {
  name: take('module.foundry-search-conn.${solutionName}', 64)
  scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
  params: {
    solutionName: solutionSuffix
    aiServicesAccountName: aiFoundryResourceName
    projectName: foundryProjectName
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
// allowSharedKeyAccess=false: all access is identity-based (managed identity).
// The Function App host authenticates to AzureWebJobsStorage and the Event Grid
// system topic delivers to the queue via managed identity (no account keys).
// ============================================================================

module storageAccount './modules/data/storage-account.bicep' = {
  name: take('module.storage-account.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    allowSharedKeyAccess: false
    containers: [
      { name: documentsContainerName, publicAccess: 'None' }
      { name: 'config', publicAccess: 'None' }
      { name: 'deployment-package', publicAccess: 'None' }
    ]
    queues: storageQueueNames
  }
}

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
// Provisions the ACR and grants AcrPull to the shared managed identity (used by
// both the frontend App Service and the backend Container Instance). Application
// images are built and pushed to this ACR by a post-deployment step.
module containerRegistry './modules/compute/container-registry.bicep' = {
  name: take('module.container-registry.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    sku: 'Basic'
    identity: {
      type: 'SystemAssigned, UserAssigned'
      userAssignedIdentities: {
        '${userAssignedIdentity.outputs.resourceId}': {}
      }
    }
    acrPullPrincipalIds: [
      userAssignedIdentity.outputs.principalId
    ]
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
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: userAssignedIdentity.outputs.resourceId
      }
    ]
    workloadProfileName: 'Consumption'
    ingressTargetPort: 8000
    scaleSettings: {
      minReplicas: 1
      maxReplicas: 3
    }
    containers: [
      {
        name: 'backend'
        image: sampleContainerImage
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: concat(
          [
            { name: 'AZURE_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
            { name: 'AZURE_UAMI_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
            { name: 'AZURE_TENANT_ID', value: subscription().tenantId }
            { name: 'AZURE_ENVIRONMENT', value: 'production' }
            { name: 'AZURE_AI_PROJECT_ENDPOINT', value: projectEndpoint }
            { name: 'AZURE_OPENAI_ENDPOINT', value: aiFoundryEndpoint }
            { name: 'AZURE_AI_SERVICES_ENDPOINT', value: aiFoundryEndpoint }
            { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
            { name: 'AZURE_AI_AGENT_API_VERSION', value: azureAiAgentApiVersion }
            { name: 'AZURE_OPENAI_GPT_DEPLOYMENT', value: gptModelName }
            { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
            { name: 'AZURE_DB_TYPE', value: databaseType }
            { name: 'AZURE_INDEX_STORE', value: indexStoreValue }
            { name: 'AZURE_COSMOS_ENDPOINT', value: isCosmos ? cosmosDb!.outputs.endpoint : '' }
            { name: 'AZURE_AI_SEARCH_ENDPOINT', value: isCosmos ? aiSearch!.outputs.endpoint : '' }
            { name: 'AZURE_AI_SEARCH_INDEX', value: isCosmos ? searchIndexName : '' }
            { name: 'AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME', value: searchKnowledgeBaseName }
            { name: 'AZURE_AI_SEARCH_KNOWLEDGE_SOURCE_NAME', value: searchKnowledgeSourceName }
            { name: 'AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION', value: searchKnowledgeBaseApiVersion }
            { name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: isCosmos ? aiProjectSearchConnection!.outputs.connectionName : '' }
            { name: 'AZURE_POSTGRES_ENDPOINT', value: postgresLibpqUri }
            { name: 'AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME', value: !isCosmos ? userAssignedIdentity.outputs.name : '' }
            { name: 'AZURE_SPEECH_SERVICE_NAME', value: speechService.outputs.name }
            { name: 'AZURE_SPEECH_SERVICE_REGION', value: azureAiServiceLocation }
            { name: 'AZURE_SPEECH_ACCOUNT_RESOURCE_ID', value: speechService.outputs.resourceId }
            { name: 'AZURE_CONTENT_SAFETY_ENABLED', value: 'true' }
            { name: 'AZURE_CONTENT_SAFETY_ENDPOINT', value: contentSafety.outputs.endpoint }
            { name: 'CWYD_ORCHESTRATOR_NAME', value: databaseType == 'postgresql' ? 'langgraph' : 'agent_framework' }
            { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storageAccount.outputs.name }
            { name: 'AZURE_DOCUMENTS_CONTAINER', value: documentsContainerName }
            { name: 'AZURE_DOC_PROCESSING_QUEUE', value: docProcessingQueueName }
            { name: 'AZURE_INGESTION_TRIGGER', value: ingestionTrigger }
          ],
          enableMonitoring
            ? [ { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString } ]
            : []
        )
      }
    ]
  }
}

// ========== Frontend Container App ========== //
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
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: userAssignedIdentity.outputs.resourceId
      }
    ]
    workloadProfileName: 'Consumption'
    ingressTargetPort: 80
    scaleSettings: {
      minReplicas: 1
      maxReplicas: 3
    }
    containers: [
      {
        name: 'frontend'
        image: sampleContainerImage
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: concat(
          [
            { name: 'VITE_BACKEND_URL', value: 'https://${backendContainerApp.outputs.fqdn}' }
            { name: 'BACKEND_API_URL', value: 'https://${backendContainerApp.outputs.fqdn}' }
          ],
          enableMonitoring
            ? [ { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString } ]
            : []
        )
      }
    ]
  }
}

// ========== Function Container App ========== //
module functionContainerApp './modules/compute/container-app.bicep' = {
  name: take('module.container-app-function.${solutionName}', 64)
  params: {
    name: 'ca-function-${solutionSuffix}'
    location: location
    tags: union(allTags, { 'azd-service-name': 'function' })
    kind: 'functionapp'
    environmentResourceId: containerAppsEnv.outputs.resourceId
    identity: {
      type: 'SystemAssigned, UserAssigned'
      userAssignedIdentities: {
        '${userAssignedIdentity.outputs.resourceId}': {}
      }
    }
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: userAssignedIdentity.outputs.resourceId
      }
    ]
    workloadProfileName: 'Consumption'
    ingressTargetPort: 80
    scaleSettings: {
      minReplicas: 1
      maxReplicas: 3
    }
    containers: [
      {
        name: 'function'
        image: sampleContainerImage
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: concat(
          [
            { name: 'AzureWebJobsStorage__accountName', value: storageAccount.outputs.name }
            { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
            { name: 'AzureWebJobsStorage__clientId', value: userAssignedIdentity.outputs.clientId }
            { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false' }
            { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
            { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
            { name: 'AZURE_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
            { name: 'AZURE_UAMI_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
            { name: 'AZURE_TENANT_ID', value: subscription().tenantId }
            { name: 'AZURE_ENVIRONMENT', value: 'production' }
            { name: 'AZURE_AI_PROJECT_ENDPOINT', value: projectEndpoint }
            { name: 'AZURE_OPENAI_ENDPOINT', value: aiFoundryEndpoint }
            { name: 'AZURE_AI_SERVICES_ENDPOINT', value: aiFoundryEndpoint }
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
      }
    ]
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
  }
}

// ============================================================================
// Role Assignments (centralized in modules/identity/role-assignments.bicep).
// main.bicep builds typed arrays of { principalId, principalType, roleDefinitionId }
// and the module loops them, scoping each assignment to its target resource.
// Mirrors the avm flavor's array-driven role-assignments module.
// ============================================================================

var foundryAccountPrincipalId = useExistingAIProject ? existingAIProject!.outputs.principalId : aiProject!.outputs.principalId
var foundryProjectPrincipalId = useExistingAIProject ? existingAIProject!.outputs.projectIdentityPrincipalId : aiProject!.outputs.projectIdentityPrincipalId

// Role-assignment definitions (roleIds map + who-gets-what arrays) live in
// ./modules/identity/role-assignments.bicep; main.bicep only supplies principals.
module roleAssignments './modules/identity/role-assignments.bicep' = {
  name: take('module.role-assignments.${solutionName}', 64)
  params: {
    isCosmos: isCosmos
    aiFoundryName: aiFoundryResourceName
    speechServiceName: speechService.outputs.name
    contentSafetyServiceName: contentSafety.outputs.name
    storageName: storageName
    aiSearchName: aiSearchName
    cosmosDbName: cosmosDbName
    useExistingAIProject: useExistingAIProject
    aiFoundrySubscriptionId: aiFoundrySubscriptionId
    aiFoundryResourceGroupName: aiFoundryResourceGroupName
    uamiPrincipalId: userAssignedIdentity.outputs.principalId
    foundryAccountPrincipalId: foundryAccountPrincipalId
    foundryProjectPrincipalId: foundryProjectPrincipalId
    functionPrincipalId: functionContainerApp.outputs.principalId
    searchPrincipalId: isCosmos ? aiSearch!.outputs.identityPrincipalId : ''
    eventGridPrincipalId: eventGridSystemTopic.outputs.systemAssignedMIPrincipalId
    deployingUserPrincipalId: deployingUserPrincipalId
    deployingUserPrincipalType: deployingUserPrincipalType
  }
}

// ========== Event Grid subscriptions (depends on roleAssignments so the     ========== //
// ========== Storage Queue Data Message Sender role has time to propagate)   ========== //
module eventGridSubscriptions './modules/data/event-grid-subscription.bicep' = {
  name: take('module.event-grid-subs.${solutionName}', 64)
  params: {
    systemTopicName: eventGridSystemTopic.outputs.name
    eventSubscriptions: [
      {
        name: 'blob-created-to-doc-processing'
        deliveryWithResourceIdentity: {
          identity: {
            type: 'SystemAssigned'
          }
          destination: {
            endpointType: 'StorageQueue'
            properties: {
              resourceId: storageAccount.outputs.resourceId
              queueName: blobEventsQueueName
              queueMessageTimeToLiveInSeconds: 86400
            }
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
    roleAssignments
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
output AZURE_AI_SERVICES_ENDPOINT string = aiFoundryEndpoint

@description('Azure OpenAI endpoint.')
output AZURE_OPENAI_ENDPOINT string = aiFoundryEndpoint

@description('AI Foundry project endpoint.')
output AZURE_AI_PROJECT_ENDPOINT string = projectEndpoint

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

@description('Chat index name. Exported so the postdeploy seed hook can run its index-population self-check; empty in postgresql mode (no AI Search).')
output AZURE_AI_SEARCH_INDEX string = databaseType == 'cosmosdb' ? searchIndexName : ''

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

@description('Function Container App URL.')
output AZURE_FUNCTION_APP_URL string = 'https://${functionContainerApp.outputs.fqdn}'

@description('Function Container App name.')
output AZURE_FUNCTION_APP_NAME string = functionContainerApp.outputs.name

@description('Container Registry login server.')
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer

@description('Container Registry resource name.')
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.name

@description('Application Insights connection string (empty when monitoring disabled).')
output AZURE_APP_INSIGHTS_CONNECTION_STRING string = appInsightsConnectionString
