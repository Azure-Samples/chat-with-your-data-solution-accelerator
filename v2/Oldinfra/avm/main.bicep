// ============================================================================
// main.bicep — Orchestrator
// Description: Pure orchestrator for Agentic Applications for UDF
//              All resource names are derived from params — no hardcoded names.
//              This file only calls modules; no inline resource definitions.
//              Supports WAF-aligned deployment via feature flags.
// ============================================================================
targetScope = 'resourceGroup'

// ============================================================================
// Parameters — Core
// ============================================================================

@description('Optional. A unique application/solution name for all resources in this deployment. This should be 3-16 characters long.')
@minLength(3)
@maxLength(16)
param solutionName string = 'cwyd'

@maxLength(5)
@description('Optional. A unique text value for the solution. This is used to ensure resource names are unique for global resources. Defaults to a 5-character substring of the unique string generated from the subscription ID, resource group name, and solution name.')
param solutionUniqueText string = take(uniqueString(subscription().id, resourceGroup().name, solutionName), 5)

@allowed([
  'australiaeast'
  'eastus2'
  'japaneast'
  'uksouth'
])
@metadata({ azd: { type: 'location' } })
@description('Required. Azure region for all services. Regions are restricted to guarantee compatibility with paired regions and replica locations for data redundancy and failover scenarios based on articles [Azure regions list](https://learn.microsoft.com/azure/reliability/regions-list) and [Azure Database for PostgreSQL Flexible Server - Azure Regions](https://learn.microsoft.com/azure/postgresql/flexible-server/overview#azure-regions). Note: In the "Deploy to Azure" interface, you will see both "Region" and "Location" fields - "Region" is only for deployment metadata while "Location" (this parameter) determines where your actual resources are deployed.')
param location string

@description('Optional. Existing Log Analytics Workspace Resource ID.')
param existingLogAnalyticsWorkspaceId string = ''

var solutionSuffix = toLower(trim(replace(
  replace(
    replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''),
    ' ',
    ''
  ),
  '*',
  ''
)))

@description('Optional. The pricing tier for the App Service plan.')
@allowed([
  'B2'
  'B3'
  'S2'
  'S3'
])
param hostingPlanSku string = 'B3'

@description('Optional. The type of database to deploy (cosmos or postgres).')
@allowed([
  'PostgreSQL'
  'CosmosDB'
])
param databaseType string = 'PostgreSQL'

@description('Azure Cosmos DB Account Name.')
var azureCosmosDBAccountName string = 'cosmos-${solutionSuffix}'

@description('Name of Web App.')
var websiteName string = 'app-${solutionSuffix}'

@description('Name of Admin Web App.')
var adminWebsiteName string = '${websiteName}-admin'

@description('Name of Application Insights.')
var applicationInsightsName string = 'appi-${solutionSuffix}'

@description('Name of the Workbook.')
var workbookDisplayName string = 'workbook-${solutionSuffix}'

@description('Optional. Use semantic search.')
param azureSearchUseSemanticSearch bool = false

@description('Optional. Semantic search config.')
param azureSearchSemanticSearchConfig string = 'default'

@description('Optional. Is the index prechunked.')
param azureSearchIndexIsPrechunked string = 'false'

@description('Optional. Top K results.')
param azureSearchTopK string = '5'

@description('Optional. Enable in domain.')
param azureSearchEnableInDomain string = 'true'

@description('Optional. Id columns.')
param azureSearchFieldId string = 'id'

@description('Optional. Content columns.')
param azureSearchContentColumn string = 'content'

@description('Optional. Vector columns.')
param azureSearchVectorColumn string = 'content_vector'

@description('Optional. Filename column.')
param azureSearchFilenameColumn string = 'filename'

@description('Optional. Search filter.')
param azureSearchFilter string = ''

@description('Optional. Title column.')
param azureSearchTitleColumn string = 'title'

@description('Optional. Metadata column.')
param azureSearchFieldsMetadata string = 'metadata'

@description('Optional. Source column.')
param azureSearchSourceColumn string = 'source'

@description('Optional. Text column.')
param azureSearchTextColumn string = 'text'

@description('Optional. Layout Text column.')
param azureSearchLayoutTextColumn string = 'layoutText'

@description('Optional. Chunk column.')
param azureSearchChunkColumn string = 'chunk'

@description('Optional. Offset column.')
param azureSearchOffsetColumn string = 'offset'

@description('Optional. Url column.')
param azureSearchUrlColumn string = 'url'

@description('Optional. Whether to use Azure Search Integrated Vectorization. If the database type is PostgreSQL, set this to false.')
param azureSearchUseIntegratedVectorization bool = false

// ============================================================================
// Parameters — Azure OpenAI Configuration
// ============================================================================

@description('Optional. Name of Azure OpenAI Resource.')
var azureOpenAIResourceName string = 'oai-${solutionSuffix}'

@description('Optional. Name of Azure OpenAI Resource SKU.')
param azureOpenAISkuName string = 'S0'

@description('Optional. Azure OpenAI Model Deployment Name.')
param azureOpenAIModel string = 'gpt-4.1'

@description('Optional. Azure OpenAI Model Name.')
param azureOpenAIModelName string = 'gpt-4.1'

@description('Optional. Azure OpenAI Model Version.')
param azureOpenAIModelVersion string = '2025-04-14'

@description('Optional. Azure OpenAI Model Capacity - See here for more info  https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/quota.')
param azureOpenAIModelCapacity int = 150

@description('Optional. Whether to enable the use of a vision LLM and Computer Vision for embedding images. If the database type is PostgreSQL, set this to false.')
param useAdvancedImageProcessing bool = false

@description('Optional. The maximum number of images to pass to the vision model in a single request.')
param advancedImageProcessingMaxImages int = 1

@description('Optional. Orchestration strategy: openai_function or semantic_kernel or langchain str. If you use a old version of turbo (0301), please select langchain. If the database type is PostgreSQL, set this to sementic_kernel.')
@allowed([
  'openai_function'
  'semantic_kernel'
  'langchain'
])
param orchestrationStrategy string = 'semantic_kernel'

@description('Optional. Chat conversation type: custom or byod. If the database type is PostgreSQL, set this to custom.')
@allowed([
  'custom'
  'byod'
])
param conversationFlow string = 'custom'

@description('Optional. Azure OpenAI Temperature.')
param azureOpenAITemperature string = '0'

@description('Optional. Azure OpenAI Top P.')
param azureOpenAITopP string = '1'

@description('Optional. Azure OpenAI Max Tokens.')
param azureOpenAIMaxTokens string = '1000'

@description('Optional. Azure OpenAI Stop Sequence.')
param azureOpenAIStopSequence string = '\\n'

@description('Optional. Azure OpenAI System Message.')
param azureOpenAISystemMessage string = 'You are an AI assistant that helps people find information.'

// ============================================================================
// Parameters — Orchestration and Conversation Flow
// ============================================================================

@description('Optional. Azure OpenAI Api Version.')
param azureOpenAIApiVersion string = '2024-02-01'

@description('Optional. Whether or not to stream responses from Azure OpenAI.')
param azureOpenAIStream string = 'true'

@description('Optional. Azure OpenAI Embedding Model Deployment Name.')
param azureOpenAIEmbeddingModel string = 'text-embedding-3-small'

@description('Optional. Azure OpenAI Embedding Model Name.')
param azureOpenAIEmbeddingModelName string = 'text-embedding-3-small'

@description('Optional. Azure OpenAI Embedding Model Version.')
param azureOpenAIEmbeddingModelVersion string = '1'

@description('Optional. Azure OpenAI Embedding Model Capacity - See here for more info https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/quota .')
param azureOpenAIEmbeddingModelCapacity int = 100

// ============================================================================
// Parameters — Azure AI Search Configuration
// ============================================================================

@description('Optional. Azure Search vector field dimensions. Must match the embedding model dimensions. 1536 for text-embedding-3-small, 3072 for text-embedding-3-large. See https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-azure-openai-embedding#supported-dimensions-by-modelname.(Only for databaseType=CosmosDB)')
param azureSearchDimensions string = '1536'

// ============================================================================
// Parameters — Advanced Image Processing
// ============================================================================

@description('Optional. Name of Computer Vision Resource (if useAdvancedImageProcessing=true).')
var computerVisionName string = 'cv-${solutionSuffix}'

@description('Optional. Name of Computer Vision Resource SKU (if useAdvancedImageProcessing=true).')
@allowed([
  'F0'
  'S1'
])
param computerVisionSkuName string = 'S1'

@description('Optional. Location of Computer Vision Resource (if useAdvancedImageProcessing=true).')
@allowed([
  // List taken from https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/how-to/image-retrieval?tabs=python#prerequisites
  'eastus'
  'westus'
  'koreacentral'
  'francecentral'
  'northeurope'
  'westeurope'
  'southeastasia'
  ''
])
param computerVisionLocation string = ''

@description('Optional. Azure Computer Vision Vectorize Image API Version.')
param computerVisionVectorizeImageApiVersion string = '2024-02-01'

@description('Optional. Azure Computer Vision Vectorize Image Model Version.')
param computerVisionVectorizeImageModelVersion string = '2023-04-15'

@description('Azure AI Search Resource.')
var azureAISearchName string = 'srch-${solutionSuffix}'

@description('Optional. The SKU of the search service you want to create. E.g. free or standard.')
@allowed([
  'free'
  'basic'
  'standard'
  'standard2'
  'standard3'
])
param azureSearchSku string = 'standard'

@description('Azure AI Search Index.')
var azureSearchIndex string = 'index-${solutionSuffix}'

@description('Azure AI Search Indexer.')
var azureSearchIndexer string = 'indexer-${solutionSuffix}'

@description('Azure AI Search Datasource.')
var azureSearchDatasource string = 'datasource-${solutionSuffix}'

@description('Optional. Azure AI Search Conversation Log Index.')
param azureSearchConversationLogIndex string = 'conversations'

@description('Name of Storage Account.')
var storageAccountName string = 'st${solutionSuffix}'

@description('Name of Function App for Batch document processing.')
var functionName string = 'func-${solutionSuffix}'

// ============================================================================
// Parameters — Identity and Deployment Metadata
// ============================================================================

@description('Optional. A new GUID string generated for this deployment. This can be used for unique naming if needed.')
param newGuidString string = newGuid()

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
// Parameters — App Hosting and Runtime Settings
// ============================================================================

@description('Optional. Application Environment.')
param appEnvironment string = 'Prod'

@description('Optional. Hosting model for the web apps. This value is fixed as "container", which uses prebuilt containers for faster deployment.')
param hostingModel string = 'container'

