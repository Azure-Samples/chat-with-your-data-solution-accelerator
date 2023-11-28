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
param rgName string = ''
param storageAccountName string = ''
param formRecognizerName string = ''
param contentSafetyName string = ''
@secure()
param appSettings object = {}
param serviceName string = 'web'
param useKeyVault bool
param openAIKey string = ''
param storageAccountKey string = ''
param formRecognizerKey string = ''
param searchKey string = ''
param contentSafetyKey string = ''
@secure()
param keyVaultEndpoint string = ''

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
      USE_KEY_VAULT: useKeyVault ? useKeyVault : ''
      AZURE_KEY_VAULT_ENDPOINT: useKeyVault ? keyVaultEndpoint : ''
      AZURE_OPENAI_KEY: useKeyVault ? openAIKey : listKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', azureOpenAIName), '2023-05-01').key1
      AZURE_SEARCH_KEY: useKeyVault ? searchKey : listAdminKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.Search/searchServices', azureCognitiveSearchName), '2021-04-01-preview').primaryKey
      AZURE_BLOB_ACCOUNT_KEY: useKeyVault ? storageAccountKey : listKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.Storage/storageAccounts', storageAccountName), '2021-09-01').keys[0].value
      AZURE_FORM_RECOGNIZER_KEY: useKeyVault ? formRecognizerKey : listKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', formRecognizerName), '2023-05-01').key1
      AZURE_CONTENT_SAFETY_KEY: useKeyVault ? contentSafetyKey : listKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', contentSafetyName), '2023-05-01').key1
    })
    
    keyVaultName: keyVaultName
    runtimeName: 'python'
    runtimeVersion: '3.11'
    scmDoBuildDuringDeployment: true
  }
}

output FRONTEND_API_IDENTITY_PRINCIPAL_ID string = web.outputs.identityPrincipalId
output FRONTEND_API_NAME string = web.outputs.name
output FRONTEND_API_URI string = web.outputs.uri
