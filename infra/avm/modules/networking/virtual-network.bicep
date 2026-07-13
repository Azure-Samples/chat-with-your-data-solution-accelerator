// ============================================================================
// Module: Virtual Network
// Description: VNet, Subnets, and NSGs using AVM modules.
//              Each subnet gets its own NSG. Subnet config is passed as param.
// AVM Modules:
//   - avm/res/network/network-security-group:0.5.3
//   - avm/res/network/virtual-network:0.8.0
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

var name = 'vnet-${solutionName}'

@description('Azure region for the resource.')
param location string = resourceGroup().location

@description('Address prefixes for the virtual network.')
param addressPrefixes array

@description('Subnet configurations.')
param subnets subnetType[] = [
  {
    name: 'backend'
    addressPrefixes: ['10.0.0.0/27']
    networkSecurityGroup: {
      name: 'nsg-backend'
      securityRules: [
        {
          name: 'deny-hop-outbound'
          properties: {
            access: 'Deny'
            destinationAddressPrefix: '*'
            destinationPortRanges: ['22', '3389']
            direction: 'Outbound'
            priority: 200
            protocol: 'Tcp'
            sourceAddressPrefix: 'VirtualNetwork'
            sourcePortRange: '*'
          }
        }
      ]
    }
  }
  {
    name: 'containers'
    addressPrefixes: ['10.0.2.0/23']
    delegation: 'Microsoft.App/environments'
    privateEndpointNetworkPolicies: 'Enabled'
    privateLinkServiceNetworkPolicies: 'Enabled'
    networkSecurityGroup: {
      name: 'nsg-containers'
      securityRules: [
        {
          name: 'deny-hop-outbound'
          properties: {
            access: 'Deny'
            destinationAddressPrefix: '*'
            destinationPortRanges: ['22', '3389']
            direction: 'Outbound'
            priority: 200
            protocol: 'Tcp'
            sourceAddressPrefix: 'VirtualNetwork'
            sourcePortRange: '*'
          }
        }
      ]
    }
  }
  {
    name: 'webserverfarm'
    addressPrefixes: ['10.0.4.0/27']
    delegation: 'Microsoft.Web/serverfarms'
    privateEndpointNetworkPolicies: 'Enabled'
    privateLinkServiceNetworkPolicies: 'Enabled'
    networkSecurityGroup: {
      name: 'nsg-webserverfarm'
      securityRules: [
        {
          name: 'deny-hop-outbound'
          properties: {
            access: 'Deny'
            destinationAddressPrefix: '*'
            destinationPortRanges: ['22', '3389']
            direction: 'Outbound'
            priority: 200
            protocol: 'Tcp'
            sourceAddressPrefix: 'VirtualNetwork'
            sourcePortRange: '*'
          }
        }
      ]
    }
  }
  {
    name: 'administration'
    addressPrefixes: ['10.0.0.32/27']
    networkSecurityGroup: {
      name: 'nsg-administration'
      securityRules: [
        {
          name: 'deny-hop-outbound'
          properties: {
            access: 'Deny'
            destinationAddressPrefix: '*'
            destinationPortRanges: ['22', '3389']
            direction: 'Outbound'
            priority: 200
            protocol: 'Tcp'
            sourceAddressPrefix: 'VirtualNetwork'
            sourcePortRange: '*'
          }
        }
      ]
    }
  }
  {
    name: 'AzureBastionSubnet'
    addressPrefixes: ['10.0.0.64/26']
    networkSecurityGroup: {
      name: 'nsg-bastion'
      securityRules: [
        {
          name: 'AllowGatewayManager'
          properties: {
            access: 'Allow'
            direction: 'Inbound'
            priority: 2702
            protocol: '*'
            sourcePortRange: '*'
            destinationPortRange: '443'
            sourceAddressPrefix: 'GatewayManager'
            destinationAddressPrefix: '*'
          }
        }
        {
          name: 'AllowHttpsInBound'
          properties: {
            access: 'Allow'
            direction: 'Inbound'
            priority: 2703
            protocol: '*'
            sourcePortRange: '*'
            destinationPortRange: '443'
            sourceAddressPrefix: 'Internet'
            destinationAddressPrefix: '*'
          }
        }
        {
          name: 'AllowSshRdpOutbound'
          properties: {
            access: 'Allow'
            direction: 'Outbound'
            priority: 100
            protocol: '*'
            sourcePortRange: '*'
            destinationPortRanges: ['22', '3389']
            sourceAddressPrefix: '*'
            destinationAddressPrefix: 'VirtualNetwork'
          }
        }
        {
          name: 'AllowAzureCloudOutbound'
          properties: {
            access: 'Allow'
            direction: 'Outbound'
            priority: 110
            protocol: 'Tcp'
            sourcePortRange: '*'
            destinationPortRange: '443'
            sourceAddressPrefix: '*'
            destinationAddressPrefix: 'AzureCloud'
          }
        }
      ]
    }
  }
]

