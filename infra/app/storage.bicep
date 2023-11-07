param storageAccountName string = 'Enabled'
param location string = ''
param blobContainerName string = 'Enabled'

resource storageAccount 'Microsoft.Storage/storageAccounts@2021-09-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_GRS'
  }
}

resource storageAccountNameDefaultBlobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2021-08-01' = {
  name: '${storageAccountName}/default/${blobContainerName}'
  properties: {
    publicAccess: 'None'
  }
  dependsOn: [
    storageAccount
  ]
}

resource storageAccountNameDefaultConfig 'Microsoft.Storage/storageAccounts/blobServices/containers@2021-08-01' = {
  name: '${storageAccountName}/default/config'
  properties: {
    publicAccess: 'None'
  }
  dependsOn: [
    storageAccount
  ]
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

output StorageAccountId string = storageAccount.id
output StorageAccountName_default_doc_processing_name string = storageAccountNameDefaultDocProcessing.name
output AZURE_BLOB_ACCOUNT_KEY string =  storageAccount.listKeys().keys[0].value
