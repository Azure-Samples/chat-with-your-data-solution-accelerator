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
param allowSharedKeyAccess bool = true

@description('Enable hierarchical namespace (Data Lake Storage Gen2).')
param enableHierarchicalNamespace bool = false

@description('Blob containers to create.')
param containers array = [
  {
    name: 'default'
    publicAccess: 'None'
  }
]

@description('Storage queues to create (names). Empty = no queue service.')
param queues array = []

@description('Optional. Managed identity configuration for the resource.')
param identity object = { type: 'SystemAssigned' }

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
  identity: identity
  properties: {
    accessTier: accessTier
    allowBlobPublicAccess: allowBlobPublicAccess
    allowSharedKeyAccess: allowSharedKeyAccess
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    isHnsEnabled: enableHierarchicalNamespace
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
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-08-01' = {
  parent: storageAccount
  name: 'default'
}

resource blobContainers 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-08-01' = [for container in containers: {
  parent: blobService
  name: container.name
  properties: {
    publicAccess: container.publicAccess
  }
}]

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2025-08-01' = if (!empty(queues)) {
  parent: storageAccount
  name: 'default'
}

resource storageQueues 'Microsoft.Storage/storageAccounts/queueServices/queues@2025-08-01' = [for queueName in queues: {
  parent: queueService
  name: queueName
}]

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
