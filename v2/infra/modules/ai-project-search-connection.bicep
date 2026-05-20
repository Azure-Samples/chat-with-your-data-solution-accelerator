// ========================================================================
// Pillar:  Stable Core
// Phase:   1 (Infrastructure + Project Skeleton)
// Purpose: Foundry Project connection to Azure AI Search. Registers the
//          Search service with the Project so Foundry IQ knowledge bases
//          can resolve it by friendly name and so the Project's system
//          identity is the auth principal (Entra-only, no admin keys).
//
//          Deployed only in databaseType=='cosmosdb' mode. In
//          postgresql mode the Project uses pgvector via the
//          Postgres/AI-Search extension instead.
// ========================================================================

targetScope = 'resourceGroup'

@description('Required. Name of the parent AI Services account.')
param aiServicesAccountName string

@description('Required. Name of the Foundry Project (sub-resource of the account).')
param projectName string

@description('Required. Name of the Azure AI Search service to connect.')
param searchServiceName string

@description('Optional. Friendly name for the connection inside the Project. Lower-case, no spaces.')
param connectionName string = 'search-${searchServiceName}'

resource searchService 'Microsoft.Search/searchServices@2025-02-01-preview' existing = {
  name: searchServiceName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  name: '${aiServicesAccountName}/${projectName}'
}

resource connection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: connectionName
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${searchServiceName}.search.windows.net'
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: searchService.id
      location: searchService.location
    }
  }
}

@description('Resource ID of the Project connection.')
output resourceId string = connection.id

@description('Friendly name of the Project connection (use this from agent code / Foundry IQ knowledge-base config).')
output name string = connection.name
