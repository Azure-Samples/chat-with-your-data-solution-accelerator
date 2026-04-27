// =============================================================================
// CWYD v2 - Virtual Network module
// Pillar: Stable Core
// Phase:  1 (Infrastructure + Project Skeleton, tasks #7-#8)
//
// Wraps AVM `network/virtual-network:0.7.0` + per-subnet AVM
// `network/network-security-group:0.5.1` to deploy the v2 hub VNet.
//
// Address plan (10.0.0.0/20, 4096 addresses):
//   web              10.0.0.0/24    - Frontend Web App regional VNet integration
//                                     (App Service plan delegation)
//   containerapps    10.0.4.0/23    - Container Apps Env infrastructure subnet
//                                     (CAE requires >= /23)
//   functions        10.0.6.0/24    - Function App Flex regional VNet integration
//   postgres (cond.) 10.0.7.0/24    - Postgres Flex DELEGATED subnet
//                                     (only when databaseType == 'postgresql')
//   peps             10.0.8.0/23    - Private endpoint NICs (all PEs land here)
//   AzureBastionSubnet 10.0.10.0/26 - Bastion (fixed name, requires >= /26)
//
// Inline `privateEndpoints` arrays on existing AVM data modules in main.bicep
// reference `pepsSubnetResourceId`. Postgres uses `postgresSubnetResourceId`
// directly (delegated subnet, not a PE). CAE uses `containerAppsSubnetResourceId`.
// Web App + Function App use `webSubnetResourceId` / `functionsSubnetResourceId`.
//
// References:
//   v1 wrapper:                   infra/modules/virtualNetwork.bicep
//   MACAE pattern (read-only):    Multi-Agent-Custom-Automation-Engine-Solution-Accelerator/infra/main.bicep
//   CGSA pattern (read-only):     content-generation-solution-accelerator/infra/modules/virtualNetwork.bicep
// =============================================================================

@description('Required. Name of the virtual network.')
param name string

