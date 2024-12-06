metadata description = 'Creates an Azure Key Vault.'
param name string
param location string = resourceGroup().location
param tags object = {}
param managedIdentityObjectId string = ''

param principalId string = ''

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    accessPolicies: concat(
      managedIdentityObjectId != '' ? [
        {
          objectId: managedIdentityObjectId
          permissions: {
            keys: [
              'get'
              'list'
            ]
            secrets: [
              'get'
              'list'
            ]
          }
          tenantId: subscription().tenantId
        }
      ] : [],
      principalId != '' ? [
        {
          objectId: principalId
          permissions: {
            keys: [
              'get'
              'list'
            ]
            secrets: [
              'get'
              'list'
            ]
          }
          tenantId: subscription().tenantId
        }
      ] : []
    )
  }
}

// @description('This is the built-in Key Vault Administrator role.')
// resource kvAdminRole 'Microsoft.Authorization/roleDefinitions@2018-01-01-preview' existing = {
//   scope: resourceGroup()
//   name: '00482a5a-887f-4fb3-b363-3b7fe8e74483'
// }

// resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
//   name: guid(resourceGroup().id, managedIdentityObjectId, kvAdminRole.id)
//   properties: {
//     principalId: managedIdentityObjectId
//     roleDefinitionId:kvAdminRole.id
//     principalType: 'ServicePrincipal'
//   }
// }

output endpoint string = keyVault.properties.vaultUri
output name string = keyVault.name
output id string = keyVault.id
