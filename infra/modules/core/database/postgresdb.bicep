// ========== PostgreSQL Flexible Server (AVM + WAF aligned) ========== //

@description('The name of the PostgreSQL flexible server resource.')
param name string

@description('The Azure region where the PostgreSQL flexible server will be deployed.')
param location string

@description('Optional. Tags to be applied to the PostgreSQL flexible server resource.')
param tags object = {}

@description('Optional. Controls whether AVM telemetry is enabled for this deployment.')
param enableTelemetry bool = true

@description('Optional. Flag to enable monitoring diagnostics.')
param enableMonitoring bool = false

@description('Optional. Resource ID of the Log Analytics workspace to send diagnostics to.')
param logAnalyticsWorkspaceResourceId string = ''

@description('Optional. Flag to enable private networking for the PostgreSQL flexible server.')
param enablePrivateNetworking bool = false
param subnetResourceId string = '' // delegated subnet resource id; use empty string when not set
param privateDnsZoneResourceId string = '' // Single private DNS zone resource ID as string

@description('Optional. Object ID of the managed identity to be assigned as a PostgreSQL administrator.')
param managedIdentityObjectId string = ''

@description('Optional. Name of the managed identity to be assigned as a PostgreSQL administrator.')
param managedIdentityObjectName string = ''

@description('Optional. The administrator login name for the PostgreSQL flexible server.')
param administratorLogin string = 'admintest'

@description('Optional. The administrator login password for the PostgreSQL flexible server.')
@secure()
param administratorLoginPassword string

@description('Optional. The edition of the PostgreSQL flexible server.')
param serverEdition string = 'Burstable'

@description('Optional. The storage size in GB for the PostgreSQL flexible server.')
param skuSizeGB int = 32

@description('Optional. The compute SKU name for the PostgreSQL flexible server.')
param dbInstanceType string = 'Standard_B1ms'

@description('Optional. The availability zone where the PostgreSQL flexible server will be deployed.')
param availabilityZone int = 1

@description('Optional. Allow all IP addresses to access the PostgreSQL flexible server.')
param allowAllIPsFirewall bool = false

@description('Optional. Allow all Azure services to access the PostgreSQL flexible server.')
param allowAzureIPsFirewall bool = false

@description('Optional. PostgreSQL version.')
@allowed([
  '11'
  '12'
  '13'
  '14'
  '15'
  '16'
])
param version string = '16'

var postgresResourceName = '${name}-postgres'

// AVM PostgreSQL Flexible Server module
module postgres 'br/public:avm/res/db-for-postgre-sql/flexible-server:0.13.1' = {
  name: take('avm.res.db-for-postgre-sql.flexible-server.${postgresResourceName}', 64)
  params: {
    name: postgresResourceName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry

    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null

    skuName: dbInstanceType
    tier: serverEdition
    storageSizeGB: skuSizeGB
    version: version
    availabilityZone: availabilityZone

    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword

    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    delegatedSubnetResourceId: enablePrivateNetworking ? subnetResourceId : null
    privateDnsZoneArmResourceId: enablePrivateNetworking
      ? !empty(privateDnsZoneResourceId) ? privateDnsZoneResourceId : null
      : null

    administrators: managedIdentityObjectId != ''
      ? [
          {
            objectId: managedIdentityObjectId
            principalName: managedIdentityObjectName
            principalType: 'ServicePrincipal'
          }
        ]
      : null

    firewallRules: concat(
      allowAllIPsFirewall
        ? [
            {
              name: 'allow-all-IPs'
              startIpAddress: '0.0.0.0'
              endIpAddress: '255.255.255.255'
            }
          ]
        : [],
      allowAzureIPsFirewall
        ? [
            {
              name: 'allow-all-azure-internal-IPs'
              startIpAddress: '0.0.0.0'
              endIpAddress: '0.0.0.0'
            }
          ]
        : []
    )

    configurations: [
      {
        name: 'azure.extensions'
        value: 'vector'
        source: 'user-override'
      }
    ]
  }
}

resource delayScript 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  name: 'waitForServerReady'
  location: resourceGroup().location
  kind: 'AzurePowerShell'
  properties: {
    azPowerShellVersion: '11.0'
    scriptContent: 'start-sleep -Seconds 300'
    cleanupPreference: 'Always'
    retentionInterval: 'PT1H'
  }
  dependsOn: [
    postgres
  ]
}

// -------- Outputs -------- //
@description('Output object containing PostgreSQL server configuration details including server name, database name, username, and SSL mode.')
output postgresDbOutput object = {
  postgresSQLName: postgres.name
  postgreSQLServerName: '${postgres.name}.postgres.database.azure.com'
  postgreSQLDatabaseName: 'postgres'
  sslMode: 'Require'
}
