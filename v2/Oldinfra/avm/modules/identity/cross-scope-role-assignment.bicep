// ============================================================================
// cross-scope-role-assignment.bicep
// Description: Reusable helper that creates a single role assignment scoped
//              to an existing AI Services resource. Used for cross-resource-
//              group RBAC where the AI Services lives in a different RG.
// ============================================================================

@description('The principal ID to assign the role to.')
param principalId string

@description('The resource ID of the role definition to assign.')
param roleDefinitionId string

@description('A unique name for the role assignment.')
param roleAssignmentName string

@description('The name of the AI Foundry account to scope the role assignment to.')
param aiFoundryName string

@description('The principal type of the identity being assigned.')
@allowed(['ServicePrincipal', 'User'])
param principalType string = 'ServicePrincipal'

// Reference the existing AI Foundry resource in this resource group
resource aiFoundryAccount 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: aiFoundryName
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: roleAssignmentName
  scope: aiFoundryAccount
  properties: {
    roleDefinitionId: roleDefinitionId
    principalId: principalId
    principalType: principalType
  }
}
