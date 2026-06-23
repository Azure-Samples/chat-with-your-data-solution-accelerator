// ============================================================================
// Module: Cosmos DB (MongoDB)
// Description: Creates an Azure Cosmos DB account with MongoDB API
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

@description('MongoDB database name.')
param databaseName string = 'default'

@description('MongoDB collections to create.')
param collections array = []

@description('MongoDB server version.')
@allowed(['4.2', '5.0', '6.0', '7.0'])
param serverVersion string = '7.0'

@description('Default consistency level.')
@allowed(['Eventual', 'ConsistentPrefix', 'Session', 'BoundedStaleness', 'Strong'])
param consistencyLevel string = 'Session'

@description('Enable analytical storage (Synapse Link).')
param enableAnalyticalStorage bool = false

@description('Enable zone redundancy.')
param zoneRedundant bool = false

@description('Enable automatic failover.')
param enableAutomaticFailover bool = false

@description('HA paired region for multi-region failover.')
param haLocation string = ''

@description('Public network access setting.')
param publicNetworkAccess string = 'Enabled'

// ============================================================================
// Resource Deployment
// ============================================================================
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2025-10-15' = {
  name: name
  location: location
  tags: tags
  kind: 'MongoDB'
  properties: {
    consistencyPolicy: { defaultConsistencyLevel: consistencyLevel }
    locations: zoneRedundant && !empty(haLocation)
      ? [
          { locationName: location, failoverPriority: 0, isZoneRedundant: true }
          { locationName: haLocation, failoverPriority: 1, isZoneRedundant: true }
        ]
      : [
          { locationName: location, failoverPriority: 0, isZoneRedundant: zoneRedundant }
        ]
    databaseAccountOfferType: 'Standard'
    enableAutomaticFailover: enableAutomaticFailover
    enableMultipleWriteLocations: false
    apiProperties: { serverVersion: serverVersion }
    enableAnalyticalStorage: enableAnalyticalStorage
    capabilities: [{ name: 'EnableMongo' }]
    publicNetworkAccess: publicNetworkAccess
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/mongodbDatabases@2025-10-15' = {
  parent: cosmos
  name: databaseName
  properties: {
    resource: { id: databaseName }
  }
}

resource mongoCollections 'Microsoft.DocumentDB/databaseAccounts/mongodbDatabases/collections@2025-10-15' = [for collection in collections: {
  parent: database
  name: collection.name
  properties: {
    resource: {
      id: collection.name
      shardKey: collection.?shardKey ?? {}
      indexes: collection.?indexes ?? [
        { key: { keys: ['_id'] } }
      ]
    }
  }
}]

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the Cosmos DB account.')
output resourceId string = cosmos.id

@description('Name of the Cosmos DB account.')
output name string = cosmos.name

@description('MongoDB connection string (without credentials — use Key Vault for secrets).')
output connectionString string = 'mongodb+srv://${name}.mongo.cosmos.azure.com:443/?ssl=true&retrywrites=false&maxIdleTimeMS=120000'

@description('Endpoint of the Cosmos DB account.')
output endpoint string = 'https://${name}.mongo.cosmos.azure.com:443/'

@description('Database name.')
output databaseName string = databaseName
