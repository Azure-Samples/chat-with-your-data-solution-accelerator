metadata description = 'Creates an Azure AI Search instance.'
param name string
param location string = resourceGroup().location
param tags object = {}

param dataSourceType string

param dataSourceConnectionString string = ''

param dataSourceContainerName string = ''

param azureSearchIndex string = ''

param azureSearchIndexer string = ''

param azureSearchDataSource string = ''


resource setupSearchService 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  kind: 'AzurePowerShell'
  properties: {
    azPowerShellVersion: '8.3'
    timeout: 'PT30M'
    arguments: '-dataSourceContainerName \\"${dataSourceContainerName}\\" -dataSourceConnectionString \\"${dataSourceConnectionString}\\" -dataSourceType \\"${dataSourceType}\\" -searchServiceName \\"${name}\\" -azureSearchIndex \\"${azureSearchIndex}\\" -azureSearchIndexer \\"${azureSearchIndexer}\\" -azureSearchDataSource \\"${azureSearchDataSource}\\"'
    scriptContent: loadTextContent('SetupSearchService.ps1')
    cleanupPreference: 'OnSuccess'
    retentionInterval: 'P1D'
  }
}

output searchindexName string = setupSearchService.properties.outputs.searchIndexName
output searchIndexerName string = setupSearchService.properties.outputs.searchIndexerName
output searchdataSourceName string = setupSearchService.properties.outputs.searchdataSourceName
