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
@secure()
param appSettings object = {}

param dockerFullImageName string = ''
param useDocker bool = dockerFullImageName != ''
param healthCheckPath string = ''

// Database parameters
param databaseType string = 'CosmosDB' // 'CosmosDB' or 'PostgreSQL'


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
    appSettings: appSettings
    runtimeName: runtimeName
    runtimeVersion: runtimeVersion
    dockerFullImageName: dockerFullImageName
    scmDoBuildDuringDeployment: useDocker ? false : true
    healthCheckPath: healthCheckPath
    keyVaultName: keyVaultName
    managedIdentity: databaseType == 'PostgreSQL'
  }
}

// Storage Blob Data Contributor
module storageBlobRoleWeb '../core/security/role.bicep' = {
  name: 'storage-blob-role-web'
  params: {
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User
module openAIRoleWeb '../core/security/role.bicep' = {
  name: 'openai-role-web'
  params: {
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908'
    principalType: 'ServicePrincipal'
  }
}

// Contributor
module openAIRoleWebContributor '../core/security/role.bicep' = {
  name: 'openai-role-web-contributor'
  params: {
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: 'b24988ac-6180-42a0-ab88-20f7382dd24c'
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor
module searchRoleWeb '../core/security/role.bicep' = {
  name: 'search-role-web'
  params: {
    principalId: web.outputs.identityPrincipalId
    roleDefinitionId: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
    principalType: 'ServicePrincipal'
  }
}

module webaccess '../core/security/keyvault-access.bicep' = {
  name: 'web-keyvault-access'
  params: {
    keyVaultName: keyVaultName
    principalId: web.outputs.identityPrincipalId
  }
}

resource cosmosRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-05-15' existing = {
  name: '${appSettings.AZURE_COSMOSDB_ACCOUNT_NAME}/00000000-0000-0000-0000-000000000002'
}

module cosmosUserRole '../core/database/cosmos-sql-role-assign.bicep' = if (databaseType == 'CosmosDB') {
  name: 'cosmos-sql-user-role-${web.name}'
  params: {
    accountName: appSettings.AZURE_COSMOSDB_ACCOUNT_NAME
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
