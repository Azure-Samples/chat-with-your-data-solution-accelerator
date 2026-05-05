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

@description('Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

var userAssignedIdentities = {
  '${userAssignedResourceId}': {}
}

#disable-next-line no-deployments-resources
resource telemetry 'Microsoft.Resources/deployments@2025-04-01' = if (enableTelemetry) {
  name: 'eventgrid.${substring(uniqueString(deployment().name, location), 0, 6)}'
  properties: {
    mode: 'Incremental'
    template: {
      '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#'
      contentVersion: '1.0.0.0'
      resources: []
    }
  }
}

resource systemTopic 'Microsoft.EventGrid/systemTopics@2025-02-15' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: userAssignedIdentities
  }
  properties: {
    source: storageAccountId
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

resource eventSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2025-02-15' = {
  parent: systemTopic
  name: name
  properties: {
    deliveryWithResourceIdentity: {
      identity: {
        type: 'UserAssigned'
        userAssignedIdentity: userAssignedResourceId
      }
      destination: {
        endpointType: 'StorageQueue'
        properties: {
          queueName: queueName
          resourceId: storageAccountId
        }
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
}

#disable-next-line use-recent-api-versions
resource systemTopic_diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableMonitoring && !empty(logAnalyticsWorkspaceResourceId)) {
  name: 'diagnosticSettings'
  properties: {
    workspaceId: logAnalyticsWorkspaceResourceId
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
  scope: systemTopic
}

output name string = systemTopic.name
