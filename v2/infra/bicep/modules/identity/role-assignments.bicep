// ============================================================================
// Module: Role Assignments (centralized — all cross-service + data plane RBAC)
// Description: RG-level, cross-service, and data-plane role assignments.
//              One place to audit "who has access to what".
// ============================================================================

// ============================================================================
// Parameters
// ============================================================================

@description('Solution name suffix for generating unique role assignment GUIDs.')
param solutionName string = ''

@description('Whether to use an existing AI project (true) or create new (false).')
param useExistingAIProject bool = false

@description('Resource ID of the existing AI project (for deriving AI Services name/sub/RG).')
param existingFoundryProjectResourceId string = ''

// --- Identity Principal IDs ---

@description('Principal ID of the AI project identity (works for both new and existing projects).')
param aiProjectPrincipalId string = ''

@description('Principal ID of the AI Search identity.')
param aiSearchPrincipalId string = ''

@description('Principal ID of the backend App Service system-assigned identity (empty if not deployed).')
param backendAppServicePrincipalId string = ''

@description('Principal ID of the deploying user (for user access roles).')
param deployerPrincipalId string = ''

@description('Principal type of the deploying user.')
@allowed(['User', 'ServicePrincipal'])
param deployerPrincipalType string = 'User'

// --- Resource References ---

@description('Resource ID of the AI Foundry account (empty if not deployed — new project path).')
param aiFoundryResourceId string = ''

@description('Resource ID of the AI Search service (empty if not deployed).')
param aiSearchResourceId string = ''

@description('Resource ID of the Storage Account (empty if not deployed).')
param storageAccountResourceId string = ''

@description('Name of the Cosmos DB account (empty if not deployed).')
param cosmosDbAccountName string = ''

// ============================================================================
// Derived Variables
// ============================================================================

var existingAIFoundryName = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[8] : ''
var existingAIFoundrySubscription = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[2] : subscription().subscriptionId
var existingAIFoundryResourceGroup = useExistingAIProject ? split(existingFoundryProjectResourceId, '/')[4] : resourceGroup().name

// ============================================================================
// Role Definitions
// ============================================================================

var roleDefinitions = {
  azureAiUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Foundry User
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  cognitiveServicesOpenAIUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  storageBlobDataReader: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
}

// ============================================================================
// Existing Resource References
// ============================================================================

resource aiFoundryAccount 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = if (!empty(aiFoundryResourceId)) {
  name: last(split(aiFoundryResourceId, '/'))
}

resource aiSearchService 'Microsoft.Search/searchServices@2025-05-01' existing = if (!empty(aiSearchResourceId)) {
  name: last(split(aiSearchResourceId, '/'))
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2025-08-01' existing = if (!empty(storageAccountResourceId)) {
  name: last(split(storageAccountResourceId, '/'))
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2025-10-15' existing = if (!empty(cosmosDbAccountName)) {
  name: cosmosDbAccountName
}

resource cosmosContributorRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2025-10-15' existing = if (!empty(cosmosDbAccountName)) {
  parent: cosmosAccount
  name: '00000000-0000-0000-0000-000000000002' // Cosmos DB Built-in Data Contributor
}

// ============================================================================
// 1. AI SERVICES ROLE ASSIGNMENTS
//    Cross-service roles scoped to AI Foundry account
// ============================================================================

// AI Search → Cognitive Services OpenAI User on AI Foundry (new project, same RG)
resource assignOpenAIRoleToAISearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingAIProject && !empty(aiSearchPrincipalId) && !empty(aiFoundryResourceId)) {
  name: guid(solutionName, aiFoundryAccount.id, aiSearchPrincipalId, roleDefinitions.cognitiveServicesOpenAIUser)
  scope: aiFoundryAccount
  properties: {
    principalId: aiSearchPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.cognitiveServicesOpenAIUser)
    principalType: 'ServicePrincipal'
  }
}

// AI Search → Cognitive Services OpenAI User on existing AI Foundry (cross-scope)
module assignOpenAIToSearchExisting './cross-scope-role-assignment.bicep' = if (useExistingAIProject && !empty(aiSearchPrincipalId)) {
  name: 'assignOpenAIRoleToAISearchExisting'
  scope: resourceGroup(existingAIFoundrySubscription, existingAIFoundryResourceGroup)
  params: {
    principalId: aiSearchPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.cognitiveServicesOpenAIUser)
    roleAssignmentName: guid(solutionName, existingAIFoundryName, aiSearchPrincipalId, roleDefinitions.cognitiveServicesOpenAIUser)
    aiFoundryName: existingAIFoundryName
  }
}

// Backend App Service → Foundry User on AI Foundry (new project, same RG)
resource backendAppAiUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingAIProject && !empty(aiFoundryResourceId) && !empty(backendAppServicePrincipalId)) {
  name: guid(solutionName, aiFoundryAccount.id, backendAppServicePrincipalId, roleDefinitions.azureAiUser)
  scope: aiFoundryAccount
  properties: {
    principalId: backendAppServicePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.azureAiUser)
    principalType: 'ServicePrincipal'
  }
}

// Backend App Service → Foundry User on existing AI Foundry (cross-scope)
module backendAppAiUserExisting './cross-scope-role-assignment.bicep' = if (useExistingAIProject && !empty(backendAppServicePrincipalId)) {
  name: 'assignAiUserRoleToBackendExisting'
  scope: resourceGroup(existingAIFoundrySubscription, existingAIFoundryResourceGroup)
  params: {
    principalId: backendAppServicePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.azureAiUser)
    roleAssignmentName: guid(solutionName, existingAIFoundryName, backendAppServicePrincipalId, roleDefinitions.azureAiUser)
    aiFoundryName: existingAIFoundryName
  }
}

