param storageAccountName string
param location string = resourceGroup().location
param tags object = {}
param accessTier string = 'Hot'
param enablePrivateNetworking bool = false
param enableTelemetry bool = true
param solutionPrefix string = ''
param avmManagedIdentity object
param avmPrivateDnsZones array
param dnsZoneIndex object
param avmVirtualNetwork object

module avmStorageAccount 'br/public:avm/res/storage/storage-account:0.20.0' = {
  name: take('avm.res.storage.storage-account.${storageAccountName}', 64)
  params: {
    name: storageAccountName
    location: location
    managedIdentities: { systemAssigned: true }
    minimumTlsVersion: 'TLS1_2'
    enableTelemetry: enableTelemetry
    tags: tags
    accessTier: accessTier
    supportsHttpsTrafficOnly: true

    roleAssignments: [
      {
        principalId: avmManagedIdentity.outputs.principalId
        roleDefinitionIdOrName: 'Storage Blob Data Contributor'
        principalType: 'ServicePrincipal'
      }
    ]

    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: enablePrivateNetworking ? 'Deny' : 'Allow'
    }
    allowBlobPublicAccess: enablePrivateNetworking ? true : false
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'

    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-blob-${solutionPrefix}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'storage-dns-zone-group-blob'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageBlob].outputs.resourceId
                }
              ]
            }
            subnetResourceId: avmVirtualNetwork.outputs.subnetResourceIds[0]
            service: 'blob'
          }
          {
            name: 'pep-queue-${solutionPrefix}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'storage-dns-zone-group-queue'
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.storageQueue].outputs.resourceId
                }
              ]
            }
            subnetResourceId: avmVirtualNetwork.outputs.subnetResourceIds[0]
            service: 'queue'
          }
        ]
      : []
  }
}

output name string = avmStorageAccount.outputs.name
output id string = avmStorageAccount.outputs.resourceId
output primaryEndpoints object = avmStorageAccount.outputs.serviceEndpoints
