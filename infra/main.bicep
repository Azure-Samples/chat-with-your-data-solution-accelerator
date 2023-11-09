targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

param resourceToken string = toLower(uniqueString(subscription().id, environmentName, location))

@description('Location for all resources.')
param location string

@description('Name of App Service plan')
param hostingPlanName string = '${environmentName}-hosting-plan-${resourceToken}'

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
param hostingPlanSku string = 'B3'

@description('Name of Web App')
param websiteName string = '${environmentName}-website-${resourceToken}'

@description('Name of Application Insights')
param applicationInsightsName string = '${environmentName}-appinsights-${resourceToken}'

@description('Use semantic search')
param azureSearchUseSemanticSearch string = 'false'

@description('Semantic search config')
param azureSearchSemanticSearchConfig string = 'default'

@description('Is the index prechunked')
param azureSearchIndexIsPrechunked string = 'false'

@description('Top K results')
param azureSearchTopK string = '5'

@description('Enable in domain')
param azureSearchEnableInDomain string = 'false'

@description('Content columns')
param azureSearchContentColumns string = 'content'

@description('Filename column')
param azureSearchFilenameColumn string = 'filename'

@description('Title column')
param azureSearchTitleColumn string = 'title'

@description('Url column')
param azureSearchUrlColumn string = 'url'

@description('Name of Azure OpenAI Resource')
param azureOpenAIResource string = '${environmentName}-openai-${resourceToken}'

@description('Name of Azure OpenAI Resource SKU')
param azureOpenAISkuName string = 'S0'

@description('Azure OpenAI Model Deployment Name')
param azureOpenAIModel string = 'gpt-35-turbo'

@description('Azure OpenAI Model Name')
param azureOpenAIModelName string = 'gpt-35-turbo'

param azureOpenAIModelVersion string = '0613'

@description('Orchestration strategy: openai_function or langchain str. If you use a old version of turbo (0301), plese select langchain')
@allowed([
  'openai_function'
  'langchain'
])
param orchestrationStrategy string = 'langchain'

@description('Azure OpenAI Temperature')
param azureOpenAITemperature string = '0'

@description('Azure OpenAI Top P')
param azureOpenAITopP string = '1'

@description('Azure OpenAI Max Tokens')
param azureOpenAIMaxTokens string = '1000'

@description('Azure OpenAI Stop Sequence')
param azureOpenAIStopSequence string = '\n'

@description('Azure OpenAI System Message')
param azureOpenAISystemMessage string = 'You are an AI assistant that helps people find information.'

@description('Azure OpenAI Api Version')
param azureOpenAIApiVersion string = '2023-07-01-preview'

@description('Whether or not to stream responses from Azure OpenAI')
param azureOpenAIStream string = 'true'

@description('Azure OpenAI Embedding Model Deployment Name')
param azureOpenAIEmbeddingModel string = 'text-embedding-ada-002'

@description('Azure OpenAI Embedding Model Name')
param azureOpenAIEmbeddingModelName string = 'text-embedding-ada-002'

@description('Azure Cognitive Search Resource')
param azureCognitiveSearchName string = '${environmentName}-search-${resourceToken}'

@description('The SKU of the search service you want to create. E.g. free or standard')
@allowed([
  'free'
  'basic'
  'standard'
  'standard2'
  'standard3'
])
param azureCognitiveSearchSku string = 'standard'

@description('Azure Cognitive Search Index')
param azureSearchIndex string = '${environmentName}-index-${resourceToken}'

@description('Azure Cognitive Search Conversation Log Index')
param azureSearchConversationLogIndex string = 'conversations'

@description('Name of Storage Account')
param storageAccountName string = '${environmentName}str'

@description('Name of Function App for Batch document processing')
param functionName string = '${environmentName}-backend-${resourceToken}'

@description('Azure Form Recognizer Name')
param formRecognizerName string = '${environmentName}-formrecog-${resourceToken}'

