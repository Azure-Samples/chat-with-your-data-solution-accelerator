/****************************************************************************************************************************/
// Networking - NSGs, VNET and Subnets. Each subnet has its own NSG
/****************************************************************************************************************************/
@description('Required. Name of the virtual network.')
param name string

@description('Required. Azure region to deploy resources.')
param location string = resourceGroup().location

@description('Required. An Array of 1 or more IP Address Prefixes OR the resource ID of the IPAM pool to be used for the Virtual Network. When specifying an IPAM pool resource ID you must also set a value for the parameter called `ipamPoolNumberOfIpAddresses`.')
param addressPrefixes array

@description('Optional. An array of subnets to be created within the virtual network. Each subnet can have its own configuration and associated Network Security Group (NSG).')
param subnets subnetType[]

@description('Optional. Tags to be applied to the resources.')
param tags object = {}

@description('Optional. The resource ID of the Log Analytics Workspace to send diagnostic logs to.')
param logAnalyticsWorkspaceId string

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// 1. Create NSGs for subnets
// using AVM Network Security Group module
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/network/network-security-group

@batchSize(1)
module nsgs 'br/public:avm/res/network/network-security-group:0.5.1' = [
  for (subnet, i) in subnets: if (!empty(subnet.?networkSecurityGroup)) {
    name: take('${name}-${subnet.?networkSecurityGroup.name}-networksecuritygroup', 64)
    params: {
      name: '${subnet.?networkSecurityGroup.name}-${name}'
      location: location
      securityRules: subnet.?networkSecurityGroup.securityRules
      tags: tags
      enableTelemetry: enableTelemetry
    }
  }
]

// 2. Create VNet and subnets, with subnets associated with corresponding NSGs
// using AVM Virtual Network module
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/network/virtual-network

module virtualNetwork 'br/public:avm/res/network/virtual-network:0.7.0' = {
  name: take('${name}-virtualNetwork', 64)
  params: {
    name: name
    location: location
    addressPrefixes: addressPrefixes
    subnets: [
      for (subnet, i) in subnets: {
        name: subnet.name
        addressPrefixes: subnet.?addressPrefixes
        networkSecurityGroupResourceId: !empty(subnet.?networkSecurityGroup) ? nsgs[i]!.outputs.resourceId : null
        privateEndpointNetworkPolicies: subnet.?privateEndpointNetworkPolicies
        privateLinkServiceNetworkPolicies: subnet.?privateLinkServiceNetworkPolicies
        delegation: subnet.?delegation
      }
    ]
    diagnosticSettings: [
      {
        name: 'vnetDiagnostics'
        workspaceResourceId: logAnalyticsWorkspaceId
        logCategoriesAndGroups: [
          {
            categoryGroup: 'allLogs'
            enabled: true
          }
        ]
        metricCategories: [
          {
            category: 'AllMetrics'
            enabled: true
          }
        ]
      }
    ]
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

output name string = virtualNetwork.outputs.name
output resourceId string = virtualNetwork.outputs.resourceId

// combined output array that holds subnet details along with NSG information
output subnets subnetOutputType[] = [
  for (subnet, i) in subnets: {
    name: subnet.name
    resourceId: virtualNetwork.outputs.subnetResourceIds[i]
    nsgName: !empty(subnet.?networkSecurityGroup) ? subnet.?networkSecurityGroup.name : null
    nsgResourceId: !empty(subnet.?networkSecurityGroup) ? nsgs[i]!.outputs.resourceId : null
  }
]

@export()
@description('Custom type definition for subnet resource information as output')
type subnetOutputType = {
  @description('The name of the subnet.')
  name: string

  @description('The resource ID of the subnet.')
  resourceId: string

  @description('The name of the associated network security group, if any.')
  nsgName: string?

  @description('The resource ID of the associated network security group, if any.')
  nsgResourceId: string?
}

@export()
@description('Custom type definition for subnet configuration')
type subnetType = {
  @description('Required. The Name of the subnet resource.')
  name: string

  @description('Required. Prefixes for the subnet.') // Required to ensure at least one prefix is provided
  addressPrefixes: string[]

  @description('Optional. The delegation to enable on the subnet.')
  delegation: string?

  @description('Optional. enable or disable apply network policies on private endpoint in the subnet.')
  privateEndpointNetworkPolicies: ('Disabled' | 'Enabled' | 'NetworkSecurityGroupEnabled' | 'RouteTableEnabled')?

  @description('Optional. Enable or disable apply network policies on private link service in the subnet.')
  privateLinkServiceNetworkPolicies: ('Disabled' | 'Enabled')?

  @description('Optional. Network Security Group configuration for the subnet.')
  networkSecurityGroup: networkSecurityGroupType?

  @description('Optional. The resource ID of the route table to assign to the subnet.')
  routeTableResourceId: string?

  @description('Optional. An array of service endpoint policies.')
  serviceEndpointPolicies: object[]?

  @description('Optional. The service endpoints to enable on the subnet.')
  serviceEndpoints: string[]?

  @description('Optional. Set this property to false to disable default outbound connectivity for all VMs in the subnet. This property can only be set at the time of subnet creation and cannot be updated for an existing subnet.')
  defaultOutboundAccess: bool?
}

@export()
@description('Custom type definition for network security group configuration')
type networkSecurityGroupType = {
  @description('Required. The name of the network security group.')
  name: string

  @description('Required. The security rules for the network security group.')
  securityRules: object[]
}
