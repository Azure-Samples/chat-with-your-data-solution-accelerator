param name string
param location string
param tags object = {}
param enableTelemetry bool = true
param enableMonitoring bool = false
param logAnalyticsWorkspaceResourceId string = ''
param enablePrivateNetworking bool = false
param subnetResourceId string = '' // delegated subnet resource id; use empty string when not set
param avmPrivateDnsZones array = []
param dnsZoneIndex object = {}
// param userAssignedIdentity object = {}
param managedIdentityObjectId string = ''
param managedIdentityObjectName string = ''

param administratorLogin string = 'admintest'
@secure()
param administratorLoginPassword string = 'Initial_0524'
param serverEdition string = 'Burstable'
param skuSizeGB int = 32
param dbInstanceType string = 'Standard_B1ms'
param availabilityZone int = 1
param allowAllIPsFirewall bool = false
param allowAzureIPsFirewall bool = false

@description('PostgreSQL version')
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

module postgres 'br/public:avm/res/db-for-postgre-sql/flexible-server:0.13.1' = {
  name: take('avm.res.db-for-postgre-sql.flexible-server.${postgresResourceName}', 64)
  params: {
    name: postgresResourceName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null

    // SKU / sizing (match reference param names)
    skuName: dbInstanceType
    tier: serverEdition
    storageSizeGB: skuSizeGB
    version: version

    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword

    availabilityZone: availabilityZone

    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'

    // map to AVM expected names
    delegatedSubnetResourceId: enablePrivateNetworking ? subnetResourceId : null
    privateDnsZoneArmResourceId: (enablePrivateNetworking && length(avmPrivateDnsZones) > 0)
      ? avmPrivateDnsZones[dnsZoneIndex.postgres]!.outputs.resourceId
      : null

    // add Azure AD administrators if provided
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
  }
}

output postgresDbOutput object = {
  postgresSQLName: postgres.name
  postgreSQLServerName: '${postgres.name}.postgres.database.azure.com'
  postgreSQLDatabaseName: 'postgres'
  postgreSQLDbUser: administratorLogin
  sslMode: 'Require'
}
