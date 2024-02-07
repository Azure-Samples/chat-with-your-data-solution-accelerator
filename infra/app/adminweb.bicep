param name string
param location string = resourceGroup().location
param tags object = {}
param storageAccountName string = ''
param formRecognizerName string = ''
param contentSafetyName string = ''
param allowedOrigins array = []
param appServicePlanId string
param appCommandLine string = 'python -m streamlit run Admin.py --server.port 8000 --server.address 0.0.0.0 --server.enableXsrfProtection false'
param applicationInsightsName string = ''
param keyVaultName string = ''
param azureOpenAIName string = ''
param azureAISearchName string = ''
param speechServiceName string = ''
@secure()
param appSettings object = {}
param serviceName string = 'adminweb'
param useKeyVault bool
param openAIKeyName string = ''
param storageAccountKeyName string = ''
param formRecognizerKeyName string = ''
param searchKeyName string = ''
param contentSafetyKeyName string = ''
param speechKeyName string = ''
param keyVaultEndpoint string = ''
param authType string

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
      AZURE_AUTH_TYPE: authType
      USE_KEY_VAULT: useKeyVault ? useKeyVault : ''
      AZURE_KEY_VAULT_ENDPOINT: useKeyVault ? keyVaultEndpoint : ''
      AZURE_OPENAI_KEY: useKeyVault ? openAIKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', azureOpenAIName), '2023-05-01').key1
      AZURE_SEARCH_KEY: useKeyVault ? searchKeyName : listAdminKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.Search/searchServices', azureAISearchName), '2021-04-01-preview').primaryKey
      AZURE_BLOB_ACCOUNT_KEY: useKeyVault ? storageAccountKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.Storage/storageAccounts', storageAccountName), '2021-09-01').keys[0].value
      AZURE_FORM_RECOGNIZER_KEY: useKeyVault ? formRecognizerKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', formRecognizerName), '2023-05-01').key1
      AZURE_CONTENT_SAFETY_KEY: useKeyVault ? contentSafetyKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', contentSafetyName), '2023-05-01').key1
      AZURE_SPEECH_SERVICE_KEY: useKeyVault ? speechKeyName: listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', speechServiceName), '2023-05-01').key1
    })
    keyVaultName: keyVaultName
    runtimeName: 'python'
    runtimeVersion: '3.11'
    scmDoBuildDuringDeployment: true
  }
}

output WEBSITE_ADMIN_IDENTITY_PRINCIPAL_ID string = adminweb.outputs.identityPrincipalId
output WEBSITE_ADMIN_NAME string = adminweb.outputs.name
output WEBSITE_ADMIN_URI string = adminweb.outputs.uri
