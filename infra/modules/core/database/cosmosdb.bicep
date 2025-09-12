param name string
param location string
param tags object = {}
param enableTelemetry bool = true
param enableMonitoring bool = false
param logAnalyticsWorkspaceResourceId string = ''
param enablePrivateNetworking bool = false
param subnetResourceId string = 'null'
// param privateDnsZoneResourceIds array = []
@description('Conditional. Resource ID of the Private DNS Zone. Required if enablePrivateNetworking is true.')
param privateDnsZoneResourceId string = ''

// // Define DNS zone group configs as a variable
// var privateDnsZoneGroupConfigs = [for zoneId in privateDnsZoneResourceIds: {
//   privateDnsZoneResourceId: zoneId
// }]
param userAssignedIdentityPrincipalId string
param enableRedundancy bool = false
param cosmosDbHaLocation string = ''

var cosmosDbResourceName = name
var cosmosDbDatabaseName = 'db_conversation_history'
var cosmosDbContainerName = 'conversations'
var partitionKeyPath = '/userId'

// // Only compute DNS-related values when private networking is enabled. When disabled, set safe defaults so these vars won't reference arrays or objects.
// var cosmosDnsIndex = enablePrivateNetworking ? (dnsZoneIndex.cosmosDb ?? dnsZoneIndex.cosmosDB ?? 0) : 0
// var hasCosmosDnsConfig = enablePrivateNetworking ? (length(avmPrivateDnsZones) > cosmosDnsIndex) : false
// var cosmosPrivateDnsZoneGroupConfigs = enablePrivateNetworking && hasCosmosDnsConfig
//   ? [
//       { privateDnsZoneResourceId: avmPrivateDnsZones[cosmosDnsIndex]!.outputs.resourceId }
//     ]
//   : []

module cosmosDb 'br/public:avm/res/document-db/database-account:0.15.1' = {
  name: take('avm.res.document-db.database-account.${cosmosDbResourceName}', 64)
  params: {
    name: cosmosDbResourceName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    databaseAccountOfferType: 'Standard'
    sqlDatabases: [
      {
        name: cosmosDbDatabaseName
        containers: [
          {
            name: cosmosDbContainerName
            paths: [
              partitionKeyPath
            ]
            kind: 'Hash'
            version: 2
          }
        ]
      }
    ]
    dataPlaneRoleDefinitions: [
      {
        roleName: 'Cosmos DB SQL Data Contributor'
        dataActions: [
          'Microsoft.DocumentDB/databaseAccounts/readMetadata'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/*'
          'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*'
        ]
        assignments: [{ principalId: userAssignedIdentityPrincipalId }]
      }
    ]
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    networkRestrictions: {
      networkAclBypass: 'None'
      publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    }
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${cosmosDbResourceName}'
            customNetworkInterfaceName: 'nic-${cosmosDbResourceName}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                { privateDnsZoneResourceId: privateDnsZoneResourceId }
                // { privateDnsZoneResourceId: avmPrivateDnsZone!.outputs.resourceId.value }
              ]
            }
            service: 'Sql'
            subnetResourceId: subnetResourceId
          }
        ]
      : []
    zoneRedundant: enableRedundancy ? true : false
    capabilitiesToAdd: enableRedundancy ? null : ['EnableServerless']
    automaticFailover: enableRedundancy ? true : false
    failoverLocations: enableRedundancy
      ? [
          {
            failoverPriority: 0
            isZoneRedundant: true
            locationName: location
          }
          {
            failoverPriority: 1
            isZoneRedundant: true
            locationName: cosmosDbHaLocation
          }
        ]
      : [
          {
            locationName: location
            failoverPriority: 0
          }
        ]
  }
}

output cosmosOutput object = {
  cosmosAccountName: cosmosDb.outputs.name
  cosmosDatabaseName: cosmosDbDatabaseName
  cosmosContainerName: cosmosDbContainerName
  // Add more outputs as needed from cosmosDb.outputs
}
