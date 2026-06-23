// ============================================================================
// Module: Azure Container Registry
// Description: Creates an Azure Container Registry
// API: Microsoft.ContainerRegistry/registries@2025-04-01
// ============================================================================

@description('Solution name used for naming convention.')
param solutionName string

@description('Name of the container registry.')
param name string = replace('cr${solutionName}', '-', '')

@description('Azure region for deployment.')
param location string

@description('Resource tags.')
param tags object = {}

@description('SKU for the container registry.')
@allowed(['Basic', 'Standard', 'Premium'])
param sku string = 'Premium'

@description('Enable admin user.')
param adminUserEnabled bool = false

@description('Public network access setting.')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Enabled'

@description('Export policy status.')
param exportPolicyStatus string = 'enabled'

// ============================================================================
// Resource Deployment
// ============================================================================
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    adminUserEnabled: adminUserEnabled
    publicNetworkAccess: publicNetworkAccess
    dataEndpointEnabled: false
    networkRuleBypassOptions: 'AzureServices'
    policies: {
      exportPolicy: {
        status: exportPolicyStatus
      }
      retentionPolicy: {
        status: 'enabled'
        days: 7
      }
      trustPolicy: {
        status: 'disabled'
        type: 'Notary'
      }
    }
    zoneRedundancy: 'Disabled'
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('The name of the container registry.')
output name string = containerRegistry.name

@description('The login server URL.')
output loginServer string = containerRegistry.properties.loginServer

@description('The resource ID of the container registry.')
output resourceId string = containerRegistry.id