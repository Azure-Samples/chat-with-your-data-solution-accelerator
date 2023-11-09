param storageAccountName string = ''
param location string = ''
param blobContainerName string = ''

resource storageAccount 'Microsoft.Storage/storageAccounts@2021-09-01' = {
  name: storageAccountName
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
  dependsOn: []
}

resource storageAccountNameDefaultDocProcessingPoison 'Microsoft.Storage/storageAccounts/queueServices/queues@2022-09-01' = {
  parent: storageAccountNameDefault
  name: 'doc-processing-poison'
  properties: {
    metadata: {}
  }
  dependsOn: []
}

output STORAGE_ACCOUNT_ID string = storageAccount.id
output STORAGE_ACCOUNT_NAME_DEFAULT_DOC_PROCESSING_NAME string = storageAccountNameDefaultDocProcessing.name
output AZURE_BLOB_ACCOUNT_KEY string =  storageAccount.listKeys().keys[0].value
