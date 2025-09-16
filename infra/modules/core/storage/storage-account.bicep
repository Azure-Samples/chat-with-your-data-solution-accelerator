@description('Required. Name of the storage account (lowercase).')
param storageAccountName string
@description('Optional. Location for the storage account. Defaults to the resource group location.')
param location string = resourceGroup().location
@description('Optional. Tags to apply to the storage account.')
param tags object = {}
@allowed(['Cool', 'Hot', 'Premium', 'Cold'])
@description('Optional. Specifies the access tier for BlobStorage, valid values: Cool, Hot, Premium, Cold.')
param accessTier string = 'Hot'
@description('Optional. Minimum permitted TLS version for requests to the storage account.')
param minimumTlsVersion string = 'TLS1_2'
@description('Optional. Enforces HTTPS only traffic when set to true.')
param supportsHttpsTrafficOnly bool = true
@description('Optional. Storage account SKU (limited to values supported by AVM module version 0.21.0).')
@allowed([
  'Standard_LRS'
  'Standard_GRS'
  'Standard_RAGRS'
  'Standard_ZRS'
  'Standard_GZRS'
  'Standard_RAGZRS'
  'Premium_LRS'
  'Premium_ZRS'
])
param skuName string = 'Standard_GRS'
@description('Optional. Array of blob containers to create. Each item: { name: string, publicAccess?: string }')
param containers array = []
@description('Optional. Array of storage queues to create. Each item: { name: string }')
param queues array = []
@description('Optional. Role assignments for the storage account (array of objects with principalId, roleDefinitionIdOrName, principalType).')
param roleAssignments array = []
@description('Optional. Array of user assigned identity resource IDs.')
param userAssignedIdentityResourceIds array = []
@description('Required. Array of private DNS zone resource IDs used to associate private endpoints.')
param privateDnsZoneResourceIds array = []
// @description('Required. Array of AVM private DNS zone module outputs used to associate private endpoints.')
// param avmPrivateDnsZones array
// @description('Required. Object containing keys used to index into avmPrivateDnsZones outputs (e.g. storageBlob, storageQueue).')
// param dnsZoneIndex object
@description('Optional. If true, disables public network access and provisions private endpoints for blob and queue services.')
param enablePrivateNetworking bool = false
@description('Optional. Controls whether AVM telemetry is enabled for this deployment.')
param enableTelemetry bool = true
@description('Optional. A friendly string representing the application/solution name to give to all resource names in this deployment. This should be 3-16 characters long.')
param solutionPrefix string = ''
@description('Required. Subnet resource ID for private endpoints. This is a string, not an object.')
param subnetResourceId string = ''
// @description('Required. Output object from the AVM virtual network deployment containing subnet resource IDs used for private endpoints.')
// param avmVirtualNetwork object

var containerItems = [
  for c in containers: {
    name: c.name
    publicAccess: c.publicAccess ?? 'None'
  }
]

var queueItems = [
  for q in queues: {
    name: q.name
  }
]

var kind = 'StorageV2'

module avmStorage '../../storage/storage-account/main.bicep' = {
  name: take('avm.res.storage.storage-account.${storageAccountName}', 64)
  params: {
    name: storageAccountName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    minimumTlsVersion: minimumTlsVersion
    supportsHttpsTrafficOnly: supportsHttpsTrafficOnly
    accessTier: accessTier
    skuName: skuName
    kind: kind
    blobServices: empty(containers) ? null : { containers: containerItems }
    queueServices: empty(queues) ? null : { queues: queueItems }
    // Use only user-assigned identities
    managedIdentities: { systemAssigned: false, userAssignedResourceIds: userAssignedIdentityResourceIds }
    roleAssignments: roleAssignments
    allowBlobPublicAccess: enablePrivateNetworking ? true : false
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    networkAcls: { bypass: 'AzureServices', defaultAction: enablePrivateNetworking ? 'Deny' : 'Allow' }
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-blob-${solutionPrefix}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'storage-dns-zone-group-blob'
                  privateDnsZoneResourceId: privateDnsZoneResourceIds[0]
                  // privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageBlob].outputs.resourceId.value
                }
              ]
            }
            subnetResourceId: subnetResourceId
            // subnetResourceId: avmVirtualNetwork.outputs.subnetPrivateEndpointsResourceId.value
            service: 'blob'
          }
          {
            name: 'pep-queue-${solutionPrefix}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'storage-dns-zone-group-queue'
                  privateDnsZoneResourceId: privateDnsZoneResourceIds[1]
                  // privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageQueue].outputs.resourceId.value
                }
              ]
            }
            subnetResourceId: subnetResourceId
            // subnetResourceId: avmVirtualNetwork.outputs.subnetPrivateEndpointsResourceId.value
            service: 'queue'
          }
        ]
      : []
  }
}

output name string = avmStorage.outputs.name
output id string = avmStorage.outputs.resourceId
output primaryEndpoints object = avmStorage.outputs.serviceEndpoints
