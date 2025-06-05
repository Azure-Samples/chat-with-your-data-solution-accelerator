metadata description = 'Creates an Application Insights instance and a Log Analytics workspace.'
param logAnalyticsName string
param applicationInsightsName string
param applicationInsightsDashboardName string = ''
param location string = resourceGroup().location
param tags object = {}
@description('Resource ID of existing Log Analytics workspace. If not provided, a new one will be created.')
param existingLogAnalyticsResourceId string = ''

var useExistingLogAnalytics = existingLogAnalyticsResourceId != ''
module logAnalytics 'loganalytics.bicep' = if (!useExistingLogAnalytics) {
  name: 'loganalytics'
  params: {
    name: logAnalyticsName
    location: location
    tags: tags
  }
}

var logAnalyticsWorkspaceId = useExistingLogAnalytics ? existingLogAnalyticsResourceId : logAnalytics.outputs.id
var logAnalyticsWorkspaceName = useExistingLogAnalytics ? last(split(existingLogAnalyticsResourceId, '/')) : logAnalytics.outputs.name


module applicationInsights 'applicationinsights.bicep' = {
  name: 'applicationinsights'
  params: {
    name: applicationInsightsName
    location: location
    tags: tags
    dashboardName: applicationInsightsDashboardName
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId

  }
}

output applicationInsightsConnectionString string = applicationInsights.outputs.connectionString
output applicationInsightsInstrumentationKey string = applicationInsights.outputs.instrumentationKey
output applicationInsightsName string = applicationInsights.outputs.name
output applicationInsightsId string = applicationInsights.outputs.id
output logAnalyticsWorkspaceId string = logAnalyticsWorkspaceId
output logAnalyticsWorkspaceName string = logAnalyticsWorkspaceName
