targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@description('provide a 2-13 character prefix for all resources.')
param ResourcePrefix string = environmentName

@description('Location for all resources.')
param Location string

@description('Name of App Service plan')
param HostingPlanName string = '${ResourcePrefix}-hosting-plan'

@description('The pricing tier for the App Service plan')
@allowed([
  'F1'
  'D1'
  'B1'
  'B2'
  'B3'
  'S1'
  'S2'
  'S3'
  'P1'
  'P2'
  'P3'
  'P4'
])
param HostingPlanSku string = 'B3'

@description('Name of Web App')
param WebsiteName string = '${ResourcePrefix}-website'

@description('Name of Application Insights')
param ApplicationInsightsName string = '${ResourcePrefix}-appinsights'

@description('Use semantic search')
param AzureSearchUseSemanticSearch string = 'false'

@description('Semantic search config')
param AzureSearchSemanticSearchConfig string = 'default'

@description('Is the index prechunked')
param AzureSearchIndexIsPrechunked string = 'false'

@description('Top K results')
param AzureSearchTopK string = '5'

@description('Enable in domain')
param AzureSearchEnableInDomain string = 'false'

@description('Content columns')
param AzureSearchContentColumns string = 'content'

@description('Filename column')
param AzureSearchFilenameColumn string = 'filename'

@description('Title column')
param AzureSearchTitleColumn string = 'title'

@description('Url column')
param AzureSearchUrlColumn string = 'url'

@description('Name of Azure OpenAI Resource')
param AzureOpenAIResource string = '${ResourcePrefix}-openai'

@description('Name of Azure OpenAI Resource SKU')
param AzureOpenAISkuName string = 'S0'

@description('Azure OpenAI Model Deployment Name')
param AzureOpenAIModel string = 'gpt-35-turbo'

@description('Azure OpenAI Model Name')
param AzureOpenAIModelName string = 'gpt-35-turbo'

param AzureOpenAIModelVersion string = '0613'

@description('Orchestration strategy: openai_function or langchain str. If you use a old version of turbo (0301), plese select langchain')
@allowed([
  'openai_function'
  'langchain'
])
param OrchestrationStrategy string = 'langchain'

@description('Azure OpenAI Temperature')
param AzureOpenAITemperature string = '0'

@description('Azure OpenAI Top P')
param AzureOpenAITopP string = '1'

@description('Azure OpenAI Max Tokens')
param AzureOpenAIMaxTokens string = '1000'

@description('Azure OpenAI Stop Sequence')
param AzureOpenAIStopSequence string = '\n'

@description('Azure OpenAI System Message')
param AzureOpenAISystemMessage string = 'You are an AI assistant that helps people find information.'

@description('Azure OpenAI Api Version')
param AzureOpenAIApiVersion string = '2023-07-01-preview'

@description('Whether or not to stream responses from Azure OpenAI')
param AzureOpenAIStream string = 'true'

@description('Azure OpenAI Embedding Model Deployment Name')
param AzureOpenAIEmbeddingModel string = 'text-embedding-ada-002'

@description('Azure OpenAI Embedding Model Name')
param AzureOpenAIEmbeddingModelName string = 'text-embedding-ada-002'

@description('Azure Cognitive Search Resource')
param AzureCognitiveSearch string = '${ResourcePrefix}-search'

@description('The SKU of the search service you want to create. E.g. free or standard')
@allowed([
  'free'
  'basic'
  'standard'
  'standard2'
  'standard3'
])
param AzureCognitiveSearchSku string = 'standard'

@description('Azure Cognitive Search Index')
param AzureSearchIndex string = '${ResourcePrefix}-index'

@description('Azure Cognitive Search Conversation Log Index')
param AzureSearchConversationLogIndex string = 'conversations'

@description('Name of Storage Account')
param StorageAccountName string = '${ResourcePrefix}str'

