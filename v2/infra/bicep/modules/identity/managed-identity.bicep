// ============================================================================
// Module: User-Assigned Managed Identity (Generic)
// Description: Creates a user-assigned managed identity.
//              This module is NOT called from main.bicep by default.
//              Use it when you need a user-assigned identity for specific scenarios
//              (e.g., Container Apps, cross-tenant access, pre-provisioned RBAC).
// ============================================================================

@description('Solution name used for resource naming.')
param solutionName string

@description('Name of the managed identity.')
param identityName string = 'id-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

// ============================================================================
// Resource Deployment
// ============================================================================
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the managed identity.')
output resourceId string = managedIdentity.id

@description('Principal ID (object ID) of the managed identity.')
output principalId string = managedIdentity.properties.principalId

@description('Client ID of the managed identity.')
output clientId string = managedIdentity.properties.clientId

@description('Name of the managed identity.')
output name string = managedIdentity.name
