param solutionName string
param solutionLocation string
@description('The name of the SQL logical server.')
param serverName string = '${solutionName}-postgres'

param administratorLogin string = 'admintest'
@secure()
param administratorLoginPassword string = 'Initial_0524'
param serverEdition string = 'Burstable'
param skuSizeGB int = 32
param dbInstanceType string = 'Standard_B1ms'
// param haMode string = 'ZoneRedundant'
param availabilityZone string = '1'
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

resource serverName_resource 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: serverName
  location: solutionLocation
  sku: {
    name: dbInstanceType
    tier: serverEdition
  }
  properties: {
    version: version
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword

    highAvailability: {
      mode: 'Disabled'
    }
    storage: {
      storageSizeGB: skuSizeGB
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    availabilityZone: availabilityZone
  }
}

// resource serverName_firewallrules 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2021-06-01' = [for rule in firewallrules: {
//   parent: serverName_resource
//   name: rule.Name
//   properties: {
//     startIpAddress: rule.StartIpAddress
//     endIpAddress: rule.EndIpAddress
//   }
// }]


resource firewall_all 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = if (allowAllIPsFirewall) {
  parent: serverName_resource
  name: 'allow-all-IPs'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '255.255.255.255'
  }
  dependsOn: [
    serverName_resource
  ]
}

resource firewall_azure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = if (allowAzureIPsFirewall) {
  parent: serverName_resource
  name: 'allow-all-azure-internal-IPs'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
  dependsOn: [
    firewall_all
  ]
}

resource configurations 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2023-12-01-preview' = {
  name: 'azure.extensions'
  parent: serverName_resource
  properties: {
    value: 'vector'
    source: 'user-override'
  }
  dependsOn: [
    firewall_all,firewall_azure
  ]
}


output postgresDbOutput object = {
  postgresSQLName: serverName_resource.name
  postgreSQLServerName: serverName_resource.name
  postgreSQLDatabaseName: 'postgres'
  postgreSQLDbUser: administratorLogin
  postgreSQLDbPwd: administratorLoginPassword
  sslMode: 'Require'
}