@description('Name of Function App for Batch document processing')
param FunctionName string = '${ResourcePrefix}-backend'

@description('Azure Form Recognizer Name')
param FormRecognizerName string = '${ResourcePrefix}-formrecog'

@description('Azure Content Safety Name')
param ContentSafetyName string = '${ResourcePrefix}-contentsafety'
param newGuidString string = newGuid()

var BlobContainerName = 'documents'
var QueueName = 'doc-processing'
var ClientKey = '${uniqueString(guid(subscription().id, deployment().name))}${newGuidString}'
var EventGridSystemTopicName = 'doc-processing'
var tags = { 'azd-env-name': environmentName }

resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-${ResourcePrefix}'
  location: Location
  tags: tags
}

module OpenAI 'core/ai/cognitiveservices.bicep' = {
  name: 'openai'
  scope: rg
  params: {
    name: AzureOpenAIResource
    location: Location
    tags: tags
    sku: {
      name: AzureOpenAISkuName
    }
    deployments: [
      {
        name: AzureOpenAIModel
        model: {
          format: 'OpenAI'
          name: AzureOpenAIModelName
          version: AzureOpenAIModelVersion
        }
        sku: {
          name: 'Standard'
          capacity: 30
        }
      }
      {
        name: AzureOpenAIEmbeddingModel
        model: {
          format: 'OpenAI'
          name: AzureOpenAIEmbeddingModelName
          version: '2'
        }
        capacity: 30
      }
    ]
  }
}

module AzureCognitiveSearch_resource './core/search/search-services.bicep' = {
  name: AzureCognitiveSearch
  scope: rg
  params:{
    name: AzureCognitiveSearch
    location: Location
    tags: {
      deployment : 'chatwithyourdata-sa'
    }
    sku: {
      name: AzureCognitiveSearchSku
    }
  }
}

module Other_Resources './app/resources.bicep' = {
  name: 'AllResources'
  scope: rg
  params: {
    FormRecognizerName: FormRecognizerName
    ContentSafetyName: ContentSafetyName
    Location: Location
    EventGridSystemTopicName: EventGridSystemTopicName
    StorageAccountId: StorageAccount.outputs.StorageAccountId
    QueueName: StorageAccount.outputs.StorageAccountName_default_doc_processing_name
    BlobContainerName: BlobContainerName
  }
}

module HostingPlan './core/host/appserviceplan.bicep' = {
  name: HostingPlanName
  scope: rg
  params: {
    name: HostingPlanName
    location: Location
    sku: {
      name: HostingPlanSku
    }
    kind: 'linux'
    reserved: true
  }
}

