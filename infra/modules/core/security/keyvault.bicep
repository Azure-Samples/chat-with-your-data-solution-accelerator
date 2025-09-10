metadata description = 'Creates an Azure Key Vault.'

@description('Required. Name of the Key Vault to create.')
@minLength(3)
@maxLength(24)
param name string

@description('Optional. Azure location for the Key Vault. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('Optional. Tags to apply to the Key Vault and associated resources.')
param tags resourceInput<'Microsoft.Resources/resourceGroups@2025-04-01'>.tags = {}

@description('Optional. Object ID of a managed identity to be granted Key Vault Secrets User role.')
param managedIdentityObjectId string = ''

@description('Optional. Enable private networking (private endpoint + Private DNS zone). Defaults to false.')
param enablePrivateNetworking bool = false

@description('Optional. Enable usage telemetry for the module. Defaults to false.')
param enableTelemetry bool = false

@description('Optional. Enable monitoring (Diagnostic Settings) sending logs to the provided Log Analytics Workspace. Defaults to false.')
param enableMonitoring bool = false

@description('Optional. Enable purge protection for the Key Vault. Irreversible once enabled after retention period starts.')
param enablePurgeProtection bool = false

@description('Conditional. Resource ID of the Log Analytics Workspace. Required if enableMonitoring is true.')
param logAnalyticsWorkspaceResourceId string = ''

@description('Conditional. Resource ID of the subnet used for the private endpoint. Required if enablePrivateNetworking is true.')
param subnetResourceId string = 'null'

@description('Conditional. Module output contract supplying the Private DNS Zone. Required if enablePrivateNetworking is true.')
param avmPrivateDnsZone object = {}

@description('Optional. Object ID (principalId) of an additional principal to assign Key Vault Secrets User role.')
param principalId string = ''

@description('Optional. Array of secrets to create in the Key Vault. Avoid storing sensitive production secret values directly in source.')
param secrets array = []

module keyvault 'br/public:avm/res/key-vault/vault:0.12.1' = {
  name: take('avm.res.key-vault.vault.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    sku: 'standard'
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
    enablePurgeProtection: enablePurgeProtection
    enableVaultForDeployment: true
    enableVaultForDiskEncryption: true
    enableVaultForTemplateDeployment: true
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${name}'
            customNetworkInterfaceName: 'nic-${name}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                { privateDnsZoneResourceId: avmPrivateDnsZone!.outputs.resourceId.value }
              ]
            }
            service: 'vault'
            subnetResourceId: subnetResourceId
          }
        ]
      : []
    roleAssignments: concat(
      managedIdentityObjectId != ''
        ? [
            {
              principalId: managedIdentityObjectId
              principalType: 'ServicePrincipal'
              roleDefinitionIdOrName: 'Key Vault Secrets User'
            }
          ]
        : [],
      principalId != ''
        ? [
            {
              principalId: principalId
              principalType: 'User'
              roleDefinitionIdOrName: 'Key Vault Secrets User'
            }
          ]
        : []
    )
    secrets: secrets
    enableTelemetry: enableTelemetry
  }
}

@description('Key Vault DNS endpoint (vault URI) used for secret access.')
output endpoint string = keyvault.outputs.uri

@description('Key Vault resource name.')
output name string = keyvault.name

@description('Full Azure resource ID of the Key Vault.')
output id string = keyvault.outputs.resourceId
