// ============================================================================
// Module: Managed Identity
// Description: AVM wrapper for User-Assigned Managed Identity
// AVM Module: avm/res/managed-identity/user-assigned-identity
// Usage: Call this module once per identity from main.bicep
// ============================================================================

@description('Solution name used for resource naming.')
param solutionName string

@description('Name of the managed identity.')
param identityName string = 'id-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// ============================================================================
// AVM Module Deployment
// ============================================================================
module managedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.5.0' = {
  name: take('avm.res.managed-identity.user-assigned-identity.${identityName}', 64)
  params: {
    name: identityName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the managed identity.')
output resourceId string = managedIdentity.outputs.resourceId

@description('Principal ID of the managed identity.')
output principalId string = managedIdentity.outputs.principalId

@description('Client ID of the managed identity.')
output clientId string = managedIdentity.outputs.clientId

@description('Name of the managed identity.')
output name string = managedIdentity.outputs.name
