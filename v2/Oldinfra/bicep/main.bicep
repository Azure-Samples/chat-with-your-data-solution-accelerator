targetScope = 'resourceGroup'

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

@description('Name of Web App.')
var websiteName string = 'app-${solutionSuffix}'

@description('Name of Admin Web App.')
var adminWebsiteName string = '${websiteName}-admin'

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

@description('Optional. Azure Search vector field dimensions. Must match the embedding model dimensions. 1536 for text-embedding-3-small, 3072 for text-embedding-3-large. See https://learn.microsoft.com/en-us/azure/search/cognitive-search-skill-azure-openai-embedding#supported-dimensions-by-modelname.(Only for databaseType=CosmosDB)')
param azureSearchDimensions string = '1536'

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

@description('Name of Function App for Batch document processing.')
var functionName string = 'func-${solutionSuffix}'

@description('Optional. Principal object for user or service principal to assign application roles. Format: {"id":"<object-id>", "name":"<name-or-upn>", "type":"User|Group|ServicePrincipal"}')
param principal object = {
  id: '' // Principal ID
  name: '' // Principal name
  type: 'User' // Principal type ('User', 'Group', or 'ServicePrincipal')
}

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

@description('Optional. The tags to apply to all deployed Azure resources.')
param tags resourceInput<'Microsoft.Resources/resourceGroups@2025-04-01'>.tags = {}

@description('Optional. Enable monitoring applicable resources, aligned with the Well Architected Framework recommendations. This setting enables Application Insights and Log Analytics and configures all the resources applicable resources to send logs. Defaults to false.')
param enableMonitoring bool = false

var blobContainerName = 'documents'
var queueName = 'doc-processing'
var clientKey = '${uniqueString(subscription().id, resourceGroup().id, 'cwyd-function-host-key')}${guid(resourceGroup().id, 'cwyd-function-host-key')}'

@description('Optional. Image version tag to use.')
param appversion string = 'latest_waf' // Update GIT deployment branch

@description('OpenAI and Semantic Kernel prompt values.')
param openAISystemPrompts object

var registryName = 'cwydcontainerreg' // Update Registry name

var allTags = union(
  {
    'azd-env-name': solutionName
  },
  tags
)

var existingTags = resourceGroup().tags ?? {}

@description('Optional. Created by user name.')
param createdBy string = contains(deployer(), 'userPrincipalName')
  ? split(deployer().userPrincipalName, '@')[0]
  : deployer().objectId

// ============== //
// Resources      //
// ============== //

// ========== Resource Group Tag ========== //
resource resourceGroupTags 'Microsoft.Resources/tags@2025-04-01' = {
  name: 'default'
  properties: {
    tags: union(existingTags, allTags, {
      TemplateName: 'CWYD'
      Type: 'Non-WAF'
      CreatedBy: createdBy
    })
  }
}

// ========== Managed Identity ========== //
module managedIdentityModule './modules/identity/managed-identity.bicep' = if (databaseType == 'PostgreSQL') {
  name: take('module.managed-identity.user-assigned-identity.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
  }
}

// ========== Monitoring (Log Analytics + Application Insights) ========== //
var useExistingLogAnalytics = !empty(existingLogAnalyticsWorkspaceId)

// Existing workspace reference (for cross-subscription support)
resource existingLogAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2025-07-01' existing = if (useExistingLogAnalytics) {
  name: split(existingLogAnalyticsWorkspaceId, '/')[8]
  scope: resourceGroup(split(existingLogAnalyticsWorkspaceId, '/')[2], split(existingLogAnalyticsWorkspaceId, '/')[4])
}

// Resolve workspace resource ID and name — existing or new
var logAnalyticsWorkspaceResourceId = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspace.id
  : (enableMonitoring ? log_analytics!.outputs.resourceId : '')

