// ============================================================================
// Module: Azure Key Vault (AVM)
// AVM Module: avm/res/key-vault/vault:0.12.1
// ============================================================================

@description('Solution name used for naming convention.')
param solutionName string

@description('Optional. Override name for the Key Vault. Defaults to kv-{solutionName}.')
param name string = take('kv-${solutionName}', 24)

@description('Azure region for deployment.')
param location string

@description('Resource tags.')
param tags object = {}

@description('SKU for the key vault.')
@allowed(['standard', 'premium'])
param sku string = 'standard'

@description('Enable RBAC authorization.')
param enableRbacAuthorization bool = true

@description('Enable soft delete.')
param enableSoftDelete bool = true

@description('Soft delete retention in days.')
param softDeleteRetentionInDays int = 90

@description('Enable purge protection.')
param enablePurgeProtection bool = true

@description('Public network access setting.')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Enabled'

@description('Secrets to store in the vault (name/value pairs).')
param secrets array = []

@description('Enable Azure telemetry collection.')
param enableTelemetry bool = true

@description('Role assignments.')
param roleAssignments array = []

@description('Enable private networking.')
param enablePrivateNetworking bool = false

@description('Subnet resource ID for private endpoint.')
param privateEndpointSubnetId string = ''

@description('Private DNS zone resource IDs.')
param privateDnsZoneResourceIds array = []

// ============================================================================
// Key Vault (AVM)
// ============================================================================

var secretItems = [for secret in secrets: {
  name: secret.name
  value: secret.value
}]

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

module keyVault 'br/public:avm/res/key-vault/vault:0.12.1' = {
  name: take('avm.res.keyvault.vault.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    sku: sku
    enableRbacAuthorization: enableRbacAuthorization
    enableSoftDelete: enableSoftDelete
    softDeleteRetentionInDays: softDeleteRetentionInDays
    enablePurgeProtection: enablePurgeProtection
    publicNetworkAccess: publicNetworkAccess
    roleAssignments: !empty(roleAssignments) ? roleAssignments : []
    secrets: !empty(secrets) ? secretItems : []
    privateEndpoints: privateEndpointConfig
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('The name of the key vault.')
output name string = keyVault.outputs.name

@description('The URI of the key vault.')
output uri string = keyVault.outputs.uri

@description('The resource ID of the key vault.')
output resourceId string = keyVault.outputs.resourceId
