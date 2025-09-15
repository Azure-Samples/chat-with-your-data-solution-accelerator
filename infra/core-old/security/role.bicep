// core/security/role.bicep
metadata description = 'Creates a role assignment for a principal.'
param principalId string
param roleDefinitionId string
@description('Type of principal. Leave empty for auto-detection.')
@allowed([
  ''
  'Device'
  'ForeignGroup'
  'Group'
  'ServicePrincipal'
  'User'
])
param principalType string = ''
resource role 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().id, resourceGroup().id, principalId, roleDefinitionId)
  properties: {
    principalId: principalId
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
    // Only include principalType if explicitly provided
    ...(principalType != '' ? { principalType: principalType } : {})
  }
}
