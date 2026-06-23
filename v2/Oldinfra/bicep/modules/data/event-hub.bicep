// ============================================================================
// Module: Azure Event Hub Namespace
// Description: Creates an Azure Event Hub Namespace with event hubs
// API: Microsoft.EventHub/namespaces@2024-01-01
// ============================================================================

@description('Solution name used for naming convention.')
param solutionName string

@description('Name of the Event Hub namespace.')
param name string = 'evhns-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('The SKU tier for the Event Hub namespace.')
param sku string = 'Standard'

@description('The throughput unit or processing unit capacity.')
param capacity int = 1

@description('Event hubs to create within the namespace.')
param eventhubs array = []

// ============================================================================
// Resource Deployment
// ============================================================================
resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
    tier: sku
    capacity: capacity
  }
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

resource eventHubResources 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = [for eventhub in eventhubs: {
  name: eventhub.name
  parent: eventHubNamespace
  properties: {
    messageRetentionInDays: eventhub.?messageRetentionInDays ?? 1
    partitionCount: eventhub.?partitionCount ?? 2
  }
}]

// ============================================================================
// Outputs
// ============================================================================
@description('The name of the Event Hub namespace.')
output name string = eventHubNamespace.name

@description('The resource ID of the Event Hub namespace.')
output resourceId string = eventHubNamespace.id