@description('Azure Content Safety Name')
param contentSafetyName string = '${environmentName}-contentsafety-${resourceToken}'
param newGuidString string = newGuid()
param searchTag string = 'chatwithyourdata-sa'

var blobContainerName = 'documents'
var queueName = 'doc-processing'
var clientKey = '${uniqueString(guid(subscription().id, deployment().name))}${newGuidString}'
var eventGridSystemTopicName = 'doc-processing'
var tags = { 'azd-env-name': environmentName }


resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module openai 'core/ai/cognitiveservices.bicep' = {
  name: 'openai'
  scope: rg
  params: {
    name: azureOpenAIResource
    location: location
    tags: tags
    sku: {
      name: azureOpenAISkuName
    }
    deployments: [
      {
        name: azureOpenAIModel
        model: {
          format: 'OpenAI'
          name: azureOpenAIModelName
          version: azureOpenAIModelVersion
        }
        sku: {
          name: 'Standard'
          capacity: 30
        }
      }
      {
        name: azureOpenAIEmbeddingModel
        model: {
          format: 'OpenAI'
          name: azureOpenAIEmbeddingModelName
          version: '2'
        }
        capacity: 30
      }
    ]
  }
}

module search './core/search/search-services.bicep' = {
  name: azureCognitiveSearchName
  scope: rg
  params:{
    name: azureCognitiveSearchName
    location: location
    tags: { 
      deployment : searchTag
    }
    sku: {
      name: azureCognitiveSearchSku
    }
  }
}

module resources './app/resources.bicep' = {
  name: 'resource'
  scope: rg
  params: {
    formRecognizerName: formRecognizerName
    contentSafetyName: contentSafetyName
    location: location
    eventGridSystemTopicName: eventGridSystemTopicName
    storageAccountId: storage.outputs.STORAGE_ACCOUNT_ID
    queueName: storage.outputs.STORAGE_ACCOUNT_NAME_DEFAULT_DOC_PROCESSING_NAME
    blobContainerName: blobContainerName
  }
}

module hostingplan './core/host/appserviceplan.bicep' = {
  name: hostingPlanName
  scope: rg
  params: {
    name: hostingPlanName
    location: location
    sku: {
      name: hostingPlanSku
    }
    reserved: true
  }
}

module web './app/web.bicep' = {
  name: websiteName
  scope: rg
  params: {
    name: websiteName
    location: location
    tags: { 'azd-service-name': 'web' }
    appServicePlanId: hostingplan.outputs.name
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    azureOpenAIName: openai.outputs.name
    azureCognitiveSearchName: azureCognitiveSearchName
    appSettings: {
      AZURE_SEARCH_SERVICE: 'https://${azureCognitiveSearchName}.search.windows.net'
      AZURE_SEARCH_INDEX: azureSearchIndex
      AZURE_SEARCH_CONVERSATIONS_LOG_INDEX: azureSearchConversationLogIndex
      AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG: azureSearchSemanticSearchConfig
      AZURE_SEARCH_INDEX_IS_PRECHUNKED: azureSearchIndexIsPrechunked
      AZURE_SEARCH_TOP_K: azureSearchTopK
      AZURE_SEARCH_ENABLE_IN_DOMAIN: azureSearchEnableInDomain
      AZURE_SEARCH_CONTENT_COLUMNS: azureSearchContentColumns
      AZURE_SEARCH_FILENAME_COLUMN: azureSearchFilenameColumn
      AZURE_SEARCH_TITLE_COLUMN: azureSearchTitleColumn
      AZURE_SEARCH_URL_COLUMN: azureSearchUrlColumn
      AZURE_OPENAI_RESOURCE: azureOpenAIResource
      AZURE_OPENAI_MODEL: azureOpenAIModel
      AZURE_OPENAI_MODEL_NAME: azureOpenAIModelName
      AZURE_OPENAI_TEMPERATURE: azureOpenAITemperature
      AZURE_OPENAI_TOP_P: azureOpenAITopP
      AZURE_OPENAI_MAX_TOKENS: azureOpenAIMaxTokens
      AZURE_OPENAI_STOP_SEQUENCE: azureOpenAIStopSequence
      AZURE_OPENAI_SYSTEM_MESSAGE: azureOpenAISystemMessage
      AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
      AZURE_OPENAI_STREAM: azureOpenAIStream
      AZURE_OPENAI_EMBEDDING_MODEL: azureOpenAIEmbeddingModel
      AZURE_FORM_RECOGNIZER_ENDPOINT: 'https://${location}.api.cognitive.microsoft.com/'
      AZURE_BLOB_ACCOUNT_NAME: storageAccountName
      AZURE_BLOB_CONTAINER_NAME: blobContainerName
      ORCHESTRATION_STRATEGY: orchestrationStrategy
      AZURE_CONTENT_SAFETY_ENDPOINT: 'https://${location}.api.cognitive.microsoft.com/'
      AZURE_BLOB_ACCOUNT_KEY: storage.outputs.AZURE_BLOB_ACCOUNT_KEY
      APPINSIGHTS_CONNECTION_STRING: monitoring.outputs.applicationInsightsConnectionString
      AZURE_FORM_RECOGNIZER_KEY: resources.outputs.AZURE_FORM_RECOGNIZER_KEY
      AZURE_CONTENT_SAFETY_KEY: resources.outputs.AZURE_CONTENT_SAFETY_KEY
    }
  }
}

