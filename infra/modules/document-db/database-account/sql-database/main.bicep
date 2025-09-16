metadata name = 'DocumentDB Database Account SQL Databases'
metadata description = 'This module deploys a SQL Database in a CosmosDB Account.'

@description('Conditional. The name of the parent Database Account. Required if the template is used in a standalone deployment.')
param databaseAccountName string

@description('Required. Name of the SQL database .')
param name string

@description('Optional. Array of containers to deploy in the SQL database.')
param containers object[]?

@description('Optional. Request units per second. Will be ignored if autoscaleSettingsMaxThroughput is used. Setting throughput at the database level is only recommended for development/test or when workload across all containers in the shared throughput database is uniform. For best performance for large production workloads, it is recommended to set dedicated throughput (autoscale or manual) at the container level and not at the database level.')
param throughput int?

@description('Optional. Specifies the Autoscale settings and represents maximum throughput, the resource can scale up to. The autoscale throughput should have valid throughput values between 1000 and 1000000 inclusive in increments of 1000. If value is set to null, then autoscale will be disabled. Setting throughput at the database level is only recommended for development/test or when workload across all containers in the shared throughput database is uniform. For best performance for large production workloads, it is recommended to set dedicated throughput (autoscale or manual) at the container level and not at the database level.')
param autoscaleSettingsMaxThroughput int?

@description('Optional. Tags of the SQL database resource.')
param tags object?

resource databaseAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: databaseAccountName
}

resource sqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  name: name
  parent: databaseAccount
  tags: tags
  properties: {
    resource: {
      id: name
    }
    options: contains(databaseAccount.properties.capabilities, { name: 'EnableServerless' })
      ? null
      : {
          throughput: autoscaleSettingsMaxThroughput == null ? throughput : null
          autoscaleSettings: autoscaleSettingsMaxThroughput != null
            ? {
                maxThroughput: autoscaleSettingsMaxThroughput
              }
            : null
        }
  }
}

module container 'container/main.bicep' = [
  for container in (containers ?? []): {
    name: '${uniqueString(deployment().name, sqlDatabase.name)}-sqldb-${container.name}'
    params: {
      databaseAccountName: databaseAccountName
      sqlDatabaseName: name
      name: container.name
      analyticalStorageTtl: container.?analyticalStorageTtl
      autoscaleSettingsMaxThroughput: container.?autoscaleSettingsMaxThroughput
      conflictResolutionPolicy: container.?conflictResolutionPolicy
      defaultTtl: container.?defaultTtl
      indexingPolicy: container.?indexingPolicy
      kind: container.?kind
      version: container.?version
      paths: container.?paths
      throughput: (throughput != null || autoscaleSettingsMaxThroughput != null) && container.?throughput == null
        ? -1
        : container.?throughput
      uniqueKeyPolicyKeys: container.?uniqueKeyPolicyKeys
    }
  }
]

@description('The name of the SQL database.')
output name string = sqlDatabase.name

@description('The resource ID of the SQL database.')
output resourceId string = sqlDatabase.id

@description('The name of the resource group the SQL database was created in.')
output resourceGroupName string = resourceGroup().name
