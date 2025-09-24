@description('Optional. Array of role assignments to apply to the system-assigned identity at the Cognitive Services account scope. Each item: { roleDefinitionId: "<GUID or built-in role definition id>" }')
param roleAssignments array = []

@description('Role assignments applied to the system-assigned identity via AVM module. Objects can include: roleDefinitionId (req), roleName, principalType, resourceId.')
module roleAssignmentsModule 'br/public:avm/ptn/authorization/resource-role-assignment:0.1.2' = [
  for assignment in roleAssignments: {
    name: take(
      'avm.ptn.authorization.resource-role-assignment.${uniqueString(assignment.principalId, assignment.roleDefinitionId, assignment.resourceId)}',
      64
    )
    params: {
      principalId: assignment.principalId
      roleDefinitionId: assignment.roleDefinitionId
      resourceId: assignment.resourceId
      roleName: assignment.roleName
      principalType: assignment.principalType
    }
  }
]
