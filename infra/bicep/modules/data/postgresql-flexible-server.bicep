@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the PostgreSQL Flexible Server.')
param name string = 'psql-${solutionName}'

@description('The Azure region where the PostgreSQL Flexible Server will be deployed.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Azure AD administrators for the server. Each entry requires objectId, principalName, and principalType (User, Group, or ServicePrincipal).')
param administrators array

@description('The PostgreSQL version to deploy.')
param version string = '16'

@description('The SKU name for the PostgreSQL Flexible Server.')
param skuName string = 'Standard_B1ms'

@description('The SKU tier for the PostgreSQL Flexible Server.')
@allowed(['Burstable', 'GeneralPurpose', 'MemoryOptimized'])
param skuTier string = 'Burstable'

@description('The storage size in GB.')
param storageSizeGB int = 32

@description('Optional databases to create on the server. Each entry should have a name, and optionally charset and collation.')
param databases array = []

@description('Optional server configurations (e.g., extensions). Each entry should have a name, value, and source.')
param configurations array = []

@description('Optional. Managed identity configuration for the resource.')
param identity object = { type: 'SystemAssigned' }

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2026-01-01-preview' = {
  name: name
  location: location
  tags: tags
  identity: identity
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    version: version
    storage: {
      storageSizeGB: storageSizeGB
    }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

resource firewallAllowAzureIPs 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2026-01-01-preview' = {
  name: 'AllowAllAzureServicesAndResourcesWithinAzureIps'
  parent: postgresServer
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource firewallAllowAll 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2026-01-01-preview' = {
  name: 'AllowAll'
  parent: postgresServer
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '255.255.255.255'
  }
}

// AAD admins must wait for firewall rules — server needs to be fully accessible first
@batchSize(1)
resource postgresAdmins 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2026-01-01-preview' = [
  for admin in administrators: {
    parent: postgresServer
    name: admin.objectId
    dependsOn: [
      firewallAllowAzureIPs
      firewallAllowAll
    ]
    properties: {
      principalName: admin.principalName
      principalType: admin.principalType
      tenantId: subscription().tenantId
    }
  }
]

resource serverDatabases 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2026-01-01-preview' = [
  for db in databases: {
    name: db.name
    parent: postgresServer
    properties: {
      charset: db.?charset ?? 'UTF8'
      collation: db.?collation ?? 'en_US.utf8'
    }
    dependsOn: [
      postgresAdmins
    ]
  }
]

@batchSize(1)
resource serverConfigurations 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2026-01-01-preview' = [
  for config in configurations: {
    name: config.name
    parent: postgresServer
    properties: {
      value: config.value
      source: config.source
    }
    dependsOn: [
      postgresAdmins
    ]
  }
]

@description('The fully qualified domain name of the PostgreSQL Flexible Server.')
output serverFqdn string = postgresServer.properties.fullyQualifiedDomainName

@description('The name of the PostgreSQL Flexible Server.')
output name string = postgresServer.name

@description('The resource ID of the PostgreSQL Flexible Server.')
output resourceId string = postgresServer.id
