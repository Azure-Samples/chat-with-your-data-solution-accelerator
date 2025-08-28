@export()
@description('Values to establish private networking for resources that support createing private endpoints.')
type resourcePrivateNetworkingType = {
  @description('Required. The Resource ID of the virtual network.')
  virtualNetworkResourceId: string

  @description('Required. The Resource ID of the subnet to establish the Private Endpoint(s).')
  subnetResourceId: string

  @description('Optional. The Resource ID of an existing Private DNS Zone Resource to link to the virtual network. If not provided, a new Private DNS Zone(s) will be created.')
  privateDnsZoneResourceId: string?
}
