metadata name = 'applicationinsights-instance'
metadata description = 'AVM WAF-compliant Application Insights wrapper using AVM module (br/public:avm/res/insights/component).'

// ========== //
// Parameters //
// ========== //

@description('Required. Name of the Application Insights instance.')
param name string

@description('Required. Location of the Application Insights instance.')
param location string

@description('Optional. Resource ID of the linked Log Analytics workspace.')
param workspaceResourceId string = ''

@description('Optional. Application type (e.g., web, other).')
@allowed([
  'web'
  'other'
])
param applicationType string = 'web'

@description('Optional. Retention for Application Insights (in days). AVM/WAF recommends 365.')
@minValue(30)
@maxValue(730)
param retentionInDays int = 365

@description('Optional. Enable telemetry collection.')
param enableTelemetry bool = true

@description('Optional. Resource lock setting.')
@allowed([
  'CanNotDelete'
  'ReadOnly'
  'None'
])
param lockLevel string = 'None'
param dashboardName string = ''
@description('Optional. Tags to apply.')
param tags object = {}

// ========== //
// Resources  //
// ========== //

module avmAppInsights 'br/public:avm/res/insights/component:0.6.0' = {
  name: '${name}-deploy'
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    retentionInDays: retentionInDays
    kind: applicationType
    disableIpMasking: false
    flowType: 'Bluefield'
    workspaceResourceId: empty(workspaceResourceId) ? '' : workspaceResourceId
    diagnosticSettings: empty(workspaceResourceId) ? null : [{ workspaceResourceId: workspaceResourceId }]
  }
}

// Apply a resource lock at deployment time if requested
resource appInsightsLock 'Microsoft.Authorization/locks@2017-04-01' = if (lockLevel != 'None') {
  name: '${name}-lock'
  properties: {
    level: lockLevel
    notes: 'Lock applied per AVM WAF guidelines to prevent accidental deletion or modification.'
  }
}
module applicationInsightsDashboard 'applicationinsights-dashboard.bicep' = if (!empty(dashboardName)) {
  name: 'application-insights-dashboard'
  params: {
    name: dashboardName
    location: location
    applicationInsightsName: name
  }
}

// ========== //
// Outputs    //
// ========== //

@description('Resource ID of the Application Insights instance.')
output appInsightsResourceId string = avmAppInsights.outputs.resourceId

@description('Instrumentation key of the Application Insights instance.')
output instrumentationKey string = avmAppInsights.outputs.instrumentationKey

@description('Connection string for Application Insights.')
output connectionString string = avmAppInsights.outputs.connectionString
