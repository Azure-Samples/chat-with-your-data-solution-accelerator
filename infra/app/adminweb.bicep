param name string
param location string = resourceGroup().location
param tags object = {}

param allowedOrigins array = []
param appServicePlanId string
param appCommandLine string = 'python -m streamlit run Admin.py --server.port 8000 --server.address 0.0.0.0 --server.enableXsrfProtection false'
param applicationInsightsName string = ''
// param storageAccountName string
param keyVaultName string = ''
param azureOpenAIName string = ''
param azureCognitiveSearchName string = ''
// param formRecognizerName string = ''
// param contentSafetyName string = ''

@secure()
param appSettings object = {}
param serviceName string = 'adminweb'

module adminweb '../core/host/appservice.bicep' = {
  name: '${name}-app-module'
  params: {
    name: name
    location: location
    tags: union(tags, { 'azd-service-name': serviceName })
    allowedOrigins: allowedOrigins
    appCommandLine: appCommandLine
    applicationInsightsName: applicationInsightsName
    appServicePlanId: appServicePlanId
    appSettings: union(appSettings, {
      // AZURE_BLOB_ACCOUNT_KEY: storage.listKeys().keys[0].value
      // APPINSIGHTS_INSTRUMENTATIONKEY: applicationInsights.properties.InstrumentationKey
      AZURE_OPENAI_KEY: openAI.listKeys().key1
      AZURE_SEARCH_KEY: search.listAdminKeys().primaryKey
      // AZURE_FORM_RECOGNIZER_KEY: formrecognizer.listKeys().key1
      // AZURE_CONTENT_SAFETY_KEY: ContentSafety.listKeys().key1
    })
    keyVaultName: keyVaultName
    runtimeName: 'python'
    runtimeVersion: '3.11'
    scmDoBuildDuringDeployment: true
  }
}

// resource storage 'Microsoft.Storage/storageAccounts@2021-09-01' existing = {
//   name: storageAccountName
// }

// resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = if (!empty(applicationInsightsName)) {
//   name: applicationInsightsName
// }

resource openAI 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  name: azureOpenAIName
}

resource search 'Microsoft.Search/searchServices@2021-04-01-preview' existing = {
  name: azureCognitiveSearchName
}

// resource formrecognizer 'Microsoft.CognitiveServices/accounts@2022-12-01' existing = {
//   name: formRecognizerName
// }

// resource ContentSafety 'Microsoft.CognitiveServices/accounts@2022-03-01' existing = {
//   name: contentSafetyName
// }

output WEBSITE_ADMIN_IDENTITY_PRINCIPAL_ID string = adminweb.outputs.identityPrincipalId
output WEBSITE_ADMIN_NAME string = adminweb.outputs.name
output WEBSITE_ADMIN_URI string = adminweb.outputs.uri
