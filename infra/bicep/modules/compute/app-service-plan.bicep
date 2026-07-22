// ============================================================================
// Module: App Service Plan
// Description: Creates an Azure App Service Plan
// API: Microsoft.Web/serverfarms@2025-05-01
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the App Service Plan.')
param name string = 'asp-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('SKU name for the App Service Plan.')
@allowed(['F1', 'D1', 'B1', 'B2', 'B3', 'S1', 'S2', 'S3', 'P1', 'P2', 'P3', 'P4', 'P0v3', 'P0v4', 'P1v3', 'P1v4', 'P2v3', 'P3v3'])
param skuName string = 'B2'

@description('Whether the plan is Linux-based.')
param reserved bool = true

@description('Kind of the App Service Plan.')
param kind string = 'linux'

@description('Number of instances (workers).')
param skuCapacity int = 1

@description('Enable zone redundancy. Requires Premium SKU (P1v3+).')
param zoneRedundant bool = false

@description('Optional. Managed identity configuration for the resource.')
param identity object = { type: 'SystemAssigned' }

// ============================================================================
// Resource Deployment
// ============================================================================
resource appServicePlan 'Microsoft.Web/serverfarms@2025-05-01' = {
  name: name
  location: location
  tags: tags
  kind: kind
  sku: {
    name: skuName
    capacity: skuCapacity
  }
  properties: {
    reserved: reserved
    zoneRedundant: zoneRedundant
  }
  identity: identity
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the App Service Plan.')
output resourceId string = appServicePlan.id

@description('Name of the App Service Plan.')
output name string = appServicePlan.name
