metadata name = 'applicationinsights-loganalytics-solution'
metadata description = 'Creates a comprehensive monitoring solution with Application Insights and Log Analytics using Azure Verified Modules (AVM) following Well-Architected Framework (WAF) principles.'

// ========== //
// Parameters //
// ========== //
@description('Required. Name of the Log Analytics workspace.')
param logAnalyticsName string

@description('Required. Name of the Application Insights instance.')
param applicationInsightsName string

@description('Optional. Name of the Application Insights dashboard.')
param applicationInsightsDashboardName string = ''

@description('Optional. Location for all resources.')
param location string = resourceGroup().location

@description('Optional. Tags of the resource.')
param tags object = {}

@description('Optional. Resource ID of an existing Log Analytics workspace to use instead of creating a new one.')
param existingLogAnalyticsWorkspaceId string = ''

// Security (WAF)
@description('Optional. Public network access type for ingestion.')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccessForIngestion string = 'Disabled'

@description('Optional. Public network access type for query.')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccessForQuery string = 'Enabled'

@description('Optional. Disable Non-AAD based authentication.')
param disableLocalAuth bool = true

@description('Optional. Enable RBAC-only log access.')
param enableLogAccessUsingOnlyResourcePermissions bool = true

@description('Optional. Enable system assigned managed identity on the workspace.')
param enableSystemAssignedIdentity bool = true

// Cost Optimization (WAF)
@description('Optional. Workspace daily ingestion quota (GB). -1 means unlimited.')
@minValue(-1)
param dailyQuotaGb int = 10

@description('Optional. Data retention in days (Log Analytics).')
@minValue(30)
@maxValue(730)
param dataRetention int = 90

@description('Optional. Data retention in days (Application Insights).')
@minValue(30)
@maxValue(730)
param applicationInsightsRetentionInDays int = 90

// Operational Excellence (WAF)
@description('Optional. Enable diagnostic settings.')
param enableDiagnosticSettings bool = true

@description('Optional. Sampling percentage for Application Insights telemetry.')
@minValue(0)
@maxValue(100)
param samplingPercentage int = 100

// Reliability (WAF)
@description('Optional. Enable resource locks.')
param enableResourceLocks bool = false

@description('Optional. Lock type if enabled.')
@allowed(['CanNotDelete', 'ReadOnly'])
param lockLevel string = 'CanNotDelete'

// ========= //
// Variables //
// ========= //
var commonTags = union(tags, {
  'monitoring-solution': 'chat-with-your-data'
  'avm-version': '2024-08'
})

var diagnosticSettings = enableDiagnosticSettings
  ? [
      {
        name: 'self-diagnostics'
        workspaceResourceId: logAnalyticsResourceId
        metricCategories: [
          {
            category: 'AllMetrics'
            enabled: true
          }
        ]
        logCategories: [
          {
            category: 'AuditLogs'
            enabled: true
          }
        ]
      }
    ]
  : []

var lockConfig = enableResourceLocks
  ? {
      kind: lockLevel
      name: 'monitoring-solution-lock'
    }
  : {}

// create a safe module name by truncating to 64 chars
var logAnalyticsModuleName = take('avm.res.operational-insights.workspace.${logAnalyticsName}', 64)
var appInsightsModuleName = take('avm.res.insights.component.${applicationInsightsName}', 64)

// logAnalyticsResourceId will resolve to existing id when provided, otherwise compute the resourceId for the workspace we will create in this resource group
var logAnalyticsResourceId = empty(existingLogAnalyticsWorkspaceId)
  ? resourceId('Microsoft.OperationalInsights/workspaces', logAnalyticsName)
  : existingLogAnalyticsWorkspaceId

// =========== //
// Deployments //
// =========== //
module logAnalytics 'br/public:avm/res/operational-insights/workspace:0.9.0' = if (empty(existingLogAnalyticsWorkspaceId)) {
  name: logAnalyticsModuleName
  params: {
    name: logAnalyticsName
    location: location
    tags: commonTags
    publicNetworkAccessForIngestion: publicNetworkAccessForIngestion
    publicNetworkAccessForQuery: publicNetworkAccessForQuery
    useResourcePermissions: enableLogAccessUsingOnlyResourcePermissions
    dailyQuotaGb: dailyQuotaGb
    dataRetention: dataRetention
    skuName: 'PerGB2018'
    managedIdentities: enableSystemAssignedIdentity ? { systemAssigned: true } : {}
    diagnosticSettings: diagnosticSettings
    lock: lockConfig
  }
}

module applicationInsights 'br/public:avm/res/insights/component:0.4.0' = {
  name: appInsightsModuleName
  dependsOn: empty(existingLogAnalyticsWorkspaceId) ? [logAnalytics] : []
  params: {
    name: applicationInsightsName
    location: location
    tags: commonTags
    workspaceResourceId: logAnalyticsResourceId
    disableLocalAuth: disableLocalAuth
    publicNetworkAccessForIngestion: publicNetworkAccessForIngestion
    publicNetworkAccessForQuery: publicNetworkAccessForQuery
    retentionInDays: applicationInsightsRetentionInDays
    samplingPercentage: samplingPercentage
    applicationType: 'web'
    kind: 'web'
    diagnosticSettings: diagnosticSettings
  }
}

module applicationInsightsDashboard 'br/public:avm/res/portal/dashboard:0.1.0' = if (!empty(applicationInsightsDashboardName)) {
  name: 'appinsights-dashboard'
  params: {
    name: applicationInsightsDashboardName
    location: location
    tags: commonTags
    lenses: []
  }
}

// Optionally create resource-level management locks for Log Analytics and App Insights
resource logAnalyticsLock 'Microsoft.Authorization/locks@2016-09-01' = if (enableResourceLocks) {
  name: '${logAnalyticsName}-lock'
  scope: resourceGroup()
  properties: {
    level: lockLevel
    notes: 'Lock applied by AVM WAF monitoring template'
  }
}

resource appInsightsLock 'Microsoft.Authorization/locks@2016-09-01' = if (enableResourceLocks) {
  name: '${applicationInsightsName}-lock'
  scope: resourceGroup()
  properties: {
    level: lockLevel
    notes: 'Lock applied by AVM WAF monitoring template'
  }
}

// ======= //
// Outputs //
// ======= //
@description('Connection string of the Application Insights instance.')
output applicationInsightsConnectionString string = applicationInsights.outputs.connectionString

@description('Instrumentation key of the Application Insights instance.')
output applicationInsightsInstrumentationKey string = applicationInsights.outputs.instrumentationKey

@description('Name of the Application Insights instance.')
output applicationInsightsName string = applicationInsights.outputs.name

@description('Resource ID of the Application Insights instance.')
output applicationInsightsId string = applicationInsights.outputs.resourceId

@description('Resource ID of the Log Analytics workspace.')
output logAnalyticsWorkspaceId string = logAnalyticsResourceId

@description('Name of the Log Analytics workspace.')
output logAnalyticsWorkspaceName string = empty(existingLogAnalyticsWorkspaceId)
  ? logAnalyticsName
  : last(split(existingLogAnalyticsWorkspaceId, '/'))

@description('Deployment location.')
output location string = location

@description('Resource group name.')
output resourceGroupName string = resourceGroup().name

@description('Principal ID of system-assigned MI if enabled.')
output logAnalyticsSystemAssignedIdentityPrincipalId string = ''