@description('Tags to apply to the resources.')
param tags object = {}

@description('Resource ID of the Log Analytics Workspace for diagnostics.')
param logAnalyticsWorkspaceId string

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Suffix for resource naming.')
param resourceSuffix string

// ============================================================================
// NSGs — one per subnet
// ============================================================================
@batchSize(1)
module nsgs 'br/public:avm/res/network/network-security-group:0.5.3' = [
  for (subnet, i) in subnets: if (!empty(subnet.?networkSecurityGroup)) {
    name: take('avm.res.network.nsg.${subnet.?networkSecurityGroup.name}.${resourceSuffix}', 64)
    params: {
      name: '${subnet.?networkSecurityGroup.name}-${resourceSuffix}'
      location: location
      securityRules: subnet.?networkSecurityGroup.securityRules
      tags: tags
      enableTelemetry: enableTelemetry
    }
  }
]

// ============================================================================
// Virtual Network + Subnets
// ============================================================================
module virtualNetwork 'br/public:avm/res/network/virtual-network:0.8.0' = {
  name: take('avm.res.network.virtual-network.${name}', 64)
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

// ============================================================================
// Outputs
// ============================================================================
output name string = virtualNetwork.outputs.name
output resourceId string = virtualNetwork.outputs.resourceId

output subnets subnetOutputType[] = [
  for (subnet, i) in subnets: {
    name: subnet.name
    resourceId: virtualNetwork.outputs.subnetResourceIds[i]
    nsgName: !empty(subnet.?networkSecurityGroup) ? subnet.?networkSecurityGroup.name : null
    nsgResourceId: !empty(subnet.?networkSecurityGroup) ? nsgs[i]!.outputs.resourceId : null
  }
]

// Individual subnet outputs for backward compatibility
output backendSubnetResourceId string = contains(map(subnets, subnet => subnet.name), 'backend')
  ? virtualNetwork.outputs.subnetResourceIds[indexOf(map(subnets, subnet => subnet.name), 'backend')]
  : ''
output containerSubnetResourceId string = contains(map(subnets, subnet => subnet.name), 'containers')
  ? virtualNetwork.outputs.subnetResourceIds[indexOf(map(subnets, subnet => subnet.name), 'containers')]
  : ''
output webserverfarmSubnetResourceId string = contains(map(subnets, subnet => subnet.name), 'webserverfarm')
  ? virtualNetwork.outputs.subnetResourceIds[indexOf(map(subnets, subnet => subnet.name), 'webserverfarm')]
  : ''
output administrationSubnetResourceId string = contains(map(subnets, subnet => subnet.name), 'administration')
  ? virtualNetwork.outputs.subnetResourceIds[indexOf(map(subnets, subnet => subnet.name), 'administration')]
  : ''
output bastionSubnetResourceId string = contains(map(subnets, subnet => subnet.name), 'AzureBastionSubnet')
  ? virtualNetwork.outputs.subnetResourceIds[indexOf(map(subnets, subnet => subnet.name), 'AzureBastionSubnet')]
  : ''

// ============================================================================
// Custom Types
// ============================================================================
@export()
@description('Subnet output type')
type subnetOutputType = {
  @description('The name of the subnet.')
  name: string
  @description('The resource ID of the subnet.')
  resourceId: string
  @description('The name of the associated NSG, if any.')
  nsgName: string?
  @description('The resource ID of the associated NSG, if any.')
  nsgResourceId: string?
}

@export()
@description('Subnet configuration type')
type subnetType = {
  @description('Required. The name of the subnet.')
  name: string
  @description('Required. Address prefixes for the subnet.')
  addressPrefixes: string[]
  @description('Optional. Delegation for the subnet.')
  delegation: string?
  @description('Optional. Private endpoint network policies.')
  privateEndpointNetworkPolicies: ('Disabled' | 'Enabled' | 'NetworkSecurityGroupEnabled' | 'RouteTableEnabled')?
  @description('Optional. Private link service network policies.')
  privateLinkServiceNetworkPolicies: ('Disabled' | 'Enabled')?
  @description('Optional. NSG configuration for the subnet.')
  networkSecurityGroup: networkSecurityGroupType?
  @description('Optional. Route table resource ID.')
  routeTableResourceId: string?
  @description('Optional. Service endpoint policies.')
  serviceEndpointPolicies: object[]?
  @description('Optional. Service endpoints to enable.')
  serviceEndpoints: string[]?
  @description('Optional. Disable default outbound connectivity.')
  defaultOutboundAccess: bool?
}

@export()
@description('NSG configuration type')
type networkSecurityGroupType = {
  @description('Required. The name of the NSG.')
  name: string
  @description('Required. Security rules for the NSG.')
  securityRules: object[]
}
