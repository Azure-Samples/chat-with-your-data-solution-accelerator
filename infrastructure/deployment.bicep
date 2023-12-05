@description('provide a 2-13 character prefix for all resources.')
param ResourcePrefix string

@description('Location for all resources.')
param Location string = resourceGroup().location

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
param AzureOpenAIResource string

@description('Azure OpenAI Model Deployment Name')
param AzureOpenAIModel string = 'gpt-35-turbo'

@description('Azure OpenAI Model Name')
param AzureOpenAIModelName string = 'gpt-35-turbo'

@description('Azure OpenAI Key')
@secure()
param AzureOpenAIKey string

@description('Orchestration strategy: openai_function or langchain str. If you use a old version of turbo (0301), plese select langchain')
@allowed([
  'openai_function'
  'langchain'
])
param OrchestrationStrategy string

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

@description('Azure OpenAI Embedding Model')
param AzureOpenAIEmbeddingModel string = 'text-embedding-ada-002'

@description('Azure AI Search Resource')
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

@description('Azure AI Search Index')
param AzureSearchIndex string = '${ResourcePrefix}-index'

@description('Azure AI Search Conversation Log Index')
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

var WebAppImageName = 'DOCKER|fruoccopublic.azurecr.io/rag-webapp'
var AdminWebAppImageName = 'DOCKER|fruoccopublic.azurecr.io/rag-adminwebapp'
var BackendImageName = 'DOCKER|fruoccopublic.azurecr.io/rag-backend'
var BlobContainerName = 'documents'
var QueueName = 'doc-processing'
var ClientKey = '${uniqueString(guid(resourceGroup().id, deployment().name))}${newGuidString}'
var EventGridSystemTopicName = 'doc-processing'

resource AzureCognitiveSearch_resource 'Microsoft.Search/searchServices@2022-09-01' = {
  name: AzureCognitiveSearch
  location: Location
  tags: {
    deployment : 'chatwithyourdata-sa'
  }
  sku: {
    name: AzureCognitiveSearchSku
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
  }
}

resource FormRecognizer 'Microsoft.CognitiveServices/accounts@2022-12-01' = {
  name: FormRecognizerName
  location: Location
  sku: {
    name: 'S0'
  }
  kind: 'FormRecognizer'
  identity: {
    type: 'None'
  }
  properties: {
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Enabled'
  }
}

resource ContentSafety 'Microsoft.CognitiveServices/accounts@2022-03-01' = {
  name: ContentSafetyName
  location: Location
  sku: {
    name: 'S0'
  }
  kind: 'ContentSafety'
  identity: {
    type: 'None'
  }
  properties: {
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: [] 
    }
  }
}

resource HostingPlan 'Microsoft.Web/serverfarms@2020-06-01' = {
  name: HostingPlanName
  location: Location
  sku: {
    name: HostingPlanSku
  }
  properties: {
    reserved: true
  }
  kind: 'linux'
}

