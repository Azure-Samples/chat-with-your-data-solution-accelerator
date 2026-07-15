// ============================================================================
// Module: Azure Event Grid System Topic
// Description: Deploys Azure Event Grid System Topic
// API: Microsoft.EventGrid/systemTopics@2025-02-15
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

@description('Optional. Managed identity configuration for the resource.')
param identity object = { type: 'SystemAssigned' }

// ============================================================================
// Resource
// ============================================================================
resource eventGridSystemTopic 'Microsoft.EventGrid/systemTopics@2025-02-15' = {
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
// Outputs
// ============================================================================
@description('Name of the Event Grid System Topic.')
output name string = eventGridSystemTopic.name

@description('Resource ID of the Event Grid System Topic.')
output resourceId string = eventGridSystemTopic.id

@description('System-assigned principal ID (if enabled).')
output systemAssignedMIPrincipalId string = contains(identity, 'type') && contains(identity.type, 'SystemAssigned') ? eventGridSystemTopic.identity.principalId : ''
