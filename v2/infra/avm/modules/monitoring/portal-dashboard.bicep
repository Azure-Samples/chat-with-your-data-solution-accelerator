// ============================================================================
// Module: Portal Dashboard (Application Insights)
// Description: AVM wrapper for Azure Portal Dashboard
// AVM Module: avm/res/portal/dashboard:0.3.2
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

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// ============================================================================
// AVM Module Deployment
// ============================================================================
module dashboard 'br/public:avm/res/portal/dashboard:0.3.2' = {
  name: take('avm.res.portal.dashboard.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    lenses: lenses
    metadata: !empty(metadata) ? metadata : null
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the dashboard.')
output resourceId string = dashboard.outputs.resourceId

@description('Name of the dashboard.')
output name string = dashboard.outputs.name

@description('Resource group the dashboard was deployed to.')
output resourceGroupName string = dashboard.outputs.resourceGroupName
