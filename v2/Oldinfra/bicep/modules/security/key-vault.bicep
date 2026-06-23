// ============================================================================
// Module: Azure Key Vault
// Description: Vanilla Bicep module for Azure Key Vault
// Resource: Microsoft.KeyVault/vaults@2023-07-01
// Docs: https://learn.microsoft.com/azure/templates/microsoft.keyvault/vaults
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

@description('The Microsoft Entra tenant ID for the Key Vault.')
param tenantId string = subscription().tenantId

@description('The Managed Identiry ID.')
param managedIdentityObjectId string = ''

@description('The Principal ID.')
param principalId string = ''

@description('Secrets to store in the vault (name/value pairs).')
param secrets array = []

// ============================================================================
// Key Vault Resource
// ============================================================================

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    tenantId: tenantId
    sku: {
      family: 'A'
      name: sku
    }
    accessPolicies: concat(
      managedIdentityObjectId != '' ? [
        {
          objectId: managedIdentityObjectId
          permissions: {
            keys: [
              'get'
              'list'
            ]
            secrets: [
              'get'
              'list'
            ]
          }
          tenantId: subscription().tenantId
        }
      ] : [],
      principalId != '' ? [
        {
          objectId: principalId
          permissions: {
            keys: [
              'get'
              'list'
            ]
            secrets: [
              'get'
              'list'
            ]
          }
          tenantId: subscription().tenantId
        }
      ] : []
    )
    enableRbacAuthorization: enableRbacAuthorization
    enableSoftDelete: enableSoftDelete
    softDeleteRetentionInDays: softDeleteRetentionInDays
    enablePurgeProtection: enablePurgeProtection
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
  }
}

resource keyVaultSecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = [
  for secret in secrets: {
     name: secret.name
     parent: keyVault
     tags: tags
     properties: {
       value: secret.value
     }
  }
]

// ============================================================================
// Outputs
// ============================================================================

@description('The name of the Key Vault.')
output name string = keyVault.name

@description('The URI of the Key Vault.')
output uri string = keyVault.properties.vaultUri

@description('The resource ID of the Key Vault.')
output resourceId string = keyVault.id
