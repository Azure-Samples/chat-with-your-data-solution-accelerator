metadata name = 'Storage Account Queues'
metadata description = 'This module deploys a Storage Account Queue.'

@maxLength(24)
@description('Conditional. The name of the parent Storage Account. Required if the template is used in a standalone deployment.')
param storageAccountName string

@description('Required. The name of the storage queue to deploy.')
param name string

@description('Optional. A name-value pair that represents queue metadata.')
param metadata resourceInput<'Microsoft.Storage/storageAccounts/queueServices/queues@2024-01-01'>.properties.metadata = {}

resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' existing = {
  name: storageAccountName

  resource queueServices 'queueServices@2024-01-01' existing = {
    name: 'default'
  }
}

resource queue 'Microsoft.Storage/storageAccounts/queueServices/queues@2024-01-01' = {
  name: name
  parent: storageAccount::queueServices
  properties: {
    metadata: metadata
  }
}

@description('The name of the deployed queue.')
output name string = queue.name

@description('The resource ID of the deployed queue.')
output resourceId string = queue.id

@description('The resource group of the deployed queue.')
output resourceGroupName string = resourceGroup().name
