metadata name = 'Azure Cosmos DB account'
metadata description = 'This module deploys an Azure Cosmos DB account. The API used for the account is determined by the child resources that are deployed.'

@description('Required. The name of the account.')
param name string

@description('Optional. Defaults to the current resource group scope location. Location for all resources.')
param location string = resourceGroup().location

@description('Optional. Tags for the resource.')
param tags resourceInput<'Microsoft.DocumentDB/databaseAccounts@2024-11-15'>.tags?

import { managedIdentityAllType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. The managed identity definition for this resource.')
param managedIdentities managedIdentityAllType?

@description('Optional. The offer type for the account. Defaults to "Standard".')
@allowed([
  'Standard'
])
param databaseAccountOfferType string = 'Standard'

@description('Optional. The set of locations enabled for the account. Defaults to the location where the account is deployed.')
param failoverLocations failoverLocationType[]?

@description('Optional. Indicates whether the single-region account is zone redundant. Defaults to true. This property is ignored for multi-region accounts.')
param zoneRedundant bool = true

@allowed([
  'Eventual'
  'ConsistentPrefix'
  'Session'
  'BoundedStaleness'
  'Strong'
])
@description('Optional. The default consistency level of the account. Defaults to "Session".')
param defaultConsistencyLevel string = 'Session'

@description('Optional. Opt-out of local authentication and ensure that only Microsoft Entra can be used exclusively for authentication. Defaults to true.')
param disableLocalAuthentication bool = true

@description('Optional. Flag to indicate whether to enable storage analytics. Defaults to false.')
param enableAnalyticalStorage bool = false

@description('Optional. Enable automatic failover for regions. Defaults to true.')
param automaticFailover bool = true

@description('Optional. Flag to indicate whether "Free Tier" is enabled. Defaults to false.')
param enableFreeTier bool = false

@description('Optional. Enables the account to write in multiple locations. Periodic backup must be used if enabled. Defaults to false.')
param enableMultipleWriteLocations bool = false

@description('Optional. Disable write operations on metadata resources (databases, containers, throughput) via account keys. Defaults to true.')
param disableKeyBasedMetadataWriteAccess bool = true

@minValue(1)
@maxValue(2147483647)
@description('Optional. The maximum stale requests. Required for "BoundedStaleness" consistency level. Valid ranges, Single Region: 10 to 1000000. Multi Region: 100000 to 1000000. Defaults to 100000.')
param maxStalenessPrefix int = 100000

@minValue(5)
@maxValue(86400)
@description('Optional. The maximum lag time in minutes. Required for "BoundedStaleness" consistency level. Valid ranges, Single Region: 5 to 84600. Multi Region: 300 to 86400. Defaults to 300.')
param maxIntervalInSeconds int = 300

@description('Optional. Configuration for databases when using Azure Cosmos DB for NoSQL.')
param sqlDatabases sqlDatabaseType[]?

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Optional. The total throughput limit imposed on this account in request units per second (RU/s). Default to unlimited throughput.')
param totalThroughputLimit int = -1

import { lockType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. The lock settings of the service.')
param lock lockType?

@description('Optional. Configurations for Azure Cosmos DB for NoSQL native role-based access control definitions. Allows the creations of custom role definitions.')
param dataPlaneRoleDefinitions dataPlaneRoleDefinitionType[]?

import { diagnosticSettingFullType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. The diagnostic settings for the service.')
param diagnosticSettings diagnosticSettingFullType[]?

@allowed([
  'EnableCassandra'
  'EnableTable'
  'EnableGremlin'
  'EnableMongo'
  'DisableRateLimitingResponses'
  'EnableServerless'
  'EnableNoSQLVectorSearch'
  'EnableNoSQLFullTextSearch'
  'EnableMaterializedViews'
  'DeleteAllItemsByPartitionKey'
])
@description('Optional. A list of Azure Cosmos DB specific capabilities for the account.')
param capabilitiesToAdd string[]?

@allowed([
  'Periodic'
  'Continuous'
])
@description('Optional. Configures the backup mode. Periodic backup must be used if multiple write locations are used. Defaults to "Continuous".')
param backupPolicyType string = 'Continuous'

@allowed([
  'Continuous30Days'
  'Continuous7Days'
])
@description('Optional. Configuration values to specify the retention period for continuous mode backup. Default to "Continuous30Days".')
param backupPolicyContinuousTier string = 'Continuous30Days'

@minValue(60)
@maxValue(1440)
@description('Optional. An integer representing the interval in minutes between two backups. This setting only applies to the periodic backup type. Defaults to 240.')
param backupIntervalInMinutes int = 240

@minValue(2)
@maxValue(720)
@description('Optional. An integer representing the time (in hours) that each backup is retained. This setting only applies to the periodic backup type. Defaults to 8.')
param backupRetentionIntervalInHours int = 8

@allowed([
  'Geo'
  'Local'
  'Zone'
])
@description('Optional. Setting that indicates the type of backup residency. This setting only applies to the periodic backup type. Defaults to "Local".')
param backupStorageRedundancy string = 'Local'

import { privateEndpointMultiServiceType } from 'br/public:avm/utl/types/avm-common-types:0.6.1'
@description('Optional. Configuration details for private endpoints. For security reasons, it is advised to use private endpoints whenever possible.')
param privateEndpoints privateEndpointMultiServiceType[]?

@description('Optional. The network configuration of this module. Defaults to `{ ipRules: [], virtualNetworkRules: [], publicNetworkAccess: \'Disabled\' }`.')
param networkRestrictions networkRestrictionType = {
  ipRules: []
  virtualNetworkRules: []
  publicNetworkAccess: 'Disabled'
}

@allowed([
  'Tls12'
])
@description('Optional. Setting that indicates the minimum allowed TLS version. Azure Cosmos DB for MongoDB RU and Apache Cassandra only work with TLS 1.2 or later. Defaults to "Tls12" (TLS 1.2).')
param minimumTlsVersion string = 'Tls12'

var enableReferencedModulesTelemetry = false

var formattedUserAssignedIdentities = reduce(
  map((managedIdentities.?userAssignedResourceIds ?? []), (id) => { '${id}': {} }),
  {},
  (cur, next) => union(cur, next)
) // Converts the flat array to an object like { '${id1}': {}, '${id2}': {} }

var identity = !empty(managedIdentities)
  ? {
      type: (managedIdentities.?systemAssigned ?? false)
        ? (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'SystemAssigned,UserAssigned' : 'SystemAssigned')
        : (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'UserAssigned' : null)
      userAssignedIdentities: !empty(formattedUserAssignedIdentities) ? formattedUserAssignedIdentities : null
    }
  : null

#disable-next-line no-deployments-resources
resource avmTelemetry 'Microsoft.Resources/deployments@2024-07-01' = if (enableTelemetry) {
  name: '46d3xbcp.res.documentdb-databaseaccount.${replace('-..--..-', '.', '-')}.${substring(uniqueString(deployment().name, location), 0, 4)}'
  properties: {
    mode: 'Incremental'
    template: {
      '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#'
      contentVersion: '1.0.0.0'
      resources: []
      outputs: {
        telemetry: {
          type: 'String'
          value: 'For more information, see https://aka.ms/avm/TelemetryInfo'
        }
      }
    }
  }
}

resource databaseAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: name
  location: location
  tags: tags
  identity: identity
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: databaseAccountOfferType
    backupPolicy: {
      #disable-next-line BCP225 // Value has a default
      type: backupPolicyType
      ...(backupPolicyType == 'Continuous'
        ? {
            continuousModeProperties: {
              tier: backupPolicyContinuousTier
            }
          }
        : {})
      ...(backupPolicyType == 'Periodic'
        ? {
            periodicModeProperties: {
              backupIntervalInMinutes: backupIntervalInMinutes
              backupRetentionIntervalInHours: backupRetentionIntervalInHours
              backupStorageRedundancy: backupStorageRedundancy
            }
          }
        : {})
    }
    capabilities: map(capabilitiesToAdd ?? [], capability => {
      name: capability
    })
    minimalTlsVersion: minimumTlsVersion
    capacity: {
      totalThroughputLimit: totalThroughputLimit
    }
    publicNetworkAccess: networkRestrictions.?publicNetworkAccess ?? 'Disabled'
    ...((!empty(sqlDatabases))
      ? {
          // NoSQL, MongoDB RU, Table, and Apache Gremlin common properties
          consistencyPolicy: {
            defaultConsistencyLevel: defaultConsistencyLevel
            ...(defaultConsistencyLevel == 'BoundedStaleness'
              ? {
                  maxStalenessPrefix: maxStalenessPrefix
                  maxIntervalInSeconds: maxIntervalInSeconds
                }
              : {})
          }
          enableMultipleWriteLocations: enableMultipleWriteLocations
          locations: !empty(failoverLocations)
            ? map(failoverLocations!, failoverLocation => {
                failoverPriority: failoverLocation.failoverPriority
                locationName: failoverLocation.locationName
                isZoneRedundant: failoverLocation.?isZoneRedundant ?? true
              })
            : [
                {
                  failoverPriority: 0
                  locationName: location
                  isZoneRedundant: zoneRedundant
                }
              ]
          ipRules: map(networkRestrictions.?ipRules ?? [], ipRule => {
            ipAddressOrRange: ipRule
          })
          virtualNetworkRules: map(networkRestrictions.?virtualNetworkRules ?? [], rule => {
            id: rule.subnetResourceId
            ignoreMissingVNetServiceEndpoint: false
          })
          networkAclBypass: networkRestrictions.?networkAclBypass ?? 'None'
          isVirtualNetworkFilterEnabled: !empty(networkRestrictions.?ipRules) || !empty(networkRestrictions.?virtualNetworkRules)
          enableFreeTier: enableFreeTier
          enableAutomaticFailover: automaticFailover
          enableAnalyticalStorage: enableAnalyticalStorage
        }
      : {})
    disableLocalAuth: disableLocalAuthentication
    disableKeyBasedMetadataWriteAccess: disableKeyBasedMetadataWriteAccess
  }
}

resource databaseAccount_lock 'Microsoft.Authorization/locks@2020-05-01' = if (!empty(lock ?? {}) && lock.?kind != 'None') {
  name: lock.?name ?? 'lock-${name}'
  properties: {
    level: lock.?kind ?? ''
    notes: lock.?notes ?? (lock.?kind == 'CanNotDelete'
      ? 'Cannot delete resource or child resources.'
      : 'Cannot delete or modify the resource or child resources.')
  }
  scope: databaseAccount
}

resource databaseAccount_diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = [
  for (diagnosticSetting, index) in (diagnosticSettings ?? []): {
    name: diagnosticSetting.?name ?? '${name}-diagnosticSettings'
    properties: {
      storageAccountId: diagnosticSetting.?storageAccountResourceId
      workspaceId: diagnosticSetting.?workspaceResourceId
      eventHubAuthorizationRuleId: diagnosticSetting.?eventHubAuthorizationRuleResourceId
      eventHubName: diagnosticSetting.?eventHubName
      metrics: [
        for group in (diagnosticSetting.?metricCategories ?? [{ category: 'AllMetrics' }]): {
          category: group.category
          enabled: group.?enabled ?? true
          timeGrain: null
        }
      ]
      logs: [
        for group in (diagnosticSetting.?logCategoriesAndGroups ?? [{ categoryGroup: 'allLogs' }]): {
          categoryGroup: group.?categoryGroup
          category: group.?category
          enabled: group.?enabled ?? true
        }
      ]
      marketplacePartnerId: diagnosticSetting.?marketplacePartnerResourceId
      logAnalyticsDestinationType: diagnosticSetting.?logAnalyticsDestinationType
    }
    scope: databaseAccount
  }
]

module databaseAccount_sqlDatabases 'sql-database/sql-database.bicep' = [
  for sqlDatabase in (sqlDatabases ?? []): {
    name: '${uniqueString(deployment().name, location)}-sqldb-${sqlDatabase.name}'
    params: {
      name: sqlDatabase.name
      containers: sqlDatabase.?containers
      throughput: sqlDatabase.?throughput
      databaseAccountName: databaseAccount.name
      autoscaleSettingsMaxThroughput: sqlDatabase.?autoscaleSettingsMaxThroughput
    }
  }
]

module databaseAccount_sqlRoleDefinitions 'sql-role-definition/sql-role-definition.bicep' = [
  for (nosqlRoleDefinition, index) in (dataPlaneRoleDefinitions ?? []): {
    name: '${uniqueString(deployment().name, location)}-sqlrd-${index}'
    params: {
      databaseAccountName: databaseAccount.name
      name: nosqlRoleDefinition.?name
      dataActions: nosqlRoleDefinition.?dataActions
      roleName: nosqlRoleDefinition.roleName
      assignableScopes: nosqlRoleDefinition.?assignableScopes
      sqlRoleAssignments: nosqlRoleDefinition.?assignments
    }
  }
]

module databaseAccount_privateEndpoints 'br/public:avm/res/network/private-endpoint:0.10.1' = [
  for (privateEndpoint, index) in (privateEndpoints ?? []): {
    name: '${uniqueString(deployment().name, location)}-dbAccount-PrivateEndpoint-${index}'
    scope: resourceGroup(
      split(privateEndpoint.?resourceGroupResourceId ?? resourceGroup().id, '/')[2],
      split(privateEndpoint.?resourceGroupResourceId ?? resourceGroup().id, '/')[4]
    )
    params: {
      name: privateEndpoint.?name ?? 'pep-${last(split(databaseAccount.id, '/'))}-${privateEndpoint.service}-${index}'
      privateLinkServiceConnections: privateEndpoint.?isManualConnection != true
        ? [
            {
              name: privateEndpoint.?privateLinkServiceConnectionName ?? '${last(split(databaseAccount.id, '/'))}-${privateEndpoint.service}-${index}'
              properties: {
                privateLinkServiceId: databaseAccount.id
                groupIds: [
                  privateEndpoint.service
                ]
              }
            }
          ]
        : null
      manualPrivateLinkServiceConnections: privateEndpoint.?isManualConnection == true
        ? [
            {
              name: privateEndpoint.?privateLinkServiceConnectionName ?? '${last(split(databaseAccount.id, '/'))}-${privateEndpoint.service}-${index}'
              properties: {
                privateLinkServiceId: databaseAccount.id
                groupIds: [
                  privateEndpoint.service
                ]
                requestMessage: privateEndpoint.?manualConnectionRequestMessage ?? 'Manual approval required.'
              }
            }
          ]
        : null
      subnetResourceId: privateEndpoint.subnetResourceId
      enableTelemetry: enableReferencedModulesTelemetry
      location: privateEndpoint.?location ?? reference(
        split(privateEndpoint.subnetResourceId, '/subnets/')[0],
        '2020-06-01',
        'Full'
      ).location
      lock: privateEndpoint.?lock ?? lock
      privateDnsZoneGroup: privateEndpoint.?privateDnsZoneGroup
      roleAssignments: privateEndpoint.?roleAssignments
      tags: privateEndpoint.?tags ?? tags
      customDnsConfigs: privateEndpoint.?customDnsConfigs
      ipConfigurations: privateEndpoint.?ipConfigurations
      applicationSecurityGroupResourceIds: privateEndpoint.?applicationSecurityGroupResourceIds
      customNetworkInterfaceName: privateEndpoint.?customNetworkInterfaceName
    }
  }
]

@description('The name of the database account.')
output name string = databaseAccount.name

// =============== //
//   Definitions   //
// =============== //

@export()
@description('The type for the failover location.')
type failoverLocationType = {
  @description('Required. The failover priority of the region. A failover priority of 0 indicates a write region. The maximum value for a failover priority = (total number of regions - 1). Failover priority values must be unique for each of the regions in which the database account exists.')
  failoverPriority: int

  @description('Optional. Flag to indicate whether or not this region is an AvailabilityZone region. Defaults to true.')
  isZoneRedundant: bool?

  @description('Required. The name of the region.')
  locationName: string
}

@export()
@description('The type for an Azure Cosmos DB for NoSQL native role-based access control assignment.')
type dataPlaneRoleAssignmentType = {
  @description('Optional. The unique name of the role assignment.')
  name: string?

  @description('Required. The unique identifier of the Azure Cosmos DB for NoSQL native role-based access control definition.')
  roleDefinitionId: string

  @description('Required. The unique identifier for the associated Microsoft Entra ID principal to which access is being granted through this role-based access control assignment. The tenant ID for the principal is inferred using the tenant associated with the subscription.')
  principalId: string
}

import { sqlRoleAssignmentType } from 'sql-role-definition/sql-role-definition.bicep'
@export()
@description('The type for an Azure Cosmos DB for NoSQL or Table native role-based access control definition.')
type dataPlaneRoleDefinitionType = {
  @description('Optional. The unique identifier of the role-based access control definition.')
  name: string?

  @description('Required. A user-friendly name for the role-based access control definition. This must be unique within the database account.')
  roleName: string

  @description('Optional. An array of data actions that are allowed.')
  dataActions: string[]?

  @description('Optional. A set of fully-qualified scopes at or below which role-based access control assignments may be created using this definition. This setting allows application of this definition on the entire account or any underlying resource. This setting must have at least one element. Scopes higher than the account level are not enforceable as assignable scopes. Resources referenced in assignable scopes do not need to exist at creation. Defaults to the current account scope.')
  assignableScopes: string[]?

  @description('Optional. An array of role-based access control assignments to be created for the definition.')
  assignments: sqlRoleAssignmentType[]?
}

@export()
@description('The type for an Azure Cosmos DB for NoSQL database.')
type sqlDatabaseType = {
  @description('Required. Name of the database .')
  name: string

  @description('Optional. Request units per second. Will be ignored if `autoscaleSettingsMaxThroughput` is used. Setting throughput at the database level is only recommended for development/test or when workload across all containers in the shared throughput database is uniform. For best performance for large production workloads, it is recommended to set dedicated throughput (autoscale or manual) at the container level and not at the database level. Defaults to 400.')
  throughput: int?

  @description('Optional. Specifies the autoscale settings and represents maximum throughput the resource can scale up to. The autoscale throughput should have valid throughput values between 1000 and 1000000 inclusive in increments of 1000. If the value is not set, then autoscale will be disabled. Setting throughput at the database level is only recommended for development/test or when workload across all containers in the shared throughput database is uniform. For best performance for large production workloads, it is recommended to set dedicated throughput (autoscale or manual) at the container level and not at the database level.')
  autoscaleSettingsMaxThroughput: int?

  @description('Optional. Set of containers to deploy in the database.')
  containers: {
    @description('Required. Name of the container.')
    name: string

    @maxLength(3)
    @minLength(1)
    @description('Required. List of paths using which data within the container can be partitioned. For kind=MultiHash it can be up to 3. For anything else it needs to be exactly 1.')
    paths: string[]

    @description('Optional. Default to 0. Indicates how long data should be retained in the analytical store, for a container. Analytical store is enabled when ATTL is set with a value other than 0. If the value is set to -1, the analytical store retains all historical data, irrespective of the retention of the data in the transactional store.')
    analyticalStorageTtl: int?

    @maxValue(1000000)
    @description('Optional. Specifies the Autoscale settings and represents maximum throughput, the resource can scale up to. The autoscale throughput should have valid throughput values between 1000 and 1000000 inclusive in increments of 1000. If value is set to null, then autoscale will be disabled. For best performance for large production workloads, it is recommended to set dedicated throughput (autoscale or manual) at the container level.')
    autoscaleSettingsMaxThroughput: int?

    @description('Optional. The conflict resolution policy for the container. Conflicts and conflict resolution policies are applicable if the Azure Cosmos DB account is configured with multiple write regions.')
    conflictResolutionPolicy: {
      @description('Conditional. The conflict resolution path in the case of LastWriterWins mode. Required if `mode` is set to \'LastWriterWins\'.')
      conflictResolutionPath: string?

      @description('Conditional. The procedure to resolve conflicts in the case of custom mode. Required if `mode` is set to \'Custom\'.')
      conflictResolutionProcedure: string?

      @description('Required. Indicates the conflict resolution mode.')
      mode: ('Custom' | 'LastWriterWins')
    }?

    @maxValue(2147483647)
    @minValue(-1)
    @description('Optional. Default to -1. Default time to live (in seconds). With Time to Live or TTL, Azure Cosmos DB provides the ability to delete items automatically from a container after a certain time period. If the value is set to "-1", it is equal to infinity, and items don\'t expire by default.')
    defaultTtl: int?

    @description('Optional. Indexing policy of the container.')
    indexingPolicy: object?

    @description('Optional. Default to Hash. Indicates the kind of algorithm used for partitioning.')
    kind: ('Hash' | 'MultiHash')?

    @description('Optional. Default to 1 for Hash and 2 for MultiHash - 1 is not allowed for MultiHash. Version of the partition key definition.')
    version: (1 | 2)?

    @description('Optional. Default to 400. Request Units per second. Will be ignored if autoscaleSettingsMaxThroughput is used.')
    throughput: int?

    @description('Optional. The unique key policy configuration containing a list of unique keys that enforces uniqueness constraint on documents in the collection in the Azure Cosmos DB service.')
    uniqueKeyPolicyKeys: {
      @description('Required. List of paths must be unique for each document in the Azure Cosmos DB service.')
      paths: string[]
    }[]?
  }[]?
}

@export()
@description('The type for the network restriction.')
type networkRestrictionType = {
  @description('Optional. A single IPv4 address or a single IPv4 address range in Classless Inter-Domain Routing (CIDR) format. Provided IPs must be well-formatted and cannot be contained in one of the following ranges: `10.0.0.0/8`, `100.64.0.0/10`, `172.16.0.0/12`, `192.168.0.0/16`, since these are not enforceable by the IP address filter. Example of valid inputs: `23.40.210.245` or `23.40.210.0/8`.')
  ipRules: string[]?

  @description('Optional. Specifies the network ACL bypass for Azure services. Default to "None".')
  networkAclBypass: ('AzureServices' | 'None')?

  @description('Optional. Whether requests from the public network are allowed. Default to "Disabled".')
  publicNetworkAccess: ('Enabled' | 'Disabled')?

  @description('Optional. List of virtual network access control list (ACL) rules configured for the account.')
  virtualNetworkRules: {
    @description('Required. Resource ID of a subnet.')
    subnetResourceId: string
  }[]?
}