@description('Optional. The log level for application logging. This setting controls the verbosity of logs emitted by the application. Allowed values are CRITICAL, ERROR, WARN, INFO, and DEBUG. The default value is INFO.')
@allowed([
  'CRITICAL'
  'ERROR'
  'WARN'
  'INFO'
  'DEBUG'
])
param logLevel string = 'INFO'

@description('Optional. List of comma-separated languages to recognize from the speech input. Supported languages are listed here: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=stt#supported-languages.')
param recognizedLanguages string = 'en-US,fr-FR,de-DE,it-IT'

// ============================================================================
// Parameters — Governance and Tagging
// ============================================================================

@description('Optional. The tags to apply to all deployed Azure resources.')
param tags resourceInput<'Microsoft.Resources/resourceGroups@2025-04-01'>.tags = {}

@description('Optional. Enable purge protection for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enablePurgeProtection bool = false

@description('Optional. Enable monitoring applicable resources, aligned with the Well Architected Framework recommendations. This setting enables Application Insights and Log Analytics and configures all the resources applicable resources to send logs. Defaults to false.')
param enableMonitoring bool = false

@description('Optional. Enable scalability for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enableScalability bool = false

@description('Optional. Enable redundancy for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enableRedundancy bool = false

@description('Optional. Enable private networking for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enablePrivateNetworking bool = false

@description('Optional. Size of the Jumpbox Virtual Machine when created. Set to custom value if enablePrivateNetworking is true.')
param vmSize string = 'Standard_D2s_v5'

@description('Optional. The user name for the administrator account of the virtual machine. Allows to customize credentials if `enablePrivateNetworking` is set to true.')
@secure()
param vmAdminUsername string = ''

@description('Optional. The password for the administrator account of the virtual machine. Allows to customize credentials if `enablePrivateNetworking` is set to true.')
@secure()
param vmAdminPassword string = ''

// ============================================================================
// Parameters — WAF / Monitoring / Networking Features
// ============================================================================

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Optional. Image version tag to use.')
param appversion string

var createdBy = contains(deployerInfo, 'userPrincipalName') ? split(deployerInfo.userPrincipalName, '@')[0] : deployerInfo.objectId
var deployerInfo = deployer()
var deployingUserPrincipalId = deployerInfo.objectId
var blobContainerName = 'documents'
var queueName = 'doc-processing'
var clientKey = '${uniqueString(guid(subscription().id, deployment().name))}${newGuidString}'

@description('OpenAI and Semantic Kernel prompt values.')
param openAISystemPrompts object

var registryName = 'cwydcontainerreg' // Update Registry name

var allTags = union(
  {
    'azd-env-name': solutionName
  },
  tags
)

// Tags: merge caller-supplied tags with standard metadata (matching old infra)
var existingTags = resourceGroup().tags ?? {}
var resourceTags = union(existingTags, tags, {
  TemplateName: 'CWYD'
  CreatedBy: createdBy
  DeploymentName: deployment().name
  Type: enablePrivateNetworking ? 'WAF' : 'Non-WAF'
})

// Region pairs list based on article in [Azure Database for MySQL Flexible Server - Azure Regions](https://learn.microsoft.com/azure/mysql/flexible-server/overview#azure-regions) for supported high availability regions for CosmosDB.
var cosmosDbZoneRedundantHaRegionPairs = {
  australiaeast: 'uksouth'
  centralus: 'eastus2'
  eastasia: 'southeastasia'
  eastus: 'centralus'
  eastus2: 'centralus'
  japaneast: 'australiaeast'
  northeurope: 'westeurope'
  southeastasia: 'eastasia'
  uksouth: 'westeurope'
  westeurope: 'northeurope'
}
// Paired location calculated based on 'location' parameter. This location will be used by applicable resources if `enableScalability` is set to `true`
var cosmosDbHaLocation = cosmosDbZoneRedundantHaRegionPairs[location]

// Replica regions list based on article in [Azure regions list](https://learn.microsoft.com/azure/reliability/regions-list) and [Enhance resilience by replicating your Log Analytics workspace across regions](https://learn.microsoft.com/azure/azure-monitor/logs/workspace-replication#supported-regions) for supported regions for Log Analytics Workspace.
var replicaRegionPairs = {
  australiaeast: 'australiasoutheast'
  centralus: 'westus'
  eastasia: 'japaneast'
  eastus: 'centralus'
  eastus2: 'centralus'
  japaneast: 'eastasia'
  northeurope: 'westeurope'
  southeastasia: 'eastasia'
  uksouth: 'westeurope'
  westeurope: 'northeurope'
}
var replicaLocation = replicaRegionPairs[location]

// WAF: Diagnostic settings helper — reused across modules
var monitoringDiagnosticSettings = enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : []

// WAF: Private DNS zones for private endpoints
var privateDnsZones = [
  'privatelink.documents.azure.com'
  'privatelink.postgres.database.azure.com'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.queue.${environment().suffixes.storage}'
  'privatelink.file.${environment().suffixes.storage}'
  'privatelink.search.windows.net'
  'privatelink.cognitiveservices.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.vaultcore.azure.net'
  'privatelink.table.${environment().suffixes.storage}'
]

var dnsZoneIndex = {
  cosmosDB: 0
  postgresDB: 1
  storageBlob: 2
  storageQueue: 3
  storageFile: 4
  searchService: 5
  cognitiveServices: 6
  openAI: 7
  keyVault: 8
  storageTable: 9
}

var defaultOpenAiDeployments = [
  {
    name: azureOpenAIModel
    model: {
      format: 'OpenAI'
      name: azureOpenAIModelName
      version: azureOpenAIModelVersion
    }
    sku: {
      name: 'GlobalStandard'
      capacity: azureOpenAIModelCapacity
    }
  }
  {
    name: azureOpenAIEmbeddingModel
    model: {
      format: 'OpenAI'
      name: azureOpenAIEmbeddingModelName
      version: azureOpenAIEmbeddingModelVersion
    }
    sku: {
      name: 'GlobalStandard'
      capacity: azureOpenAIEmbeddingModelCapacity
    }
  }
]

// ============================================================================
// Resource Group Tags (matching old infra)
// ============================================================================

resource resourceGroupTags 'Microsoft.Resources/tags@2025-04-01' = {
  name: 'default'
  properties: {
    tags: resourceTags
  }
}

// ============== //
// Resources      //
// ============== //

// ========== Managed Identity ========== //
module managedIdentityModule './modules/identity/managed-identity.bicep' = {
  name: take('module.managed-identity.user-assigned-identity.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

#disable-next-line no-deployments-resources
resource avmTelemetry 'Microsoft.Resources/deployments@2024-03-01' = if (enableTelemetry) {
  name: '46d3xbcp.ptn.sa-chatwithyourdata.${replace('-..--..-', '.', '-')}.${substring(uniqueString(deployment().name, location), 0, 4)}'
  properties: {
    mode: 'Incremental'
    template: {
      '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#'
      contentVersion: '1.0.0.0'
      resources: []
      outputs: {
        telemetry: {
          type: 'String'
          value: 'For more information, see https://aka.ms/avm/TelemetryInfo'
        }
      }
    }
  }
}

// ============================================================================
// Module: Monitoring
// ============================================================================

var useExistingLogAnalytics = !empty(existingLogAnalyticsWorkspaceId)

// Existing workspace reference (for cross-subscription support)
resource existingLogAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2025-07-01' existing = if (useExistingLogAnalytics) {
  name: split(existingLogAnalyticsWorkspaceId, '/')[8]
  scope: resourceGroup(split(existingLogAnalyticsWorkspaceId, '/')[2], split(existingLogAnalyticsWorkspaceId, '/')[4])
}

module log_analytics './modules/monitoring/log-analytics.bicep' = if (enableMonitoring && !useExistingLogAnalytics) {
  name: take('module.log-analytics.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    publicNetworkAccessForIngestion: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    publicNetworkAccessForQuery: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    enableReplication: enableRedundancy
    replicationLocation: replicaLocation
    dailyQuotaGb: enableRedundancy ? '10' : ''
    dataSources: enablePrivateNetworking
      ? [
          {
            tags: tags
            eventLogName: 'Application'
            eventTypes: [
              {
                eventType: 'Error'
              }
              {
                eventType: 'Warning'
              }
              {
                eventType: 'Information'
              }
            ]
            kind: 'WindowsEvent'
            name: 'applicationEvent'
          }
          {
            counterName: '% Processor Time'
            instanceName: '*'
            intervalSeconds: 60
            kind: 'WindowsPerformanceCounter'
            name: 'windowsPerfCounter1'
            objectName: 'Processor'
          }
          {
            kind: 'IISLogs'
            name: 'sampleIISLog1'
            state: 'OnPremiseEnabled'
          }
        ]
      : null
  }
}

// Resolve workspace resource ID and name — existing or new
var logAnalyticsWorkspaceResourceId = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspace.id
  : (enableMonitoring ? log_analytics!.outputs.resourceId : '')
var logAnalyticsWorkspaceName = useExistingLogAnalytics
  ? split(existingLogAnalyticsWorkspaceId, '/')[8]
  : (enableMonitoring ? log_analytics!.outputs.name : '')

module app_insights './modules/monitoring/app-insights.bicep' = if (enableMonitoring) {
  name: take('module.app-insights.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    workspaceResourceId: logAnalyticsWorkspaceResourceId
  }
}

// Dashboard with pinned Application Insights parts
module applicationInsightsDashboard './modules/monitoring/portal-dashboard.bicep' = if (enableMonitoring) {
  name: take('module.portal-dashboard.${solutionName}', 64)
  params: {
    solutionName: applicationInsightsName
    location: location
    tags: tags
    lenses: [
      {
        order: 0
        parts: [
          {
            position: {
              x: 0
              y: 0
              colSpan: 2
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'id'
                  value: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                }
                {
                  name: 'Version'
                  value: '1.0'
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/AspNetOverviewPinnedPart'
              asset: {
                idInputName: 'id'
                type: 'ApplicationInsights'
              }
              defaultMenuItemId: 'overview'
            }
          }
          {
            position: {
              x: 2
              y: 0
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ComponentId'
                  value: {
                    Name: app_insights!.outputs.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'Version'
                  value: '1.0'
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/ProactiveDetectionAsyncPart'
              asset: {
                idInputName: 'ComponentId'
                type: 'ApplicationInsights'
              }
              defaultMenuItemId: 'ProactiveDetection'
            }
          }
          {
            position: {
              x: 3
              y: 0
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ComponentId'
                  value: {
                    Name: app_insights!.outputs.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'ResourceId'
                  value: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/QuickPulseButtonSmallPart'
              asset: {
                idInputName: 'ComponentId'
                type: 'ApplicationInsights'
              }
            }
          }
          {
            position: {
              x: 4
              y: 0
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ComponentId'
                  value: {
                    Name: app_insights!.outputs.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'TimeContext'
                  value: {
                    durationMs: 86400000
                    endTime: null
                    createdTime: '2018-05-04T01:20:33.345Z'
                    isInitialTime: true
                    grain: 1
                    useDashboardTimeRange: false
                  }
                }
                {
                  name: 'Version'
                  value: '1.0'
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/AvailabilityNavButtonPart'
              asset: {
                idInputName: 'ComponentId'
                type: 'ApplicationInsights'
              }
            }
          }
          {
            position: {
              x: 5
              y: 0
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ComponentId'
                  value: {
                    Name: app_insights!.outputs.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'TimeContext'
                  value: {
                    durationMs: 86400000
                    endTime: null
                    createdTime: '2018-05-08T18:47:35.237Z'
                    isInitialTime: true
                    grain: 1
                    useDashboardTimeRange: false
                  }
                }
                {
                  name: 'ConfigurationId'
                  value: '78ce933e-e864-4b05-a27b-71fd55a6afad'
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/AppMapButtonPart'
              asset: {
                idInputName: 'ComponentId'
                type: 'ApplicationInsights'
              }
            }
          }
          {
            position: {
              x: 0
              y: 1
              colSpan: 3
              rowSpan: 1
            }
            metadata: {
              inputs: []
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  settings: {
                    content: '# Usage'
                    title: ''
                    subtitle: ''
                  }
                }
              }
            }
          }
          {
            position: {
              x: 3
              y: 1
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ComponentId'
                  value: {
                    Name: app_insights!.outputs.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'TimeContext'
                  value: {
                    durationMs: 86400000
                    endTime: null
                    createdTime: '2018-05-04T01:22:35.782Z'
                    isInitialTime: true
                    grain: 1
                    useDashboardTimeRange: false
                  }
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/UsageUsersOverviewPart'
              asset: {
                idInputName: 'ComponentId'
                type: 'ApplicationInsights'
              }
            }
          }
          {
            position: {
              x: 4
              y: 1
              colSpan: 3
              rowSpan: 1
            }
            metadata: {
              inputs: []
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  settings: {
                    content: '# Reliability'
                    title: ''
                    subtitle: ''
                  }
                }
              }
            }
          }
          {
            position: {
              x: 7
              y: 1
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ResourceId'
                  value: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                }
                {
                  name: 'DataModel'
                  value: {
                    version: '1.0.0'
                    timeContext: {
                      durationMs: 86400000
                      createdTime: '2018-05-04T23:42:40.072Z'
                      isInitialTime: false
                      grain: 1
                      useDashboardTimeRange: false
                    }
                  }
                  isOptional: true
                }
                {
                  name: 'ConfigurationId'
                  value: '8a02f7bf-ac0f-40e1-afe9-f0e72cfee77f'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/CuratedBladeFailuresPinnedPart'
              isAdapter: true
              asset: {
                idInputName: 'ResourceId'
                type: 'ApplicationInsights'
              }
              defaultMenuItemId: 'failures'
            }
          }
          {
            position: {
              x: 8
              y: 1
              colSpan: 3
              rowSpan: 1
            }
            metadata: {
              inputs: []
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  settings: {
                    content: '# Responsiveness\r\n'
                    title: ''
                    subtitle: ''
                  }
                }
              }
            }
          }
          {
            position: {
              x: 11
              y: 1
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ResourceId'
                  value: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                }
                {
                  name: 'DataModel'
                  value: {
                    version: '1.0.0'
                    timeContext: {
                      durationMs: 86400000
                      createdTime: '2018-05-04T23:43:37.804Z'
                      isInitialTime: false
                      grain: 1
                      useDashboardTimeRange: false
                    }
                  }
                  isOptional: true
                }
                {
                  name: 'ConfigurationId'
                  value: '2a8ede4f-2bee-4b9c-aed9-2db0e8a01865'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/CuratedBladePerformancePinnedPart'
              isAdapter: true
              asset: {
                idInputName: 'ResourceId'
                type: 'ApplicationInsights'
              }
              defaultMenuItemId: 'performance'
            }
          }
          {
            position: {
              x: 12
              y: 1
              colSpan: 3
              rowSpan: 1
            }
            metadata: {
              inputs: []
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  settings: {
                    content: '# Browser'
                    title: ''
                    subtitle: ''
                  }
                }
              }
            }
          }
          {
            position: {
              x: 15
              y: 1
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ComponentId'
                  value: {
                    Name: app_insights!.outputs.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'MetricsExplorerJsonDefinitionId'
                  value: 'BrowserPerformanceTimelineMetrics'
                }
                {
                  name: 'TimeContext'
                  value: {
                    durationMs: 86400000
                    createdTime: '2018-05-08T12:16:27.534Z'
                    isInitialTime: false
                    grain: 1
                    useDashboardTimeRange: false
                  }
                }
                {
                  name: 'CurrentFilter'
                  value: {
                    eventTypes: [
                      4
                      1
                      3
                      5
                      2
                      6
                      13
                    ]
                    typeFacets: {}
                    isPermissive: false
                  }
                }
                {
                  name: 'id'
                  value: {
                    Name: app_insights!.outputs.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'Version'
                  value: '1.0'
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/MetricsExplorerBladePinnedPart'
              asset: {
                idInputName: 'ComponentId'
                type: 'ApplicationInsights'
              }
              defaultMenuItemId: 'browser'
            }
          }
          {
            position: {
              x: 0
              y: 2
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'sessions/count'
                          aggregationType: 5
                          namespace: 'microsoft.insights/components/kusto'
                          metricVisualization: {
                            displayName: 'Sessions'
                            color: '#47BDF5'
                          }
                        }
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'users/count'
                          aggregationType: 5
                          namespace: 'microsoft.insights/components/kusto'
                          metricVisualization: {
                            displayName: 'Users'
                            color: '#7E58FF'
                          }
                        }
                      ]
                      title: 'Unique sessions and users'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                      openBladeOnClick: {
                        openBlade: true
                        destinationBlade: {
                          extensionName: 'HubsExtension'
                          bladeName: 'ResourceMenuBlade'
                          parameters: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                            menuid: 'segmentationUsers'
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 4
              y: 2
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'requests/failed'
                          aggregationType: 7
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Failed requests'
                            color: '#EC008C'
                          }
                        }
                      ]
                      title: 'Failed requests'
                      visualization: {
                        chartType: 3
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                      openBladeOnClick: {
                        openBlade: true
                        destinationBlade: {
                          extensionName: 'HubsExtension'
                          bladeName: 'ResourceMenuBlade'
                          parameters: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                            menuid: 'failures'
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 8
              y: 2
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'requests/duration'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Server response time'
                            color: '#00BCF2'
                          }
                        }
                      ]
                      title: 'Server response time'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                      openBladeOnClick: {
                        openBlade: true
                        destinationBlade: {
                          extensionName: 'HubsExtension'
                          bladeName: 'ResourceMenuBlade'
                          parameters: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                            menuid: 'performance'
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 12
              y: 2
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'browserTimings/networkDuration'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Page load network connect time'
                            color: '#7E58FF'
                          }
                        }
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'browserTimings/processingDuration'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Client processing time'
                            color: '#44F1C8'
                          }
                        }
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'browserTimings/sendDuration'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Send request time'
                            color: '#EB9371'
                          }
                        }
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'browserTimings/receiveDuration'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Receiving response time'
                            color: '#0672F1'
                          }
                        }
                      ]
                      title: 'Average page load time breakdown'
                      visualization: {
                        chartType: 3
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 0
              y: 5
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'availabilityResults/availabilityPercentage'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Availability'
                            color: '#47BDF5'
                          }
                        }
                      ]
                      title: 'Average availability'
                      visualization: {
                        chartType: 3
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                      openBladeOnClick: {
                        openBlade: true
                        destinationBlade: {
                          extensionName: 'HubsExtension'
                          bladeName: 'ResourceMenuBlade'
                          parameters: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                            menuid: 'availability'
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 4
              y: 5
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'exceptions/server'
                          aggregationType: 7
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Server exceptions'
                            color: '#47BDF5'
                          }
                        }
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'dependencies/failed'
                          aggregationType: 7
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Dependency failures'
                            color: '#7E58FF'
                          }
                        }
                      ]
                      title: 'Server exceptions and Dependency failures'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 8
              y: 5
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'performanceCounters/processorCpuPercentage'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Processor time'
                            color: '#47BDF5'
                          }
                        }
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'performanceCounters/processCpuPercentage'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Process CPU'
                            color: '#7E58FF'
                          }
                        }
                      ]
                      title: 'Average processor and process CPU utilization'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 12
              y: 5
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'exceptions/browser'
                          aggregationType: 7
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Browser exceptions'
                            color: '#47BDF5'
                          }
                        }
                      ]
                      title: 'Browser exceptions'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 0
              y: 8
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'availabilityResults/count'
                          aggregationType: 7
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Availability test results count'
                            color: '#47BDF5'
                          }
                        }
                      ]
                      title: 'Availability test results count'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 4
              y: 8
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'performanceCounters/processIOBytesPerSecond'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Process IO rate'
                            color: '#47BDF5'
                          }
                        }
                      ]
                      title: 'Average process I/O rate'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 8
              y: 8
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${app_insights!.outputs.name}'
                          }
                          name: 'performanceCounters/memoryAvailableBytes'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Available memory'
                            color: '#47BDF5'
                          }
                        }
                      ]
                      title: 'Average available memory'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
        ]
      }
    ]
  }
}

