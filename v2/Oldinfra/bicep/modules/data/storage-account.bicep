// ============================================================================
// Module: Storage Account
// Description: Creates an Azure Storage Account with blob container
// API: Microsoft.Storage/storageAccounts@2025-08-01
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the storage account.')
param name string = take('st${toLower(replace(solutionName, '-', ''))}', 24)

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Storage account SKU.')
param skuName string = 'Standard_LRS'

@description('Storage account kind.')
param kind string = 'StorageV2'

@description('Access tier.')
@allowed(['Hot', 'Cool'])
param accessTier string = 'Hot'

@description('Allow blob public access.')
param allowBlobPublicAccess bool = false

@description('Allow shared key access.')
param allowSharedKeyAccess bool = false

@description('Blob containers to create.')
param containers array = [
  {
    name: 'default'
    publicAccess: 'None'
  }
]

@description('Optional. Storage queue service settings to create queues or diagnostics.')
param queues array = []

@description('Optional. Delete retention policy for blob service.')
param deleteRetentionPolicy object = {}

@description('Network ACLs for the storage account.')
param networkAcls object = {
  defaultAction: 'Allow'
  bypass: 'AzureServices'
}

// ============================================================================
// Resource Deployment
// ============================================================================
resource storageAccount 'Microsoft.Storage/storageAccounts@2025-08-01' = {
  name: name
  location: location
  tags: tags
  kind: kind
  sku: {
    name: skuName
  }
  properties: {
    accessTier: accessTier
    allowBlobPublicAccess: allowBlobPublicAccess
    allowSharedKeyAccess: allowSharedKeyAccess
    defaultToOAuthAuthentication: false
    dnsEndpointType: 'standard'
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    networkAcls: networkAcls
    encryption: {
      services: {
        blob: {
          enabled: true
        }
        file: {
          enabled: true
        }
      }
      keySource: 'Microsoft.Storage'
      requireInfrastructureEncryption: true
    }
  }

  resource blobServices 'blobServices' = if (!empty(containers)) {
    name: 'default'
    properties: {
      deleteRetentionPolicy: deleteRetentionPolicy
    }
    resource container 'containers' = [
      for container in containers: {
        name: container.name
        properties: {
          publicAccess: contains(container, 'publicAccess') ? container.publicAccess : 'None'
        }
      }
    ]
  }

  resource queueServices 'queueServices' = if (!empty(queues)) {
    name: 'default'
    properties: {
      cors: {
        corsRules: []
      }
    }
    resource queue 'queues' = [
      for queue in queues: {
        name: queue.name
        properties: {
          metadata: {}
        }
      }
    ]
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the Storage Account.')
output resourceId string = storageAccount.id

@description('Name of the Storage Account.')
output name string = storageAccount.name

@description('Primary blob endpoint.')
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob

@description('All service endpoints.')
output serviceEndpoints object = storageAccount.properties.primaryEndpoints
