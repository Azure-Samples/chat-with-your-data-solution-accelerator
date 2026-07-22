// ============================================================================
// Module: Azure Event Grid System Topic — Event Subscriptions
// Description: Creates event subscriptions on an existing Event Grid System
//              Topic. Deployed as a SEPARATE nested deployment from the topic +
//              role assignment so that, by the time this deployment's
//              authorization preflight runs, the identity-based delivery role
//              (Storage Queue Data Message Sender) granted in the parent module
//              has propagated. A single deployment with only dependsOn ordering
//              does not provide this propagation slack.
// API: Microsoft.EventGrid/systemTopics/eventSubscriptions@2025-02-15
// ============================================================================

@description('Name of the existing Event Grid System Topic to attach subscriptions to.')
param systemTopicName string

@description('Event subscriptions to create on the system topic.')
param eventSubscriptions array = []

// ============================================================================
// Existing system topic reference (created by the parent event-grid module).
// ============================================================================
resource eventGridSystemTopic 'Microsoft.EventGrid/systemTopics@2025-02-15' existing = {
  name: systemTopicName
}

// ============================================================================
// Event Subscriptions. Each uses identity-based delivery
// (deliveryWithResourceIdentity) when provided, otherwise a plain destination.
// ============================================================================
resource systemTopicSubscriptions 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2025-02-15' = [
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
  }
]
