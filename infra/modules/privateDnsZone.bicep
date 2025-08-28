// This module is here solely to reduce the size of the main bicep file for meet the 4MB limit
// The AVM Module 'br/public:avm/res/network/private-dns-zone' should be used if size is available.

@description('Required. Private DNS zone name.')
param name string

@description('Required. The resource ID of the virtual network to link.')
param virtualNetworkResourceId string

@description('Optional. Tags of the resource.')
param tags object?

// Private DNS Zones are global resources and may not support all regions, even if those regions support the underlying services. 
// The Private DNS Zone creation should use 'global' as the location.
resource privateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: name
  location: 'global' // Private DNS zones must use 'global' as location
  tags: tags
}

resource virtualNetworkLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: '${last(split(virtualNetworkResourceId, '/'))}-vnetlink'
  parent: privateDnsZone
  location: 'global' // Virtual Network Links must also use 'global' as location
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: virtualNetworkResourceId
    }
  }
}

@description('The resource group the private DNS zone was deployed into.')
output resourceGroupName string = resourceGroup().name

@description('The name of the private DNS zone.')
output name string = privateDnsZone.name

@description('The resource ID of the private DNS zone.')
output resourceId string = privateDnsZone.id

@description('The location the resource was deployed into.')
output location string = privateDnsZone.location
