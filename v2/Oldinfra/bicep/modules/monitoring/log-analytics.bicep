// ============================================================================
// Module: Log Analytics Workspace
// Description: Vanilla Bicep module for Log Analytics Workspace
// Resource: Microsoft.OperationalInsights/workspaces@2023-09-01
// Docs: https://learn.microsoft.com/azure/templates/microsoft.operationalinsights/workspaces
// Note: This module only handles NEW workspace creation.
//       Existing workspace logic is handled in main.bicep.
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Optional. Override name for the Log Analytics workspace. Defaults to log-{solutionName}.')
param name string = 'log-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Retention period in days.')
param retentionInDays int = 365

@description('SKU name for the workspace.')
param skuName string = 'PerGB2018'

// ============================================================================
// Resource
// ============================================================================

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    retentionInDays: retentionInDays
    sku: {
      name: skuName
    }
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Resource ID of the Log Analytics workspace.')
output resourceId string = logAnalytics.id

@description('Name of the Log Analytics workspace.')
output name string = logAnalytics.name

@description('Location of the workspace.')
output location string = logAnalytics.location

@description('Log Analytics workspace customer ID.')
output logAnalyticsWorkspaceId string = logAnalytics.properties.customerId
