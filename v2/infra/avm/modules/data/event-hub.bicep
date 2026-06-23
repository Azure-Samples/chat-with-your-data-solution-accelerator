// ============================================================================
// Module: Azure Event Hub Namespace (AVM)
// ============================================================================

@description('Solution name used for naming convention.')
param solutionName string

@description('Name of the Event Hub namespace.')
param name string = 'evhns-${solutionName}'

@description('Azure region for deployment.')
param location string

@description('Resource tags.')
param tags object = {}

@description('Enable Azure telemetry collection.')
param enableTelemetry bool = true

@description('SKU configuration for the namespace.')
param sku object = {
  name: 'Standard'
  capacity: 1
}

@description('Event hubs to create within the namespace.')
param eventhubs array = []

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

@description('Role assignments.')
param roleAssignments array = []

@description('Enable private networking.')
param enablePrivateNetworking bool = false

@description('Subnet resource ID for private endpoint.')
param privateEndpointSubnetId string = ''

@description('Private DNS zone resource IDs.')
param privateDnsZoneResourceIds array = []

// ============================================================================
// Event Hub Namespace (AVM)
// ============================================================================

var eventHubItems = [for eh in eventhubs: {
  name: eh.name
  messageRetentionInDays: contains(eh, 'messageRetentionInDays') ? eh.messageRetentionInDays : 1
  partitionCount: contains(eh, 'partitionCount') ? eh.partitionCount : 2
}]

var dnsZoneConfigs = [for (zoneId, i) in privateDnsZoneResourceIds: {
  name: 'config${i}'
  privateDnsZoneResourceId: zoneId
}]

var privateEndpointConfig = enablePrivateNetworking && !empty(privateEndpointSubnetId) ? [
  {
    subnetResourceId: privateEndpointSubnetId
    privateDnsZoneGroup: !empty(privateDnsZoneResourceIds) ? {
      privateDnsZoneGroupConfigs: dnsZoneConfigs
    } : null
  }
] : []

module eventHubNamespace 'br/public:avm/res/event-hub/namespace:0.14.1' = {
  name: take('avm.res.eventhub.namespace.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    skuName: sku.name
    skuCapacity: sku.capacity
    eventhubs: eventHubItems
    managedIdentities: managedIdentities
    roleAssignments: !empty(roleAssignments) ? roleAssignments : []
    privateEndpoints: privateEndpointConfig
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('The name of the Event Hub namespace.')
output name string = eventHubNamespace.outputs.name

@description('The resource ID of the Event Hub namespace.')
output resourceId string = eventHubNamespace.outputs.resourceId
