param name string
param location string
param storageAccountId string
param queueName string
param blobContainerName string

resource eventGridSystemTopic 'Microsoft.EventGrid/systemTopics@2021-12-01' = {
  name: name
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
