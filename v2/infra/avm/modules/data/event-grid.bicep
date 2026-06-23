// ============================================================================
// Module: Azure Event Grid System Topic
// Description: AVM wrapper for Azure Event Grid System Topic
// AVM Module: avm/res/event-grid/system-topic:0.6.5
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the Event Grid System Topic.')
param name string = 'evgt-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Resource ID of the source that publishes events (e.g., Storage Account resource ID).')
param source string

@description('The type of the event source. E.g., Microsoft.Storage.StorageAccounts.')
param topicType string

@description('Event subscriptions to create on the system topic.')
param eventSubscriptions array = []

@description('Diagnostic settings for monitoring.')
param diagnosticSettings array = []

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

// ============================================================================
// AVM Module Deployment
// ============================================================================
module eventGridSystemTopic 'br/public:avm/res/event-grid/system-topic:0.6.5' = {
  name: take('avm.res.event-grid.system-topic.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    source: source
    topicType: topicType
    eventSubscriptions: eventSubscriptions
    diagnosticSettings: !empty(diagnosticSettings) ? diagnosticSettings : []
    managedIdentities: managedIdentities
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Name of the Event Grid System Topic.')
output name string = eventGridSystemTopic.outputs.name

@description('Resource ID of the Event Grid System Topic.')
output resourceId string = eventGridSystemTopic.outputs.resourceId

@description('System-assigned principal ID (if enabled).')
output systemAssignedMIPrincipalId string = eventGridSystemTopic.outputs.?systemAssignedMIPrincipalId ?? ''