module web './app/web.bicep' = {
  name: WebsiteName
  scope: rg
  params: {
    name: WebsiteName
    location: Location
    tags: { 'azd-service-name': 'web' }
    appServicePlanId: HostingPlanName
    StorageAccountName: StorageAccountName
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    AzureOpenAIName: OpenAI.outputs.name
    AzureCognitiveSearchName: AzureCognitiveSearch
    FormRecognizerName: FormRecognizerName
    ContentSafetyName: ContentSafetyName
    appSettings: {
      AZURE_SEARCH_SERVICE: 'https://${AzureCognitiveSearch}.search.windows.net'
      AZURE_SEARCH_INDEX: AzureSearchIndex
      AZURE_SEARCH_CONVERSATIONS_LOG_INDEX: AzureSearchConversationLogIndex
      AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG: AzureSearchSemanticSearchConfig
      AZURE_SEARCH_INDEX_IS_PRECHUNKED: AzureSearchIndexIsPrechunked
      AZURE_SEARCH_TOP_K: AzureSearchTopK
      AZURE_SEARCH_ENABLE_IN_DOMAIN: AzureSearchEnableInDomain
      AZURE_SEARCH_CONTENT_COLUMNS: AzureSearchContentColumns
      AZURE_SEARCH_FILENAME_COLUMN: AzureSearchFilenameColumn
      AZURE_SEARCH_TITLE_COLUMN: AzureSearchTitleColumn
      AZURE_SEARCH_URL_COLUMN: AzureSearchUrlColumn
      AZURE_OPENAI_RESOURCE: AzureOpenAIResource
      AZURE_OPENAI_MODEL: AzureOpenAIModel
      AZURE_OPENAI_MODEL_NAME: AzureOpenAIModelName
      AZURE_OPENAI_TEMPERATURE: AzureOpenAITemperature
      AZURE_OPENAI_TOP_P: AzureOpenAITopP
      AZURE_OPENAI_MAX_TOKENS: AzureOpenAIMaxTokens
      AZURE_OPENAI_STOP_SEQUENCE: AzureOpenAIStopSequence
      AZURE_OPENAI_SYSTEM_MESSAGE: AzureOpenAISystemMessage
      AZURE_OPENAI_API_VERSION: AzureOpenAIApiVersion
      AZURE_OPENAI_STREAM: AzureOpenAIStream
      AZURE_OPENAI_EMBEDDING_MODEL: AzureOpenAIEmbeddingModel
      AZURE_FORM_RECOGNIZER_ENDPOINT: 'https://${Location}.api.cognitive.microsoft.com/'
      AZURE_BLOB_ACCOUNT_NAME: StorageAccountName
      AZURE_BLOB_CONTAINER_NAME: BlobContainerName
      ORCHESTRATION_STRATEGY: OrchestrationStrategy
      AZURE_CONTENT_SAFETY_ENDPOINT: 'https://${Location}.api.cognitive.microsoft.com/'
    }
  }
  dependsOn:[
    HostingPlan
    StorageAccount
    monitoring
    OpenAI
  ]
}

module adminweb './app/adminweb.bicep' = {
  name: '${WebsiteName}-admin'
  scope: rg
  params: {
    name: '${WebsiteName}-admin'
    location: Location
    tags: { 'azd-service-name': 'adminweb' }
    appServicePlanId: HostingPlanName
    StorageAccountName: StorageAccountName
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    AzureOpenAIName: OpenAI.outputs.name
    AzureCognitiveSearchName: AzureCognitiveSearch
    FormRecognizerName: FormRecognizerName
    ContentSafetyName: ContentSafetyName
    appSettings: {
      AZURE_SEARCH_SERVICE: 'https://${AzureCognitiveSearch}.search.windows.net'
      AZURE_SEARCH_INDEX: AzureSearchIndex
      AZURE_SEARCH_USE_SEMANTIC_SEARCH: AzureSearchUseSemanticSearch
      AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG: AzureSearchSemanticSearchConfig
      AZURE_SEARCH_INDEX_IS_PRECHUNKED: AzureSearchIndexIsPrechunked
      AZURE_SEARCH_TOP_K: AzureSearchTopK
      AZURE_SEARCH_ENABLE_IN_DOMAIN: AzureSearchEnableInDomain
      AZURE_SEARCH_CONTENT_COLUMNS: AzureSearchContentColumns
      AZURE_SEARCH_FILENAME_COLUMN: AzureSearchFilenameColumn
      AZURE_SEARCH_TITLE_COLUMN: AzureSearchTitleColumn
      AZURE_SEARCH_URL_COLUMN: AzureSearchUrlColumn
      AZURE_OPENAI_RESOURCE: AzureOpenAIResource
      AZURE_OPENAI_MODEL: AzureOpenAIModel
      AZURE_OPENAI_MODEL_NAME: AzureOpenAIModelName
      AZURE_OPENAI_TEMPERATURE: AzureOpenAITemperature
      AZURE_OPENAI_TOP_P: AzureOpenAITopP
      AZURE_OPENAI_MAX_TOKENS: AzureOpenAIMaxTokens
      AZURE_OPENAI_STOP_SEQUENCE: AzureOpenAIStopSequence
      AZURE_OPENAI_SYSTEM_MESSAGE: AzureOpenAISystemMessage
      AZURE_OPENAI_API_VERSION: AzureOpenAIApiVersion
      AZURE_OPENAI_STREAM: AzureOpenAIStream
      AZURE_OPENAI_EMBEDDING_MODEL: AzureOpenAIEmbeddingModel
      AZURE_FORM_RECOGNIZER_ENDPOINT: 'https://${Location}.api.cognitive.microsoft.com/'
      AZURE_BLOB_ACCOUNT_NAME: StorageAccountName
      AZURE_BLOB_CONTAINER_NAME: BlobContainerName
      DOCUMENT_PROCESSING_QUEUE_NAME: QueueName
      BACKEND_URL: 'https://${FunctionName}.azurewebsites.net'
      FUNCTION_KEY: ClientKey
      ORCHESTRATION_STRATEGY: OrchestrationStrategy
      AZURE_CONTENT_SAFETY_ENDPOINT: 'https://${Location}.api.cognitive.microsoft.com/'
    }
  }
  dependsOn:[
    HostingPlan
    StorageAccount
    monitoring
    OpenAI
  ]
}

