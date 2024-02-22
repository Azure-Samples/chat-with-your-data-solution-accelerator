param name string
param location string = ''
param appServicePlanId string
param storageAccountName string = ''
param tags object = {}
@secure()
param appSettings object = {}
param serviceName string = 'function'
param runtimeName string = 'python'
param runtimeVersion string = '3.11'
@secure()
param clientKey string
param keyVaultName string = ''
param azureOpenAIName string = ''
param azureAISearchName string = ''
param formRecognizerName string = ''
param contentSafetyName string = ''
param speechServiceName string = ''
param useKeyVault bool
param openAIKeyName string = ''
param storageAccountKeyName string = ''
param formRecognizerKeyName string = ''
param searchKeyName string = ''
param contentSafetyKeyName string = ''
param speechKeyName string = ''
param keyVaultEndpoint string = ''
param authType string

module function '../core/host/functions.bicep' = {
  name: '${name}-app-module'
  params: {
    name: name
    location: location
    tags: union(tags, { 'azd-service-name': serviceName })
    appServicePlanId: appServicePlanId
    storageAccountName: storageAccountName
    keyVaultName: keyVaultName
    runtimeName: runtimeName
    runtimeVersion: runtimeVersion
    appSettings: union(appSettings, {
        AZURE_AUTH_TYPE: authType
        USE_KEY_VAULT: useKeyVault ? useKeyVault : ''
        AZURE_KEY_VAULT_ENDPOINT: useKeyVault ? keyVaultEndpoint : ''
        AZURE_OPENAI_KEY: useKeyVault ? openAIKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', azureOpenAIName), '2023-05-01').key1
        AZURE_SEARCH_KEY: useKeyVault ? searchKeyName : listAdminKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.Search/searchServices', azureAISearchName), '2021-04-01-preview').primaryKey
        AZURE_BLOB_ACCOUNT_KEY: useKeyVault ? storageAccountKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.Storage/storageAccounts', storageAccountName), '2021-09-01').keys[0].value
        AZURE_FORM_RECOGNIZER_KEY: useKeyVault ? formRecognizerKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', formRecognizerName), '2023-05-01').key1
        AZURE_CONTENT_SAFETY_KEY: useKeyVault ? contentSafetyKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', contentSafetyName), '2023-05-01').key1
        AZURE_SPEECH_SERVICE_KEY: useKeyVault ? speechKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', speechServiceName), '2023-05-01').key1
      })
  }
}

resource functionNameDefaultClientKey 'Microsoft.Web/sites/host/functionKeys@2018-11-01' = {
  name: '${name}/default/clientKey'
  properties: {
    name: 'ClientKey'
    value: clientKey
  }
  dependsOn: [
    function
    waitFunctionDeploymentSection
  ]
}

resource waitFunctionDeploymentSection 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
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
    function
  ]
}

output FUNCTION_IDENTITY_PRINCIPAL_ID string = function.outputs.identityPrincipalId
