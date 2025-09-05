@description('Azure Event Grid System Topic')
param name string
param location string
param tags object = {}
param enableTelemetry bool = true
param enableMonitoring bool = false
param logAnalyticsWorkspaceResourceId string = ''

// Event Grid-specific parameters
param storageAccountId string
param queueName string
param blobContainerName string

var eventGridSystemTopicName = name

module avmEventGridSystemTopic 'br/public:avm/res/event-grid/system-topic:0.6.3' = {
  name: take('avm.res.event-grid.system-topic.${eventGridSystemTopicName}', 64)
  params: {
    // Required parameters
    name: eventGridSystemTopicName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    source: storageAccountId
    topicType: 'Microsoft.Storage.StorageAccounts'

    // WAF aligned configuration for Monitoring
    diagnosticSettings: enableMonitoring
      ? [
          {
            name: 'diagnosticSettings'
            workspaceResourceId: logAnalyticsWorkspaceResourceId
            metricCategories: [
              {
                category: 'AllMetrics'
              }
            ]
          }
        ]
      : []

    // System-assigned managed identity for better security
    managedIdentities: {
      systemAssigned: true
    }

    // Event subscription configuration
    eventSubscriptions: [
      {
        name: 'BlobEvents'
        destination: {
          endpointType: 'StorageQueue'
          properties: {
            queueMessageTimeToLiveInSeconds: -1 // Never expire
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
        retryPolicy: {
          maxDeliveryAttempts: 30
          eventTimeToLiveInMinutes: 1440 // 24 hours
        }
        eventDeliverySchema: 'EventGridSchema'
      }
    ]

    // External role assignments to grant proper access to storage queue
    externalResourceRoleAssignments: [
      {
        description: 'Allow Event Grid System Topic to write to storage queue'
        resourceId: storageAccountId
        roleDefinitionId: '974c5e8b-45b9-4653-ba55-5f855dd0fb88' // Storage Queue Data Contributor
      }
      {
        description: 'Allow Event Grid System Topic to send messages to storage queue'
        resourceId: storageAccountId
        roleDefinitionId: 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a' // Storage Queue Data Message Sender
      }
    ]
  }
}

output eventGridOutput object = {
  name: avmEventGridSystemTopic.outputs.name
  id: avmEventGridSystemTopic.outputs.resourceId
  systemAssignedMIPrincipalId: avmEventGridSystemTopic.outputs.?systemAssignedMIPrincipalId
}
