param contentSafetyName string
param formRecognizerName string
param eventGridSystemTopicName string
param location string
param storageAccountId string
param queueName string
param blobContainerName string

resource formRecognizer 'Microsoft.CognitiveServices/accounts@2022-12-01' = {
  name: formRecognizerName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'FormRecognizer'
  identity: {
    type: 'None'
  }
  properties: {
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Enabled'
  }
}

resource contentSafety 'Microsoft.CognitiveServices/accounts@2022-03-01' = {
  name: contentSafetyName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'ContentSafety'
  identity: {
    type: 'None'
  }
  properties: {
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: [] 
    }
  }
}

resource eventGridSystemTopic 'Microsoft.EventGrid/systemTopics@2021-12-01' = {
  name: eventGridSystemTopicName
  location: location
  properties: {
    source: storageAccountId
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

resource eventGridSystemTopicNameBlobEvents 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2021-12-01' = {
  parent: eventGridSystemTopic
  name: 'BlobEvents'
  properties: {
    destination: {
      endpointType: 'StorageQueue'
      properties: {
        queueMessageTimeToLiveInSeconds: -1
        queueName: queueName
        resourceId: storageAccountId
      }
    }
    filter: {
      includedEventTypes: [
        'Microsoft.Storage.BlobCreated'
        'Microsoft.Storage.BlobDeleted'
      ]
      enableAdvancedFilteringOnArrays: true
      subjectBeginsWith: '/blobServices/default/containers/${blobContainerName}/blobs/'
    }
    labels: []
    eventDeliverySchema: 'EventGridSchema'
    retryPolicy: {
      maxDeliveryAttempts: 30
      eventTimeToLiveInMinutes: 1440
    }
  }
}

output AZURE_FORM_RECOGNIZER_KEY string =  formRecognizer.listKeys().key1
output AZURE_CONTENT_SAFETY_KEY string =  contentSafety.listKeys().key1
