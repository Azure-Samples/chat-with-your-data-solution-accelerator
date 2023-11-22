param name string
param location string
param blobContainerName string

resource storageAccount 'Microsoft.Storage/storageAccounts@2021-09-01' = {
  name: name
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_GRS'
  }
  resource storageAccountNameDefaultBlob 'blobServices' = {
    name: 'default'
    resource storageAccountNameDefaultBlobContainer 'containers' = {
      name: blobContainerName
      properties: {
        publicAccess: 'None'
      }
    }
    resource storageAccountNameDefaultConfig 'containers' = {
      name: 'config'
      properties: {
        publicAccess: 'None'
      }
    }
  }
}

resource storageAccountNameDefault 'Microsoft.Storage/storageAccounts/queueServices@2022-09-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    cors: {
      corsRules: []
    }
  }
}

resource storageAccountNameDefaultDocProcessing 'Microsoft.Storage/storageAccounts/queueServices/queues@2022-09-01' = {
  parent: storageAccountNameDefault
  name: 'doc-processing'
  properties: {
    metadata: {}
  }
}

resource storageAccountNameDefaultDocProcessingPoison 'Microsoft.Storage/storageAccounts/queueServices/queues@2022-09-01' = {
  parent: storageAccountNameDefault
  name: 'doc-processing-poison'
  properties: {
    metadata: {}
  }
}

output STORAGE_ACCOUNT_ID string = storageAccount.id
output STORAGE_ACCOUNT_NAME string = storageAccount.name
