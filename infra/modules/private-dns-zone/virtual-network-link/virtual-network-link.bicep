metadata name = 'Private DNS Zone Virtual Network Link'
metadata description = 'This module deploys a Private DNS Zone Virtual Network Link.'

@description('Conditional. The name of the parent Private DNS zone. Required if the template is used in a standalone deployment.')
param privateDnsZoneName string

@description('Optional. The name of the virtual network link.')
param name string = '${last(split(virtualNetworkResourceId, '/'))}-vnetlink'

@description('Optional. The location of the PrivateDNSZone. Should be global.')
param location string = 'global'

@description('Optional. Tags of the resource.')
param tags resourceInput<'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01'>.tags?

@description('Optional. Is auto-registration of virtual machine records in the virtual network in the Private DNS zone enabled?.')
param registrationEnabled bool = false

@description('Required. Link to another virtual network resource ID.')
param virtualNetworkResourceId string

@description('Optional. The resolution policy on the virtual network link. Only applicable for virtual network links to privatelink zones, and for A,AAAA,CNAME queries. When set to `NxDomainRedirect`, Azure DNS resolver falls back to public resolution if private dns query resolution results in non-existent domain response. `Default` is configured as the default option.')
param resolutionPolicy string?

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  name: privateDnsZoneName
}

resource virtualNetworkLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: name
  parent: privateDnsZone
  location: location
  tags: tags
  properties: {
    registrationEnabled: registrationEnabled
    virtualNetwork: {
      id: virtualNetworkResourceId
    }
    resolutionPolicy: resolutionPolicy
  }
}

@description('The name of the deployed virtual network link.')
output name string = virtualNetworkLink.name

@description('The resource ID of the deployed virtual network link.')
output resourceId string = virtualNetworkLink.id

@description('The resource group of the deployed virtual network link.')
output resourceGroupName string = resourceGroup().name

@description('The location the resource was deployed into.')
output location string = virtualNetworkLink.location
