// ============================================================================
// Module: Portal Dashboard (Application Insights)
// Description: Vanilla Bicep module for Azure Portal Dashboard
// Resource: Microsoft.Portal/dashboards@2025-04-01-preview
// Docs: https://learn.microsoft.com/azure/templates/microsoft.portal/dashboards
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the dashboard.')
param name string = 'dash-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Lenses (tile groups) to display on the dashboard.')
param lenses array = []

@description('Dashboard metadata (time range, filters, etc.).')
param metadata object = {}

// ============================================================================
// Resource
// ============================================================================
resource dashboard 'Microsoft.Portal/dashboards@2025-04-01-preview' = {
  name: name
  location: location
  tags: tags
  properties: {
    lenses: lenses
    metadata: !empty(metadata) ? metadata : {}
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the dashboard.')
output resourceId string = dashboard.id

@description('Name of the dashboard.')
output name string = dashboard.name

@description('Resource group the dashboard was deployed to.')
output resourceGroupName string = resourceGroup().name
