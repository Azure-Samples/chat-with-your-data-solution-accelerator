param name string
param location string = resourceGroup().location
param tags object = {}
param allowedOrigins array = []
param appServicePlanId string
param appCommandLine string = 'python -m streamlit run Admin.py --server.port 8000 --server.address 0.0.0.0 --server.enableXsrfProtection false'
param runtimeName string = 'python'
param runtimeVersion string = ''
param applicationInsightsName string = ''
param keyVaultName string = ''
@secure()
param appSettings object = {}
param dockerFullImageName string = ''
param useDocker bool = dockerFullImageName != ''
param databaseType string = 'CosmosDB' // 'CosmosDB' or 'PostgreSQL'

module adminweb '../core/host/appservice.bicep' = {
  name: '${name}-app-module'
  params: {
    name: name
    location: location
    tags: tags
    allowedOrigins: allowedOrigins
    appCommandLine: useDocker ? '' : appCommandLine
    runtimeName: runtimeName
    runtimeVersion: runtimeVersion
    keyVaultName: keyVaultName
    dockerFullImageName: dockerFullImageName
    scmDoBuildDuringDeployment: useDocker ? false : true
    applicationInsightsName: applicationInsightsName
    appServicePlanId: appServicePlanId
    managedIdentity: databaseType == 'PostgreSQL'
    appSettings: appSettings
  }
}

// Storage Blob Data Contributor
module storageRoleBackend '../core/security/role.bicep' = {
  name: 'storage-role-backend'
  params: {
    principalId: adminweb.outputs.identityPrincipalId
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User
module openAIRoleBackend '../core/security/role.bicep' = {
  name: 'openai-role-backend'
  params: {
    principalId: adminweb.outputs.identityPrincipalId
    roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908'
    principalType: 'ServicePrincipal'
  }
}

// Contributor
// This role is used to grant the service principal contributor access to the resource group
// See if this is needed in the future.
module openAIRoleBackendContributor '../core/security/role.bicep' = {
  name: 'openai-role-backend-contributor'
  params: {
    principalId: adminweb.outputs.identityPrincipalId
    roleDefinitionId: 'b24988ac-6180-42a0-ab88-20f7382dd24c'
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor
module searchRoleBackend '../core/security/role.bicep' = {
  name: 'search-role-backend'
  params: {
    principalId: adminweb.outputs.identityPrincipalId
    roleDefinitionId: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
    principalType: 'ServicePrincipal'
  }
}

module adminwebaccess '../core/security/keyvault-access.bicep' = {
  name: 'adminweb-keyvault-access'
  params: {
    keyVaultName: keyVaultName
    principalId: adminweb.outputs.identityPrincipalId
  }
}

output WEBSITE_ADMIN_IDENTITY_PRINCIPAL_ID string = adminweb.outputs.identityPrincipalId
output WEBSITE_ADMIN_NAME string = adminweb.outputs.name
output WEBSITE_ADMIN_URI string = adminweb.outputs.uri
