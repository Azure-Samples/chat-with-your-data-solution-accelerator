// ============================================================================
// Module: Azure Event Grid System Topic
// Description: Deploys Azure Event Grid System Topic
// API: Microsoft.EventGrid/systemTopics@2025-07-15-preview
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the Event Grid System Topic.')
param name string = 'evgt-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Resource ID of the source that publishes events (e.g., Storage Account resource ID).')
param source string

@description('The type of the event source. E.g., Microsoft.Storage.StorageAccounts.')
param topicType string

@description('Event subscriptions to create on the system topic.')
param eventSubscriptions array = []

@description('Optional. Managed identity configuration for the resource.')
param identity object = { type: 'SystemAssigned' }

// ============================================================================
// Resource
// ============================================================================
resource eventGridSystemTopic 'Microsoft.EventGrid/systemTopics@2025-07-15-preview' = {
  name: name
  location: location
  tags: tags
  identity: identity
  properties: {
    source: source
    topicType: topicType
  }
}

// ============================================================================
// Event Subscriptions
// ============================================================================
resource systemTopicSubscriptions 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2025-07-15-preview' = [
  for sub in eventSubscriptions: {
    name: sub.name
    parent: eventGridSystemTopic
    properties: {
      destination: sub.destination
      filter: sub.?filter ?? {}
      eventDeliverySchema: sub.?eventDeliverySchema ?? 'EventGridSchema'
      retryPolicy: sub.?retryPolicy ?? {
        maxDeliveryAttempts: 30
        eventTimeToLiveInMinutes: 1440
      }
    }
  }
]

// ============================================================================
// Outputs
// ============================================================================
@description('Name of the Event Grid System Topic.')
output name string = eventGridSystemTopic.name

@description('Resource ID of the Event Grid System Topic.')
output resourceId string = eventGridSystemTopic.id

@description('System-assigned principal ID (if enabled).')
output systemAssignedMIPrincipalId string = (identity.?systemAssigned ?? false) ? eventGridSystemTopic.identity.principalId : ''
