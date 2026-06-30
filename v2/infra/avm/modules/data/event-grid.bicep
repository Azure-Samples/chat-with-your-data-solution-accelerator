// ============================================================================
// Module: Azure Event Grid System Topic
// Description: AVM wrapper for Azure Event Grid System Topic with split
//              deployment pattern to avoid the managed identity authorization
//              race condition. Deploys in three steps using only AVM modules:
//                1. System topic without subscriptions (gets MI principal ID)
//                2. Role assignment (Storage Queue Data Message Sender)
//                3. System topic update with subscriptions (depends on step 2)
// AVM Modules:
//   - avm/res/event-grid/system-topic:0.6.5
//   - avm/ptn/authorization/resource-role-assignment:0.1.2
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

@description('Event subscriptions to create on the system topic. Deployed AFTER the role assignment.')
param eventSubscriptions array = []

@description('Diagnostic settings for monitoring.')
param diagnosticSettings array = []

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

@description('Name of the storage account for scoping the role assignment. Required when eventSubscriptions use deliveryWithResourceIdentity.')
param storageAccountName string = ''

// ============================================================================
// Step 1: Deploy system topic WITHOUT subscriptions (gets MI principal ID)
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
    eventSubscriptions: []
    diagnosticSettings: !empty(diagnosticSettings) ? diagnosticSettings : []
    managedIdentities: managedIdentities
  }
}

// ============================================================================
// Step 2: Grant Storage Queue Data Message Sender to the system topic's MI
// Uses AVM role assignment pattern module. The source param IS the storage
// account resource ID, so we use it directly as the role assignment target.
// ============================================================================
module eventGridQueueSenderRole 'br/public:avm/ptn/authorization/resource-role-assignment:0.1.2' = if (!empty(storageAccountName) && !empty(eventSubscriptions)) {
  name: take('avm.ptn.authorization.role-assignment.evgt-queue-sender', 64)
  params: {
    principalId: eventGridSystemTopic.outputs.?systemAssignedMIPrincipalId ?? ''
    roleDefinitionId: 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a' // Storage Queue Data Message Sender
    resourceId: source // Storage Account resource ID
    roleName: 'Storage Queue Data Message Sender'
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// Step 3: Update system topic WITH event subscriptions AFTER role propagates
// ARM treats this as an idempotent update to the same topic resource, adding
// the subscriptions. The authorization preflight passes because step 2 granted
// the required role.
// ============================================================================
module eventGridSystemTopicWithSubscriptions 'br/public:avm/res/event-grid/system-topic:0.6.5' = if (!empty(eventSubscriptions)) {
  name: take('avm.res.event-grid.system-topic.${name}.subs', 64)
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
  dependsOn: [
    eventGridQueueSenderRole
  ]
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
