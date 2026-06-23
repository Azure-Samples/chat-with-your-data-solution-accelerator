// ============================================================================
// Module: AI Search
// Description: Deploys Azure AI Search with a two-step pattern:
//   Step 1: Plain Bicep resource for fast initial creation (name, location, SKU)
//   Step 2: Separate module deployment to enable managed identity & full config
// This reduces deployment time by making the resource available immediately
// while identity enablement proceeds as a separate ARM deployment.
// ============================================================================

targetScope = 'resourceGroup'

@description('Solution name suffix used to derive the resource name.')
@minLength(3)
param solutionName string

@description('Optional. Override name for the search service. Defaults to srch-{solutionName}.')
param name string = 'srch-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('SKU name for the search service.')
@allowed(['free', 'basic', 'standard', 'standard2', 'standard3', 'storage_optimized_l1', 'storage_optimized_l2'])
param skuName string = 'basic'

@description('Number of replicas.')
param replicaCount int = 1

@description('Number of partitions.')
param partitionCount int = 1

@description('Hosting mode.')
@allowed(['Default', 'HighDensity'])
param hostingMode string = 'Default'

@description('Semantic search tier.')
@allowed(['disabled', 'free', 'standard'])
param semanticSearch string = 'free'

@description('Whether to disable local authentication.')
param disableLocalAuth bool = true

@description('Managed identity type for the search service.')
param managedIdentityType string = 'SystemAssigned'

@description('Public network access setting.')
param publicNetworkAccess string = 'Enabled'

// ============================================================================
// Step 1: Initial resource creation (fast — no identity)
// ============================================================================
resource aiSearch 'Microsoft.Search/searchServices@2025-05-01' = {
  name: name
  location: location
  sku: {
    name: skuName
  }
}

// ============================================================================
// Step 2: Separate deployment — enables identity & full configuration
// ============================================================================
module searchServiceUpdate 'ai-search-identity.bicep' = {
  name: 'searchServiceUpdate'
  params: {
    name: aiSearch.name
    location: location
    tags: tags
    skuName: skuName
    replicaCount: replicaCount
    partitionCount: partitionCount
    hostingMode: hostingMode
    semanticSearch: semanticSearch
    disableLocalAuth: disableLocalAuth
    managedIdentityType: managedIdentityType
    publicNetworkAccess: publicNetworkAccess
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Resource ID of the AI Search service.')
output resourceId string = aiSearch.id

@description('Name of the AI Search service.')
output name string = aiSearch.name

@description('Endpoint URL of the AI Search service.')
output endpoint string = 'https://${aiSearch.name}.search.windows.net'

@description('System-assigned identity principal ID.')
output identityPrincipalId string = searchServiceUpdate.outputs.systemAssignedMIPrincipalId
