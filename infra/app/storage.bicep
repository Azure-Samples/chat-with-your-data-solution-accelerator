param storageAccountName string = 'Enabled'
param location string = ''
param blobContainerName string = 'Enabled'

resource StorageAccount 'Microsoft.Storage/storageAccounts@2021-09-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_GRS'
  }
}

resource StorageAccountName_default_BlobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2021-08-01' = {
  name: '${storageAccountName}/default/${blobContainerName}'
  properties: {
    publicAccess: 'None'
  }
  dependsOn: [
    StorageAccount
  ]
}

resource StorageAccountName_default_config 'Microsoft.Storage/storageAccounts/blobServices/containers@2021-08-01' = {
  name: '${storageAccountName}/default/config'
  properties: {
    publicAccess: 'None'
  }
  dependsOn: [
    StorageAccount
  ]
}

resource StorageAccountName_default 'Microsoft.Storage/storageAccounts/queueServices@2022-09-01' = {
  parent: StorageAccount
  name: 'default'
  properties: {
    cors: {
      corsRules: []
    }
  }
}

resource StorageAccountName_default_doc_processing 'Microsoft.Storage/storageAccounts/queueServices/queues@2022-09-01' = {
  parent: StorageAccountName_default
  name: 'doc-processing'
  properties: {
    metadata: {}
  }
  dependsOn: []
}

resource StorageAccountName_default_doc_processing_poison 'Microsoft.Storage/storageAccounts/queueServices/queues@2022-09-01' = {
  parent: StorageAccountName_default
  name: 'doc-processing-poison'
  properties: {
    metadata: {}
  }
  dependsOn: []
}

output StorageAccountId string = StorageAccount.id
output StorageAccountName_default_doc_processing_name string = StorageAccountName_default_doc_processing.name
