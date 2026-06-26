// ============================================================================
// Module: Role Assignments (centralized — all cross-service + data plane RBAC)
// Description: RG-level, cross-service, and data-plane role assignments for the
//              native bicep flavor. One place to audit "who has access to what".
//              Mirrors the avm flavor's centralized, array-driven role-assignments
//              module: the caller (main.bicep) builds typed arrays of
//              { principalId, principalType, roleDefinitionId } and this module
//              loops them, scoping each assignment to its target resource.
// ============================================================================

// ============================================================================
// Parameters — target resource names (scopes)
// ============================================================================

@description('Whether the deployment targets Cosmos DB + AI Search (true) or PostgreSQL (false).')
param isCosmos bool

@description('Name of the AI Foundry (Cognitive Services) account.')
param aiFoundryName string

@description('Name of the Speech service account.')
param speechServiceName string

@description('Name of the Content Safety service account.')
param contentSafetyServiceName string

@description('Name of the Container Registry.')
param containerRegistryName string

@description('Name of the Storage Account.')
param storageName string

@description('Name of the AI Search service (cosmosdb mode only).')
param aiSearchName string

@description('Name of the Cosmos DB account (cosmosdb mode only).')
param cosmosDbName string

// ============================================================================
// Parameters — role assignment data (typed by scope)
// Each item: { principalId: string, principalType: string, roleDefinitionId: string (GUID) }
// ============================================================================

@description('Role assignments scoped to the AI Foundry account.')
param foundryRoleAssignments array = []

@description('Role assignments scoped to the Speech service.')
param speechRoleAssignments array = []

@description('Role assignments scoped to the Content Safety service.')
param contentSafetyRoleAssignments array = []

@description('Role assignments scoped to the Container Registry.')
param registryRoleAssignments array = []

@description('Role assignments scoped to the Storage Account.')
param storageRoleAssignments array = []

@description('Role assignments scoped to the AI Search service (cosmosdb mode only).')
param searchRoleAssignments array = []

@description('Cosmos DB SQL data-plane role assignments (cosmosdb mode only). Each item: { principalId, roleDefinitionId (Cosmos SQL role GUID) }.')
param cosmosSqlRoleAssignments array = []

// ============================================================================
// Existing Resource References (deterministic names = calculable scopes)
// ============================================================================

resource aiFoundryAccountResource 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: aiFoundryName
}

resource speechServiceResource 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: speechServiceName
}

resource contentSafetyResource 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: contentSafetyServiceName
}

resource containerRegistryResource 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  #disable-next-line BCP334
  name: containerRegistryName
}

resource storageAccountResource 'Microsoft.Storage/storageAccounts@2025-08-01' existing = {
  #disable-next-line BCP334
  name: storageName
}

resource searchServiceResource 'Microsoft.Search/searchServices@2025-05-01' existing = if (isCosmos) {
  name: aiSearchName
}

resource cosmosAccountResource 'Microsoft.DocumentDB/databaseAccounts@2025-10-15' existing = if (isCosmos) {
  name: cosmosDbName
}

// ============================================================================
// Role Assignments — one typed loop per scope
// ============================================================================

resource foundryRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for ra in foundryRoleAssignments: {
    name: guid(aiFoundryAccountResource.id, ra.principalId, ra.roleDefinitionId)
    scope: aiFoundryAccountResource
    properties: {
      principalId: ra.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', ra.roleDefinitionId)
      principalType: ra.principalType
    }
  }
]

resource speechRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for ra in speechRoleAssignments: {
    name: guid(speechServiceResource.id, ra.principalId, ra.roleDefinitionId)
    scope: speechServiceResource
    properties: {
      principalId: ra.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', ra.roleDefinitionId)
      principalType: ra.principalType
    }
  }
]

resource contentSafetyRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for ra in contentSafetyRoleAssignments: {
    name: guid(contentSafetyResource.id, ra.principalId, ra.roleDefinitionId)
    scope: contentSafetyResource
    properties: {
      principalId: ra.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', ra.roleDefinitionId)
      principalType: ra.principalType
    }
  }
]

resource registryRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for ra in registryRoleAssignments: {
    name: guid(containerRegistryResource.id, ra.principalId, ra.roleDefinitionId)
    scope: containerRegistryResource
    properties: {
      principalId: ra.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', ra.roleDefinitionId)
      principalType: ra.principalType
    }
  }
]

resource storageRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for ra in storageRoleAssignments: {
    name: guid(storageAccountResource.id, ra.principalId, ra.roleDefinitionId)
    scope: storageAccountResource
    properties: {
      principalId: ra.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', ra.roleDefinitionId)
      principalType: ra.principalType
    }
  }
]

resource searchRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for ra in searchRoleAssignments: if (isCosmos) {
    name: guid(searchServiceResource.id, ra.principalId, ra.roleDefinitionId)
    scope: searchServiceResource
    properties: {
      principalId: ra.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', ra.roleDefinitionId)
      principalType: ra.principalType
    }
  }
]

resource cosmosSqlRoles 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2025-10-15' = [
  for ra in cosmosSqlRoleAssignments: if (isCosmos) {
    parent: cosmosAccountResource
    name: guid(cosmosAccountResource.id, ra.principalId, ra.roleDefinitionId)
    properties: {
      principalId: ra.principalId
      roleDefinitionId: '${cosmosAccountResource.id}/sqlRoleDefinitions/${ra.roleDefinitionId}'
      scope: cosmosAccountResource.id
    }
  }
]
