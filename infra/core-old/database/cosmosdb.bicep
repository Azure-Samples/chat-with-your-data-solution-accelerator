@description('Azure Cosmos DB Account Name')
param name string
param location string

@description('Name')
param accountName string = name
param databaseName string = 'db_conversation_history'
param collectionName string = 'conversations'

param containers array = [
  {
    name: collectionName
    id: collectionName
    partitionKey: '/userId'
  }
]

@allowed(['GlobalDocumentDB', 'MongoDB', 'Parse'])
param kind string = 'GlobalDocumentDB'

param tags object = {}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2022-08-15' = {
  name: accountName
  kind: kind
  location: location
  tags: tags
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
    apiProperties: (kind == 'MongoDB') ? { serverVersion: '4.0' } : {}
    capabilities: [{ name: 'EnableServerless' }]
    disableKeyBasedMetadataWriteAccess: true
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2022-05-15' = {
  name: '${accountName}/${databaseName}'
  properties: {
    resource: { id: databaseName }
  }

  resource list 'containers' = [
    for container in containers: {
      name: container.name
      properties: {
        resource: {
          id: container.id
          partitionKey: { paths: [container.partitionKey] }
        }
        options: {}
      }
    }
  ]

  dependsOn: [
    cosmos
  ]
}

var cosmosAccountKey = cosmos.listKeys().primaryMasterKey

output cosmosOutput object = {
  cosmosAccountName: cosmos.name
  cosmosAccountKey: cosmosAccountKey
  cosmosDatabaseName: databaseName
  cosmosContainerName: collectionName
}