module adminweb './app/adminweb.bicep' = {
  name: '${websiteName}-admin'
  scope: rg
  params: {
    name: '${websiteName}-admin'
    location: location
    tags: { 'azd-service-name': 'adminweb' }
    appServicePlanId: hostingplan.outputs.name
    applicationInsightsName: monitoring.outputs.applicationInsightsName
    azureOpenAIName: openai.outputs.name
    azureCognitiveSearchName: azureCognitiveSearchName
    appSettings: {
      AZURE_SEARCH_SERVICE: 'https://${azureCognitiveSearchName}.search.windows.net'
      AZURE_SEARCH_INDEX: azureSearchIndex
      AZURE_SEARCH_USE_SEMANTIC_SEARCH: azureSearchUseSemanticSearch
      AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG: azureSearchSemanticSearchConfig
      AZURE_SEARCH_INDEX_IS_PRECHUNKED: azureSearchIndexIsPrechunked
      AZURE_SEARCH_TOP_K: azureSearchTopK
      AZURE_SEARCH_ENABLE_IN_DOMAIN: azureSearchEnableInDomain
      AZURE_SEARCH_CONTENT_COLUMNS: azureSearchContentColumns
      AZURE_SEARCH_FILENAME_COLUMN: azureSearchFilenameColumn
      AZURE_SEARCH_TITLE_COLUMN: azureSearchTitleColumn
      AZURE_SEARCH_URL_COLUMN: azureSearchUrlColumn
      AZURE_OPENAI_RESOURCE: azureOpenAIResource
      AZURE_OPENAI_MODEL: azureOpenAIModel
      AZURE_OPENAI_MODEL_NAME: azureOpenAIModelName
      AZURE_OPENAI_TEMPERATURE: azureOpenAITemperature
      AZURE_OPENAI_TOP_P: azureOpenAITopP
      AZURE_OPENAI_MAX_TOKENS: azureOpenAIMaxTokens
      AZURE_OPENAI_STOP_SEQUENCE: azureOpenAIStopSequence
      AZURE_OPENAI_SYSTEM_MESSAGE: azureOpenAISystemMessage
      AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
      AZURE_OPENAI_STREAM: azureOpenAIStream
      AZURE_OPENAI_EMBEDDING_MODEL: azureOpenAIEmbeddingModel
      AZURE_FORM_RECOGNIZER_ENDPOINT: 'https://${location}.api.cognitive.microsoft.com/'
      AZURE_BLOB_ACCOUNT_NAME: storageAccountName
      AZURE_BLOB_CONTAINER_NAME: blobContainerName
      DOCUMENT_PROCESSING_QUEUE_NAME: queueName
      BACKEND_URL: 'https://${functionName}.azurewebsites.net'
      FUNCTION_KEY: clientKey
      ORCHESTRATION_STRATEGY: orchestrationStrategy
      AZURE_CONTENT_SAFETY_ENDPOINT: 'https://${location}.api.cognitive.microsoft.com/'
      AZURE_BLOB_ACCOUNT_KEY: storage.outputs.AZURE_BLOB_ACCOUNT_KEY
      APPINSIGHTS_INSTRUMENTATIONKEY: monitoring.outputs.applicationInsightsInstrumentationKey
      AZURE_FORM_RECOGNIZER_KEY: resources.outputs.AZURE_FORM_RECOGNIZER_KEY
      AZURE_CONTENT_SAFETY_KEY: resources.outputs.AZURE_CONTENT_SAFETY_KEY
    }
  }
}

