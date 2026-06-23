// ============================================================================
// Module: Azure App Configuration (AVM)
// ============================================================================

@description('Solution name used for naming convention.')
param solutionName string

@description('Name of the App Configuration store.')
param name string = 'appcs-${solutionName}'

@description('Azure region for deployment.')
param location string

@description('Resource tags.')
param tags object = {}

@description('Enable Azure telemetry collection.')
param enableTelemetry bool = true

@description('SKU for the configuration store.')
@allowed(['Free', 'Standard'])
param sku string = 'Standard'

@description('Disable local (key-based) authentication.')
param disableLocalAuth bool = true

@description('Enable purge protection.')
param enablePurgeProtection bool = false

@description('Soft delete retention in days.')
param softDeleteRetentionInDays int = 7

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

@description('Role assignments.')
param roleAssignments array = []

@description('Key-value pairs to store in the configuration.')
param keyValues array = []

@description('Optional. Public network access override. Set to Enabled to allow ARM keyValues writes during deploy.')
param publicNetworkAccess string = ''

@description('Enable private networking.')
param enablePrivateNetworking bool = false

@description('Subnet resource ID for private endpoint.')
param privateEndpointSubnetId string = ''

@description('Private DNS zone resource IDs.')
param privateDnsZoneResourceIds array = []

// ============================================================================
// App Configuration (AVM)
// ============================================================================

var dnsZoneConfigs = [for (zoneId, i) in privateDnsZoneResourceIds: {
  name: 'config${i}'
  privateDnsZoneResourceId: zoneId
}]

var privateEndpointConfig = enablePrivateNetworking && !empty(privateEndpointSubnetId) ? [
  {
    subnetResourceId: privateEndpointSubnetId
    privateDnsZoneGroup: !empty(privateDnsZoneResourceIds) ? {
      privateDnsZoneGroupConfigs: dnsZoneConfigs
    } : null
  }
] : []

module configStore 'br/public:avm/res/app-configuration/configuration-store:0.9.2' = {
  name: take('avm.res.appconfiguration.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    sku: sku
    disableLocalAuth: disableLocalAuth
    enablePurgeProtection: enablePurgeProtection
    softDeleteRetentionInDays: softDeleteRetentionInDays
    managedIdentities: managedIdentities
    roleAssignments: !empty(roleAssignments) ? roleAssignments : []
    keyValues: !empty(keyValues) ? keyValues : []
    publicNetworkAccess: !empty(publicNetworkAccess) ? publicNetworkAccess : null
    privateEndpoints: privateEndpointConfig
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('The name of the configuration store.')
output name string = configStore.outputs.name

@description('The endpoint of the configuration store.')
output endpoint string = configStore.outputs.endpoint

@description('The resource ID of the configuration store.')
output resourceId string = configStore.outputs.resourceId
