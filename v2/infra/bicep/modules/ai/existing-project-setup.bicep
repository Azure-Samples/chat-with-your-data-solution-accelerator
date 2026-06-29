// ============================================================================
// Module: Existing AI Foundry Project Reference — Vanilla Bicep
// Description: References an existing AI Services account and project to
//              retrieve their identities. No deployments, no connections.
//              Use generic ai-foundry-connection and ai-foundry-model-deployment
//              modules for those concerns.
// ============================================================================

@description('Required. The name of the existing Cognitive Services account.')
param name string

@description('Required. The name of the existing AI project.')
param projectName string

@description('Optional. Principal ID of the user-assigned managed identity that needs data-plane access to the BYO foundry. Empty disables its grants.')
param uamiPrincipalId string = ''

@description('Optional. Object ID of the deploying user/principal that needs data-plane access to the BYO foundry. Empty disables its grants.')
param deployingUserPrincipalId string = ''

@description('Optional. Principal type of the deploying user (User or ServicePrincipal).')
param deployingUserPrincipalType string = 'User'

@description('Optional. Principal ID of the AI Search service identity (cosmosdb mode only). Empty disables its grants.')
param searchPrincipalId string = ''

@description('Optional. Whether the deployment targets Cosmos DB + AI Search (true); enables the search identity grants on the BYO foundry.')
param isCosmos bool = false

// ----- Role definition GUIDs (built-in roles) — RBAC owned by this module,
// not by main.bicep, mirroring modules/identity/role-assignments.bicep. -----
var roleIds = {
  cognitiveServicesOpenAIUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  azureAiUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
}

// The UAMI (app runtime), deploying user, and cosmos-mode search identity need
// these data-plane roles on the BYO foundry account.
var foundryRoleAssignments = union(
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

// ============================================================================
// Existing Resource References
// ============================================================================

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: name
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' existing = {
  parent: aiServices
  name: projectName
}

// ============================================================================
// Role Assignments — granted on the existing foundry account scope. Because
// this module is deployed into the foundry's own subscription/resource group,
// these assignments work even when the BYO foundry is cross-subscription.
// Entries with an empty principalId are filtered out to avoid InvalidPrincipalId.
// ============================================================================

var foundryRoleAssignmentsToCreate = filter(
  foundryRoleAssignments,
  assignment => !empty(assignment.principalId)
)

resource foundryRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for assignment in foundryRoleAssignmentsToCreate: {
    name: guid(aiServices.id, assignment.principalId, assignment.roleDefinitionId)
    scope: aiServices
    properties: {
      principalId: assignment.principalId
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', assignment.roleDefinitionId)
      principalType: assignment.principalType
    }
  }
]

// ============================================================================
// Outputs (aligned with ai-foundry-project.bicep)
// ============================================================================

@description('Resource ID of the AI Services account.')
output resourceId string = aiServices.id

@description('Name of the AI Services account.')
output name string = aiServices.name

@description('Endpoint of the AI Services account (OpenAI Language Model Instance API).')
output endpoint string = aiServices.properties.endpoints['OpenAI Language Model Instance API']

@description('Endpoint of the AI Services account (Cognitive Services).')
output cognitiveServicesEndpoint string = aiServices.properties.endpoint

@description('Azure OpenAI Content Understanding endpoint URL.')
output azureOpenAiCuEndpoint string = aiServices.properties.endpoints['Content Understanding']

@description('System-assigned identity principal ID of the AI Services account (empty if none).')
output principalId string = contains(aiServices, 'identity') && contains(aiServices.identity, 'principalId') ? aiServices.identity.principalId : ''

@description('Resource ID of the AI Foundry project.')
output projectResourceId string = aiProject.id

@description('Name of the AI Foundry project.')
output projectName string = aiProject.name

@description('AI Foundry project endpoint.')
output projectEndpoint string = aiProject.properties.endpoints['AI Foundry API']

@description('System-assigned identity principal ID of the project (empty if none).')
output projectIdentityPrincipalId string = contains(aiProject, 'identity') && contains(aiProject.identity, 'principalId') ? aiProject.identity.principalId : ''
