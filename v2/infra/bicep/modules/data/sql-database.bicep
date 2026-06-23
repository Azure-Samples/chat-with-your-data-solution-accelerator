// ============================================================================
// Module: SQL Database
// Description: Creates an Azure SQL Server and Database
// API: Microsoft.Sql/servers@2025-01-01
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the SQL Server.')
param name string = 'sql-${solutionName}'

@description('Name of the SQL Database.')
param databaseName string = 'sqldb-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Principal ID of the deployer for admin access.')
param deployerPrincipalId string

@description('SKU name for the database.')
param skuName string = 'GP_S_Gen5'

@description('SKU tier for the database.')
param skuTier string = 'GeneralPurpose'

@description('SKU family.')
param skuFamily string = 'Gen5'

@description('vCore capacity.')
param skuCapacity int = 2

@description('Auto-pause delay in minutes.')
param autoPauseDelay int = 60

@description('Minimum capacity (vCores).')
param minCapacity int = 1

@description('Optional. Managed identity configuration for the resource.')
param identity object = { type: 'SystemAssigned' }

// ============================================================================
// Resource Deployment
// ============================================================================
resource sqlServer 'Microsoft.Sql/servers@2025-01-01' = {
  name: name
  location: location
  tags: tags
  identity: identity
  properties: {
    publicNetworkAccess: 'Enabled'
    version: '12.0'
    restrictOutboundNetworkAccess: 'Disabled'
    minimalTlsVersion: '1.2'
    administrators: {
      login: deployerPrincipalId
      sid: deployerPrincipalId
      tenantId: subscription().tenantId
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: true
    }
  }
}

resource firewallRule 'Microsoft.Sql/servers/firewallRules@2025-01-01' = {
  name: 'AllowSpecificRange'
  parent: sqlServer
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '255.255.255.255'
  }
}

resource AllowAllWindowsAzureIps 'Microsoft.Sql/servers/firewallRules@2025-01-01' = {
  name: 'AllowAllWindowsAzureIps'
  parent: sqlServer
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource sqlDB 'Microsoft.Sql/servers/databases@2025-01-01' = {
  parent: sqlServer
  name: databaseName
  location: location
  sku: {
    name: skuName
    tier: skuTier
    family: skuFamily
    capacity: skuCapacity
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    autoPauseDelay: autoPauseDelay
    minCapacity: minCapacity
    readScale: 'Disabled'
    zoneRedundant: false
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Fully qualified domain name of the SQL Server.')
output serverFqdn string = '${name}.database.windows.net'

@description('Name of the SQL Database.')
output databaseName string = databaseName

@description('Resource ID of the SQL Server.')
output serverResourceId string = sqlServer.id

@description('Name of the SQL Server.')
output name string = sqlServer.name
