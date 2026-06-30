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

@description('Name of the storage account used to scope the Storage Queue Data Message Sender role assignment. Required when eventSubscriptions use identity-based (deliveryWithResourceIdentity) delivery.')
param storageAccountName string = ''

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
// Role assignment: grant the system topic's managed identity permission to
// write to the destination Storage Queue. Required for identity-based
// (deliveryWithResourceIdentity) delivery when the storage account has
// shared-key access disabled. Scoped to the storage account.
// ============================================================================
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = if (!empty(storageAccountName)) {
  name: storageAccountName
}

resource eventGridQueueSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(storageAccountName) && !empty(eventSubscriptions)) {
  name: guid(storageAccount.id, eventGridSystemTopic.id, 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a')
  scope: storageAccount
  properties: {
    principalId: eventGridSystemTopic.identity.principalId
    // Storage Queue Data Message Sender
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a')
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// Event Subscriptions
// Deployed AFTER the role assignment so the identity-based delivery
// authorization preflight passes (mirrors the avm flavor's split pattern).
// Each subscription uses identity-based delivery (deliveryWithResourceIdentity)
// when provided, otherwise falls back to a plain destination.
// ============================================================================
resource systemTopicSubscriptions 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2025-07-15-preview' = [
  for sub in eventSubscriptions: {
    name: sub.name
    parent: eventGridSystemTopic
    properties: union(
      {
        filter: sub.?filter ?? {}
        eventDeliverySchema: sub.?eventDeliverySchema ?? 'EventGridSchema'
        retryPolicy: sub.?retryPolicy ?? {
          maxDeliveryAttempts: 30
          eventTimeToLiveInMinutes: 1440
        }
      },
      sub.?deliveryWithResourceIdentity != null
        ? { deliveryWithResourceIdentity: sub.deliveryWithResourceIdentity }
        : { destination: sub.destination }
    )
    dependsOn: [
      eventGridQueueSenderRole
    ]
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
output systemAssignedMIPrincipalId string = contains(identity, 'type') && contains(identity.type, 'SystemAssigned') ? eventGridSystemTopic.identity.principalId : ''
