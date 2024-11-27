param solutionName string
param solutionLocation string
param managedIdentityObjectId string
param managedIdentityObjectName string
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
    authConfig: {
      tenantId: subscription().tenantId
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Enabled'
    }
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

resource delayScript 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  name: 'waitForServerReady'
  location: resourceGroup().location
  kind: 'AzureCLI'
  dependsOn: [
    serverName_resource
  ]
  properties: {
    azCliVersion: '2.38.0' // Adjust version if needed
    timeout: 'PT5M' // 5 minutes timeout
    scriptContent: '''
      echo "Waiting for PostgreSQL server to be ready..."
      for i in {1..30}; do
        state=$(az postgres flexible-server show --name ${serverName_resource.name} --resource-group ${resourceGroup().name} --query state -o tsv)
        if [ "$state" == "Ready" ]; then
          echo "Server is ready!"
          exit 0
        fi
        echo "Server state: $state. Retrying in 10 seconds..."
        sleep 10
      done
      echo "Server did not become ready in time."
      exit 1
    '''
    retentionInterval: 'P1D' // Retain script logs for 1 day
  }
}

resource azureADAdministrator 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2022-12-01' = {
  parent: serverName_resource
  name: managedIdentityObjectId
  properties: {
    principalType: 'SERVICEPRINCIPAL'
    principalName: managedIdentityObjectName
    tenantId: subscription().tenantId
  }
  dependsOn: [
    delayScript
  ]
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
    delayScript
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
    delayScript
  ]
}

resource configurations 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2023-12-01-preview' = {
  name: 'azure.extensions'
  parent: serverName_resource
  properties: {
    value: 'pg_diskann'
    source: 'user-override'
  }
  dependsOn: [
    firewall_all,firewall_azure
  ]
}


output postgresDbOutput object = {
  postgresSQLName: serverName_resource.name
  postgreSQLServerName: '${serverName_resource.name}.postgres.database.azure.com'
  postgreSQLDatabaseName: 'postgres'
  postgreSQLDbUser: administratorLogin
  postgreSQLDbPwd: administratorLoginPassword
  sslMode: 'Require'
}
