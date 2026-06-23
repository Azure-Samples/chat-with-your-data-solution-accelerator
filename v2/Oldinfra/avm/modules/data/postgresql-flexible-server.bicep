// ============================================================================
// Module: PostgreSQL Flexible Server
// Description: AVM wrapper for Azure Database for PostgreSQL Flexible Server
// AVM Module: avm/res/db-for-postgre-sql/flexible-server:0.15.4
// WAF: https://learn.microsoft.com/azure/well-architected/service-guides/postgresql
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the PostgreSQL Flexible Server.')
param name string = 'psql-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Azure AD administrators for the server. Each entry requires objectId, principalName, and principalType (User, Group, or ServicePrincipal).')
param administrators array

@description('The PostgreSQL version to deploy.')
param version string = '16'

@description('SKU name for the PostgreSQL Flexible Server.')
param skuName string = 'Standard_B1ms'

@description('SKU tier for the PostgreSQL Flexible Server.')
@allowed(['Burstable', 'GeneralPurpose', 'MemoryOptimized'])
param skuTier string = 'Burstable'

@description('Storage size in GB.')
param storageSizeGB int = 32

@description('Availability zone for the server.')
param availabilityZone int = 1

@description('Optional databases to create on the server. Each entry should have a name, and optionally charset and collation.')
param databases array = []

@description('Optional server configurations (e.g., extensions). Each entry should have a name, value, and source.')
param configurations array = []

// --- WAF: Monitoring ---
@description('Diagnostic settings for monitoring.')
param diagnosticSettings array = []

// --- WAF: Private Networking ---
@description('Public network access setting.')
param publicNetworkAccess string = 'Enabled'

@description('Whether to enable private networking.')
param enablePrivateNetworking bool = false

@description('Subnet resource ID for the private endpoint.')
param privateEndpointSubnetId string = ''

@description('Private DNS zone resource IDs for PostgreSQL.')
param privateDnsZoneResourceIds array = []

var privateDnsZoneConfigs = [for (zoneId, i) in privateDnsZoneResourceIds: {
  name: 'dns-zone-${i}'
  privateDnsZoneResourceId: zoneId
}]

// --- WAF: Redundancy ---
@description('High availability mode.')
@allowed(['Disabled', 'SameZone', 'ZoneRedundant'])
param highAvailability string = 'Disabled'

@description('Standby availability zone for high availability.')
param highAvailabilityZone int = -1

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

// ============================================================================
// AVM Module Deployment
// ============================================================================
module postgresServer 'br/public:avm/res/db-for-postgre-sql/flexible-server:0.15.4' = {
  name: take('avm.res.postgre-sql.flexible-server.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    skuName: skuName
    tier: skuTier
    storageSizeGB: storageSizeGB
    version: version
    availabilityZone: availabilityZone
    highAvailability: highAvailability
    highAvailabilityZone: highAvailabilityZone
    publicNetworkAccess: publicNetworkAccess
    diagnosticSettings: !empty(diagnosticSettings) ? diagnosticSettings : []
    managedIdentities: managedIdentities
    administrators: [for admin in administrators: {
      objectId: admin.objectId
      principalName: admin.principalName
      principalType: admin.principalType
    }]
    firewallRules: publicNetworkAccess == 'Enabled' ? [
      {
        name: 'AllowAllAzureServicesAndResourcesWithinAzureIps'
        startIpAddress: '0.0.0.0'
        endIpAddress: '0.0.0.0'
      }
      {
        name: 'AllowAll'
        startIpAddress: '0.0.0.0'
        endIpAddress: '255.255.255.255'
      }
    ] : []
    privateEndpoints: enablePrivateNetworking ? [
      {
        name: 'pep-${name}'
        customNetworkInterfaceName: 'nic-${name}'
        subnetResourceId: privateEndpointSubnetId
        service: 'postgresqlServer'
        privateDnsZoneGroup: {
          privateDnsZoneGroupConfigs: privateDnsZoneConfigs
        }
      }
    ] : []
    databases: [for db in databases: {
      name: db.name
      charset: db.?charset ?? 'UTF8'
      collation: db.?collation ?? 'en_US.utf8'
    }]
    configurations: [for config in configurations: {
      name: config.name
      value: config.value
      source: config.source
    }]
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Fully qualified domain name of the PostgreSQL Flexible Server.')
output serverFqdn string = postgresServer.outputs.?fqdn ?? '${name}.postgres.database.azure.com'

@description('Name of the PostgreSQL Flexible Server.')
output name string = postgresServer.outputs.name

@description('Resource ID of the PostgreSQL Flexible Server.')
output resourceId string = postgresServer.outputs.resourceId
