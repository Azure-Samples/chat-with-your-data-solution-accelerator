// ============================================================================
// Module: Private Endpoint
// Description: AVM wrapper for Azure Private Endpoint
// AVM Module: avm/res/network/private-endpoint
// Usage: Call once per private endpoint from main.bicep
// ============================================================================

@description('Name of the private endpoint.')
param name string

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Optional. Custom NIC name for the private endpoint.')
param customNetworkInterfaceName string = ''

@description('Resource ID of the subnet for the private endpoint.')
param subnetResourceId string

@description('Private link service connections configuration.')
param privateLinkServiceConnections array

@description('Optional. Private DNS zone group configuration.')
param privateDnsZoneGroup object?

// ============================================================================
// AVM Module Deployment
// ============================================================================
module privateEndpoint 'br/public:avm/res/network/private-endpoint:0.12.0' = {
  name: take('avm.res.network.private-endpoint.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    customNetworkInterfaceName: !empty(customNetworkInterfaceName) ? customNetworkInterfaceName : 'nic-${name}'
    subnetResourceId: subnetResourceId
    privateLinkServiceConnections: privateLinkServiceConnections
    privateDnsZoneGroup: privateDnsZoneGroup
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the private endpoint.')
output resourceId string = privateEndpoint.outputs.resourceId

@description('Name of the private endpoint.')
output name string = privateEndpoint.outputs.name
