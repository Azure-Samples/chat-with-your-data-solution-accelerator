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
param azureCognitiveSearchName string = ''
param rgName string = ''
param formRecognizerName string = ''
param contentSafetyName string = ''
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
      AUTH_TYPE: authType
      AZURE_OPENAI_KEY: listKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', azureOpenAIName), '2023-05-01').key1
      AZURE_SEARCH_KEY: listAdminKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.Search/searchServices', azureCognitiveSearchName), '2021-04-01-preview').primaryKey
      AZURE_BLOB_ACCOUNT_KEY: listKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.Storage/storageAccounts', storageAccountName), '2021-09-01').keys[0].value
      AZURE_FORM_RECOGNIZER_KEY: listKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', formRecognizerName), '2023-05-01').key1
      AZURE_CONTENT_SAFETY_KEY: listKeys(resourceId(subscription().subscriptionId, rgName, 'Microsoft.CognitiveServices/accounts', contentSafetyName), '2023-05-01').key1
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
