param name string
param location string = ''
param appServicePlanId string
param storageAccountName string = ''
param tags object = {}
@secure()
param appSettings object = {}
param applicationInsightsName string = ''
param runtimeName string = 'python'
param runtimeVersion string = ''
@secure()
param clientKey string
param keyVaultName string = ''
param azureOpenAIName string = ''
param azureAISearchName string = ''
param formRecognizerName string = ''
param contentSafetyName string = ''
param speechServiceName string = ''
param computerVisionName string = ''
param useKeyVault bool
param openAIKeyName string = ''
param storageAccountKeyName string = ''
param formRecognizerKeyName string = ''
param searchKeyName string = ''
param computerVisionKeyName string = ''
param contentSafetyKeyName string = ''
param speechKeyName string = ''
param authType string
param dockerFullImageName string = ''

module function '../core/host/functions.bicep' = {
  name: '${name}-app-module'
  params: {
    name: name
    location: location
    tags: tags
    appServicePlanId: appServicePlanId
    applicationInsightsName: applicationInsightsName
    storageAccountName: storageAccountName
    keyVaultName: keyVaultName
    runtimeName: runtimeName
    runtimeVersion: runtimeVersion
    dockerFullImageName: dockerFullImageName
    appSettings: union(appSettings, {
        WEBSITES_ENABLE_APP_SERVICE_STORAGE: 'false'
        AZURE_AUTH_TYPE: authType
        USE_KEY_VAULT: useKeyVault ? useKeyVault : ''
        AZURE_OPENAI_API_KEY: useKeyVault ? openAIKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', azureOpenAIName), '2023-05-01').key1
        AZURE_SEARCH_KEY: useKeyVault ? searchKeyName : listAdminKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.Search/searchServices', azureAISearchName), '2021-04-01-preview').primaryKey
        AZURE_BLOB_ACCOUNT_KEY: useKeyVault ? storageAccountKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.Storage/storageAccounts', storageAccountName), '2021-09-01').keys[0].value
        AZURE_FORM_RECOGNIZER_KEY: useKeyVault ? formRecognizerKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', formRecognizerName), '2023-05-01').key1
        AZURE_CONTENT_SAFETY_KEY: useKeyVault ? contentSafetyKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', contentSafetyName), '2023-05-01').key1
        AZURE_SPEECH_SERVICE_KEY: useKeyVault ? speechKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', speechServiceName), '2023-05-01').key1
        AZURE_COMPUTER_VISION_KEY: useKeyVault ? computerVisionKeyName : listKeys(resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', computerVisionName), '2023-05-01').key1
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

// Cognitive Services User
module openAIRoleFunction '../core/security/role.bicep' = if (authType == 'rbac') {
  name: 'openai-role-function'
  params: {
    principalId: function.outputs.identityPrincipalId
    roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908'
    principalType: 'ServicePrincipal'
  }
}

// Contributor
// This role is used to grant the service principal contributor access to the resource group
// See if this is needed in the future.
module openAIRoleFunctionContributor '../core/security/role.bicep' = if (authType == 'rbac') {
  name: 'openai-role-function-contributor'
  params: {
    principalId: function.outputs.identityPrincipalId
    roleDefinitionId: 'b24988ac-6180-42a0-ab88-20f7382dd24c'
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor
module searchRoleFunction '../core/security/role.bicep' = if (authType == 'rbac') {
  name: 'search-role-function'
  params: {
    principalId: function.outputs.identityPrincipalId
    roleDefinitionId: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
    principalType: 'ServicePrincipal'
  }
}

// Storage Blob Data Contributor
module storageBlobRoleFunction '../core/security/role.bicep' = if (authType == 'rbac') {
  name: 'storage-blob-role-function'
  params: {
    principalId: function.outputs.identityPrincipalId
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    principalType: 'ServicePrincipal'
  }
}

// Storage Queue Data Contributor
module storageQueueRoleFunction '../core/security/role.bicep' = if (authType == 'rbac') {
  name: 'storage-queue-role-function'
  params: {
    principalId: function.outputs.identityPrincipalId
    roleDefinitionId: '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
    principalType: 'ServicePrincipal'
  }
}

module functionaccess '../core/security/keyvault-access.bicep' = if (useKeyVault) {
  name: 'function-keyvault-access'
  params: {
    keyVaultName: keyVaultName
    principalId: function.outputs.identityPrincipalId
  }
}

output FUNCTION_IDENTITY_PRINCIPAL_ID string = function.outputs.identityPrincipalId
output functionName string = function.outputs.name
