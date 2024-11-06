param name string
param location string = resourceGroup().location
param tags object = {}
param allowedOrigins array = []
param appCommandLine string = ''
param appServicePlanId string
param applicationInsightsName string = ''
param runtimeName string = 'python'
param runtimeVersion string = ''
param keyVaultName string = ''
param azureOpenAIName string = ''
param azureAISearchName string = ''
param storageAccountName string = ''
param formRecognizerName string = ''
param contentSafetyName string = ''
param speechServiceName string = ''
param computerVisionName string = ''
@secure()
param appSettings object = {}
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
param useDocker bool = dockerFullImageName != ''
param healthCheckPath string = ''
param cosmosDBKeyName string = ''

module web '../core/host/appservice.bicep' = {
  name: '${name}-app-module'
  params: {
    name: name
    location: location
    tags: tags
    allowedOrigins: allowedOrigins
    appCommandLine: useDocker ? '' : appCommandLine
    applicationInsightsName: applicationInsightsName
    appServicePlanId: appServicePlanId
    appSettings: union(appSettings, {
      AZURE_AUTH_TYPE: authType
      USE_KEY_VAULT: useKeyVault ? useKeyVault : ''
      AZURE_OPENAI_API_KEY: useKeyVault
        ? openAIKeyName
        : listKeys(
            resourceId(
              subscription().subscriptionId,
              resourceGroup().name,
              'Microsoft.CognitiveServices/accounts',
              azureOpenAIName
            ),
            '2023-05-01'
          ).key1
      AZURE_SEARCH_KEY: useKeyVault
        ? searchKeyName
        : listAdminKeys(
            resourceId(
              subscription().subscriptionId,
              resourceGroup().name,
              'Microsoft.Search/searchServices',
              azureAISearchName
            ),
            '2021-04-01-preview'
          ).primaryKey
      AZURE_BLOB_ACCOUNT_KEY: useKeyVault
        ? storageAccountKeyName
        : listKeys(
            resourceId(
              subscription().subscriptionId,
              resourceGroup().name,
              'Microsoft.Storage/storageAccounts',
              storageAccountName
            ),
            '2021-09-01'
          ).keys[0].value
      AZURE_FORM_RECOGNIZER_KEY: useKeyVault
        ? formRecognizerKeyName
        : listKeys(
            resourceId(
              subscription().subscriptionId,
              resourceGroup().name,
              'Microsoft.CognitiveServices/accounts',
              formRecognizerName
            ),
            '2023-05-01'
          ).key1
      AZURE_CONTENT_SAFETY_KEY: useKeyVault
        ? contentSafetyKeyName
        : listKeys(
            resourceId(
              subscription().subscriptionId,
              resourceGroup().name,
              'Microsoft.CognitiveServices/accounts',
              contentSafetyName
            ),
            '2023-05-01'
          ).key1
      AZURE_SPEECH_SERVICE_KEY: useKeyVault
        ? speechKeyName
        : listKeys(
            resourceId(
              subscription().subscriptionId,
              resourceGroup().name,
              'Microsoft.CognitiveServices/accounts',
              speechServiceName
            ),
            '2023-05-01'
          ).key1
      AZURE_COMPUTER_VISION_KEY: (useKeyVault || computerVisionName == '')
        ? computerVisionKeyName
        : listKeys(
            resourceId(
              subscription().subscriptionId,
              resourceGroup().name,
              'Microsoft.CognitiveServices/accounts',
              computerVisionName
            ),
            '2023-05-01'
          ).key1
      AZURE_COSMOSDB_ACCOUNT_KEY: (useKeyVault || cosmosDBKeyName == '')
        ? cosmosDBKeyName
        : listKeys(
            resourceId(
              subscription().subscriptionId,
              resourceGroup().name,
              'Microsoft.DocumentDB/databaseAccounts',
              cosmosDBKeyName
            ),
            '2022-08-15'
          ).primaryMasterKey
    })
    keyVaultName: keyVaultName
    runtimeName: runtimeName
    runtimeVersion: runtimeVersion
    dockerFullImageName: dockerFullImageName
    scmDoBuildDuringDeployment: useDocker ? false : true
    healthCheckPath: healthCheckPath
  }
}

// Storage Blob Data Contributor
module storageBlobRoleWeb '../core/security/role.bicep' = if (authType == 'rbac') {
  name: 'storage-blob-role-web'
  params: {
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User
module openAIRoleWeb '../core/security/role.bicep' = if (authType == 'rbac') {
  name: 'openai-role-web'
  params: {
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908'
    principalType: 'ServicePrincipal'
  }
}

// Contributor
// This role is used to grant the service principal contributor access to the resource group
// See if this is needed in the future.
module openAIRoleWebContributor '../core/security/role.bicep' = if (authType == 'rbac') {
  name: 'openai-role-web-contributor'
  params: {
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: 'b24988ac-6180-42a0-ab88-20f7382dd24c'
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor
module searchRoleWeb '../core/security/role.bicep' = if (authType == 'rbac') {
  name: 'search-role-web'
  params: {
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
    principalType: 'ServicePrincipal'
  }
}

module webaccess '../core/security/keyvault-access.bicep' = if (useKeyVault) {
  name: 'web-keyvault-access'
  params: {
    keyVaultName: keyVaultName
    principalId: web.outputs.identityPrincipalId
  }
}

resource cosmosRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-05-15' existing = {
  name: '${json(appSettings.AZURE_COSMOSDB_INFO).accountName}/00000000-0000-0000-0000-000000000002'
}

module cosmosUserRole '../core/database/cosmos-sql-role-assign.bicep' = {
  name: 'cosmos-sql-user-role-${web.name}'
  params: {
    accountName: json(appSettings.AZURE_COSMOSDB_INFO).accountName
    roleDefinitionId: cosmosRoleDefinition.id
    principalId: web.outputs.identityPrincipalId
  }
  dependsOn: [
    cosmosRoleDefinition
  ]
}

output FRONTEND_API_IDENTITY_PRINCIPAL_ID string = web.outputs.identityPrincipalId
output FRONTEND_API_NAME string = web.outputs.name
output FRONTEND_API_URI string = web.outputs.uri
