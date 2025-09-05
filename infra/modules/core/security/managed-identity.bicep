// ========== Managed Identity ========== //
targetScope = 'resourceGroup'

// @minLength(3)
// @maxLength(15)
// @description('Solution Name')
// param solutionName string

@description('Solution Location')
param solutionLocation string

@description('Name')
param miName string

@description('Enable Telemetry')
param enableTelemetry bool = false

@description('Optional. Tags to be applied to the resources.')
param tags object = {}

module userAssignedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: take('avm.res.managed-identity.user-assigned-identity.${miName}', 64)
  params: {
    name: miName
    location: solutionLocation
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

@description('This is the built-in owner role. See https://docs.microsoft.com/azure/role-based-access-control/built-in-roles#owner')
resource ownerRoleDefinition 'Microsoft.Authorization/roleDefinitions@2018-01-01-preview' existing = {
  scope: resourceGroup()
  name: '8e3af657-a8ff-443c-a75c-2fe8c4bcb635'
}

// var userAssignedIdentityId = userAssignedIdentity.outputs.resourceId

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, ownerRoleDefinition.id)
  properties: {
    principalId: userAssignedIdentity.outputs.principalId
    roleDefinitionId: ownerRoleDefinition.id
    principalType: 'ServicePrincipal'
  }
}

output managedIdentityOutput object = {
  id: userAssignedIdentity.outputs.resourceId
  objectId: userAssignedIdentity.outputs.principalId
  name: miName
}
