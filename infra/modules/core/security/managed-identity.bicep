// ========== Managed Identity ========== //
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

output managedIdentityOutput object = {
  id: userAssignedIdentity.outputs.resourceId
  objectId: userAssignedIdentity.outputs.principalId
  clientId: userAssignedIdentity.outputs.clientId
  name: miName
}
