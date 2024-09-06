@minLength(3)
@maxLength(15)
@description('Solution Name')
param solutionName string
param solutionLocation string

@description('Name')
param accountName string = '${ solutionName }-cosmos'
param databaseName string = 'db_conversation_history'
param collectionName string = 'conversations'


param containers array = [
  {
    name: collectionName
    id: collectionName
    partitionKey: '/userId'
  }
]

@allowed([ 'GlobalDocumentDB', 'MongoDB', 'Parse' ])
param kind string = 'GlobalDocumentDB'

param tags object = {}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2022-08-15' = {
  name: accountName
  kind: kind
  location: solutionLocation
  tags: tags
  properties: {
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [
      {
        locationName: solutionLocation
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    databaseAccountOfferType: 'Standard'
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    apiProperties: (kind == 'MongoDB') ? { serverVersion: '4.0' } : {}
    capabilities: [ { name: 'EnableServerless' } ]
  }
}


resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2022-05-15' = {
  name: '${accountName}/${databaseName}'
  properties: {
    resource: { id: databaseName }
  }

  resource list 'containers' = [for container in containers: {
    name: container.name
    properties: {
      resource: {
        id: container.id
        partitionKey: { paths: [ container.partitionKey ] }
      }
      options: {}
    }
  }]

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
