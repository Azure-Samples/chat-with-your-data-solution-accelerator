metadata name = 'Network Security Groups'
metadata description = 'This module deploys a Network security Group (NSG).'

@description('Required. Name of the Network Security Group.')
param name string

@description('Optional. Location for all resources.')
param location string = resourceGroup().location

@description('Optional. Array of Security Rules to deploy to the Network Security Group. When not provided, an NSG including only the built-in roles will be deployed.')
param securityRules securityRuleType[]?

@description('Optional. When enabled, flows created from Network Security Group connections will be re-evaluated when rules are updates. Initial enablement will trigger re-evaluation. Network Security Group connection flushing is not available in all regions.')
param flushConnection bool = false

@description('Optional. Tags of the NSG resource.')
param tags object?

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

#disable-next-line no-deployments-resources
resource avmTelemetry 'Microsoft.Resources/deployments@2024-03-01' = if (enableTelemetry) {
  name: '46d3xbcp.res.network-networksecuritygroup.${replace('-..--..-', '.', '-')}.${substring(uniqueString(deployment().name, location), 0, 4)}'
  properties: {
    mode: 'Incremental'
    template: {
      '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#'
      contentVersion: '1.0.0.0'
      resources: []
      outputs: {
        telemetry: {
          type: 'String'
          value: 'For more information, see https://aka.ms/avm/TelemetryInfo'
        }
      }
    }
  }
}

resource networkSecurityGroup 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    flushConnection: flushConnection
    securityRules: [
      for securityRule in securityRules ?? []: {
        name: securityRule.name
        properties: {
          access: securityRule.properties.access
          description: securityRule.properties.?description ?? ''
          destinationAddressPrefix: securityRule.properties.?destinationAddressPrefix ?? ''
          destinationAddressPrefixes: securityRule.properties.?destinationAddressPrefixes ?? []
          destinationApplicationSecurityGroups: map(
            securityRule.properties.?destinationApplicationSecurityGroupResourceIds ?? [],
            (destinationApplicationSecurityGroupResourceId) => {
              id: destinationApplicationSecurityGroupResourceId
            }
          )
          destinationPortRange: securityRule.properties.?destinationPortRange ?? ''
          destinationPortRanges: securityRule.properties.?destinationPortRanges ?? []
          direction: securityRule.properties.direction
          priority: securityRule.properties.priority
          protocol: securityRule.properties.protocol
          sourceAddressPrefix: securityRule.properties.?sourceAddressPrefix ?? ''
          sourceAddressPrefixes: securityRule.properties.?sourceAddressPrefixes ?? []
          sourceApplicationSecurityGroups: map(
            securityRule.properties.?sourceApplicationSecurityGroupResourceIds ?? [],
            (sourceApplicationSecurityGroupResourceId) => {
              id: sourceApplicationSecurityGroupResourceId
            }
          )
          sourcePortRange: securityRule.properties.?sourcePortRange ?? ''
          sourcePortRanges: securityRule.properties.?sourcePortRanges ?? []
        }
      }
    ]
  }
}

@description('The resource group the network security group was deployed into.')
output resourceGroupName string = resourceGroup().name

@description('The resource ID of the network security group.')
output resourceId string = networkSecurityGroup.id

@description('The name of the network security group.')
output name string = networkSecurityGroup.name

@description('The location the resource was deployed into.')
output location string = networkSecurityGroup.location

// =============== //
//   Definitions   //
// =============== //

@export()
@description('The type of a security rule.')
type securityRuleType = {
  @description('Required. The name of the security rule.')
  name: string

  @description('Required. The properties of the security rule.')
  properties: {
    @description('Required. Whether network traffic is allowed or denied.')
    access: ('Allow' | 'Deny')

    @description('Optional. The description of the security rule.')
    description: string?

    @description('Optional. Optional. The destination address prefix. CIDR or destination IP range. Asterisk "*" can also be used to match all source IPs. Default tags such as "VirtualNetwork", "AzureLoadBalancer" and "Internet" can also be used.')
    destinationAddressPrefix: string?

    @description('Optional. The destination address prefixes. CIDR or destination IP ranges.')
    destinationAddressPrefixes: string[]?

    @description('Optional. The resource IDs of the application security groups specified as destination.')
    destinationApplicationSecurityGroupResourceIds: string[]?

    @description('Optional. The destination port or range. Integer or range between 0 and 65535. Asterisk "*" can also be used to match all ports.')
    destinationPortRange: string?

    @description('Optional. The destination port ranges.')
    destinationPortRanges: string[]?

    @description('Required. The direction of the rule. The direction specifies if rule will be evaluated on incoming or outgoing traffic.')
    direction: ('Inbound' | 'Outbound')

    @minValue(100)
    @maxValue(4096)
    @description('Required. Required. The priority of the rule. The value can be between 100 and 4096. The priority number must be unique for each rule in the collection. The lower the priority number, the higher the priority of the rule.')
    priority: int

    @description('Required. Network protocol this rule applies to.')
    protocol: ('Ah' | 'Esp' | 'Icmp' | 'Tcp' | 'Udp' | '*')

    @description('Optional. The CIDR or source IP range. Asterisk "*" can also be used to match all source IPs. Default tags such as "VirtualNetwork", "AzureLoadBalancer" and "Internet" can also be used. If this is an ingress rule, specifies where network traffic originates from.')
    sourceAddressPrefix: string?

    @description('Optional. The CIDR or source IP ranges.')
    sourceAddressPrefixes: string[]?

    @description('Optional. The resource IDs of the application security groups specified as source.')
    sourceApplicationSecurityGroupResourceIds: string[]?

    @description('Optional. The source port or range. Integer or range between 0 and 65535. Asterisk "*" can also be used to match all ports.')
    sourcePortRange: string?

    @description('Optional. The source port ranges.')
    sourcePortRanges: string[]?
  }
}
