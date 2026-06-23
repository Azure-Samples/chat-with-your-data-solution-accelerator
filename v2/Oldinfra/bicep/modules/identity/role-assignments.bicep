// ============================================================================
// Module: Role Assignments (centralized — all cross-service + data plane RBAC)
// Description: RG-level, cross-service, and data-plane role assignments.
//              One place to audit "who has access to what".
//
//              Supports two assignment kinds:
//                1. ARM control-plane roles (default) via
//                   Microsoft.Authorization/roleAssignments — pass an ARM
//                   role definition GUID in `roleDefinitionId`.
//                2. Cosmos DB SQL data-plane roles — set `cosmosDbAccountName`
//                   to the target Cosmos NoSQL account. `roleDefinitionId`
//                   then refers to a Cosmos SQL role definition GUID
//                   (defaults to Built-in Data Contributor
//                   00000000-0000-0000-0000-000000000002). This is required
//                   when local auth is disabled — ARM role assignments alone
//                   do NOT grant Cosmos data-plane access.
// ============================================================================

@description('The principal ID of the user, group, or service principal to assign the role to.')
param principalId string

@allowed([
  'Device'
  'ForeignGroup'
  'Group'
  'ServicePrincipal'
  'User'
])
@description('The type of principal to assign the role to. Allowed values: Device, ForeignGroup, Group, ServicePrincipal, User. Ignored for Cosmos SQL role assignments (Cosmos infers type from the principal).')
param principalType string = 'ServicePrincipal'

@description('The role definition ID to assign. For ARM assignments this is a built-in or custom role GUID. For Cosmos SQL assignments (when cosmosDbAccountName is set) this is a Cosmos SQL role definition GUID — defaults to the Built-in Data Contributor (00000000-0000-0000-0000-000000000002).')
param roleDefinitionId string

@description('Optional. The name of an existing Cosmos DB (NoSQL) account. When provided, this module creates a Cosmos SQL data-plane role assignment instead of an ARM role assignment.')
param cosmosDbAccountName string = ''


resource role 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(cosmosDbAccountName)) {
  name: guid(subscription().id, resourceGroup().id, principalId, roleDefinitionId)
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
  }
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = if (!empty(cosmosDbAccountName)) {
  name: cosmosDbAccountName
}

resource cosmosSqlRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (!empty(cosmosDbAccountName)) {
  parent: cosmos
  name: guid(resourceGroup().id, cosmosDbAccountName, principalId, roleDefinitionId)
  properties: {
    principalId: principalId
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/${roleDefinitionId}'
    scope: cosmos.id
  }
}