resource Website 'Microsoft.Web/sites@2020-06-01' = {
  name: WebsiteName
  location: Location
  properties: {
    serverFarmId: HostingPlanName
    siteConfig: {
      appSettings: [
        { name: 'APPINSIGHTS_CONNECTION_STRING', value: reference(ApplicationInsights.id, '2015-05-01').ConnectionString}
        { name: 'AZURE_SEARCH_SERVICE', value: 'https://${AzureCognitiveSearch}.search.windows.net'}
        { name: 'AZURE_SEARCH_INDEX', value: AzureSearchIndex}
        { name: 'AZURE_SEARCH_CONVERSATIONS_LOG_INDEX', value: AzureSearchConversationLogIndex}
        { name: 'AZURE_SEARCH_KEY', value: listAdminKeys('Microsoft.Search/searchServices/${AzureCognitiveSearch}', '2021-04-01-preview').primaryKey}
        { name: 'AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG', value: AzureSearchSemanticSearchConfig}
        { name: 'AZURE_SEARCH_INDEX_IS_PRECHUNKED', value: AzureSearchIndexIsPrechunked}
        { name: 'AZURE_SEARCH_TOP_K', value: AzureSearchTopK}
        { name: 'AZURE_SEARCH_ENABLE_IN_DOMAIN', value: AzureSearchEnableInDomain}
        { name: 'AZURE_SEARCH_CONTENT_COLUMNS', value: AzureSearchContentColumns}
        { name: 'AZURE_SEARCH_FILENAME_COLUMN', value: AzureSearchFilenameColumn}
        { name: 'AZURE_SEARCH_TITLE_COLUMN', value: AzureSearchTitleColumn}
        { name: 'AZURE_SEARCH_URL_COLUMN', value: AzureSearchUrlColumn}
        { name: 'AZURE_OPENAI_RESOURCE', value: AzureOpenAIResource}
        { name: 'AZURE_OPENAI_KEY', value: AzureOpenAIKey}
        { name: 'AZURE_OPENAI_MODEL', value: AzureOpenAIModel}
        { name: 'AZURE_OPENAI_MODEL_NAME', value: AzureOpenAIModelName}
        { name: 'AZURE_OPENAI_TEMPERATURE', value: AzureOpenAITemperature}
        { name: 'AZURE_OPENAI_TOP_P', value: AzureOpenAITopP}
        { name: 'AZURE_OPENAI_MAX_TOKENS', value: AzureOpenAIMaxTokens}
        { name: 'AZURE_OPENAI_STOP_SEQUENCE', value: AzureOpenAIStopSequence}
        { name: 'AZURE_OPENAI_SYSTEM_MESSAGE', value: AzureOpenAISystemMessage}
        { name: 'AZURE_OPENAI_API_VERSION', value: AzureOpenAIApiVersion}
        { name: 'AZURE_OPENAI_STREAM', value: AzureOpenAIStream}
        { name: 'AZURE_OPENAI_EMBEDDING_MODEL', value: AzureOpenAIEmbeddingModel}
        { name: 'AZURE_FORM_RECOGNIZER_ENDPOINT', value: 'https://${Location}.api.cognitive.microsoft.com/'}
        { name: 'AZURE_FORM_RECOGNIZER_KEY', value: listKeys('Microsoft.CognitiveServices/accounts/${FormRecognizerName}', '2023-05-01').key1}
        { name: 'AZURE_BLOB_ACCOUNT_NAME', value: StorageAccountName}
        { name: 'AZURE_BLOB_ACCOUNT_KEY', value: listKeys(StorageAccount.id, '2019-06-01').keys[0].value}
        { name: 'AZURE_BLOB_CONTAINER_NAME', value: BlobContainerName}
        { name: 'ORCHESTRATION_STRATEGY', value: OrchestrationStrategy}
        { name: 'AZURE_CONTENT_SAFETY_ENDPOINT', value: 'https://${Location}.api.cognitive.microsoft.com/'}
        { name: 'AZURE_CONTENT_SAFETY_KEY', value: listKeys('Microsoft.CognitiveServices/accounts/${ContentSafetyName}', '2023-05-01').key1}
      ]
      linuxFxVersion: WebAppImageName
    }
  }
  dependsOn: [
    HostingPlan
  ]
}

