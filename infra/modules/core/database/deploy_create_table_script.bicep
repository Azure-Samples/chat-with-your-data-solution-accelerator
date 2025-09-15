@description('Specifies the location for resources.')
param solutionLocation string

param baseUrl string
param identity string
param postgresSqlServerName string
param managedIdentityName string

resource create_index 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  kind: 'AzureCLI'
  name: 'create_postgres_table'
  location: solutionLocation // Replace with your desired location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity}': {}
    }
  }
  properties: {
    azCliVersion: '2.52.0'
    primaryScriptUri: '${baseUrl}scripts/run_create_table_script.sh'
    arguments: '${baseUrl} ${resourceGroup().name} ${postgresSqlServerName} ${managedIdentityName}' // Specify any arguments for the script
    timeout: 'PT1H' // Specify the desired timeout duration
    retentionInterval: 'PT1H' // Specify the desired retention interval
    cleanupPreference: 'OnSuccess'
  }
}
