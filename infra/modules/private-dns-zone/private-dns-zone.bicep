metadata name = 'Private DNS Zones'
metadata description = 'This module deploys a Private DNS zone.'

@description('Required. Private DNS zone name.')
param name string

// @description('Optional. Array of A records.')
// param a aType[]?

// @description('Optional. Array of AAAA records.')
// param aaaa aaaaType[]?

// @description('Optional. Array of CNAME records.')
// param cname cnameType[]?

// @description('Optional. Array of MX records.')
// param mx mxType[]?

// @description('Optional. Array of PTR records.')
// param ptr ptrType[]?

// @description('Optional. Array of SOA records.')
// param soa soaType[]?

// @description('Optional. Array of SRV records.')
// param srv srvType[]?

// @description('Optional. Array of TXT records.')
// param txt txtType[]?

@description('Optional. Array of custom objects describing vNet links of the DNS zone. Each object should contain properties \'virtualNetworkResourceId\' and \'registrationEnabled\'. The \'vnetResourceId\' is a resource ID of a vNet to link, \'registrationEnabled\' (bool) enables automatic DNS registration in the zone for the linked vNet.')
param virtualNetworkLinks virtualNetworkLinkType[]?

@description('Optional. The location of the PrivateDNSZone. Should be global.')
param location string = 'global'

// import { roleAssignmentType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
// @sys.description('Optional. Array of role assignments to create.')
// param roleAssignments roleAssignmentType[]?

@description('Optional. Tags of the resource.')
param tags object?

import { lockType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@sys.description('Optional. The lock settings of the service.')
param lock lockType?

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// var builtInRoleNames = {
//   Contributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
//   'Network Contributor': subscriptionResourceId(
//     'Microsoft.Authorization/roleDefinitions',
//     '4d97b98b-1d4f-4787-a291-c67834d212e7'
//   )
//   Owner: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8e3af657-a8ff-443c-a75c-2fe8c4bcb635')
//   'Private DNS Zone Contributor': subscriptionResourceId(
//     'Microsoft.Authorization/roleDefinitions',
//     'b12aa53e-6015-4669-85d0-8515ebb3ae7f'
//   )
//   Reader: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'acdd72a7-3385-48ef-bd42-f606fba81ae7')
//   'Role Based Access Control Administrator': subscriptionResourceId(
//     'Microsoft.Authorization/roleDefinitions',
//     'f58310d9-a9f6-439a-9e8d-f62e7b41a168'
//   )
// }

// var formattedRoleAssignments = [
//   for (roleAssignment, index) in (roleAssignments ?? []): union(roleAssignment, {
//     roleDefinitionId: builtInRoleNames[?roleAssignment.roleDefinitionIdOrName] ?? (contains(
//         roleAssignment.roleDefinitionIdOrName,
//         '/providers/Microsoft.Authorization/roleDefinitions/'
//       )
//       ? roleAssignment.roleDefinitionIdOrName
//       : subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAssignment.roleDefinitionIdOrName))
//   })
// ]

#disable-next-line no-deployments-resources
resource avmTelemetry 'Microsoft.Resources/deployments@2024-03-01' = if (enableTelemetry) {
  name: '46d3xbcp.res.network-privatednszone.${replace('-..--..-', '.', '-')}.${substring(uniqueString(deployment().name, location), 0, 4)}'
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

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: name
  location: location
  tags: tags
}

module privateDnsZone_virtualNetworkLinks 'virtual-network-link/virtual-network-link.bicep' = [
  for (virtualNetworkLink, index) in (virtualNetworkLinks ?? []): {
    name: '${uniqueString(deployment().name, location)}-PrivateDnsZone-VNetLink-${index}'
    params: {
      privateDnsZoneName: privateDnsZone.name
      name: virtualNetworkLink.?name ?? '${last(split(virtualNetworkLink.virtualNetworkResourceId, '/'))}-vnetlink'
      virtualNetworkResourceId: virtualNetworkLink.virtualNetworkResourceId
      location: virtualNetworkLink.?location ?? 'global'
      registrationEnabled: virtualNetworkLink.?registrationEnabled ?? false
      tags: virtualNetworkLink.?tags ?? tags
      resolutionPolicy: virtualNetworkLink.?resolutionPolicy
    }
  }
]

resource privateDnsZone_lock 'Microsoft.Authorization/locks@2020-05-01' = if (!empty(lock ?? {}) && lock.?kind != 'None') {
  name: lock.?name ?? 'lock-${name}'
  properties: {
    level: lock.?kind ?? ''
    notes: lock.?notes ?? (lock.?kind == 'CanNotDelete'
      ? 'Cannot delete resource or child resources.'
      : 'Cannot delete or modify the resource or child resources.')
  }
  scope: privateDnsZone
}

@description('The resource ID of the private DNS zone.')
output resourceId string = privateDnsZone.id

// ================ //
// Definitions      //
// ================ //

@export()
@description('The type for the virtual network link.')
type virtualNetworkLinkType = {
  @description('Optional. The resource name.')
  @minLength(1)
  @maxLength(80)
  name: string?

  @description('Required. The resource ID of the virtual network to link.')
  virtualNetworkResourceId: string

  @description('Optional. The Azure Region where the resource lives.')
  location: string?

  @description('Optional. Is auto-registration of virtual machine records in the virtual network in the Private DNS zone enabled?.')
  registrationEnabled: bool?

  @description('Optional. Resource tags.')
  tags: resourceInput<'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01'>.tags?

  @description('Optional. The resolution type of the private-dns-zone fallback machanism.')
  resolutionPolicy: ('Default' | 'NxDomainRedirect')?
}
