// ============================================================================
// Module: Private DNS Zone
// Description: AVM wrapper for Azure Private DNS Zone
// AVM Module: avm/res/network/private-dns-zone
// Usage: Call once per DNS zone from main.bicep
// ============================================================================

@description('Name of the private DNS zone (e.g., privatelink.cognitiveservices.azure.com).')
param name string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Virtual network links to associate with the DNS zone.')
param virtualNetworkLinks array = []

@description('Optional. Array of A records.')
param a array = []

// ============================================================================
// AVM Module Deployment
// ============================================================================
module privateDnsZone 'br/public:avm/res/network/private-dns-zone:0.8.1' = {
  name: take('avm.res.network.private-dns-zone.${split(name, '.')[1]}', 64)
  params: {
    name: name
    tags: tags
    enableTelemetry: enableTelemetry
    virtualNetworkLinks: virtualNetworkLinks
    a: a
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the private DNS zone.')
output resourceId string = privateDnsZone.outputs.resourceId

@description('Name of the private DNS zone.')
output name string = privateDnsZone.outputs.name
