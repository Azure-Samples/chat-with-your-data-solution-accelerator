// ============================================================================
// Module: AI Foundry Project Connection (Single) — Vanilla Bicep
// Description: Creates a single connection on an AI Foundry project.
//              Generic, reusable — call once per connection type from main.bicep.
//              Supports any connection category (CognitiveSearch, AzureBlob,
//              AppInsights, RemoteTool, etc.) via parameterized properties.
// ============================================================================

targetScope = 'resourceGroup'

@description('Required. Name of the parent AI Services account.')
param aiServicesAccountName string

@description('Required. Name of the AI Foundry project.')
param projectName string

@description('Required. Solution name suffix used to generate the connection name.')
param solutionName string

@description('Optional. Connection name. Defaults to lowercase category with solution suffix.')
param connectionName string = toLower('${category}-connection-${solutionName}')

@description('Required. Connection category (e.g., CognitiveSearch, AzureBlob, AppInsights, RemoteTool).')
param category string

@description('Required. Connection target (URL or resource ID).')
param target string

@description('Required. Authentication type (e.g., AAD, ApiKey, ProjectManagedIdentity).')
param authType string

@description('Optional. Whether the connection is shared to all project users.')
param isSharedToAll bool = true

@description('Optional. Whether this is the default connection for its category.')
param isDefault bool = false

@description('Optional. Connection metadata object.')
param metadata object = {}

@description('Optional. Whether to use workspace-managed identity for authentication.')
param useWorkspaceManagedIdentity bool = false

@secure()
@description('Optional. Credentials key (for ApiKey auth type).')
param credentialsKey string = ''

// ============================================================================
// Existing Resource References
// ============================================================================
resource aiServicesAccount 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: aiServicesAccountName
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' existing = {
  parent: aiServicesAccount
  name: projectName
}

// ============================================================================
// Connection
// ============================================================================
var baseProperties = {
  category: category
  target: target
  authType: authType
  isSharedToAll: isSharedToAll
  metadata: metadata
  useWorkspaceManagedIdentity: useWorkspaceManagedIdentity
}

var optionalDefault = isDefault ? { isDefault: true } : {}
var optionalCredentials = !empty(credentialsKey) ? { credentials: { key: credentialsKey } } : {}

resource connection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = {
  parent: aiProject
  name: connectionName
  properties: any(union(baseProperties, optionalDefault, optionalCredentials))
}

// ============================================================================
// Outputs
// ============================================================================
@description('Connection name.')
output connectionName string = connection.name

@description('Connection resource ID.')
output connectionId string = connection.id
