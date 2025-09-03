metadata name = 'monitoring-solution'
metadata description = 'AVM WAF-compliant monitoring solution that integrates Application Insights with Log Analytics for centralized telemetry, diagnostics, and observability.'

// ========== //
// Parameters //
// ========== //

@description('Required. Name of the Log Analytics workspace.')
param logAnalyticsName string
@description('Optional. Unique deployment suffix to avoid naming conflicts.')
param deploymentSuffix string = utcNow('MMddHHmmss')
@description('Required. Name of the Application Insights instance.')
param applicationInsightsName string

@description('Required. Location for resources.')
param location string

@description('Optional. SKU for the Log Analytics workspace.')
@allowed([
  'PerGB2018'
])
param logAnalyticsSku string = 'PerGB2018'

@description('Optional. Retention period for Log Analytics (in days).')
@minValue(30)
@maxValue(730)
param logRetentionInDays int = 30

@description('Optional. Daily ingestion quota (GB) for cost control. -1 = unlimited.')
@minValue(-1)
param dailyQuotaGb int = -1

@description('Optional. Resource lock setting for protecting monitoring resources.')
@allowed([
  'CanNotDelete'
  'ReadOnly'
  'None'
])
param lockLevel string = 'None'

@description('Optional. Tags to apply to monitoring resources.')
param tags object = {}

@description('Optional. Retention for Application Insights (in days). AVM/WAF recommends 365.')
@minValue(30)
@maxValue(730)
param appInsightsRetentionInDays int = 365

@description('Optional. Use an existing Log Analytics workspace by providing its resource ID. If provided, the module will not create a new workspace.')
param existingLogAnalyticsWorkspaceId string = ''

@description('Optional. Dashboard name to create/link for Application Insights (pass-through).')
param applicationInsightsDashboardName string = ''

// ========== //
// Resources  //
// ========== //

// Log Analytics workspace
module logAnalytics './loganalytics.bicep' = if (empty(existingLogAnalyticsWorkspaceId)) {
  name: '${logAnalyticsName}-deploy-${deploymentSuffix}'
  params: {
    name: logAnalyticsName
    location: location
    sku: logAnalyticsSku
    retentionInDays: logRetentionInDays
    dailyQuotaGb: dailyQuotaGb
    lockLevel: lockLevel
    tags: tags
  }
}

var workspaceResourceId = empty(existingLogAnalyticsWorkspaceId)
  ? logAnalytics!.outputs.workspaceResourceId
  : existingLogAnalyticsWorkspaceId

// Application Insights
module appInsights './applicationinsights.bicep' = {
  name: '${applicationInsightsName}-deploy--${deploymentSuffix}'
  params: {
    name: applicationInsightsName
    location: location
    workspaceResourceId: workspaceResourceId
    retentionInDays: appInsightsRetentionInDays
    lockLevel: lockLevel
    tags: tags
  }
}

// ========== //
// Outputs    //
// ========== //

@description('Resource ID of the Log Analytics workspace.')
output logAnalyticsWorkspaceId string = empty(existingLogAnalyticsWorkspaceId)
  ? logAnalytics!.outputs.workspaceResourceId
  : existingLogAnalyticsWorkspaceId

@description('Resource ID of the Application Insights instance.')
output appInsightsId string = appInsights.outputs.appInsightsResourceId

// Compatibility aliases used by upstream templates
@description('Legacy alias for the Application Insights resource id (backwards compatibility).')
output applicationInsightsId string = appInsights.outputs.appInsightsResourceId

@description('Application Insights resource name (backwards compatibility).')
output applicationInsightsName string = applicationInsightsName

@description('Application Insights connection string (backwards compatibility).')
output applicationInsightsConnectionString string = appInsights.outputs.connectionString

@description('Application Insights instrumentation key (backwards compatibility).')
output applicationInsightsInstrumentationKey string = appInsights.outputs.instrumentationKey

@description('Application Insights dashboard name (pass-through).')
output applicationInsightsDashboardName string = applicationInsightsDashboardName

@description('Resource Group name where monitoring resources are deployed.')
output resourceGroupName string = resourceGroup().name

@description('Location where monitoring resources are deployed.')
output location string = location
