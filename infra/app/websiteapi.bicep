param name string
param location string = resourceGroup().location
param tags object = {}

param allowedOrigins array = []
param appCommandLine string = ''
param appServicePlanId string
param applicationInsightsName string = ''
param StorageAccountName string 
param keyVaultName string = ''
param AzureOpenAIName string = ''
param AzureCognitiveSearchName string = ''
param FormRecognizerName string = ''
param ContentSafetyName string = ''

param appSettings array = []
param serviceName string = 'Website'

module Website '../core/host/appservice.bicep' = {
  name: '${name}-app-module'
  params: {
    name: name
    location: location
    tags: union(tags, { 'azd-service-name': serviceName })
    allowedOrigins: allowedOrigins
    appCommandLine: appCommandLine
    applicationInsightsName: applicationInsightsName
    appServicePlanId: appServicePlanId
    appSettings: union(toObject(appSettings, entry => entry.name, entry => entry.value), {
      AZURE_BLOB_ACCOUNT_KEY: storage.listKeys().keys[0].value
      APPINSIGHTS_CONNECTION_STRING: applicationInsights.properties.ConnectionString
      AZURE_OPENAI_KEY: openai.listKeys().key1
      AZURE_SEARCH_KEY: search.listAdminKeys().primaryKey
      AZURE_FORM_RECOGNIZER_KEY: formrecognizer.listKeys().key1
      AZURE_CONTENT_SAFETY_KEY: ContentSafety.listKeys().key1
    })
    
    keyVaultName: keyVaultName
    runtimeName: 'python'
    runtimeVersion: '3.11'
    scmDoBuildDuringDeployment: true
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2021-09-01' existing = {
  name: StorageAccountName
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = if (!empty(applicationInsightsName)) {
  name: applicationInsightsName
}

resource openai 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  name: AzureOpenAIName
}

resource search 'Microsoft.Search/searchServices@2021-04-01-preview' existing = {
  name: AzureCognitiveSearchName
}

resource formrecognizer 'Microsoft.CognitiveServices/accounts@2022-12-01' existing = {
  name: FormRecognizerName
}

resource ContentSafety 'Microsoft.CognitiveServices/accounts@2022-03-01' existing = {
  name: ContentSafetyName
}

output FRONTEND_API_IDENTITY_PRINCIPAL_ID string = Website.outputs.identityPrincipalId
output FRONTEND_API_NAME string = Website.outputs.name
output FRONTEND_API_URI string = Website.outputs.uri