// ========== Log Analytics module ========== //
module log_analytics './modules/monitoring/log-analytics.bicep' = if (enableMonitoring && !useExistingLogAnalytics) {
  name: take('module.log-analytics.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Application Insights module ========== //
module app_insights './modules/monitoring/app-insights.bicep' = if (enableMonitoring) {
  name: take('module.app-insights.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    workspaceResourceId: logAnalyticsWorkspaceResourceId
  }
  scope: resourceGroup(resourceGroup().name)
}

module applicationInsightsDashboard './modules/monitoring/portal-dashboard.bicep' = if (enableMonitoring) {
  name: take('module.portal-dashboard.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
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

module cosmosDBModule './modules/data/cosmos-db-nosql.bicep' = if (databaseType == 'CosmosDB') {
  name: take('module.cosmos-db-nosql.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
  }
}

var postgresDBName = 'postgres'
module postgresDBModule './modules/data/postgresql-flexible-server.bicep' = if (databaseType == 'PostgreSQL') {
  name: take('module.postgre-sql.flexible-server.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: 'eastus2'
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

// Store secrets in a keyvault
module keyvault './modules/security/key-vault.bicep' = {
  name: take('module.key-vault.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    principalId: principal.id
    managedIdentityObjectId: databaseType == 'PostgreSQL'
      ? managedIdentityModule!.outputs.principalId
      : ''
    secrets: [
      {
        name: 'FUNCTION-KEY'
        value: clientKey
      }
    ]
  }
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

module openai './modules/ai/ai-services.bicep' = {
  name: take('module.ai-services.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    namePrefix: 'oai'
    location: location
    tags: tags
    sku: azureOpenAISkuName
    kind: 'OpenAI'
  }
}

// Model deployments (single loop for both existing and new paths)
@batchSize(1)
module model_deployments './modules/ai/ai-foundry-model-deployment.bicep' = [for (deployment, i) in defaultOpenAiDeployments: {
  name: take('module.model-deployment-${i}.${solutionName}', 64)
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
  params: {
    solutionName: solutionSuffix
    namePrefix: 'cv'
    kind: 'ComputerVision'
    location: computerVisionLocation != '' ? computerVisionLocation : location
    tags: tags
    sku: computerVisionSkuName
  }
}


module formrecognizer './modules/ai/ai-services.bicep' = {
  name: take('module.app-service-formrecognizer.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    namePrefix: 'di'
    location: location
    tags: tags
    kind: 'FormRecognizer'
  }
}

module contentsafety './modules/ai/ai-services.bicep' = {
  name: take('module.app-service-contentsafety.${solutionName}', 64)
  scope: resourceGroup()
  params: {
    solutionName: solutionSuffix
    namePrefix: 'cs'
    location: location
    tags: tags
    kind: 'ContentSafety'
  }
}

// Search Index Data Reader
module searchIndexRoleOpenai './modules/identity/role-assignments.bicep' = {
  name: 'search-index-role-openai'
  params: {
    principalId: openai.outputs.identityPrincipalId
    roleDefinitionId: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
    principalType: 'ServicePrincipal'
  }
}

// Search Service Contributor
module searchServiceRoleOpenai './modules/identity/role-assignments.bicep' = {
  name: 'search-service-role-openai'
  params: {
    principalId: openai.outputs.identityPrincipalId
    roleDefinitionId: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
    principalType: 'ServicePrincipal'
  }
}

// Storage Blob Data Reader
module blobDataReaderRoleSearch './modules/identity/role-assignments.bicep' = if (databaseType == 'CosmosDB') {
  name: 'blob-data-reader-role-search'
  params: {
    principalId: search!.outputs.identityPrincipalId
    roleDefinitionId: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services OpenAI User
module openAiRoleSearchService './modules/identity/role-assignments.bicep' = if (databaseType == 'CosmosDB') {
  name: 'openai-role-searchservice'
  params: {
    principalId: search!.outputs.identityPrincipalId
    roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    principalType: 'ServicePrincipal'
  }
}

module speechService './modules/ai/ai-services.bicep' = {
  name: take('module.ai-services.SpeechServices.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    namePrefix: 'spch'
    location: location
    tags: allTags
    sku: 'S0'
    kind: 'SpeechServices'
  }
}

module search './modules/ai/ai-search.bicep' = if (databaseType == 'CosmosDB') {
  name: take('module.ai-search.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    skuName: azureSearchSku
    semanticSearch: azureSearchUseSemanticSearch ? 'free' : 'disabled'
  }
}

module webServerFarm './modules/compute/app-service-plan.bicep' = {
  name: take('module.app-service-plan.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    skuName: hostingPlanSku
    skuCapacity: 2
    reserved: true
  }
}

var webLinuxFxVersion = hostingModel == 'container'
  ? 'DOCKER|${registryName}.azurecr.io/rag-webapp:${appversion}'
  : 'PYTHON|3.11'
module web './modules/compute/app-service.bicep' = {
  name: take('module.web.site.${websiteName}${hostingModel == 'container' ? '-docker' : ''}', 64)
  params: {
    solutionName: hostingModel == 'container' ? '${websiteName}-docker' : websiteName
    location: location
    tags: union(tags, { 'azd-service-name': 'web' })
    linuxFxVersion: webLinuxFxVersion
    serverFarmResourceId: webServerFarm.outputs.resourceId
    userAssignedIdentityId: databaseType == 'PostgreSQL' ? managedIdentityModule!.outputs.resourceId : null
    appSettings: union(
      {
        AZURE_BLOB_ACCOUNT_NAME: storage.outputs.name
        AZURE_BLOB_CONTAINER_NAME: blobContainerName
        AZURE_FORM_RECOGNIZER_ENDPOINT: formrecognizer.outputs.endpoint
        AZURE_COMPUTER_VISION_ENDPOINT: useAdvancedImageProcessing ? computerVision!.outputs.endpoint : ''
        AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_API_VERSION: computerVisionVectorizeImageApiVersion
        AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_MODEL_VERSION: computerVisionVectorizeImageModelVersion
        AZURE_CONTENT_SAFETY_ENDPOINT: contentsafety.outputs.endpoint
        AZURE_OPENAI_RESOURCE: openai.outputs.name
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
        USE_ADVANCED_IMAGE_PROCESSING: useAdvancedImageProcessing
        ADVANCED_IMAGE_PROCESSING_MAX_IMAGES: advancedImageProcessingMaxImages
        ORCHESTRATION_STRATEGY: orchestrationStrategy
        CONVERSATION_FLOW: conversationFlow
        LOGLEVEL: logLevel
        DATABASE_TYPE: databaseType
        OPEN_AI_FUNCTIONS_SYSTEM_PROMPT: openAISystemPrompts.OPEN_AI_FUNCTIONS_SYSTEM_PROMPT
        SEMENTIC_KERNEL_SYSTEM_PROMPT: openAISystemPrompts.SEMANTIC_KERNEL_SYSTEM_PROMPT
      },
      // Conditionally add database-specific settings
      databaseType == 'CosmosDB'
        ? {
            AZURE_COSMOSDB_ACCOUNT_NAME: cosmosDBModule!.outputs.name
            AZURE_COSMOSDB_DATABASE_NAME: cosmosDBModule!.outputs.databaseName
            AZURE_COSMOSDB_CONVERSATIONS_CONTAINER_NAME: cosmosDBModule!.outputs.containerName
            AZURE_COSMOSDB_ENABLE_FEEDBACK: true
            AZURE_SEARCH_USE_SEMANTIC_SEARCH: azureSearchUseSemanticSearch
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
            AZURE_SEARCH_CHUNK_COLUMN: azureSearchChunkColumn
            AZURE_SEARCH_OFFSET_COLUMN: azureSearchOffsetColumn
            AZURE_SEARCH_URL_COLUMN: azureSearchUrlColumn
            AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION: azureSearchUseIntegratedVectorization
          }
        : databaseType == 'PostgreSQL'
            ? {
                AZURE_POSTGRESQL_HOST_NAME: postgresDBModule!.outputs.serverFqdn
                AZURE_POSTGRESQL_DATABASE_NAME: postgresDBName
                AZURE_POSTGRESQL_USER: managedIdentityModule!.outputs.name
                MANAGED_IDENTITY_CLIENT_ID: managedIdentityModule!.outputs.clientId
                MANAGED_IDENTITY_RESOURCE_ID: managedIdentityModule!.outputs.resourceId
                AZURE_CLIENT_ID: managedIdentityModule!.outputs.clientId
              }
            : {}
    )
  }
}

// Storage Blob Data Contributor
module storageBlobRoleWeb './modules/identity/role-assignments.bicep' = {
  name: 'storage-blob-role-web'
  params: {
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User
module openAIRoleWeb './modules/identity/role-assignments.bicep' = {
  name: 'openai-role-web'
  params: {
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908'
    principalType: 'ServicePrincipal'
  }
}

// Contributor
module openAIRoleWebContributor './modules/identity/role-assignments.bicep' = {
  name: 'openai-role-web-contributor'
  params: {
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: 'b24988ac-6180-42a0-ab88-20f7382dd24c'
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor
module searchRoleWeb './modules/identity/role-assignments.bicep' = {
  name: 'search-role-web'
  params: {
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
    principalType: 'ServicePrincipal'
  }
}

// ----------------------------------------------------------------------------
// Cosmos DB SQL data-plane role assignments (Built-in Data Contributor)
//
// ARM `Microsoft.Authorization/roleAssignments` does NOT grant Cosmos DB
// data-plane access — operations like list/read/write on conversations are
// gated by `Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments` against
// the Cosmos SQL role definition. Without these the web/admin/function apps
// fail with: "Request is blocked: Principal does not have required RBAC
// permissions to perform action ... readMetadata ... on resource ...".
// ----------------------------------------------------------------------------
module cosmosDataRoleWeb './modules/identity/role-assignments.bicep' = if (databaseType == 'CosmosDB') {
  name: 'cosmos-data-role-web'
  params: {
    cosmosDbAccountName: databaseType == 'CosmosDB' ? cosmosDBModule!.outputs.name : ''
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: '00000000-0000-0000-0000-000000000002'
  }
}

var adminWebLinuxFxVersion = hostingModel == 'container'
  ? 'DOCKER|${registryName}.azurecr.io/rag-adminwebapp:${appversion}'
  : 'PYTHON|3.11'
module adminweb './modules/compute/app-service.bicep' = {
  name: take('module.web.site.${adminWebsiteName}${hostingModel == 'container' ? '-docker' : ''}', 64)
  params: {
    solutionName: hostingModel == 'container' ? '${adminWebsiteName}-docker' : adminWebsiteName
    location: location
    tags: union(tags, { 'azd-service-name': hostingModel == 'container' ? 'adminweb-docker' : 'adminweb' })
    linuxFxVersion: adminWebLinuxFxVersion
    serverFarmResourceId: webServerFarm.outputs.resourceId
    userAssignedIdentityId: databaseType == 'PostgreSQL' ? managedIdentityModule!.outputs.resourceId : ''
    appSettings: union(
      {
        AZURE_BLOB_ACCOUNT_NAME: storage.outputs.name
        AZURE_BLOB_CONTAINER_NAME: blobContainerName
        AZURE_FORM_RECOGNIZER_ENDPOINT: formrecognizer.outputs.endpoint
        AZURE_COMPUTER_VISION_ENDPOINT: useAdvancedImageProcessing ? computerVision!.outputs.endpoint : ''
        AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_API_VERSION: computerVisionVectorizeImageApiVersion
        AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_MODEL_VERSION: computerVisionVectorizeImageModelVersion
        AZURE_CONTENT_SAFETY_ENDPOINT: contentsafety.outputs.endpoint
        AZURE_OPENAI_RESOURCE: openai.outputs.name
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

        USE_ADVANCED_IMAGE_PROCESSING: useAdvancedImageProcessing
        BACKEND_URL: 'https://${hostingModel == 'container' ? '${functionName}-docker' : functionName}.azurewebsites.net'
        DOCUMENT_PROCESSING_QUEUE_NAME: queueName
        FUNCTION_KEY: clientKey
        ORCHESTRATION_STRATEGY: orchestrationStrategy
        CONVERSATION_FLOW: conversationFlow
        LOGLEVEL: logLevel
        DATABASE_TYPE: databaseType
      },
      // Conditionally add database-specific settings
      databaseType == 'CosmosDB'
        ? {
            AZURE_SEARCH_SERVICE: 'https://${azureAISearchName}.search.windows.net'
            AZURE_SEARCH_INDEX: azureSearchIndex
            AZURE_SEARCH_USE_SEMANTIC_SEARCH: azureSearchUseSemanticSearch
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
            AZURE_SEARCH_CHUNK_COLUMN: azureSearchChunkColumn
            AZURE_SEARCH_OFFSET_COLUMN: azureSearchOffsetColumn
            AZURE_SEARCH_URL_COLUMN: azureSearchUrlColumn
            AZURE_SEARCH_DATASOURCE_NAME: azureSearchDatasource
            AZURE_SEARCH_INDEXER_NAME: azureSearchIndexer
            AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION: azureSearchUseIntegratedVectorization
          }
        : databaseType == 'PostgreSQL'
            ? {
                AZURE_POSTGRESQL_HOST_NAME: postgresDBModule!.outputs.serverFqdn
                AZURE_POSTGRESQL_DATABASE_NAME: postgresDBName
                AZURE_POSTGRESQL_USER: managedIdentityModule!.outputs.name
                MANAGED_IDENTITY_CLIENT_ID: managedIdentityModule!.outputs.clientId
                MANAGED_IDENTITY_RESOURCE_ID: managedIdentityModule!.outputs.resourceId
              }
            : {}
    )
  }
}

// Storage Blob Data Contributor
module storageRoleBackend './modules/identity/role-assignments.bicep' = {
  name: 'storage-role-backend'
  params: {
    principalId: adminweb.outputs.identityPrincipalId
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User
module openAIRoleBackend './modules/identity/role-assignments.bicep' = {
  name: 'openai-role-backend'
  params: {
    principalId: adminweb.outputs.identityPrincipalId
    roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908'
    principalType: 'ServicePrincipal'
  }
}

// Contributor
// This role is used to grant the service principal contributor access to the resource group
// See if this is needed in the future.
module openAIRoleBackendContributor './modules/identity/role-assignments.bicep' = {
  name: 'openai-role-backend-contributor'
  params: {
    principalId: adminweb.outputs.identityPrincipalId
    roleDefinitionId: 'b24988ac-6180-42a0-ab88-20f7382dd24c'
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor
module searchRoleBackend './modules/identity/role-assignments.bicep' = {
  name: 'search-role-backend'
  params: {
    principalId: adminweb.outputs.identityPrincipalId
    roleDefinitionId: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB SQL data-plane role for the admin web app (see rationale above).
module cosmosDataRoleAdminWeb './modules/identity/role-assignments.bicep' = if (databaseType == 'CosmosDB') {
  name: 'cosmos-data-role-adminweb'
  params: {
    cosmosDbAccountName: databaseType == 'CosmosDB' ? cosmosDBModule!.outputs.name : ''
    principalId: adminweb.outputs.identityPrincipalId
    roleDefinitionId: '00000000-0000-0000-0000-000000000002'
  }
}

module function './modules/compute/function-app.bicep' = {
  name: hostingModel == 'container' ? '${functionName}-docker' : functionName
  params: {
    name: hostingModel == 'container' ? '${functionName}-docker' : functionName
    location: location
    tags: union(tags, { 'azd-service-name': 'function' })
    kind: hostingModel == 'container' ? 'functionapp,linux,container' : 'functionapp,linux'
    runtimeStack: 'python'
    runtimeVersion: '3.11'
    dockerFullImageName: hostingModel == 'container' ? '${registryName}.azurecr.io/rag-backend:${appversion}' : ''
    serverFarmResourceId: webServerFarm.outputs.resourceId
    userAssignedIdentityId: databaseType == 'PostgreSQL' ? managedIdentityModule!.outputs.resourceId : ''
    userAssignedIdentityClientId: databaseType == 'PostgreSQL' ? managedIdentityModule!.outputs.clientId : ''
    applicationInsightsName: enableMonitoring ? app_insights!.outputs.name : ''
    storageAccountName: storage.outputs.name
    appSettings: union(
      {
        AZURE_BLOB_ACCOUNT_NAME: storage.outputs.name
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
        AZURE_OPENAI_RESOURCE: openai.outputs.name
        AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
        USE_ADVANCED_IMAGE_PROCESSING: useAdvancedImageProcessing ? 'true' : 'false'
        DOCUMENT_PROCESSING_QUEUE_NAME: queueName
        ORCHESTRATION_STRATEGY: orchestrationStrategy
        LOGLEVEL: logLevel
        PACKAGE_LOGGING_LEVEL: 'WARNING'
        AZURE_LOGGING_PACKAGES: ''
        AZURE_OPENAI_SYSTEM_MESSAGE: azureOpenAISystemMessage
        DATABASE_TYPE: databaseType
        APP_ENV: appEnvironment
        BACKEND_URL: backendUrl
        AZURE_SEARCH_DIMENSIONS: azureSearchDimensions
        APPLICATIONINSIGHTS_ENABLED: enableMonitoring ? 'true' : 'false'
      },
      // Conditionally add database-specific settings
      databaseType == 'CosmosDB'
        ? {
            AZURE_SEARCH_INDEX: azureSearchIndex
            AZURE_SEARCH_SERVICE: 'https://${azureAISearchName}.search.windows.net'
            AZURE_SEARCH_DATASOURCE_NAME: azureSearchDatasource
            AZURE_SEARCH_INDEXER_NAME: azureSearchIndexer
            AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION: azureSearchUseIntegratedVectorization
            AZURE_SEARCH_FIELDS_ID: azureSearchFieldId
            AZURE_SEARCH_CONTENT_COLUMN: azureSearchContentColumn
            AZURE_SEARCH_CONTENT_VECTOR_COLUMN: azureSearchVectorColumn
            AZURE_SEARCH_TITLE_COLUMN: azureSearchTitleColumn
            AZURE_SEARCH_FIELDS_METADATA: azureSearchFieldsMetadata
            AZURE_SEARCH_SOURCE_COLUMN: azureSearchSourceColumn
            AZURE_SEARCH_CHUNK_COLUMN: azureSearchChunkColumn
            AZURE_SEARCH_OFFSET_COLUMN: azureSearchOffsetColumn
            AZURE_SEARCH_TOP_K: azureSearchTopK
          }
        : databaseType == 'PostgreSQL'
            ? {
                AZURE_POSTGRESQL_HOST_NAME: postgresDBModule!.outputs.serverFqdn
                AZURE_POSTGRESQL_DATABASE_NAME: postgresDBName
                AZURE_POSTGRESQL_USER: managedIdentityModule!.outputs.name
                MANAGED_IDENTITY_CLIENT_ID: managedIdentityModule!.outputs.clientId
                MANAGED_IDENTITY_RESOURCE_ID: managedIdentityModule!.outputs.resourceId
                AZURE_CLIENT_ID: managedIdentityModule!.outputs.clientId
              }
            : {}
    )
  }
}

// Cognitive Services User
module openAIRoleFunction './modules/identity/role-assignments.bicep' = {
  name: 'openai-role-function'
  params: {
    principalId: function!.outputs.principalId
    roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908'
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services OpenAI User — required for data-plane calls against the OpenAI account
// when local auth is disabled. Cognitive Services User alone does not grant the OpenAI
// dataActions (e.g. openai/deployments/*/completions/action).
module openAIDataRoleWeb './modules/identity/role-assignments.bicep' = {
  name: 'openai-data-role-web'
  params: {
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    principalType: 'ServicePrincipal'
  }
}

module openAIDataRoleAdmin './modules/identity/role-assignments.bicep' = {
  name: 'openai-data-role-admin'
  params: {
    principalId: adminweb.outputs.identityPrincipalId
    roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    principalType: 'ServicePrincipal'
  }
}

module openAIDataRoleFunction './modules/identity/role-assignments.bicep' = {
  name: 'openai-data-role-function'
  params: {
    principalId: function!.outputs.principalId
    roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    principalType: 'ServicePrincipal'
  }
}

// User-assigned managed identity (used by the apps via AZURE_CLIENT_ID in PostgreSQL mode)
// needs the same Cognitive Services + OpenAI data-plane access as the system-assigned MIs;
// otherwise DefaultAzureCredential picks the user-assigned identity and calls to Document
// Intelligence / Content Safety / OpenAI fail with PermissionDenied.
module cognitiveServicesUserRoleManagedIdentity './modules/identity/role-assignments.bicep' = if (databaseType == 'PostgreSQL') {
  name: 'cognitive-services-role-managed-identity'
  params: {
    principalId: managedIdentityModule!.outputs.principalId
    roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908'
    principalType: 'ServicePrincipal'
  }
}

module openAIDataRoleManagedIdentity './modules/identity/role-assignments.bicep' = if (databaseType == 'PostgreSQL') {
  name: 'openai-data-role-managed-identity'
  params: {
    principalId: managedIdentityModule!.outputs.principalId
    roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    principalType: 'ServicePrincipal'
  }
}

// Contributor
// This role is used to grant the service principal contributor access to the resource group
// See if this is needed in the future.
module openAIRoleFunctionContributor './modules/identity/role-assignments.bicep' = {
  name: 'openai-role-function-contributor'
  params: {
    principalId: function!.outputs.principalId
    roleDefinitionId: 'b24988ac-6180-42a0-ab88-20f7382dd24c'
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor
module searchRoleFunction './modules/identity/role-assignments.bicep' = {
  name: 'search-role-function'
  params: {
    principalId: function!.outputs.principalId
    roleDefinitionId: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
    principalType: 'ServicePrincipal'
  }
}

// Storage Blob Data Contributor
module storageBlobRoleFunction './modules/identity/role-assignments.bicep' = {
  name: 'storage-blob-role-function'
  params: {
    principalId: databaseType == 'PostgreSQL' ? managedIdentityModule!.outputs.principalId : function!.outputs.principalId
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    principalType: 'ServicePrincipal'
  }
}

// Storage Queue Data Contributor
module storageQueueRoleFunction './modules/identity/role-assignments.bicep' = {
  name: 'storage-queue-role-function'
  params: {
    principalId: databaseType == 'PostgreSQL' ? managedIdentityModule!.outputs.principalId : function!.outputs.principalId
    roleDefinitionId: '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB SQL data-plane role for the function app (see rationale above).
module cosmosDataRoleFunction './modules/identity/role-assignments.bicep' = if (databaseType == 'CosmosDB') {
  name: 'cosmos-data-role-function'
  params: {
    cosmosDbAccountName: databaseType == 'CosmosDB' ? cosmosDBModule!.outputs.name : ''
    principalId: function!.outputs.principalId
    roleDefinitionId: '00000000-0000-0000-0000-000000000002'
  }
}

var wookbookContents = loadTextContent('../workbooks/workbook.json')
var wookbookContentsSubReplaced = replace(wookbookContents, '{subscription-id}', subscription().id)
var wookbookContentsRGReplaced = replace(wookbookContentsSubReplaced, '{resource-group}', resourceGroup().name)
var wookbookContentsAppServicePlanReplaced = replace(wookbookContentsRGReplaced, '{app-service-plan}', webServerFarm.outputs.name)
var wookbookContentsBackendAppServiceReplaced = replace(
  wookbookContentsAppServicePlanReplaced,
  '{backend-app-service}',
  function!.outputs.name
)
var wookbookContentsWebAppServiceReplaced = replace(
  wookbookContentsBackendAppServiceReplaced,
  '{web-app-service}',
  web.outputs.name
)
var wookbookContentsAdminAppServiceReplaced = replace(
  wookbookContentsWebAppServiceReplaced,
  '{admin-app-service}',
  adminweb.outputs.name
)
var wookbookContentsEventGridReplaced = replace(
  wookbookContentsAdminAppServiceReplaced,
  '{event-grid}',
  avmEventGridSystemTopic!.outputs.name
)
var wookbookContentsLogAnalyticsReplaced = replace(
  wookbookContentsEventGridReplaced,
  '{log-analytics-resource-id}',
  enableMonitoring ? log_analytics!.outputs.resourceId : ''
)
var wookbookContentsOpenAIReplaced = replace(wookbookContentsLogAnalyticsReplaced, '{open-ai}', openai.outputs.name)
var wookbookContentsAISearchReplaced = replace(wookbookContentsOpenAIReplaced, '{ai-search}', search!.outputs.name)
var wookbookContentsStorageAccountReplaced = replace(
  wookbookContentsAISearchReplaced,
  '{storage-account}',
  storage.outputs.name
)
module workbook './modules/monitoring/workbook.bicep' = if (enableMonitoring) {
  name: take('module.monitoring.workbook.${solutionName}', 64)
  scope: resourceGroup()
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    serializedData: wookbookContentsStorageAccountReplaced
  }
}

module avmEventGridSystemTopic './modules/data/event-grid.bicep' = {
  name: take('module.app-service-eventgrid.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    source: storage.outputs.resourceId
    topicType: 'Microsoft.Storage.StorageAccounts'
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
  }
}

module storage './modules/data/storage-account.bicep' = {
  name: take('module.storage-account.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    skuName: 'Standard_GRS'
    deleteRetentionPolicy: azureSearchUseIntegratedVectorization
      ? {
          enabled: true
          days: 7
        }
      : {}
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
    queues: [
      {
        name: 'doc-processing'
      }
      {
        name: 'doc-processing-poison'
      }
    ]
  }
}

// USER ROLES
// Storage Blob Data Contributor
module storageRoleUser './modules/identity/role-assignments.bicep' = if (principal.id != '') {
  name: 'storage-role-user'
  params: {
    principalId: principal.id
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    principalType: 'User'
  }
}

// Cognitive Services User
module openaiRoleUser './modules/identity/role-assignments.bicep' = if (principal.id != '') {
  name: 'openai-role-user'
  params: {
    principalId: principal.id
    roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908'
    principalType: 'User'
  }
}

// Contributor
module openaiRoleUserContributor './modules/identity/role-assignments.bicep' = if (principal.id != '') {
  name: 'openai-role-user-contributor'
  params: {
    principalId: principal.id
    roleDefinitionId: 'b24988ac-6180-42a0-ab88-20f7382dd24c'
    principalType: 'User'
  }
}

// Search Index Data Contributor
module searchRoleUser './modules/identity/role-assignments.bicep' = if (principal.id != '' && databaseType == 'CosmosDB') {
  name: 'search-role-user'
  params: {
    principalId: principal.id
    roleDefinitionId: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
    principalType: 'User'
  }
}

// Cosmos DB SQL data-plane role for the deploying user — enables local
// development and Data Explorer queries when local auth is disabled.
module cosmosDataRoleUser './modules/identity/role-assignments.bicep' = if (principal.id != '' && databaseType == 'CosmosDB') {
  name: 'cosmos-data-role-user'
  params: {
    cosmosDbAccountName: databaseType == 'CosmosDB' ? cosmosDBModule!.outputs.name : ''
    principalId: principal.id
    roleDefinitionId: '00000000-0000-0000-0000-000000000002'
    principalType: 'User'
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
  account_name: databaseType == 'CosmosDB' ? cosmosDBModule!.outputs.name : ''
  database_name: databaseType == 'CosmosDB' ? cosmosDBModule!.outputs.databaseName : ''
  conversations_container_name: databaseType == 'CosmosDB' ? cosmosDBModule!.outputs.containerName : ''
})

var azurePostgresDBInfo = string({
  host_name: databaseType == 'PostgreSQL' ? postgresDBModule!.outputs.serverFqdn : ''
  database_name: databaseType == 'PostgreSQL' ? 'postgres' : ''
  user: ''
})

var azureFormRecognizerInfo = string({
  endpoint: formrecognizer.outputs.endpoint
})

var azureBlobStorageInfo = string({
  container_name: blobContainerName
  account_name: storage.outputs.name
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
  service_name: speechService.outputs.name
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
  resource: openai.outputs.name
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
output SERVICE_FUNCTION_RESOURCE_NAME string = function!.outputs.name

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