resource WebsiteName_admin 'Microsoft.Web/sites@2020-06-01' = {
  name: '${WebsiteName}-admin'
  location: Location
  properties: {
    serverFarmId: HostingPlanName
    siteConfig: {
      appSettings: [
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: reference(ApplicationInsights.id, '2015-05-01').InstrumentationKey }
        { name: 'AZURE_SEARCH_SERVICE', value: 'https://${AzureCognitiveSearch}.search.windows.net' }
        { name: 'AZURE_SEARCH_KEY', value: listAdminKeys('Microsoft.Search/searchServices/${AzureCognitiveSearch}', '2021-04-01-preview').primaryKey }
        { name: 'AZURE_SEARCH_INDEX', value: AzureSearchIndex }
        { name: 'AZURE_SEARCH_USE_SEMANTIC_SEARCH', value: AzureSearchUseSemanticSearch }
        { name: 'AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG', value: AzureSearchSemanticSearchConfig }
        { name: 'AZURE_SEARCH_INDEX_IS_PRECHUNKED', value: AzureSearchIndexIsPrechunked }
        { name: 'AZURE_SEARCH_TOP_K', value: AzureSearchTopK }
        { name: 'AZURE_SEARCH_ENABLE_IN_DOMAIN', value: AzureSearchEnableInDomain }
        { name: 'AZURE_SEARCH_CONTENT_COLUMNS', value: AzureSearchContentColumns}
        { name: 'AZURE_SEARCH_FILENAME_COLUMN', value: AzureSearchFilenameColumn }
        { name: 'AZURE_SEARCH_TITLE_COLUMN', value: AzureSearchTitleColumn}
        { name: 'AZURE_SEARCH_URL_COLUMN', value: AzureSearchUrlColumn }
        { name: 'AZURE_OPENAI_RESOURCE', value: AzureOpenAIResource}
        { name: 'AZURE_OPENAI_KEY', value: AzureOpenAIKey}
        { name: 'AZURE_OPENAI_MODEL', value: AzureOpenAIModel }
        { name: 'AZURE_OPENAI_MODEL_NAME', value: AzureOpenAIModelName }
        { name: 'AZURE_OPENAI_TEMPERATURE', value: AzureOpenAITemperature }
        { name: 'AZURE_OPENAI_TOP_P', value: AzureOpenAITopP }
        { name: 'AZURE_OPENAI_MAX_TOKENS', value: AzureOpenAIMaxTokens }
        { name: 'AZURE_OPENAI_STOP_SEQUENCE', value: AzureOpenAIStopSequence }
        { name: 'AZURE_OPENAI_SYSTEM_MESSAGE', value: AzureOpenAISystemMessage }
        { name: 'AZURE_OPENAI_API_VERSION', value: AzureOpenAIApiVersion }
        { name: 'AZURE_OPENAI_STREAM', value: AzureOpenAIStream }
        { name: 'AZURE_OPENAI_EMBEDDING_MODEL', value: AzureOpenAIEmbeddingModel }
        { name: 'AZURE_FORM_RECOGNIZER_ENDPOINT', value: 'https://${Location}.api.cognitive.microsoft.com/' }
        { name: 'AZURE_FORM_RECOGNIZER_KEY', value: listKeys('Microsoft.CognitiveServices/accounts/${FormRecognizerName}', '2023-05-01').key1 }
        { name: 'AZURE_BLOB_ACCOUNT_NAME', value: StorageAccountName }
        { name: 'AZURE_BLOB_ACCOUNT_KEY', value: listKeys(StorageAccount.id, '2019-06-01').keys[0].value }
        { name: 'AZURE_BLOB_CONTAINER_NAME', value: BlobContainerName }
        { name: 'DOCUMENT_PROCESSING_QUEUE_NAME', value: QueueName}
        { name: 'BACKEND_URL', value: 'https://${FunctionName}.azurewebsites.net'}
        { name: 'FUNCTION_KEY', value: ClientKey}
        { name: 'ORCHESTRATION_STRATEGY', value: OrchestrationStrategy}
        { name: 'AZURE_CONTENT_SAFETY_ENDPOINT', value: 'https://${Location}.api.cognitive.microsoft.com/'}
        { name: 'AZURE_CONTENT_SAFETY_KEY', value: listKeys('Microsoft.CognitiveServices/accounts/${ContentSafetyName}', '2023-05-01').key1}
      ]
      linuxFxVersion: AdminWebAppImageName
    }
  }
  dependsOn: [
    HostingPlan
  ]
}

resource StorageAccount 'Microsoft.Storage/storageAccounts@2021-08-01' = {
  name: StorageAccountName
  location: Location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_GRS'
  }
}

resource StorageAccountName_default_BlobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2021-08-01' = {
  name: '${StorageAccountName}/default/${BlobContainerName}'
  properties: {
    publicAccess: 'None'
  }
  dependsOn: [
    StorageAccount
  ]
}

resource StorageAccountName_default_config 'Microsoft.Storage/storageAccounts/blobServices/containers@2021-08-01' = {
  name: '${StorageAccountName}/default/config'
  properties: {
    publicAccess: 'None'
  }
  dependsOn: [
    StorageAccount
  ]
}

resource StorageAccountName_default 'Microsoft.Storage/storageAccounts/queueServices@2022-09-01' = {
  parent: StorageAccount
  name: 'default'
  properties: {
    cors: {
      corsRules: []
    }
  }
}

resource StorageAccountName_default_doc_processing 'Microsoft.Storage/storageAccounts/queueServices/queues@2022-09-01' = {
  parent: StorageAccountName_default
  name: 'doc-processing'
  properties: {
    metadata: {}
  }
  dependsOn: []
}

resource StorageAccountName_default_doc_processing_poison 'Microsoft.Storage/storageAccounts/queueServices/queues@2022-09-01' = {
  parent: StorageAccountName_default
  name: 'doc-processing-poison'
  properties: {
    metadata: {}
  }
  dependsOn: []
}

resource ApplicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: ApplicationInsightsName
  location: Location
  tags: {
    'hidden-link:${resourceId('Microsoft.Web/sites', ApplicationInsightsName)}': 'Resource'
  }
  properties: {
    Application_Type: 'web'
  }
  kind: 'web'
}

