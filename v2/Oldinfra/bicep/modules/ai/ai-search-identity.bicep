// ============================================================================
// Module: AI Search Identity Update
// Description: Separate deployment that enables managed identity and applies
//              full configuration on an existing AI Search service.
//              Called by ai-search.bicep as Step 2 of the two-step pattern.
// ============================================================================

targetScope = 'resourceGroup'

@description('The name of the existing AI Search service.')
param name string

@description('The Azure region of the search service.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('SKU name for the search service.')
param skuName string = 'basic'

@description('Number of replicas.')
param replicaCount int = 1

@description('Number of partitions.')
param partitionCount int = 1

@description('Hosting mode.')
@allowed(['Default', 'HighDensity'])
param hostingMode string = 'Default'

@description('Semantic search tier.')
param semanticSearch string = 'free'

@description('Whether to disable local authentication.')
param disableLocalAuth bool = true

@description('Managed identity type for the search service.')
param managedIdentityType string = 'SystemAssigned'

@description('Public network access setting.')
param publicNetworkAccess string = 'Enabled'

resource searchServiceUpdate 'Microsoft.Search/searchServices@2025-05-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  identity: {
    type: managedIdentityType
  }
  properties: {
    replicaCount: replicaCount
    partitionCount: partitionCount
    hostingMode: hostingMode
    semanticSearch: semanticSearch
    disableLocalAuth: disableLocalAuth
    publicNetworkAccess: publicNetworkAccess
  }
}

@description('The principal ID of the AI Search system-assigned managed identity.')
output systemAssignedMIPrincipalId string = searchServiceUpdate.identity.principalId