// ============================================================================
// Module: Networking (WAF — conditional on enablePrivateNetworking)
// ============================================================================

module virtualNetwork './modules/networking/virtual-network.bicep' = if (enablePrivateNetworking) {
  name: take('module.virtualNetwork.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    addressPrefixes: ['10.0.0.0/20'] // 4096 addresses (enough for 8 /23 subnets or 16 /24)
    location: location
    tags: tags
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceResourceId
    resourceSuffix: solutionSuffix
    enableTelemetry: enableTelemetry
  }
}

// Bastion Host — secure access to jumpbox VM
module bastionHost './modules/networking/bastion-host.bicep' = if (enablePrivateNetworking) {
  name: take('module.bastion-host.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    virtualNetworkResourceId: virtualNetwork!.outputs.resourceId
    publicIPDiagnosticSettings: monitoringDiagnosticSettings
    diagnosticSettings: monitoringDiagnosticSettings
  }
}

// WAF: Maintenance Configuration for VM patching
module maintenanceConfiguration './modules/compute/maintenance-configuration.bicep' = if (enablePrivateNetworking) {
  name: take('module.maintenance-configuration.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// WAF: Data Collection Rules for VM monitoring
var dataCollectionRulesLocation = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspace!.location
  : (enableMonitoring ? log_analytics!.outputs.location : location)
module windowsVmDataCollectionRules './modules/monitoring/data-collection-rule.bicep' = if (enablePrivateNetworking && enableMonitoring) {
  name: take('module.data-collection-rule.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: dataCollectionRulesLocation
    tags: tags
    enableTelemetry: enableTelemetry
    logAnalyticsWorkspaceResourceId: logAnalyticsWorkspaceResourceId
  }
}

// WAF: Proximity Placement Group for VM
var virtualMachineAvailabilityZone = 1
module proximityPlacementGroup './modules/compute/proximity-placement-group.bicep' = if (enablePrivateNetworking) {
  name: take('module.proximity-placement-group.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    availabilityZone: virtualMachineAvailabilityZone
    vmSizes: [vmSize]
  }
}

// Jumpbox VM — administration access when private networking is enabled
module jumpboxVM './modules/compute/virtual-machine.bicep' = if (enablePrivateNetworking) {
  name: take('module.virtual-machine.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    imageReference: {
      offer: 'WindowsServer'
      publisher: 'MicrosoftWindowsServer'
      sku: '2019-datacenter'
      version: 'latest'
    }
    vmSize: vmSize
    availabilityZone: virtualMachineAvailabilityZone
    adminUsername: empty(vmAdminUsername) ? 'testvmuser' : vmAdminUsername
    adminPassword: empty(vmAdminPassword) ? 'Vm!${uniqueString(subscription().subscriptionId, solutionName)}${guid(subscription().subscriptionId, solutionName, 'vm-admin-password')}' : vmAdminPassword
    subnetResourceId: virtualNetwork!.outputs.administrationSubnetResourceId
    deployingUserPrincipalId: deployingUserPrincipalId
    deployingUserPrincipalType: deployingUserPrincipalType
    roleAssignments: [
      {
        roleDefinitionIdOrName: '1c0163c0-47e6-4577-8991-ea5c82e286e4' // Virtual Machine Administrator Login
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
    ]
    diagnosticSettings: monitoringDiagnosticSettings
    maintenanceConfigurationResourceId: maintenanceConfiguration!.outputs.resourceId
    proximityPlacementGroupResourceId: proximityPlacementGroup!.outputs.resourceId
    extensionMonitoringAgentConfig: enableMonitoring ? {
      dataCollectionRuleAssociations: [
        {
          dataCollectionRuleResourceId: windowsVmDataCollectionRules!.outputs.resourceId
          name: 'send-${logAnalyticsWorkspaceName}'
        }
      ]
      enabled: true
      tags: tags
    } : null
  }
}

// Private DNS Zones — one per service, linked to VNet
@batchSize(5)
module privateDnsZoneDeployments './modules/networking/private-dns-zone.bicep' = [
  for (zone, i) in privateDnsZones: if (enablePrivateNetworking) {
    name: 'module.private-dns-zone.${contains(zone, 'azurecontainerapps.io') ? 'containerappenv' : split(zone, '.')[1]}'
    params: {
      name: zone
      tags: allTags
      enableTelemetry: enableTelemetry
      virtualNetworkLinks: [
        {
          name: take('vnetlink-${virtualNetwork!.outputs.name}-${split(zone, '.')[1]}', 80)
          virtualNetworkResourceId: virtualNetwork!.outputs.resourceId
        }
      ]
    }
  }
]

// ============================================================================
// Module: Data
// ============================================================================

module cosmosDBModule './modules/data/cosmos-db-nosql.bicep' = if (databaseType == 'CosmosDB') {
  name: take('module.cosmos-db-nosql.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    diagnosticSettings: monitoringDiagnosticSettings
    zoneRedundant: enableRedundancy
    enableAutomaticFailover: enableRedundancy
    haLocation: cosmosDbHaLocation
    enablePrivateNetworking: enablePrivateNetworking
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.cosmosDB]!.outputs.resourceId
    ] : []
    sqlRoleDefinitions: [
      {
        roleName: 'Cosmos DB SQL Data Contributor'
        dataActions: [
          'Microsoft.DocumentDB/databaseAccounts/readMetadata'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/*'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*'
        ]
        assignments: [{ principalId: managedIdentityModule.outputs.principalId }]
      }
    ]
  }
}

var postgresDBName = 'postgres'
module postgresDBModule './modules/data/postgresql-flexible-server.bicep' = if (databaseType == 'PostgreSQL') {
  name: take('module.postgre-sql.flexible-server.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    diagnosticSettings: monitoringDiagnosticSettings
    skuName: enableScalability ? 'Standard_D2s_v3' : 'Standard_B1ms'
    skuTier: enableScalability ? 'GeneralPurpose' : 'Burstable'
    highAvailability: enableRedundancy ? 'ZoneRedundant' : 'Disabled'
    highAvailabilityZone: enableRedundancy ? 2 : -1
    enablePrivateNetworking: enablePrivateNetworking
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.postgresDB]!.outputs.resourceId
    ] : []
    administrators: concat(
      managedIdentityModule!.outputs.principalId != ''
        ? [
            {
              objectId: managedIdentityModule!.outputs.principalId
              principalName: managedIdentityModule!.outputs.name
              principalType: 'ServicePrincipal'
            }
          ]
        : [],
      !empty(principal.id)
        ? [
            {
              objectId: principal.id
              principalName: principal.name
              principalType: principal.type
            }
          ]
        : []
    )
    configurations: [
      {
        name: 'azure.extensions'
        value: 'vector'
        source: 'user-override'
      }
    ]
  }
}

// If advanced image processing is used, storage account already should be publicly accessible.
// Computer Vision requires files to be publicly accessible as per the official docsumentation: https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/how-to/blob-storage-search
var enablePrivateEndpointsStorage = enablePrivateNetworking && !useAdvancedImageProcessing
module storage './modules/data/storage-account.bicep' = {
  name: take('module.storage-account.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    skuName: 'Standard_GRS'
    containers: [
        {
          name: blobContainerName
          publicAccess: 'None'
        }
        {
          name: 'config'
          publicAccess: 'None'
        }
      ]
    queueServices: {
      queues: [
        {
          name: 'doc-processing'
        }
        {
          name: 'doc-processing-poison'
        }
      ]
    }
    roleAssignments: [
      {
        principalId: managedIdentityModule.outputs.principalId
        roleDefinitionIdOrName: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
        principalType: 'ServicePrincipal'
      }
      {
        principalId: managedIdentityModule.outputs.principalId
        roleDefinitionIdOrName: '974c5e8b-45b9-4653-ba55-5f855dd0fb88' // Storage Queue Data Contributor
        principalType: 'ServicePrincipal'
      }
      {
        principalId: managedIdentityModule.outputs.principalId
        roleDefinitionIdOrName: 'Storage File Data Privileged Contributor'
        principalType: 'ServicePrincipal'
      }
      {
        principalId: managedIdentityModule.outputs.principalId
        roleDefinitionIdOrName: '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3' // Storage Table Data Contributor
        principalType: 'ServicePrincipal'
      }
    ]
    allowSharedKeyAccess: true
    publicNetworkAccess: enablePrivateEndpointsStorage ? 'Disabled' : 'Enabled'
    networkAcls: { bypass: 'AzureServices', defaultAction: enablePrivateEndpointsStorage ? 'Deny' : 'Allow' }
    enablePrivateNetworking: enablePrivateNetworking
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateEndpointServices: enablePrivateNetworking ? [
      { service: 'blob',  privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.storageBlob]!.outputs.resourceId }
      { service: 'queue', privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.storageQueue]!.outputs.resourceId }
      { service: 'file',  privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.storageFile]!.outputs.resourceId }
      { service: 'table', privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.storageTable]!.outputs.resourceId }
    ] : []
  }
}

// Store secrets in a keyvault
module keyvault './modules/security/key-vault.bicep' = {
  name: take('module.key-vault.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    enablePurgeProtection: enablePurgeProtection
    softDeleteRetentionInDays: 7
    diagnosticSettings: monitoringDiagnosticSettings
    enablePrivateNetworking: enablePrivateNetworking
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.keyVault]!.outputs.resourceId
    ] : []
    roleAssignments: concat(
      managedIdentityModule!.outputs.principalId != ''
        ? [
            {
              principalId: managedIdentityModule!.outputs.principalId
              principalType: 'ServicePrincipal'
              roleDefinitionIdOrName: 'Key Vault Secrets User'
            }
          ]
        : [],
      !empty(principal.id)
        ? [
            {
              principalId: principal.id
              roleDefinitionIdOrName: 'Key Vault Secrets User'
            }
          ]
        : []
    )
    secrets: [
      {
        name: 'FUNCTION-KEY'
        value: clientKey
      }
    ]
    enableTelemetry: enableTelemetry
  }
}

module openai './modules/ai/ai-services.bicep' = {
  name: take('module.ai-services.${solutionName}', 64)
  scope: resourceGroup()
  params: {
    solutionName: solutionSuffix
    namePrefix: 'oai'
    location: location
    tags: allTags
    kind: 'OpenAI'
    sku: azureOpenAISkuName
    disableLocalAuth: true
    enablePrivateNetworking: enablePrivateNetworking
    diagnosticSettings: monitoringDiagnosticSettings
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    managedIdentities: {
      systemAssigned: true, userAssignedResourceIds: [managedIdentityModule.outputs.resourceId]
    }
    enableTelemetry: enableTelemetry
    allowedFqdnList: concat(
      [
        '${storageAccountName}.blob.${environment().suffixes.storage}'
        '${storageAccountName}.queue.${environment().suffixes.storage}'
      ],
      databaseType == 'CosmosDB' ? ['${azureAISearchName}.search.windows.net'] : []
    )
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.openAI]!.outputs.resourceId
    ] : []
    roleAssignments: concat(
      [
        {
          roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908' //Cognitive Services User
          principalId: managedIdentityModule.outputs.principalId
          principalType: 'ServicePrincipal'
        }
        {
          roleDefinitionIdOrName: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services Contributor
          principalId: managedIdentityModule.outputs.principalId
          principalType: 'ServicePrincipal'
        }
      ],
      !empty(principal.id)
        ? [
            {
              roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908' //Cognitive Services User
              principalId: principal.id
            }
            {
              roleDefinitionIdOrName: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services Contributor
              principalId: principal.id
            }
          ]
        : []
    )
  }
}

// Model deployments (single loop for both existing and new paths)
@batchSize(1)
module model_deployments './modules/ai/ai-foundry-model-deployment.bicep' = [for (deployment, i) in defaultOpenAiDeployments: {
  name: take('module.model-deployment-${i}.${solutionName}', 64)
  scope: resourceGroup(subscription().subscriptionId, resourceGroup().name)
  params: {
    aiServicesAccountName: openai.outputs.name
    deploymentName: deployment.name
    modelName: deployment.model.name
    modelVersion: deployment.model.version
    skuName: deployment.sku.name
    skuCapacity: deployment.sku.capacity
  }
}]

module computerVision './modules/ai/ai-services.bicep' = if (useAdvancedImageProcessing) {
  name: take('module.ai-services.computerVision.${solutionName}', 64)
  scope: resourceGroup()
  params: {
    solutionName: solutionSuffix
    namePrefix: 'cv'
    kind: 'ComputerVision'
    disableLocalAuth: true
    location: computerVisionLocation != '' ? computerVisionLocation : 'eastus' // Default to eastus if no location provided
    tags: allTags
    sku: computerVisionSkuName
    diagnosticSettings: monitoringDiagnosticSettings
    enablePrivateNetworking: enablePrivateNetworking
    enableTelemetry: enableTelemetry
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    managedIdentities: {
      systemAssigned: true, userAssignedResourceIds: [managedIdentityModule.outputs.resourceId]
    }
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
    ] : []
    roleAssignments: concat(
      [
        {
          roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908' //Cognitive Services User
          principalId: managedIdentityModule.outputs.principalId
          principalType: 'ServicePrincipal'
        }
      ],
      !empty(principal.id)
        ? [
            {
              roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908' //Cognitive Services User
              principalId: principal.id
            }
          ]
        : []
    )
  }
}

// The Web socket from front end application connects to Speech service over a public internet and it does not work over a Private endpoint.
// So public access is enabled even if AVM WAF is enabled.
var enablePrivateNetworkingSpeech = false
module speechService './modules/ai/ai-services.bicep' = {
  name: take('module.ai-services.SpeechServices.${solutionName}', 64)
  scope: resourceGroup()
  params: {
    solutionName: solutionSuffix
    namePrefix: 'spch'
    location: location
    kind: 'SpeechServices'
    sku: 'S0'
    disableLocalAuth: true
    tags: allTags
    enablePrivateNetworking: enablePrivateNetworkingSpeech
    diagnosticSettings: monitoringDiagnosticSettings
    enableTelemetry: enableTelemetry
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    managedIdentities: {
      systemAssigned: true, userAssignedResourceIds: [managedIdentityModule.outputs.resourceId]
    }
    privateEndpointSubnetId: enablePrivateNetworkingSpeech ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworkingSpeech ? [
      privateDnsZoneDeployments[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
    ] : []
    roleAssignments: concat(
      [
        {
          roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908' //Cognitive Services User
          principalId: managedIdentityModule.outputs.principalId
          principalType: 'ServicePrincipal'
        }
      ],
      !empty(principal.id)
        ? [
            {
              roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908' //Cognitive Services User
              principalId: principal.id
            }
          ]
        : []
    )
  }
}

// Update your formrecognizer module
module formrecognizer './modules/ai/ai-services.bicep' = {
  name: take('module.ai-services.FormRecognizer.${solutionName}', 64)
  scope: resourceGroup()
  params: {
    solutionName: solutionSuffix
    namePrefix: 'di'
    location: location
    kind: 'FormRecognizer'
    disableLocalAuth: true
    allowedFqdnList: [
      '${storageAccountName}.blob.${environment().suffixes.storage}'
      '${storageAccountName}.queue.${environment().suffixes.storage}'
    ]
    enablePrivateNetworking: enablePrivateNetworking
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    managedIdentities: {
      systemAssigned: true, userAssignedResourceIds: [managedIdentityModule.outputs.resourceId]
    }
    enableTelemetry: enableTelemetry
    diagnosticSettings: monitoringDiagnosticSettings
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
    ] : []
    roleAssignments: concat(
      [
        {
          roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908' //Cognitive Services User
          principalId: managedIdentityModule.outputs.principalId
          principalType: 'ServicePrincipal'
        }
        {
          roleDefinitionIdOrName: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
          principalId: managedIdentityModule.outputs.principalId
          principalType: 'ServicePrincipal'
        }
      ],
      !empty(principal.id)
        ? [
            {
              roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908' //Cognitive Services User
              principalId: principal.id
            }
          ]
        : []
    )
  }
}

module contentsafety './modules/ai/ai-services.bicep' = {
  name: take('module.ai-services.ContentSafety.${solutionName}', 64)
  scope: resourceGroup()
  params: {
    solutionName: solutionSuffix
    namePrefix: 'cs'
    location: location
    tags: allTags
    kind: 'ContentSafety'
    disableLocalAuth: true
    diagnosticSettings: monitoringDiagnosticSettings
    enablePrivateNetworking: enablePrivateNetworking
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    managedIdentities: {
      systemAssigned: true, userAssignedResourceIds: [managedIdentityModule.outputs.resourceId]
    }
    enableTelemetry: enableTelemetry
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
    ] : []
    roleAssignments: concat(
      [
        {
          roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908' //Cognitive Services User
          principalId: managedIdentityModule.outputs.principalId
          principalType: 'ServicePrincipal'
        }
      ],
      !empty(principal.id)
        ? [
            {
              roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908' //Cognitive Services User
              principalId: principal.id
            }
          ]
        : []
    )
  }
}

// Separate module for Search Service to enable managed identity and update other properties, as this reduces deployment time for the search service
module search './modules/ai/ai-search.bicep' = if (databaseType == 'CosmosDB') {
  name: take('module.ai-search.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    enableTelemetry: enableTelemetry
    skuName: azureSearchSku
    disableLocalAuth: false
    semanticSearch: azureSearchUseSemanticSearch ? 'free' : 'disabled'
    diagnosticSettings: monitoringDiagnosticSettings
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    managedIdentities: {
      systemAssigned: true, userAssignedResourceIds: [managedIdentityModule.outputs.resourceId]
    }
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-search-${solutionSuffix}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'search-dns-zone-group-blob'
                  privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.searchService]!.outputs.resourceId
                }
              ]
            }
            subnetResourceId: virtualNetwork!.outputs.backendSubnetResourceId
            service: 'searchService'
          }
        ]
      : []
    roleAssignments: concat(
      [
        {
          roleDefinitionIdOrName: '8ebe5a00-799e-43f5-93ac-243d3dce84a7' // Search Index Data Contributor
          principalId: managedIdentityModule.outputs.principalId
          principalType: 'ServicePrincipal'
        }
        {
          roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0' // Search Service Contributor
          principalId: managedIdentityModule.outputs.principalId
          principalType: 'ServicePrincipal'
        }
        {
          roleDefinitionIdOrName: '1407120a-92aa-4202-b7e9-c0e197c71c8f' // Search Index Data Reader
          principalId: managedIdentityModule.outputs.principalId
          principalType: 'ServicePrincipal'
        }
      ],
      !empty(principal.id)
        ? [
            {
              roleDefinitionIdOrName: '8ebe5a00-799e-43f5-93ac-243d3dce84a7' // Search Index Data Contributor
              principalId: principal.id
            }
            {
              roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0' // Search Service Contributor
              principalId: principal.id
            }
            {
              roleDefinitionIdOrName: '1407120a-92aa-4202-b7e9-c0e197c71c8f' // Search Index Data Reader
              principalId: principal.id
            }
          ]
        : []
    )
  }
}

// ============================================================================
// Module: Compute
// ============================================================================

module webServerFarm './modules/compute/app-service-plan.bicep' = {
  name: take('module.app-service-plan.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    skuName: (enableScalability || enableRedundancy) ? 'P1v3' : hostingPlanSku
    skuCapacity: enableScalability ? 3 : 2
    zoneRedundant: enableRedundancy
    diagnosticSettings: monitoringDiagnosticSettings
  }
}

var webLinuxFxVersion = hostingModel == 'container'
  ? 'DOCKER|${registryName}.azurecr.io/rag-webapp:${appversion}'
  : 'PYTHON|3.11'
// endToEndEncryptionEnabled is only supported on Premium v2/v3 or Isolated v2 App Service Plans.
var appServicePlanIsPremium = enableScalability || enableRedundancy
module web './modules/compute/app-service.bicep' = {
  name: take('module.web.site.${websiteName}${hostingModel == 'container' ? '-docker' : ''}', 64)
  scope: resourceGroup()
  params: {
    solutionName: hostingModel == 'container' ? '${websiteName}-docker' : websiteName
    location: location
    tags: union(tags, { 'azd-service-name': hostingModel == 'container' ? 'web-docker' : 'web' })
    kind: hostingModel == 'container' ? 'app,linux,container' : 'app,linux'
    enableTelemetry: enableTelemetry
    serverFarmResourceId: webServerFarm.outputs.resourceId
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    managedIdentities: {
      systemAssigned: true, userAssignedResourceIds: [managedIdentityModule.outputs.resourceId]
    }
    linuxFxVersion: webLinuxFxVersion
    diagnosticSettings: monitoringDiagnosticSettings
    applicationInsightResourceId: enableMonitoring ? app_insights!.outputs.resourceId : ''
    virtualNetworkSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.webserverfarmSubnetResourceId : ''
    vnetRouteAllEnabled: enablePrivateNetworking ? true : false
    e2eEncryptionEnabled: appServicePlanIsPremium
    appSettings: union(
      {
        AZURE_BLOB_ACCOUNT_NAME: storageAccountName
        AZURE_BLOB_CONTAINER_NAME: blobContainerName
        AZURE_FORM_RECOGNIZER_ENDPOINT: formrecognizer.outputs.endpoint
        AZURE_COMPUTER_VISION_ENDPOINT: useAdvancedImageProcessing ? computerVision!.outputs.endpoint : ''
        AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_API_VERSION: computerVisionVectorizeImageApiVersion
        AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_MODEL_VERSION: computerVisionVectorizeImageModelVersion
        AZURE_CONTENT_SAFETY_ENDPOINT: contentsafety.outputs.endpoint
        AZURE_KEY_VAULT_ENDPOINT: keyvault.outputs.uri
        AZURE_OPENAI_RESOURCE: azureOpenAIResourceName
        AZURE_OPENAI_MODEL: azureOpenAIModel
        AZURE_OPENAI_MODEL_NAME: azureOpenAIModelName
        AZURE_OPENAI_MODEL_VERSION: azureOpenAIModelVersion
        AZURE_OPENAI_TEMPERATURE: azureOpenAITemperature
        AZURE_OPENAI_TOP_P: azureOpenAITopP
        AZURE_OPENAI_MAX_TOKENS: azureOpenAIMaxTokens
        AZURE_OPENAI_STOP_SEQUENCE: azureOpenAIStopSequence
        AZURE_OPENAI_SYSTEM_MESSAGE: azureOpenAISystemMessage
        AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
        AZURE_OPENAI_STREAM: azureOpenAIStream
        AZURE_OPENAI_EMBEDDING_MODEL: azureOpenAIEmbeddingModel
        AZURE_OPENAI_EMBEDDING_MODEL_NAME: azureOpenAIEmbeddingModelName
        AZURE_OPENAI_EMBEDDING_MODEL_VERSION: azureOpenAIEmbeddingModelVersion
        AZURE_SPEECH_SERVICE_NAME: speechService.outputs.name
        AZURE_SPEECH_SERVICE_REGION: location
        AZURE_SPEECH_RECOGNIZER_LANGUAGES: recognizedLanguages
        AZURE_SPEECH_REGION_ENDPOINT: speechService.outputs.endpoint
        USE_ADVANCED_IMAGE_PROCESSING: useAdvancedImageProcessing ? 'true' : 'false'
        ADVANCED_IMAGE_PROCESSING_MAX_IMAGES: string(advancedImageProcessingMaxImages)
        ORCHESTRATION_STRATEGY: orchestrationStrategy
        CONVERSATION_FLOW: conversationFlow
        LOGLEVEL: logLevel
        PACKAGE_LOGGING_LEVEL: 'WARNING'
        AZURE_LOGGING_PACKAGES: ''
        DATABASE_TYPE: databaseType
        MANAGED_IDENTITY_CLIENT_ID: managedIdentityModule.outputs.clientId
        MANAGED_IDENTITY_RESOURCE_ID: managedIdentityModule.outputs.resourceId
        AZURE_CLIENT_ID: managedIdentityModule.outputs.clientId // Required so LangChain AzureSearch vector store authenticates with this user-assigned managed identity
        APP_ENV: appEnvironment
        AZURE_SEARCH_DIMENSIONS: azureSearchDimensions
        APPLICATIONINSIGHTS_ENABLED: enableMonitoring ? 'true' : 'false'
        // APPLICATIONINSIGHTS_CONNECTION_STRING: enableMonitoring ? app_insights!.outputs.connectionString : ''
      },
      openAISystemPrompts,
      databaseType == 'CosmosDB'
        ? {
            AZURE_COSMOSDB_ACCOUNT_NAME: azureCosmosDBAccountName
            AZURE_COSMOSDB_DATABASE_NAME: cosmosDBModule!.outputs.databaseName
            AZURE_COSMOSDB_CONVERSATIONS_CONTAINER_NAME: cosmosDBModule!.outputs.containerName
            AZURE_COSMOSDB_ENABLE_FEEDBACK: 'true'
            AZURE_SEARCH_USE_SEMANTIC_SEARCH: azureSearchUseSemanticSearch ? 'true' : 'false'
            AZURE_SEARCH_SERVICE: 'https://${azureAISearchName}.search.windows.net'
            AZURE_SEARCH_INDEX: azureSearchIndex
            AZURE_SEARCH_CONVERSATIONS_LOG_INDEX: azureSearchConversationLogIndex
            AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG: azureSearchSemanticSearchConfig
            AZURE_SEARCH_INDEX_IS_PRECHUNKED: azureSearchIndexIsPrechunked
            AZURE_SEARCH_TOP_K: azureSearchTopK
            AZURE_SEARCH_ENABLE_IN_DOMAIN: azureSearchEnableInDomain
            AZURE_SEARCH_FILENAME_COLUMN: azureSearchFilenameColumn
            AZURE_SEARCH_FILTER: azureSearchFilter
            AZURE_SEARCH_FIELDS_ID: azureSearchFieldId
            AZURE_SEARCH_CONTENT_COLUMN: azureSearchContentColumn
            AZURE_SEARCH_CONTENT_VECTOR_COLUMN: azureSearchVectorColumn
            AZURE_SEARCH_TITLE_COLUMN: azureSearchTitleColumn
            AZURE_SEARCH_FIELDS_METADATA: azureSearchFieldsMetadata
            AZURE_SEARCH_SOURCE_COLUMN: azureSearchSourceColumn
            AZURE_SEARCH_TEXT_COLUMN: azureSearchUseIntegratedVectorization ? azureSearchTextColumn : ''
            AZURE_SEARCH_LAYOUT_TEXT_COLUMN: azureSearchUseIntegratedVectorization ? azureSearchLayoutTextColumn : ''
            AZURE_SEARCH_CHUNK_COLUMN: azureSearchChunkColumn
            AZURE_SEARCH_OFFSET_COLUMN: azureSearchOffsetColumn
            AZURE_SEARCH_URL_COLUMN: azureSearchUrlColumn
            AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION: azureSearchUseIntegratedVectorization ? 'true' : 'false'
          }
        : databaseType == 'PostgreSQL'
            ? {
                AZURE_POSTGRESQL_HOST_NAME: postgresDBModule!.outputs.serverFqdn
                AZURE_POSTGRESQL_DATABASE_NAME: postgresDBName
                AZURE_POSTGRESQL_USER: managedIdentityModule!.outputs.name
              }
            : {}
    )
  }
}

var adminWebLinuxFxVersion = hostingModel == 'container'
  ? 'DOCKER|${registryName}.azurecr.io/rag-adminwebapp:${appversion}'
  : 'PYTHON|3.11'
module adminweb './modules/compute/app-service.bicep' = {
  name: take('module.web.site.${adminWebsiteName}${hostingModel == 'container' ? '-docker' : ''}', 64)
  scope: resourceGroup()
  params: {
    solutionName: hostingModel == 'container' ? '${adminWebsiteName}-docker' : adminWebsiteName
    name: hostingModel == 'container' ? '${adminWebsiteName}-docker' : adminWebsiteName
    location: location
    tags: union(tags, { 'azd-service-name': hostingModel == 'container' ? 'adminweb-docker' : 'adminweb' })
    kind: hostingModel == 'container' ? 'app,linux,container' : 'app,linux'
    serverFarmResourceId: webServerFarm.outputs.resourceId
    enableTelemetry: enableTelemetry
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    managedIdentities: {
      systemAssigned: true, userAssignedResourceIds: [managedIdentityModule.outputs.resourceId]
    }
    linuxFxVersion: adminWebLinuxFxVersion
    diagnosticSettings: monitoringDiagnosticSettings
    vnetRouteAllEnabled: enablePrivateNetworking ? true : false
    virtualNetworkSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.webserverfarmSubnetResourceId : ''
    e2eEncryptionEnabled: appServicePlanIsPremium
    appSettings: union(
      {
        AZURE_BLOB_ACCOUNT_NAME: storageAccountName
        AZURE_BLOB_CONTAINER_NAME: blobContainerName
        AZURE_FORM_RECOGNIZER_ENDPOINT: formrecognizer.outputs.endpoint
        AZURE_COMPUTER_VISION_ENDPOINT: useAdvancedImageProcessing ? computerVision!.outputs.endpoint : ''
        AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_API_VERSION: computerVisionVectorizeImageApiVersion
        AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_MODEL_VERSION: computerVisionVectorizeImageModelVersion
        AZURE_CONTENT_SAFETY_ENDPOINT: contentsafety.outputs.endpoint
        AZURE_KEY_VAULT_ENDPOINT: keyvault.outputs.uri
        AZURE_OPENAI_RESOURCE: azureOpenAIResourceName
        AZURE_OPENAI_MODEL: azureOpenAIModel
        AZURE_OPENAI_MODEL_NAME: azureOpenAIModelName
        AZURE_OPENAI_MODEL_VERSION: azureOpenAIModelVersion
        AZURE_OPENAI_TEMPERATURE: azureOpenAITemperature
        AZURE_OPENAI_TOP_P: azureOpenAITopP
        AZURE_OPENAI_MAX_TOKENS: azureOpenAIMaxTokens
        AZURE_OPENAI_STOP_SEQUENCE: azureOpenAIStopSequence
        AZURE_OPENAI_SYSTEM_MESSAGE: azureOpenAISystemMessage
        AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
        AZURE_OPENAI_STREAM: azureOpenAIStream
        AZURE_OPENAI_EMBEDDING_MODEL: azureOpenAIEmbeddingModel
        AZURE_OPENAI_EMBEDDING_MODEL_NAME: azureOpenAIEmbeddingModelName
        AZURE_OPENAI_EMBEDDING_MODEL_VERSION: azureOpenAIEmbeddingModelVersion

        USE_ADVANCED_IMAGE_PROCESSING: useAdvancedImageProcessing ? 'true' : 'false'
        BACKEND_URL: 'https://${hostingModel == 'container' ? '${functionName}-docker' : functionName}.azurewebsites.net'
        DOCUMENT_PROCESSING_QUEUE_NAME: queueName
        FUNCTION_KEY: 'FUNCTION-KEY'
        ORCHESTRATION_STRATEGY: orchestrationStrategy
        CONVERSATION_FLOW: conversationFlow
        LOGLEVEL: logLevel
        PACKAGE_LOGGING_LEVEL: 'WARNING'
        AZURE_LOGGING_PACKAGES: ''
        DATABASE_TYPE: databaseType
        USE_KEY_VAULT: 'true'
        MANAGED_IDENTITY_CLIENT_ID: managedIdentityModule.outputs.clientId
        MANAGED_IDENTITY_RESOURCE_ID: managedIdentityModule.outputs.resourceId
        AZURE_CLIENT_ID: managedIdentityModule.outputs.clientId // Pin DefaultAzureCredential to the user-assigned MI (which holds Search/OpenAI/Cosmos RBAC); otherwise the system-assigned MI is picked and gets 403 Forbidden.
        APP_ENV: appEnvironment
        AZURE_SEARCH_DIMENSIONS: azureSearchDimensions
        APPLICATIONINSIGHTS_ENABLED: enableMonitoring ? 'true' : 'false'
        // APPLICATIONINSIGHTS_CONNECTION_STRING: enableMonitoring ? app_insights!.outputs.connectionString : ''
      },
      openAISystemPrompts,
      databaseType == 'CosmosDB'
        ? {
            AZURE_SEARCH_SERVICE: 'https://${azureAISearchName}.search.windows.net'
            AZURE_SEARCH_INDEX: azureSearchIndex
            AZURE_SEARCH_USE_SEMANTIC_SEARCH: azureSearchUseSemanticSearch ? 'true' : 'false'
            AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG: azureSearchSemanticSearchConfig
            AZURE_SEARCH_INDEX_IS_PRECHUNKED: azureSearchIndexIsPrechunked
            AZURE_SEARCH_TOP_K: azureSearchTopK
            AZURE_SEARCH_ENABLE_IN_DOMAIN: azureSearchEnableInDomain
            AZURE_SEARCH_FILENAME_COLUMN: azureSearchFilenameColumn
            AZURE_SEARCH_FILTER: azureSearchFilter
            AZURE_SEARCH_FIELDS_ID: azureSearchFieldId
            AZURE_SEARCH_CONTENT_COLUMN: azureSearchContentColumn
            AZURE_SEARCH_CONTENT_VECTOR_COLUMN: azureSearchVectorColumn
            AZURE_SEARCH_TITLE_COLUMN: azureSearchTitleColumn
            AZURE_SEARCH_FIELDS_METADATA: azureSearchFieldsMetadata
            AZURE_SEARCH_SOURCE_COLUMN: azureSearchSourceColumn
            AZURE_SEARCH_TEXT_COLUMN: azureSearchUseIntegratedVectorization ? azureSearchTextColumn : ''
            AZURE_SEARCH_LAYOUT_TEXT_COLUMN: azureSearchUseIntegratedVectorization ? azureSearchLayoutTextColumn : ''
            AZURE_SEARCH_CHUNK_COLUMN: azureSearchChunkColumn
            AZURE_SEARCH_OFFSET_COLUMN: azureSearchOffsetColumn
            AZURE_SEARCH_URL_COLUMN: azureSearchUrlColumn
            AZURE_SEARCH_DATASOURCE_NAME: azureSearchDatasource
            AZURE_SEARCH_INDEXER_NAME: azureSearchIndexer
            AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION: azureSearchUseIntegratedVectorization ? 'true' : 'false'
          }
        : databaseType == 'PostgreSQL'
            ? {
                AZURE_POSTGRESQL_HOST_NAME: postgresDBModule!.outputs.serverFqdn
                AZURE_POSTGRESQL_DATABASE_NAME: postgresDBName
                AZURE_POSTGRESQL_USER: managedIdentityModule!.outputs.name
              }
            : {}
    )
  }
}

module function './modules/compute/function-app.bicep' = {
  name: hostingModel == 'container' ? '${functionName}-docker' : functionName
  scope: resourceGroup()
  params: {
    name: hostingModel == 'container' ? '${functionName}-docker' : functionName
    location: location
    tags: union(tags, { 'azd-service-name': hostingModel == 'container' ? 'function-docker' : 'function' })
    kind: hostingModel == 'container' ? 'functionapp,linux,container' : 'functionapp,linux'
    serverFarmResourceId: webServerFarm.outputs.resourceId
    storageAccountName: storage.outputs.name
    applicationInsightResourceId: enableMonitoring ? app_insights!.outputs.resourceId : ''
    enableTelemetry: enableTelemetry
    userAssignedIdentityClientId: managedIdentityModule.outputs.clientId
    managedIdentities: { systemAssigned: true, userAssignedResourceIds: !empty(managedIdentityModule.outputs.resourceId) ? [managedIdentityModule.outputs.resourceId] : [] }
    runtimeStack: 'python'
    runtimeVersion: '3.11'
    dockerFullImageName: hostingModel == 'container' ? '${registryName}.azurecr.io/rag-backend:${appversion}' : ''
    virtualNetworkSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.webserverfarmSubnetResourceId : ''
    siteConfig: {
      alwaysOn: true
      cors: {
        allowedOrigins: []
      }
      healthCheckPath: ''
      minTlsVersion: '1.2'
      ftpsState: 'FtpsOnly'
    }
    appSettings: union(
      {
        AZURE_BLOB_ACCOUNT_NAME: storageAccountName
        AZURE_BLOB_CONTAINER_NAME: blobContainerName
        AZURE_FORM_RECOGNIZER_ENDPOINT: formrecognizer.outputs.endpoint
        AZURE_COMPUTER_VISION_ENDPOINT: useAdvancedImageProcessing ? computerVision!.outputs.endpoint : ''
        AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_API_VERSION: computerVisionVectorizeImageApiVersion
        AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_MODEL_VERSION: computerVisionVectorizeImageModelVersion
        AZURE_CONTENT_SAFETY_ENDPOINT: contentsafety.outputs.endpoint
        AZURE_KEY_VAULT_ENDPOINT: keyvault.outputs.uri
        AZURE_OPENAI_MODEL: azureOpenAIModel
        AZURE_OPENAI_MODEL_NAME: azureOpenAIModelName
        AZURE_OPENAI_MODEL_VERSION: azureOpenAIModelVersion
        AZURE_OPENAI_EMBEDDING_MODEL: azureOpenAIEmbeddingModel
        AZURE_OPENAI_EMBEDDING_MODEL_NAME: azureOpenAIEmbeddingModelName
        AZURE_OPENAI_EMBEDDING_MODEL_VERSION: azureOpenAIEmbeddingModelVersion
        AZURE_OPENAI_RESOURCE: azureOpenAIResourceName
        AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion

        USE_ADVANCED_IMAGE_PROCESSING: useAdvancedImageProcessing ? 'true' : 'false'
        DOCUMENT_PROCESSING_QUEUE_NAME: queueName
        ORCHESTRATION_STRATEGY: orchestrationStrategy
        LOGLEVEL: logLevel
        PACKAGE_LOGGING_LEVEL: 'WARNING'
        AZURE_LOGGING_PACKAGES: ''
        AZURE_OPENAI_SYSTEM_MESSAGE: azureOpenAISystemMessage
        DATABASE_TYPE: databaseType
        MANAGED_IDENTITY_CLIENT_ID: managedIdentityModule.outputs.clientId
        MANAGED_IDENTITY_RESOURCE_ID: managedIdentityModule.outputs.resourceId
        AZURE_CLIENT_ID: managedIdentityModule.outputs.clientId // Required so LangChain AzureSearch vector store authenticates with this user-assigned managed identity
        APP_ENV: appEnvironment
        BACKEND_URL: backendUrl
        AZURE_SEARCH_DIMENSIONS: azureSearchDimensions
        APPLICATIONINSIGHTS_ENABLED: enableMonitoring ? 'true' : 'false'
        APPLICATIONINSIGHTS_CONNECTION_STRING: enableMonitoring ? app_insights!.outputs.connectionString : ''
      },
      openAISystemPrompts,
      databaseType == 'CosmosDB'
        ? {
            AZURE_SEARCH_INDEX: azureSearchIndex
            AZURE_SEARCH_SERVICE: 'https://${azureAISearchName}.search.windows.net'
            AZURE_SEARCH_DATASOURCE_NAME: azureSearchDatasource
            AZURE_SEARCH_INDEXER_NAME: azureSearchIndexer
            AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION: azureSearchUseIntegratedVectorization ? 'true' : 'false'
            AZURE_SEARCH_FIELDS_ID: azureSearchFieldId
            AZURE_SEARCH_CONTENT_COLUMN: azureSearchContentColumn
            AZURE_SEARCH_CONTENT_VECTOR_COLUMN: azureSearchVectorColumn
            AZURE_SEARCH_TITLE_COLUMN: azureSearchTitleColumn
            AZURE_SEARCH_FIELDS_METADATA: azureSearchFieldsMetadata
            AZURE_SEARCH_SOURCE_COLUMN: azureSearchSourceColumn
            AZURE_SEARCH_TEXT_COLUMN: azureSearchUseIntegratedVectorization ? azureSearchTextColumn : ''
            AZURE_SEARCH_LAYOUT_TEXT_COLUMN: azureSearchUseIntegratedVectorization ? azureSearchLayoutTextColumn : ''
            AZURE_SEARCH_CHUNK_COLUMN: azureSearchChunkColumn
            AZURE_SEARCH_OFFSET_COLUMN: azureSearchOffsetColumn
            AZURE_SEARCH_TOP_K: azureSearchTopK
          }
        : databaseType == 'PostgreSQL'
            ? {
                AZURE_POSTGRESQL_HOST_NAME: postgresDBModule!.outputs.serverFqdn
                AZURE_POSTGRESQL_DATABASE_NAME: postgresDBName
                AZURE_POSTGRESQL_USER: managedIdentityModule!.outputs.name
              }
            : {}
    )
  }
}

var wookbookContents = loadTextContent('../workbooks/workbook.json')
var wookbookContentsSubReplaced = replace(wookbookContents, '{subscription-id}', subscription().id)
var wookbookContentsRGReplaced = replace(wookbookContentsSubReplaced, '{resource-group}', resourceGroup().name)
var wookbookContentsAppServicePlanReplaced = replace(wookbookContentsRGReplaced, '{app-service-plan}', webServerFarm.outputs.name)
var wookbookContentsBackendAppServiceReplaced = replace(
  wookbookContentsAppServicePlanReplaced,
  '{backend-app-service}',
  functionName
)
var wookbookContentsWebAppServiceReplaced = replace(
  wookbookContentsBackendAppServiceReplaced,
  '{web-app-service}',
  websiteName
)
var wookbookContentsAdminAppServiceReplaced = replace(
  wookbookContentsWebAppServiceReplaced,
  '{admin-app-service}',
  adminWebsiteName
)
var wookbookContentsEventGridReplaced = replace(
  wookbookContentsAdminAppServiceReplaced,
  '{event-grid}',
  avmEventGridSystemTopic!.outputs.name
)
var wookbookContentsLogAnalyticsReplaced = replace(
  wookbookContentsEventGridReplaced,
  '{log-analytics-resource-id}',
  log_analytics!.outputs.resourceId
)
var wookbookContentsOpenAIReplaced = replace(wookbookContentsLogAnalyticsReplaced, '{open-ai}', azureOpenAIResourceName)
var wookbookContentsAISearchReplaced = replace(wookbookContentsOpenAIReplaced, '{ai-search}', azureAISearchName)
var wookbookContentsStorageAccountReplaced = replace(
  wookbookContentsAISearchReplaced,
  '{storage-account}',
  storageAccountName
)
module workbook './modules/monitoring/workbook.bicep' = if (enableMonitoring) {
  name: take('module.monitoring.workbook.${solutionName}', 64)
  scope: resourceGroup()
  params: {
    solutionName: workbookDisplayName
    location: location
    tags: allTags
    serializedData: wookbookContentsStorageAccountReplaced
  }
}

module avmEventGridSystemTopic './modules/data/event-grid.bicep'= {
  name: take('modules.event-grid.system-topic.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    source: storage.outputs.resourceId
    topicType: 'Microsoft.Storage.StorageAccounts'
    location: location
    tags: allTags
    diagnosticSettings: enableMonitoring
      ? [
          {
            name: 'diagnosticSettings'
            workspaceResourceId: log_analytics!.outputs.resourceId
            metricCategories: [
              {
                category: 'AllMetrics'
              }
            ]
          }
        ]
      : []
    eventSubscriptions: [
      {
        name: 'evts-${solutionSuffix}'
        destination: {
          endpointType: 'StorageQueue'
          properties: {
            queueName: queueName
            resourceId: storage.outputs.resourceId
          }
        }
        eventDeliverySchema: 'EventGridSchema'
        filter: {
          includedEventTypes: [
            'Microsoft.Storage.BlobCreated'
            'Microsoft.Storage.BlobDeleted'
          ]
          enableAdvancedFilteringOnArrays: true
          subjectBeginsWith: '/blobServices/default/containers/${blobContainerName}/blobs/'
        }
        retryPolicy: {
          maxDeliveryAttempts: 30
          eventTimeToLiveInMinutes: 1440
        }
        expirationTimeUtc: '2099-01-01T11:00:21.715Z'
      }
    ]
    enableTelemetry: enableTelemetry
  }
}

var systemAssignedRoleAssignments = union(
  databaseType == 'CosmosDB'
    ? [
        {
          principalId: search.?outputs.identityPrincipalId
          resourceId: storage.outputs.resourceId
          roleName: 'Storage Blob Data Contributor'
          roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
          principalType: 'ServicePrincipal'
        }
        {
          principalId: search.?outputs.identityPrincipalId
          resourceId: openai.outputs.resourceId
          roleName: 'Cognitive Services User'
          roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908'
          principalType: 'ServicePrincipal'
        }
        {
          principalId: search.?outputs.identityPrincipalId
          resourceId: openai.outputs.resourceId
          roleName: 'Cognitive Services OpenAI User'
          roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
          principalType: 'ServicePrincipal'
        }
      ]
    : [],
  [
    {
      principalId: formrecognizer.outputs.identityPrincipalId
      resourceId: storage.outputs.resourceId
      roleName: 'Storage Blob Data Contributor'
      roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
      principalType: 'ServicePrincipal'
    }
  ]
)

@description('Role assignments applied to the system-assigned identity via AVM module. Objects can include: roleDefinitionId (req), roleName, principalType, resourceId.')
module systemAssignedIdentityRoleAssignments './modules/identity/role-assignments.bicep' = {
  name: take('module.resource-role-assignment.system-assigned', 64)
  params: {
    roleAssignments: systemAssignedRoleAssignments
  }
}

var azureOpenAIModelInfo = string({
  model: azureOpenAIModel
  model_name: azureOpenAIModelName
  model_version: azureOpenAIModelVersion
})

var azureOpenAIEmbeddingModelInfo = string({
  model: azureOpenAIEmbeddingModel
  model_name: azureOpenAIEmbeddingModelName
  model_version: azureOpenAIEmbeddingModelVersion
})

var azureCosmosDBInfo = string({
  account_name: databaseType == 'CosmosDB' ? azureCosmosDBAccountName : ''
  database_name: databaseType == 'CosmosDB' ? cosmosDBModule!.outputs.name : ''
  conversations_container_name: databaseType == 'CosmosDB' ? cosmosDBModule!.outputs.containerName : ''
})

var azurePostgresDBInfo = string({
  host_name: databaseType == 'PostgreSQL' ? postgresDBModule!.outputs.serverFqdn : ''
  database_name: databaseType == 'PostgreSQL' ? postgresDBName : ''
  user: ''
})

var azureFormRecognizerInfo = string({
  endpoint: formrecognizer.outputs.endpoint
})

var azureBlobStorageInfo = string({
  container_name: blobContainerName
  account_name: storageAccountName
})

var azureSpeechServiceInfo = string({
  service_name: speechService.outputs.name
  service_region: location
  recognizer_languages: recognizedLanguages
})

var azureSearchServiceInfo = databaseType == 'CosmosDB'
  ? string({
      service_name: azureAISearchName
      service: search!.outputs.endpoint
      use_semantic_search: azureSearchUseSemanticSearch
      semantic_search_config: azureSearchSemanticSearchConfig
      index_is_prechunked: azureSearchIndexIsPrechunked
      top_k: azureSearchTopK
      enable_in_domain: azureSearchEnableInDomain
      content_column: azureSearchContentColumn
      content_vector_column: azureSearchVectorColumn
      filename_column: azureSearchFilenameColumn
      filter: azureSearchFilter
      title_column: azureSearchTitleColumn
      fields_metadata: azureSearchFieldsMetadata
      source_column: azureSearchSourceColumn
      text_column: azureSearchTextColumn
      layout_column: azureSearchLayoutTextColumn
      url_column: azureSearchUrlColumn
      use_integrated_vectorization: azureSearchUseIntegratedVectorization
      index: azureSearchIndex
      indexer_name: azureSearchIndexer
      datasource_name: azureSearchDatasource
    })
  : ''

var azureComputerVisionInfo = string({
  service_name: computerVisionName
  endpoint: useAdvancedImageProcessing ? computerVision!.outputs.endpoint : ''
  location: useAdvancedImageProcessing ? location : ''
  vectorize_image_api_version: computerVisionVectorizeImageApiVersion
  vectorize_image_model_version: computerVisionVectorizeImageModelVersion
})

var azureOpenaiConfigurationInfo = string({
  service_name: speechService.outputs.name
  stream: azureOpenAIStream
  system_message: azureOpenAISystemMessage
  stop_sequence: azureOpenAIStopSequence
  max_tokens: azureOpenAIMaxTokens
  top_p: azureOpenAITopP
  temperature: azureOpenAITemperature
  api_version: azureOpenAIApiVersion
  resource: azureOpenAIResourceName
})

var azureContentSafetyInfo = string({
  endpoint: contentsafety.outputs.endpoint
})

var backendUrl = hostingModel == 'container'
  ? 'https://${functionName}-docker.azurewebsites.net'
  : 'https://${functionName}.azurewebsites.net'

@description('Connection string for the Application Insights instance.')
output APPLICATIONINSIGHTS_CONNECTION_STRING string = enableMonitoring
  ? app_insights!.outputs.connectionString
  : ''

@description('App Service hosting model used (code or container).')
output AZURE_APP_SERVICE_HOSTING_MODEL string = hostingModel

@description('Name of the resource group.')
output resourceGroupName string = resourceGroup().name

@description('Application environment (e.g., Prod, Dev).')
output APP_ENV string = appEnvironment

@description('Blob storage info (container and account).')
output AZURE_BLOB_STORAGE_INFO string = azureBlobStorageInfo

@description('Computer Vision service information.')
output AZURE_COMPUTER_VISION_INFO string = azureComputerVisionInfo

@description('Content Safety service endpoint information.')
output AZURE_CONTENT_SAFETY_INFO string = azureContentSafetyInfo

@description('Form Recognizer service endpoint information.')
output AZURE_FORM_RECOGNIZER_INFO string = azureFormRecognizerInfo

@description('Primary deployment location.')
output AZURE_LOCATION string = location

@description('Azure OpenAI model information.')
output AZURE_OPENAI_MODEL_INFO string = azureOpenAIModelInfo

@description('Azure OpenAI configuration details.')
output AZURE_OPENAI_CONFIGURATION_INFO string = azureOpenaiConfigurationInfo

@description('Azure OpenAI embedding model information.')
output AZURE_OPENAI_EMBEDDING_MODEL_INFO string = azureOpenAIEmbeddingModelInfo

@description('Name of the resource group.')
output AZURE_RESOURCE_GROUP string = resourceGroup().name

@description('Azure Cognitive Search service information (if deployed).')
output AZURE_SEARCH_SERVICE_INFO string = azureSearchServiceInfo

@description('Azure Speech service information.')
output AZURE_SPEECH_SERVICE_INFO string = azureSpeechServiceInfo

@description('Azure tenant identifier.')
output AZURE_TENANT_ID string = tenant().tenantId

@description('Name of the document processing queue.')
output DOCUMENT_PROCESSING_QUEUE_NAME string = queueName

@description('Orchestration strategy selected (openai_function, semantic_kernel, etc.).')
output ORCHESTRATION_STRATEGY string = orchestrationStrategy

@description('Backend URL for the function app.')
output BACKEND_URL string = backendUrl

@description('Azure WebJobs Storage connection string for the Functions app.')
output AzureWebJobsStorage string = storage.outputs.name

@description('Frontend web application resource name (for azd deploy).')
output SERVICE_WEB_RESOURCE_NAME string = web.outputs.name

@description('Admin web application resource name (for azd deploy).')
output SERVICE_ADMINWEB_RESOURCE_NAME string = adminweb.outputs.name

@description('Function app resource name (for azd deploy).')
output SERVICE_FUNCTION_RESOURCE_NAME string = function.outputs.name

@description('Frontend web application URI.')
output FRONTEND_WEBSITE_NAME string = web.outputs.appUrl

@description('Admin web application URI.')
output ADMIN_WEBSITE_NAME string = adminweb.outputs.appUrl

@description('Configured log level for applications.')
output LOGLEVEL string = logLevel

@description('Conversation flow type in use (custom or byod).')
output CONVERSATION_FLOW string = conversationFlow

@description('Whether advanced image processing is enabled.')
output USE_ADVANCED_IMAGE_PROCESSING bool = useAdvancedImageProcessing

@description('Whether Azure Search is using integrated vectorization.')
output AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION bool = azureSearchUseIntegratedVectorization

@description('Maximum number of images sent per advanced image processing request.')
output ADVANCED_IMAGE_PROCESSING_MAX_IMAGES int = advancedImageProcessingMaxImages

@description('Unique token for this solution deployment (short suffix).')
output RESOURCE_TOKEN string = solutionSuffix

@description('Cosmos DB related information (account/database/container).')
output AZURE_COSMOSDB_INFO string = azureCosmosDBInfo

@description('PostgreSQL related information (host/database/user).')
output AZURE_POSTGRESQL_INFO string = azurePostgresDBInfo

@description('Selected database type for this deployment.')
output DATABASE_TYPE string = databaseType

@description('System prompt for OpenAI functions.')
output OPEN_AI_FUNCTIONS_SYSTEM_PROMPT string = openAISystemPrompts.OPEN_AI_FUNCTIONS_SYSTEM_PROMPT

@description('System prompt used by the Semantic Kernel orchestration.')
output SEMANTIC_KERNEL_SYSTEM_PROMPT string = openAISystemPrompts.SEMANTIC_KERNEL_SYSTEM_PROMPT