resource Function 'Microsoft.Web/sites@2018-11-01' = {
  name: FunctionName
  kind: 'functionapp,linux'
  location: Location
  tags: {}
  properties: {
    siteConfig: {
      appSettings: [
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4'}
        { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false'}
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: reference(ApplicationInsights.id, '2015-05-01').InstrumentationKey}
        { name: 'AzureWebJobsStorage', value: 'DefaultEndpointsProtocol=https;AccountName=${StorageAccountName};AccountKey=${listKeys(StorageAccount.id, '2019-06-01').keys[0].value};EndpointSuffix=core.windows.net'}
        { name: 'AZURE_OPENAI_MODEL', value: AzureOpenAIModel}
        { name: 'AZURE_OPENAI_EMBEDDING_MODEL', value: AzureOpenAIEmbeddingModel}
        { name: 'AZURE_OPENAI_RESOURCE', value: AzureOpenAIResource}
        { name: 'AZURE_OPENAI_KEY', value: AzureOpenAIKey}
        { name: 'AZURE_BLOB_ACCOUNT_NAME', value: StorageAccountName}
        { name: 'AZURE_BLOB_ACCOUNT_KEY', value: listKeys(StorageAccount.id, '2019-06-01').keys[0].value}
        { name: 'AZURE_BLOB_CONTAINER_NAME', value: BlobContainerName}
        { name: 'AZURE_FORM_RECOGNIZER_ENDPOINT', value: 'https://${Location}.api.cognitive.microsoft.com/'}
        { name: 'AZURE_FORM_RECOGNIZER_KEY', value: listKeys('Microsoft.CognitiveServices/accounts/${FormRecognizerName}', '2023-05-01').key1}
        { name: 'AZURE_SEARCH_SERVICE', value: 'https://${AzureCognitiveSearch}.search.windows.net'}
        { name: 'AZURE_SEARCH_KEY', value: listAdminKeys('Microsoft.Search/searchServices/${AzureCognitiveSearch}', '2021-04-01-preview').primaryKey}
        { name: 'DOCUMENT_PROCESSING_QUEUE_NAME', value: QueueName}
        { name: 'AZURE_OPENAI_API_VERSION', value: AzureOpenAIApiVersion}
        { name: 'AZURE_SEARCH_INDEX', value: AzureSearchIndex}
        { name: 'ORCHESTRATION_STRATEGY', value: OrchestrationStrategy}
        { name: 'AZURE_CONTENT_SAFETY_ENDPOINT', value: 'https://${Location}.api.cognitive.microsoft.com/'}
        { name: 'AZURE_CONTENT_SAFETY_KEY', value: listKeys('Microsoft.CognitiveServices/accounts/${ContentSafetyName}', '2023-05-01').key1}
      ]
      cors: {
        allowedOrigins: [
          'https://portal.azure.com'
        ]
      }
      use32BitWorkerProcess: false
      linuxFxVersion: BackendImageName
      appCommandLine: ''
      alwaysOn: true
    }
    serverFarmId: HostingPlan.id
    clientAffinityEnabled: false
    httpsOnly: true
  }
}

resource FunctionName_default_clientKey 'Microsoft.Web/sites/host/functionKeys@2018-11-01' = {
  name: '${FunctionName}/default/clientKey'
  properties: {
    name: 'ClientKey'
    value: ClientKey
  }
  dependsOn: [
    Function
    WaitFunctionDeploymentSection
  ]
}

resource WaitFunctionDeploymentSection 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  kind: 'AzurePowerShell'
  name: 'WaitFunctionDeploymentSection'
  location: Location
  properties: {
    azPowerShellVersion: '3.0'
    scriptContent: 'start-sleep -Seconds 300'
    cleanupPreference: 'Always'
    retentionInterval: 'PT1H'
  }
  dependsOn: [
    Function
  ]
}

resource EventGridSystemTopic 'Microsoft.EventGrid/systemTopics@2021-12-01' = {
  name: EventGridSystemTopicName
  location: Location
  properties: {
    source: StorageAccount.id
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

resource EventGridSystemTopicName_BlobEvents 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2021-12-01' = {
  parent: EventGridSystemTopic
  name: 'BlobEvents'
  properties: {
    destination: {
      endpointType: 'StorageQueue'
      properties: {
        queueMessageTimeToLiveInSeconds: -1
        queueName: StorageAccountName_default_doc_processing.name
        resourceId: StorageAccount.id
      }
    }
    filter: {
      includedEventTypes: [
        'Microsoft.Storage.BlobCreated'
        'Microsoft.Storage.BlobDeleted'
      ]
      enableAdvancedFilteringOnArrays: true
      subjectBeginsWith: '/blobServices/default/containers/${BlobContainerName}/blobs/'
    }
    labels: []
    eventDeliverySchema: 'EventGridSchema'
    retryPolicy: {
      maxDeliveryAttempts: 30
      eventTimeToLiveInMinutes: 1440
    }
  }
}
