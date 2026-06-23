// ============================================================================
// Module: Storage Account
// Description: AVM wrapper for Azure Storage Account with WAF alignment
// AVM Module: avm/res/storage/storage-account:0.32.0
// WAF: https://learn.microsoft.com/azure/well-architected/service-guides/storage-accounts
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

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Blob containers to create.')
param containers array = [
  {
    name: 'default'
    publicAccess: 'None'
  }
]

@description('Optional. Storage queue service settings to create queues or diagnostics.')
param queueServices object = {}

// --- WAF: Monitoring ---
@description('Diagnostic settings for monitoring.')
param diagnosticSettings array = []

// --- WAF: Private Networking ---
@description('Public network access setting.')
param publicNetworkAccess string = 'Enabled'

@description('Network ACLs for the storage account.')
param networkAcls object = {
  defaultAction: 'Allow'
  bypass: 'AzureServices'
}

@description('Whether to enable private networking.')
param enablePrivateNetworking bool = false

@description('Subnet resource ID for the private endpoint.')
param privateEndpointSubnetId string = ''

@description('Private DNS zone resource IDs for Storage (blob).')
param privateDnsZoneResourceIds array = []

@description('Per-service private endpoint definitions. Each item: { service: blob|queue|file|table|web|dfs, privateDnsZoneResourceId: <id> }. Required when enablePrivateNetworking=true and the function app uses AzureWebJobsStorage with managed identity — the host needs blob, queue and table reachable, and the consumption/elastic SKUs additionally need file.')
param privateEndpointServices array = []

var privateDnsZoneConfigs = [for (zoneId, i) in privateDnsZoneResourceIds: {
  name: 'dns-zone-${i}'
  privateDnsZoneResourceId: zoneId
}]

// Resolve PEs from the new per-service list (one PE per service, each with its matching DNS zone).
var multiServicePrivateEndpoints = [for s in privateEndpointServices: {
  name: 'pep-${name}-${s.service}'
  customNetworkInterfaceName: 'nic-${name}-${s.service}'
  subnetResourceId: privateEndpointSubnetId
  service: s.service
  privateDnsZoneGroup: {
    privateDnsZoneGroupConfigs: [
      {
        name: '${s.service}-dns'
        privateDnsZoneResourceId: s.privateDnsZoneResourceId
      }
    ]
  }
}]

// Legacy single-blob fallback for callers that haven't migrated to privateEndpointServices.
var legacyBlobPrivateEndpoints = [
  {
    name: 'pep-${name}'
    customNetworkInterfaceName: 'nic-${name}'
    subnetResourceId: privateEndpointSubnetId
    service: 'blob'
    privateDnsZoneGroup: {
      privateDnsZoneGroupConfigs: privateDnsZoneConfigs
    }
  }
]

var resolvedPrivateEndpoints = !empty(privateEndpointServices) ? multiServicePrivateEndpoints : legacyBlobPrivateEndpoints

// --- Role Assignments ---
@description('Optional. Array of role assignments to create on the Storage Account.')
param roleAssignments array = []

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

// ============================================================================
// AVM Module Deployment
// ============================================================================
module storage 'br/public:avm/res/storage/storage-account:0.32.0' = {
  name: take('avm.res.storage.storage-account.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    skuName: skuName
    kind: kind
    accessTier: accessTier
    allowBlobPublicAccess: allowBlobPublicAccess
    allowSharedKeyAccess: allowSharedKeyAccess
    enableHierarchicalNamespace: enableHierarchicalNamespace
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    requireInfrastructureEncryption: true
    publicNetworkAccess: publicNetworkAccess
    networkAcls: networkAcls
    managedIdentities: managedIdentities
    blobServices: {
      containers: [for container in containers: {
        name: container.name
        publicAccess: container.publicAccess
      }]
      diagnosticSettings: !empty(diagnosticSettings) ? diagnosticSettings : []
    }
    queueServices: queueServices
    diagnosticSettings: !empty(diagnosticSettings) ? diagnosticSettings : []
    privateEndpoints: enablePrivateNetworking ? resolvedPrivateEndpoints : []
    roleAssignments: !empty(roleAssignments) ? roleAssignments : []
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the Storage Account.')
output resourceId string = storage.outputs.resourceId

@description('Name of the Storage Account.')
output name string = storage.outputs.name

@description('Primary blob endpoint.')
output blobEndpoint string = storage.outputs.primaryBlobEndpoint

@description('Service endpoints.')
output serviceEndpoints object = storage.outputs.serviceEndpoints
