@description('provide a 2-13 character prefix for all resources.')
param ResourcePrefix string

@description('The name of the Azure Function app.')
param functionAppName string = '${ResourcePrefix}-func-backend'

@description('Location for all resources.')
param location string = resourceGroup().location

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

@description('Application Insights Connection String - Created during the "Chat with your data" Solution Accelerator')
@secure()
param AppInsightsConnectionString string

@description('Azure Cognitive Search Resource - Created during the "Chat with your data" Solution Accelerator')
param AzureCognitiveSearch string

@description('Azure Cognitive Search Index - Created during the "Chat with your data" Solution Accelerator')
param AzureSearchIndex string

@description('Azure Cognitive Search Conversation Log Index - Created during the "Chat with your data" Solution Accelerator')
param AzureSearchConversationLogIndex string = 'conversations'

@description('Azure Cognitive Search Key - Created during the "Chat with your data" Solution Accelerator')
@secure()
param AzureSearchKey string

@description('Semantic search config - Created during the "Chat with your data" Solution Accelerator')
param AzureSearchSemanticSearchConfig string = 'default'

@description('Is the index prechunked - Created during the "Chat with your data" Solution Accelerator')
param AzureSearchIndexIsPrechunked string = 'false'

@description('Top K results - Created during the "Chat with your data" Solution Accelerator')
param AzureSearchTopK string = '5'

@description('Enable in domain - Created during the "Chat with your data" Solution Accelerator')
param AzureSearchEnableInDomain string = 'false'

@description('Content columns - Created during the "Chat with your data" Solution Accelerator')
param AzureSearchContentColumns string = 'content'

@description('Filename column - Created during the "Chat with your data" Solution Accelerator')
param AzureSearchFilenameColumn string = 'filename'

@description('Title column - Created during the "Chat with your data" Solution Accelerator')
param AzureSearchTitleColumn string = 'title'

@description('Url column - Created during the "Chat with your data" Solution Accelerator')
param AzureSearchUrlColumn string = 'url'

@description('Name of Azure OpenAI Resource - Created during the "Chat with your data" Solution Accelerator')
param AzureOpenAIResource string

@description('Azure OpenAI Model Deployment Name - Created during the "Chat with your data" Solution Accelerator')
param AzureOpenAIModel string = 'gpt-35-turbo'

@description('Azure OpenAI Model Name - Created during the "Chat with your data" Solution Accelerator')
param AzureOpenAIModelName string = 'gpt-35-turbo'

@description('Azure OpenAI Key - Created during the "Chat with your data" Solution Accelerator')
@secure()
param AzureOpenAIKey string

@description('Orchestration strategy: openai_function or langchain str. If you use a old version of turbo (0301), plese select langchain - Created during the "Chat with your data" Solution Accelerator')
@allowed([
  'openai_function'
  'langchain'
])
param OrchestrationStrategy string

@description('Azure OpenAI Temperature - Created during the "Chat with your data" Solution Accelerator')
param AzureOpenAITemperature string = '0'

@description('Azure OpenAI Top P - Created during the "Chat with your data" Solution Accelerator')
param AzureOpenAITopP string = '1'

@description('Azure OpenAI Max Tokens - Created during the "Chat with your data" Solution Accelerator')
param AzureOpenAIMaxTokens string = '1000'

@description('Azure OpenAI Stop Sequence - Created during the "Chat with your data" Solution Accelerator')
param AzureOpenAIStopSequence string = '\n'

@description('Azure OpenAI System Message - Created during the "Chat with your data" Solution Accelerator')
param AzureOpenAISystemMessage string = 'You are an AI assistant that helps people find information.'

@description('Azure OpenAI Api Version - Created during the "Chat with your data" Solution Accelerator')
param AzureOpenAIApiVersion string = '2023-07-01-preview'

@description('Whether or not to stream responses from Azure OpenAI - Created during the "Chat with your data" Solution Accelerator')
param AzureOpenAIStream string = 'true'

@description('Azure OpenAI Embedding Model - Created during the "Chat with your data" Solution Accelerator')
param AzureOpenAIEmbeddingModel string = 'text-embedding-ada-002'

@description('Azure Form Recognizer Endpoint - Created during the "Chat with your data" Solution Accelerator')
param AzureFormRecognizerEndpoint string

@description('Azure Form Recognizer Key - Created during the "Chat with your data" Solution Accelerator')
@secure()
param AzureFormRecognizerKey string

@description('Storage Account Name - Created during the "Chat with your data" Solution Accelerator') 
param AzureBlobAccountName string

@description('Storage Account Key - Created during the "Chat with your data" Solution Accelerator')
@secure()
param AzureBlobAccountKey string

@description('Storage Account Container Name - Created during the "Chat with your data" Solution Accelerator')
param AzureBlobContainerName string

var BackendImageName = 'DOCKER|cscicontainer.azurecr.io/cwyod_backend-pr'

resource HostingPlan 'Microsoft.Web/serverfarms@2020-06-01' = {
  name: HostingPlanName
  location: location
  sku: {
    name: HostingPlanSku
  }
  properties: {
    reserved: true
  }
  kind: 'linux'
}

resource Function 'Microsoft.Web/sites@2018-11-01' = {
  name: functionAppName
  kind: 'functionapp,linux'
  location: location
  tags: {}
  properties: {
    siteConfig: {
      appSettings: [
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4'}
        { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false'}
        { name: 'APPINSIGHTS_CONNECTION_STRING', value: AppInsightsConnectionString}
        { name: 'AZURE_SEARCH_SERVICE', value: 'https://${AzureCognitiveSearch}.search.windows.net'}
        { name: 'AZURE_SEARCH_INDEX', value: AzureSearchIndex}
        { name: 'AZURE_SEARCH_CONVERSATIONS_LOG_INDEX', value: AzureSearchConversationLogIndex}
        { name: 'AZURE_SEARCH_KEY', value: AzureSearchKey}
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
        { name: 'AZURE_FORM_RECOGNIZER_ENDPOINT', value: AzureFormRecognizerEndpoint}
        { name: 'AZURE_FORM_RECOGNIZER_KEY', value: AzureFormRecognizerKey}
        { name: 'AZURE_BLOB_ACCOUNT_NAME', value: AzureBlobAccountName}
        { name: 'AZURE_BLOB_ACCOUNT_KEY', value: AzureBlobAccountKey}
        { name: 'AZURE_BLOB_CONTAINER_NAME', value: AzureBlobContainerName}
        { name: 'ORCHESTRATION_STRATEGY', value: OrchestrationStrategy}
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

resource WaitFunctionDeploymentSection 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  kind: 'AzurePowerShell'
  name: 'WaitFunctionDeploymentSection'
  location: location
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