module StorageAccount './app/storage.bicep' = {
  name: 'Storage_Account'
  scope: rg
  params: {
    StorageAccountName: StorageAccountName
    Location: Location
    BlobContainerName: BlobContainerName
  }
}

module monitoring './core/monitor/monitoring.bicep' = {
  name: 'monitoring'
  scope: rg
  params: {
    applicationInsightsName: ApplicationInsightsName
    location: Location
    tags: {
      'hidden-link:${resourceId('Microsoft.Web/sites', ApplicationInsightsName)}': 'Resource'
    }
    logAnalyticsName: '${ResourcePrefix}-logAnalytics'
    applicationInsightsDashboardName: 'dash-${ApplicationInsightsName}'
  }
}

module function './app/function.bicep' = {
  name: FunctionName
  scope: rg
  params:{
    name: FunctionName
    location: Location
    tags: { 'azd-service-name': 'function' }
    appServicePlanId: HostingPlanName
    storageAccountName: StorageAccountName
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    AzureOpenAIName: OpenAI.outputs.name
    AzureCognitiveSearchName: AzureCognitiveSearch
    FormRecognizerName: FormRecognizerName
    ContentSafetyName: ContentSafetyName
    runtimeName:'python'
    runtimeVersion:'3.11'
    ClientKey: ClientKey
    appSettings: {
      FUNCTIONS_EXTENSION_VERSION: '~4'
      WEBSITES_ENABLE_APP_SERVICE_STORAGE: 'false'
      AZURE_OPENAI_MODEL: AzureOpenAIModel
      AZURE_OPENAI_EMBEDDING_MODEL: AzureOpenAIEmbeddingModel
      AZURE_OPENAI_RESOURCE: AzureOpenAIResource
      AZURE_BLOB_ACCOUNT_NAME: StorageAccountName
      AZURE_BLOB_CONTAINER_NAME: BlobContainerName
      AZURE_FORM_RECOGNIZER_ENDPOINT: 'https://${Location}.api.cognitive.microsoft.com/'
      AZURE_SEARCH_SERVICE: 'https://${AzureCognitiveSearch}.search.windows.net'
      DOCUMENT_PROCESSING_QUEUE_NAME: QueueName
      AZURE_OPENAI_API_VERSION: AzureOpenAIApiVersion
      AZURE_SEARCH_INDEX: AzureSearchIndex
      ORCHESTRATION_STRATEGY: OrchestrationStrategy
      AZURE_CONTENT_SAFETY_ENDPOINT: 'https://${Location}.api.cognitive.microsoft.com/'
    }
  }
  dependsOn:[
    StorageAccount
    HostingPlan
    monitoring
    OpenAI
  ]
}
