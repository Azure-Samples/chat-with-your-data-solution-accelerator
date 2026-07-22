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

@description('Name of the Storage Account.')
param storageName string

@description('Name of the AI Search service (cosmosdb mode only).')
param aiSearchName string

@description('Name of the Cosmos DB account (cosmosdb mode only).')
param cosmosDbName string

// ============================================================================
// Parameters — principal IDs (who receives the roles) + flags
// ============================================================================

@description('Whether the AI Foundry project is an existing (BYO) resource; when true, foundry-scoped roles are granted cross-scope via the cross-scope-role-assignment helper instead of in-RG.')
param useExistingAIProject bool = false

@description('Subscription ID of the existing (BYO) AI Foundry account; used to scope cross-scope foundry role assignments. Defaults to the current subscription.')
param aiFoundrySubscriptionId string = subscription().subscriptionId

@description('Resource group of the existing (BYO) AI Foundry account; used to scope cross-scope foundry role assignments. Defaults to the current resource group.')
param aiFoundryResourceGroupName string = resourceGroup().name

@description('Principal ID of the user-assigned managed identity.')
param uamiPrincipalId string

@description('Principal ID of the AI Foundry account managed identity.')
param foundryAccountPrincipalId string = ''

@description('Principal ID of the AI Foundry project managed identity.')
param foundryProjectPrincipalId string = ''

@description('Principal ID of the Function App system-assigned identity.')
param functionPrincipalId string

@description('Principal ID of the Event Grid system topic system-assigned identity. When provided, Storage Queue Data Message Sender is granted on the storage account so identity-based delivery works.')
param eventGridPrincipalId string = ''

@description('Principal ID of the AI Search service identity (cosmosdb mode only).')
param searchPrincipalId string = ''

@description('Object ID of the deploying user/principal.')
param deployingUserPrincipalId string

@description('Principal type of the deploying user (User or ServicePrincipal).')
param deployingUserPrincipalType string = 'User'

// ============================================================================
// Variables — role definition GUIDs + typed role-assignment items per scope.
// Centralized here so main.bicep owns no RBAC definitions; each loop below
// consumes the matching array.
// ============================================================================

// ----- Role definition GUIDs (built-in roles) -----
var roleIds = {
  cognitiveServicesOpenAIUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  azureAiUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
  cognitiveServicesSpeechUser: 'f2dc8367-1007-4938-bd23-fe263f013447'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  storageBlobDataOwner: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  storageQueueDataContributor: '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  storageQueueDataMessageSender: 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a'
  storageAccountContributor: '17d1049b-9a84-46fb-8f53-869881c3d3ab'
}
var cosmosDataContributorRoleId = '00000000-0000-0000-0000-000000000002'

// Foundry data-plane grants. The same who-gets-what set serves both paths:
//   - new project (same RG) → in-RG foundryRoles loop below
//   - existing/BYO project   → cross-scope foundryRolesExisting module loop,
//     which lands each assignment in the foundry's own subscription/RG.
var foundryRoleAssignmentsBase = union(
  [
    { principalId: uamiPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.cognitiveServicesOpenAIUser }
    { principalId: uamiPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.cognitiveServicesUser }
    { principalId: uamiPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.azureAiUser }
    { principalId: deployingUserPrincipalId, principalType: deployingUserPrincipalType, roleDefinitionId: roleIds.cognitiveServicesUser }
    { principalId: deployingUserPrincipalId, principalType: deployingUserPrincipalType, roleDefinitionId: roleIds.azureAiUser }
  ],
  isCosmos
    ? [
        { principalId: searchPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.cognitiveServicesUser }
        { principalId: searchPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.cognitiveServicesOpenAIUser }
      ]
    : []
)

var foundryRoleAssignments = useExistingAIProject ? [] : foundryRoleAssignmentsBase

// Cross-scope (BYO) path: drop empty principals to avoid InvalidPrincipalId.
var existingFoundryRoleAssignments = useExistingAIProject
  ? filter(foundryRoleAssignmentsBase, assignment => !empty(assignment.principalId))
  : []

var speechRoleAssignments = [
  { principalId: uamiPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.cognitiveServicesSpeechUser }
]

var contentSafetyRoleAssignments = [
  { principalId: uamiPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.cognitiveServicesUser }
]

var storageRoleAssignments = union(
  union(
    [
      { principalId: uamiPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.storageBlobDataContributor }
      { principalId: uamiPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.storageQueueDataContributor }
      { principalId: uamiPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.storageAccountContributor }
      { principalId: foundryProjectPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.storageBlobDataContributor }
      { principalId: functionPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.storageBlobDataOwner }
      { principalId: functionPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.storageQueueDataContributor }
      { principalId: functionPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.storageAccountContributor }
      { principalId: deployingUserPrincipalId, principalType: deployingUserPrincipalType, roleDefinitionId: roleIds.storageBlobDataContributor }
    ],
    isCosmos
      ? [
          { principalId: searchPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.storageBlobDataContributor }
        ]
      : []
  ),
  !empty(eventGridPrincipalId)
    ? [
        { principalId: eventGridPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.storageQueueDataMessageSender }
      ]
    : []
)

var searchRoleAssignments = isCosmos
  ? [
      { principalId: uamiPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.searchIndexDataContributor }
      { principalId: uamiPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.searchServiceContributor }
      { principalId: foundryProjectPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.searchIndexDataReader }
      { principalId: foundryProjectPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.searchIndexDataContributor }
      { principalId: foundryProjectPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.searchServiceContributor }
      { principalId: foundryAccountPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.searchIndexDataContributor }
      { principalId: foundryAccountPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.searchIndexDataReader }
      { principalId: foundryAccountPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: roleIds.searchServiceContributor }
      { principalId: deployingUserPrincipalId, principalType: deployingUserPrincipalType, roleDefinitionId: roleIds.searchIndexDataContributor }
      { principalId: deployingUserPrincipalId, principalType: deployingUserPrincipalType, roleDefinitionId: roleIds.searchServiceContributor }
    ]
  : []

var cosmosSqlRoleAssignments = isCosmos
  ? [
      { principalId: uamiPrincipalId, roleDefinitionId: cosmosDataContributorRoleId }
    ]
  : []

// ============================================================================
// Existing Resource References (deterministic names = calculable scopes)
// ============================================================================

resource aiFoundryAccountResource 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = if (!empty(foundryRoleAssignments)) {
  name: empty(aiFoundryName) ? 'placeholder' : aiFoundryName
}

resource speechServiceResource 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: speechServiceName
}

resource contentSafetyResource 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: contentSafetyServiceName
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

// BYO foundry: grant the same data-plane roles cross-scope. The helper module
// is deployed into the foundry's own subscription/RG so the assignment is valid
// even when the existing foundry lives in a different subscription.
module foundryRolesExisting './cross-scope-role-assignment.bicep' = [
  for ra in existingFoundryRoleAssignments: {
    name: take('rbac-foundry-byo-${uniqueString(aiFoundryName, ra.principalId, ra.roleDefinitionId)}', 64)
    scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
    params: {
      principalId: ra.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', ra.roleDefinitionId)
      roleAssignmentName: guid(aiFoundryName, ra.principalId, ra.roleDefinitionId)
      aiFoundryName: aiFoundryName
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
