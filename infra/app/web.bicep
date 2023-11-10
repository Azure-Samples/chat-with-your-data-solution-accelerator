param name string
param location string = resourceGroup().location
param tags object = {}

param allowedOrigins array = []
param appCommandLine string = ''
param appServicePlanId string
param applicationInsightsName string = ''
param keyVaultName string = ''
param azureOpenAIName string = ''
param azureCognitiveSearchName string = ''

@secure()
param appSettings object = {}
param serviceName string = 'web'

module web '../core/host/appservice.bicep' = {
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
      AZURE_OPENAI_KEY: openAI.listKeys().key1
      AZURE_SEARCH_KEY: listAdminKeys('Microsoft.Search/searchServices/${azureCognitiveSearchName}', '2021-04-01-preview').primaryKey
    })
    
    keyVaultName: keyVaultName
    runtimeName: 'python'
    runtimeVersion: '3.11'
    scmDoBuildDuringDeployment: true
  }
}

resource openAI 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  name: azureOpenAIName
}

output FRONTEND_API_IDENTITY_PRINCIPAL_ID string = web.outputs.identityPrincipalId
output FRONTEND_API_NAME string = web.outputs.name
output FRONTEND_API_URI string = web.outputs.uri
