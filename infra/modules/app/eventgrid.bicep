@description('Name of the Event Grid System Topic')
param name string

@description('Location for the system topic (defaults to resource group location if not provided)')
param location string = resourceGroup().location

@description('Resource ID of the source Storage Account for the system topic')
param storageAccountId string

@description('Name of the Storage Queue to deliver events to')
param queueName string

@description('Blob container name to scope the subscription subject filter (prefix match). If empty, full account events are used.')
param blobContainerName string

@description('Optional: ISO-8601 expiration timestamp for the event subscription. Leave empty for no expiration.')
param expirationTimeUtc string = '2099-01-01T11:00:21.715Z'

param userAssignedResourceId string

@description('Tags to apply to the system topic.')
param tags object = {}

@description('Enable monitoring via diagnostic settings to a Log Analytics workspace.')
param enableMonitoring bool = false

@description('The resource ID of the Log Analytics workspace to send diagnostic logs to if monitoring is enabled.')
param logAnalyticsWorkspaceResourceId string = ''

@description('Optional. Name of the Event Subscription (defaults to evts-<system-topic-name> if not provided)')
param eventSubscriptionName string = ''

@description('Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// Generate unique event subscription name if not provided
var resolvedEventSubscriptionName = empty(eventSubscriptionName) ? 'evts-${name}' : eventSubscriptionName

module avmEventGridSystemTopic 'br/public:avm/res/event-grid/system-topic:0.6.3' = {
  name: take('avm.res.event-grid.system-topic.${name}', 64)
  params: {
    name: name
    source: storageAccountId
    topicType: 'Microsoft.Storage.StorageAccounts'
    location: location
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
    eventSubscriptions: [
      {
        name: resolvedEventSubscriptionName
        destination: {
          endpointType: 'StorageQueue'
          properties: {
            queueName: queueName
            resourceId: storageAccountId
          }
        }
        eventDeliverySchema: 'EventGridSchema'
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
          eventTimeToLiveInMinutes: 1440
        }
        expirationTimeUtc: empty(expirationTimeUtc) ? null : expirationTimeUtc
      }
    ]
    // Use only user-assigned identity
    managedIdentities: { systemAssigned: false, userAssignedResourceIds: [userAssignedResourceId] }
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

output name string = avmEventGridSystemTopic.outputs.name