// ============================================================================
// 2. SEARCH SERVICE ROLE ASSIGNMENTS
//    AI Project and Backend identities → AI Search
// ============================================================================

// AI Project → Search Index Data Reader on AI Search
resource projectSearchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(aiSearchResourceId) && !empty(aiProjectPrincipalId)) {
  name: guid(solutionName, aiSearchService.id, aiProjectPrincipalId, roleDefinitions.searchIndexDataReader)
  scope: aiSearchService
  properties: {
    principalId: aiProjectPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.searchIndexDataReader)
    principalType: 'ServicePrincipal'
  }
}

// AI Project → Search Service Contributor on AI Search
resource projectSearchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(aiSearchResourceId) && !empty(aiProjectPrincipalId)) {
  name: guid(solutionName, aiSearchService.id, aiProjectPrincipalId, roleDefinitions.searchServiceContributor)
  scope: aiSearchService
  properties: {
    principalId: aiProjectPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.searchServiceContributor)
    principalType: 'ServicePrincipal'
  }
}

// Backend App Service → Search Index Data Reader on AI Search
resource backendAppSearchReaderAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(aiSearchResourceId) && !empty(backendAppServicePrincipalId)) {
  name: guid(solutionName, aiSearchService.id, backendAppServicePrincipalId, roleDefinitions.searchIndexDataReader)
  scope: aiSearchService
  properties: {
    principalId: backendAppServicePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.searchIndexDataReader)
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// 3. STORAGE ROLE ASSIGNMENTS
//    AI Project, AI Search, and Existing Project identities → Storage
// ============================================================================

// AI Project → Storage Blob Data Contributor
resource projectStorageContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(storageAccountResourceId) && !empty(aiProjectPrincipalId)) {
  name: guid(solutionName, storageAccount.id, aiProjectPrincipalId, roleDefinitions.storageBlobDataContributor)
  scope: storageAccount
  properties: {
    principalId: aiProjectPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.storageBlobDataContributor)
    principalType: 'ServicePrincipal'
  }
}

// AI Project → Storage Blob Data Reader
resource projectStorageReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(storageAccountResourceId) && !empty(aiProjectPrincipalId)) {
  name: guid(solutionName, storageAccount.id, aiProjectPrincipalId, roleDefinitions.storageBlobDataReader)
  scope: storageAccount
  properties: {
    principalId: aiProjectPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.storageBlobDataReader)
    principalType: 'ServicePrincipal'
  }
}

// AI Search → Storage Blob Data Reader
resource searchStorageReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(storageAccountResourceId) && !empty(aiSearchPrincipalId)) {
  name: guid(solutionName, storageAccount.id, aiSearchPrincipalId, roleDefinitions.storageBlobDataReader)
  scope: storageAccount
  properties: {
    principalId: aiSearchPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.storageBlobDataReader)
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// 4. COSMOS DB ROLE ASSIGNMENTS
//    Backend App Service → Cosmos DB (data-plane, uses sqlRoleAssignments)
// ============================================================================

resource backendAppCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2025-10-15' = if (!empty(cosmosDbAccountName) && !empty(backendAppServicePrincipalId)) {
  parent: cosmosAccount
  name: guid(solutionName, cosmosContributorRoleDefinition.id, cosmosAccount.id, backendAppServicePrincipalId)
  properties: {
    principalId: backendAppServicePrincipalId
    roleDefinitionId: cosmosContributorRoleDefinition.id
    scope: cosmosAccount.id
  }
}

// ============================================================================
// 5. DEPLOYER (USER) ROLE ASSIGNMENTS
//    Deploying user → AI Services, Search, Storage (Bicep-only)
// ============================================================================

// Deploying User → Cognitive Services User on AI Services
resource deployerAiServicesAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingAIProject && !empty(deployerPrincipalId) && !empty(aiFoundryResourceId)) {
  scope: aiFoundryAccount
  name: guid(solutionName, aiFoundryAccount.id, deployerPrincipalId, roleDefinitions.cognitiveServicesUser)
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.cognitiveServicesUser)
    principalType: deployerPrincipalType
  }
}

// Deploying User → Foundry User on AI Services
resource deployerAzureAIAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingAIProject && !empty(deployerPrincipalId) && !empty(aiFoundryResourceId)) {
  scope: aiFoundryAccount
  name: guid(solutionName, aiFoundryAccount.id, deployerPrincipalId, roleDefinitions.azureAiUser)
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.azureAiUser)
    principalType: deployerPrincipalType
  }
}

// Deploying User → Search Index Data Contributor on AI Search
resource deployerSearchIndexContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId) && !empty(aiSearchResourceId)) {
  scope: aiSearchService
  name: guid(solutionName, aiSearchService.id, deployerPrincipalId, roleDefinitions.searchIndexDataContributor)
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.searchIndexDataContributor)
    principalType: deployerPrincipalType
  }
}

// Deploying User → Search Service Contributor on AI Search
resource deployerSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId) && !empty(aiSearchResourceId)) {
  scope: aiSearchService
  name: guid(solutionName, aiSearchService.id, deployerPrincipalId, roleDefinitions.searchServiceContributor)
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.searchServiceContributor)
    principalType: deployerPrincipalType
  }
}

// Deploying User → Storage Blob Data Contributor
resource deployerStorageBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId) && !empty(storageAccountResourceId)) {
  scope: storageAccount
  name: guid(solutionName, storageAccount.id, deployerPrincipalId, roleDefinitions.storageBlobDataContributor)
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.storageBlobDataContributor)
    principalType: deployerPrincipalType
  }
}

// NOTE: Deployer roles on existing AI Foundry (cross-scope) are assigned via
// 00_build_solution.py to avoid conflicts when the deployer already has the roles.
