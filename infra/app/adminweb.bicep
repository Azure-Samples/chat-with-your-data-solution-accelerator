param name string
param location string = resourceGroup().location
param tags object = {}

param allowedOrigins array = []
param appServicePlanId string
param appCommandLine string = 'python -m streamlit run Admin.py --server.port 8000 --server.address 0.0.0.0 --server.enableXsrfProtection false'
param applicationInsightsName string = ''
param keyVaultName string = ''
param azureOpenAIName string = ''
param azureCognitiveSearchName string = ''

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

output WEBSITE_ADMIN_IDENTITY_PRINCIPAL_ID string = adminweb.outputs.identityPrincipalId
output WEBSITE_ADMIN_NAME string = adminweb.outputs.name
output WEBSITE_ADMIN_URI string = adminweb.outputs.uri
