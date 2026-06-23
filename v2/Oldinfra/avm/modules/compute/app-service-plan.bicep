// ============================================================================
// Module: App Service Plan
// Description: AVM wrapper for Azure App Service Plan
// AVM Module: avm/res/web/serverfarm:0.7.0
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

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Number of instances (workers).')
param skuCapacity int = 1

@description('Diagnostic settings for monitoring.')
param diagnosticSettings array = []

@description('Enable zone redundancy. Requires Premium SKU (P1v3+).')
param zoneRedundant bool = false

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

// ============================================================================
// AVM Module Deployment
// ============================================================================
module appServicePlan 'br/public:avm/res/web/serverfarm:0.7.0' = {
  name: take('avm.res.web.serverfarm.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    skuName: skuName
    skuCapacity: skuCapacity
    reserved: reserved
    kind: kind
    diagnosticSettings: !empty(diagnosticSettings) ? diagnosticSettings : []
    zoneRedundant: zoneRedundant
    managedIdentities: managedIdentities
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the App Service Plan.')
output resourceId string = appServicePlan.outputs.resourceId

@description('Name of the App Service Plan.')
output name string = appServicePlan.outputs.name