@description('Optional. Azure region to deploy resources. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('Optional. An array of one or more IP address prefixes for the virtual network. Defaults to a single /20 (4096 addresses) which fits the v2 subnet plan with room to grow.')
param addressPrefixes array = ['10.0.0.0/20']

@allowed([
  'cosmosdb'
  'postgresql'
])
@description('Required. Mirrors the `databaseType` parameter on the parent template. When `postgresql` we add a delegated subnet for Postgres Flexible Server; when `cosmosdb` that subnet is omitted to keep the network minimal.')
param databaseType string

@description('Optional. Tags to apply to all resources created by this module.')
param tags object = {}

@description('Optional. Resource ID of the Log Analytics workspace to send VNet diagnostic logs to. Pass an empty string to skip diagnostics (e.g. when monitoring is disabled).')
param logAnalyticsWorkspaceId string = ''

@description('Optional. Suffix appended to NSG names so multiple deployments in the same RG do not collide.')
param resourceSuffix string

@description('Optional. Enable AVM telemetry for the VNet + NSG modules.')
param enableTelemetry bool = false

// -----------------------------------------------------------------------------
// Subnet definitions
// -----------------------------------------------------------------------------
// Each entry is processed by the NSG loop + handed to the AVM virtual-network
// module. Postgres entry is appended only in postgresql mode so cosmosdb-mode
// deploys do not allocate an unused /24 + NSG.
// -----------------------------------------------------------------------------

var commonAppNsgRules = [
  {
    name: 'AllowHttpsInbound'
    properties: {
      access: 'Allow'
      direction: 'Inbound'
      priority: 100
      protocol: 'Tcp'
      sourcePortRange: '*'
      destinationPortRange: '443'
      sourceAddressPrefix: 'Internet'
      destinationAddressPrefix: 'VirtualNetwork'
    }
  }
  {
    name: 'AllowAzureLoadBalancer'
    properties: {
      access: 'Allow'
      direction: 'Inbound'
      priority: 200
      protocol: '*'
      sourcePortRange: '*'
      destinationPortRange: '*'
      sourceAddressPrefix: 'AzureLoadBalancer'
      destinationAddressPrefix: 'VirtualNetwork'
    }
  }
]

var bastionNsgRules = [
  {
    name: 'AllowGatewayManagerInbound'
    properties: {
      access: 'Allow'
      direction: 'Inbound'
      priority: 2702
      protocol: 'Tcp'
      sourcePortRange: '*'
      destinationPortRange: '443'
      sourceAddressPrefix: 'GatewayManager'
      destinationAddressPrefix: '*'
    }
  }
  {
    name: 'AllowHttpsInbound'
    properties: {
      access: 'Allow'
      direction: 'Inbound'
      priority: 2703
      protocol: 'Tcp'
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

var baseSubnets = [
  {
    name: 'web'
    addressPrefixes: ['10.0.0.0/24']
    delegation: 'Microsoft.Web/serverFarms'
    networkSecurityGroup: {
      name: 'nsg-web'
      securityRules: commonAppNsgRules
    }
  }
  {
    name: 'containerapps'
    addressPrefixes: ['10.0.4.0/23']
    networkSecurityGroup: {
      name: 'nsg-containerapps'
      securityRules: []
    }
  }
  {
    name: 'functions'
    addressPrefixes: ['10.0.6.0/24']
    delegation: 'Microsoft.Web/serverFarms'
    networkSecurityGroup: {
      name: 'nsg-functions'
      securityRules: commonAppNsgRules
    }
  }
  {
    name: 'peps'
    addressPrefixes: ['10.0.8.0/23']
    privateEndpointNetworkPolicies: 'Disabled'
    privateLinkServiceNetworkPolicies: 'Disabled'
    networkSecurityGroup: {
      name: 'nsg-peps'
      securityRules: []
    }
  }
  {
    name: 'AzureBastionSubnet'
    addressPrefixes: ['10.0.10.0/26']
    networkSecurityGroup: {
      name: 'nsg-bastion'
      securityRules: bastionNsgRules
    }
  }
]

var postgresSubnet = [
  {
    name: 'postgres'
    addressPrefixes: ['10.0.7.0/24']
    delegation: 'Microsoft.DBforPostgreSQL/flexibleServers'
    networkSecurityGroup: {
      name: 'nsg-postgres'
      securityRules: []
    }
  }
]

var subnets = databaseType == 'postgresql' ? concat(baseSubnets, postgresSubnet) : baseSubnets

// -----------------------------------------------------------------------------
// 1. NSGs (one per subnet that defines `networkSecurityGroup`)
// -----------------------------------------------------------------------------
@batchSize(1)
module nsgs 'br/public:avm/res/network/network-security-group:0.5.1' = [
  for (subnet, i) in subnets: {
    name: take('avm.res.network.network-security-group.${subnet.networkSecurityGroup.name}.${resourceSuffix}', 64)
    params: {
      name: '${subnet.networkSecurityGroup.name}-${resourceSuffix}'
      location: location
      securityRules: subnet.networkSecurityGroup.securityRules
      tags: tags
      enableTelemetry: enableTelemetry
    }
  }
]

// -----------------------------------------------------------------------------
// 2. Virtual network + subnets (NSGs wired by index)
// -----------------------------------------------------------------------------
module virtualNetwork 'br/public:avm/res/network/virtual-network:0.7.0' = {
  name: take('avm.res.network.virtual-network.${name}', 64)
  params: {
    name: name
    location: location
    addressPrefixes: addressPrefixes
    subnets: [
      for (subnet, i) in subnets: {
        name: subnet.name
        addressPrefixes: subnet.addressPrefixes
        networkSecurityGroupResourceId: nsgs[i].outputs.resourceId
        privateEndpointNetworkPolicies: subnet.?privateEndpointNetworkPolicies
        privateLinkServiceNetworkPolicies: subnet.?privateLinkServiceNetworkPolicies
        delegation: subnet.?delegation
      }
    ]
    diagnosticSettings: empty(logAnalyticsWorkspaceId) ? null : [
      {
        name: 'vnetDiagnostics'
        workspaceResourceId: logAnalyticsWorkspaceId
        logCategoriesAndGroups: [
          { categoryGroup: 'allLogs', enabled: true }
        ]
        metricCategories: [
          { category: 'AllMetrics', enabled: true }
        ]
      }
    ]
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// -----------------------------------------------------------------------------
// Outputs
// -----------------------------------------------------------------------------
@description('Name of the deployed virtual network.')
output name string = virtualNetwork.outputs.name

@description('Resource ID of the deployed virtual network.')
output resourceId string = virtualNetwork.outputs.resourceId

@description('Resource ID of the `web` subnet (Frontend Web App regional VNet integration).')
output webSubnetResourceId string = virtualNetwork.outputs.subnetResourceIds[indexOf(map(subnets, s => s.name), 'web')]

@description('Resource ID of the `containerapps` subnet (Container Apps Environment infrastructure subnet).')
output containerAppsSubnetResourceId string = virtualNetwork.outputs.subnetResourceIds[indexOf(map(subnets, s => s.name), 'containerapps')]

@description('Resource ID of the `functions` subnet (Function App Flex regional VNet integration).')
output functionsSubnetResourceId string = virtualNetwork.outputs.subnetResourceIds[indexOf(map(subnets, s => s.name), 'functions')]

@description('Resource ID of the `peps` subnet (private endpoint NICs land here). All inline `privateEndpoints` arrays on AVM modules in main.bicep should reference this.')
output pepsSubnetResourceId string = virtualNetwork.outputs.subnetResourceIds[indexOf(map(subnets, s => s.name), 'peps')]

@description('Resource ID of the `AzureBastionSubnet` (consumed by AVM `network/bastion-host`).')
output bastionSubnetResourceId string = virtualNetwork.outputs.subnetResourceIds[indexOf(map(subnets, s => s.name), 'AzureBastionSubnet')]

@description('Resource ID of the `postgres` delegated subnet. Empty string in cosmosdb mode. Wired into the Postgres Flex AVM module as `delegatedSubnetResourceId`.')
output postgresSubnetResourceId string = databaseType == 'postgresql' ? virtualNetwork.outputs.subnetResourceIds[indexOf(map(subnets, s => s.name), 'postgres')] : ''
