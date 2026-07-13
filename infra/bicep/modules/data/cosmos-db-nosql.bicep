// ============================================================================
// Module: Cosmos DB
// Description: Creates an Azure Cosmos DB (NoSQL) account with database/container
// API: Microsoft.DocumentDB/databaseAccounts@2025-10-15
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the Cosmos DB account.')
param name string = 'cosmos-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Database name.')
param databaseName string = 'db_conversation_history'

@description('Container definitions.')
param containers array = [
  {
    name: 'conversations'
    partitionKeyPath: '/userId'
  }
]

@description('Optional. Managed identity configuration for the resource.')
param identity object = { type: 'SystemAssigned' }

// ============================================================================
// Resource Deployment
// ============================================================================
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2025-10-15' = {
  name: name
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  identity: identity
  properties: {
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    databaseAccountOfferType: 'Standard'
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    disableLocalAuth: true
    capabilities: [ { name: 'EnableServerless' } ]
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2025-10-15' = {
  parent: cosmos
  name: databaseName
  properties: {
    resource: { id: databaseName }
  }

  resource list 'containers' = [for container in containers: {
    name: container.name
    properties: {
      resource: {
        id: container.name
        partitionKey: { paths: [ container.partitionKeyPath ] }
      }
      options: {}
    }
  }]
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the Cosmos DB account.')
output resourceId string = cosmos.id

@description('Name of the Cosmos DB account.')
output name string = cosmos.name

@description('Endpoint of the Cosmos DB account.')
output endpoint string = 'https://${name}.documents.azure.com:443/'

@description('Database name.')
output databaseName string = databaseName

@description('Container name (first container).')
output containerName string = containers[0].name