module storage './app/storage.bicep' = {
  name: 'Storage_Account'
  scope: rg
  params: {
    storageAccountName: storageAccountName
    location: location
    blobContainerName: blobContainerName
  }
}

module monitoring './core/monitor/monitoring.bicep' = {
  name: 'monitoring'
  scope: rg
  params: {
    applicationInsightsName: applicationInsightsName
    location: location
    tags: {
      'hidden-link:${resourceId('Microsoft.Web/sites', applicationInsightsName)}': 'Resource'
    }
    logAnalyticsName: '${environmentName}-logAnalytics-${resourceToken}'
    applicationInsightsDashboardName: 'dash-${applicationInsightsName}'
  }
}

module function './app/function.bicep' = {
  name: functionName
  scope: rg
  params:{
    name: functionName
    location: location
    tags: { 'azd-service-name': 'function' }
    appServicePlanId: hostingplan.outputs.name
    storageAccountName: storageAccountName
    azureOpenAIName: openai.outputs.name
    azureCognitiveSearchName: azureCognitiveSearchName
    clientKey: clientKey
    appSettings: {
      FUNCTIONS_EXTENSION_VERSION: '~4'
      WEBSITES_ENABLE_APP_SERVICE_STORAGE: 'false'
      AZURE_OPENAI_MODEL: azureOpenAIModel
      AZURE_OPENAI_EMBEDDING_MODEL: azureOpenAIEmbeddingModel
      AZURE_OPENAI_RESOURCE: azureOpenAIResource
      AZURE_BLOB_ACCOUNT_NAME: storageAccountName
      AZURE_BLOB_CONTAINER_NAME: blobContainerName
      AZURE_FORM_RECOGNIZER_ENDPOINT: 'https://${location}.api.cognitive.microsoft.com/'
      AZURE_SEARCH_SERVICE: 'https://${azureCognitiveSearchName}.search.windows.net'
      DOCUMENT_PROCESSING_QUEUE_NAME: queueName
      AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
      AZURE_SEARCH_INDEX: azureSearchIndex
      ORCHESTRATION_STRATEGY: orchestrationStrategy
      AZURE_CONTENT_SAFETY_ENDPOINT: 'https://${location}.api.cognitive.microsoft.com/'
      AZURE_BLOB_ACCOUNT_KEY: storage.outputs.AZURE_BLOB_ACCOUNT_KEY
      APPINSIGHTS_INSTRUMENTATIONKEY: monitoring.outputs.applicationInsightsInstrumentationKey
      AZURE_FORM_RECOGNIZER_KEY: resources.outputs.AZURE_FORM_RECOGNIZER_KEY
      AZURE_CONTENT_SAFETY_KEY: resources.outputs.AZURE_CONTENT_SAFETY_KEY
    }
  }
}
