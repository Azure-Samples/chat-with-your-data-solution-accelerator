param networkInterfaceName string
param virtualMachineName string
param ipConfigurations ipConfigurationType[]

@description('Optional. Location for all resources.')
param location string

@description('Optional. Tags of the resource.')
param tags object?

param enableIPForwarding bool = false
param enableAcceleratedNetworking bool = false
param dnsServers string[] = []

@description('Required. Enable telemetry via a Globally Unique Identifier (GUID).')
param enableTelemetry bool

@description('Optional. The network security group (NSG) to attach to the network interface.')
param networkSecurityGroupResourceId string = ''

import { lockType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. The lock settings of the service.')
param lock lockType?

import { diagnosticSettingFullType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. The diagnostic settings of the service.')
param diagnosticSettings diagnosticSettingFullType[]?

import { roleAssignmentType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. Array of role assignments to create.')
param roleAssignments roleAssignmentType[]?

module networkInterface_publicIPAddresses 'br/public:avm/res/network/public-ip-address:0.8.0' = [
  for (ipConfiguration, index) in ipConfigurations: if (!empty(ipConfiguration.?pipConfiguration) && empty(ipConfiguration.?pipConfiguration.?publicIPAddressResourceId)) {
    name: '${deployment().name}-publicIP-${index}'
    params: {
      name: ipConfiguration.?pipConfiguration.?name ?? '${virtualMachineName}${ipConfiguration.?pipConfiguration.?publicIpNameSuffix}'
      diagnosticSettings: ipConfiguration.?pipConfiguration.?diagnosticSettings ?? ipConfiguration.?diagnosticSettings
      location: location
      lock: lock
      idleTimeoutInMinutes: ipConfiguration.?pipConfiguration.?idleTimeoutInMinutes
      ddosSettings: ipConfiguration.?pipConfiguration.?ddosSettings
      dnsSettings: ipConfiguration.?pipConfiguration.?dnsSettings
      publicIPAddressVersion: ipConfiguration.?pipConfiguration.?publicIPAddressVersion
      publicIPAllocationMethod: ipConfiguration.?pipConfiguration.?publicIPAllocationMethod
      publicIpPrefixResourceId: ipConfiguration.?pipConfiguration.?publicIpPrefixResourceId
      roleAssignments: ipConfiguration.?pipConfiguration.?roleAssignments
      skuName: ipConfiguration.?pipConfiguration.?skuName
      skuTier: ipConfiguration.?pipConfiguration.?skuTier
      tags: ipConfiguration.?tags ?? tags
      zones: ipConfiguration.?pipConfiguration.?zones
      enableTelemetry: ipConfiguration.?pipConfiguration.?enableTelemetry ?? ipConfiguration.?enableTelemetry ?? enableTelemetry
    }
  }
]

module networkInterface 'br/public:avm/res/network/network-interface:0.5.1' = {
  name: '${deployment().name}-NetworkInterface'
  params: {
    name: networkInterfaceName
    ipConfigurations: [
      for (ipConfiguration, index) in ipConfigurations: {
        name: ipConfiguration.?name
        privateIPAllocationMethod: ipConfiguration.?privateIPAllocationMethod
        privateIPAddress: ipConfiguration.?privateIPAddress
        publicIPAddressResourceId: !empty(ipConfiguration.?pipConfiguration)
          ? !contains(ipConfiguration.?pipConfiguration ?? {}, 'publicIPAddressResourceId')
              ? resourceId(
                  'Microsoft.Network/publicIPAddresses',
                  ipConfiguration.?pipConfiguration.?name ?? '${virtualMachineName}${ipConfiguration.?pipConfiguration.?publicIpNameSuffix}'
                )
              : ipConfiguration.?pipConfiguration.publicIPAddressResourceId
          : null
        subnetResourceId: ipConfiguration.subnetResourceId
        loadBalancerBackendAddressPools: ipConfiguration.?loadBalancerBackendAddressPools
        applicationSecurityGroups: ipConfiguration.?applicationSecurityGroups
        applicationGatewayBackendAddressPools: ipConfiguration.?applicationGatewayBackendAddressPools
        gatewayLoadBalancer: ipConfiguration.?gatewayLoadBalancer
        loadBalancerInboundNatRules: ipConfiguration.?loadBalancerInboundNatRules
        privateIPAddressVersion: ipConfiguration.?privateIPAddressVersion
        virtualNetworkTaps: ipConfiguration.?virtualNetworkTaps
      }
    ]
    location: location
    tags: tags
    diagnosticSettings: diagnosticSettings
    dnsServers: dnsServers
    enableAcceleratedNetworking: enableAcceleratedNetworking
    enableTelemetry: enableTelemetry
    enableIPForwarding: enableIPForwarding
    lock: lock
    networkSecurityGroupResourceId: !empty(networkSecurityGroupResourceId) ? networkSecurityGroupResourceId : ''
    roleAssignments: roleAssignments
  }
  dependsOn: [
    networkInterface_publicIPAddresses
  ]
}

@description('The name of the network interface.')
output name string = networkInterface.outputs.name

@description('The list of IP configurations of the network interface.')
output ipConfigurations networkInterfaceIPConfigurationOutputType[] = networkInterface.outputs.ipConfigurations

// =============== //
//   Definitions   //
// =============== //

import { dnsSettingsType, ddosSettingsType } from 'br/public:avm/res/network/public-ip-address:0.8.0'

@export()
@description('The type for the public IP address configuration.')
type publicIPConfigurationType = {
  @description('Optional. The name of the Public IP Address.')
  name: string?

  @description('Optional. The resource ID of the public IP address.')
  publicIPAddressResourceId: string?

  @description('Optional. Diagnostic settings for the public IP address.')
  diagnosticSettings: diagnosticSettingFullType[]?

  @description('Optional. The idle timeout in minutes.')
  location: string?

  @description('Optional. The lock settings of the public IP address.')
  lock: lockType?

  @description('Optional. The idle timeout of the public IP address.')
  idleTimeoutInMinutes: int?

  @description('Optional. The DDoS protection plan configuration associated with the public IP address.')
  ddosSettings: ddosSettingsType?

  @description('Optional. The DNS settings of the public IP address.')
  dnsSettings: dnsSettingsType?

  @description('Optional. The public IP address version.')
  publicIPAddressVersion: ('IPv4' | 'IPv6')?

  @description('Optional. The public IP address allocation method.')
  publicIPAllocationMethod: ('Static' | 'Dynamic')?

  @description('Optional. Resource ID of the Public IP Prefix object. This is only needed if you want your Public IPs created in a PIP Prefix.')
  publicIpPrefixResourceId: string?

  @description('Optional. The name suffix of the public IP address resource.')
  publicIpNameSuffix: string?

  @description('Optional. Array of role assignments to create.')
  roleAssignments: roleAssignmentType[]?

  @description('Optional. The SKU name of the public IP address.')
  skuName: ('Basic' | 'Standard')?

  @description('Optional. The SKU tier of the public IP address.')
  skuTier: ('Regional' | 'Global')?

  @description('Optional. The tags of the public IP address.')
  tags: object?

  @description('Optional. The zones of the public IP address.')
  zones: (1 | 2 | 3)[]?

  @description('Optional. Enable/Disable usage telemetry for the module.')
  enableTelemetry: bool?
}

import {
  backendAddressPoolType
  inboundNatRuleType
  applicationSecurityGroupType
  applicationGatewayBackendAddressPoolsType
  subResourceType
  virtualNetworkTapType
  networkInterfaceIPConfigurationOutputType
} from 'br/public:avm/res/network/network-interface:0.5.1'

@export()
@description('The type for the IP configuration.')
type ipConfigurationType = {
  @description('Optional. The name of the IP configuration.')
  name: string?

  @description('Optional. The private IP address allocation method.')
  privateIPAllocationMethod: ('Static' | 'Dynamic')?

  @description('Optional. The private IP address.')
  privateIPAddress: string?

  @description('Required. The resource ID of the subnet.')
  subnetResourceId: string

  @description('Optional. The load balancer backend address pools.')
  loadBalancerBackendAddressPools: backendAddressPoolType[]?

  @description('Optional. The application security groups.')
  applicationSecurityGroups: applicationSecurityGroupType[]?

  @description('Optional. The application gateway backend address pools.')
  applicationGatewayBackendAddressPools: applicationGatewayBackendAddressPoolsType[]?

  @description('Optional. The gateway load balancer settings.')
  gatewayLoadBalancer: subResourceType?

  @description('Optional. The load balancer inbound NAT rules.')
  loadBalancerInboundNatRules: inboundNatRuleType[]?

  @description('Optional. The private IP address version.')
  privateIPAddressVersion: ('IPv4' | 'IPv6')?

  @description('Optional. The virtual network taps.')
  virtualNetworkTaps: virtualNetworkTapType[]?

  @description('Optional. The public IP address configuration.')
  pipConfiguration: publicIPConfigurationType?

  @description('Optional. The diagnostic settings of the IP configuration.')
  diagnosticSettings: diagnosticSettingFullType[]?

  @description('Optional. The tags of the public IP address.')
  tags: object?

  @description('Optional. Enable/Disable usage telemetry for the module.')
  enableTelemetry: bool?
}
