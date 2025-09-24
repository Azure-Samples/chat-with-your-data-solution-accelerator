metadata name = 'Storage Account Blob Containers'
metadata description = 'This module deploys a Storage Account Blob Container.'

@maxLength(24)
@description('Conditional. The name of the parent Storage Account. Required if the template is used in a standalone deployment.')
param storageAccountName string

@description('Optional. The name of the parent Blob Service. Required if the template is used in a standalone deployment.')
param blobServiceName string = 'default'

@description('Required. The name of the Storage Container to deploy.')
param name string

@description('Optional. Default the container to use specified encryption scope for all writes.')
param defaultEncryptionScope string?

@description('Optional. Block override of encryption scope from the container default.')
param denyEncryptionScopeOverride bool?

@description('Optional. Enable NFSv3 all squash on blob container.')
param enableNfsV3AllSquash bool = false

@description('Optional. Enable NFSv3 root squash on blob container.')
param enableNfsV3RootSquash bool = false

@description('Optional. This is an immutable property, when set to true it enables object level immutability at the container level. The property is immutable and can only be set to true at the container creation time. Existing containers must undergo a migration process.')
param immutableStorageWithVersioningEnabled bool = false

@description('Optional. A name-value pair to associate with the container as metadata.')
param metadata resourceInput<'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01'>.properties.metadata = {}

@allowed([
  'Container'
  'Blob'
  'None'
])
@description('Optional. Specifies whether data in the container may be accessed publicly and the level of access.')
param publicAccess string = 'None'

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

#disable-next-line no-deployments-resources
resource avmTelemetry 'Microsoft.Resources/deployments@2024-03-01' = if (enableTelemetry) {
  name: '46d3xbcp.res.storage-blobcontainer.${replace('-..--..-', '.', '-')}.${substring(uniqueString(deployment().name), 0, 4)}'
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

resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' existing = {
  name: storageAccountName

  resource blobServices 'blobServices@2024-01-01' existing = {
    name: blobServiceName
  }
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  name: name
  parent: storageAccount::blobServices
  properties: {
    defaultEncryptionScope: defaultEncryptionScope
    denyEncryptionScopeOverride: denyEncryptionScopeOverride
    enableNfsV3AllSquash: enableNfsV3AllSquash == true ? enableNfsV3AllSquash : null
    enableNfsV3RootSquash: enableNfsV3RootSquash == true ? enableNfsV3RootSquash : null
    immutableStorageWithVersioning: immutableStorageWithVersioningEnabled == true
      ? {
          enabled: immutableStorageWithVersioningEnabled
        }
      : null
    metadata: metadata
    publicAccess: publicAccess
  }
}

@description('The name of the deployed container.')
output name string = container.name

@description('The resource ID of the deployed container.')
output resourceId string = container.id

@description('The resource group of the deployed container.')
output resourceGroupName string = resourceGroup().name
