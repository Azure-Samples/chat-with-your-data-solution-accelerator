metadata description = 'Creates an Application Insights instance using Azure Verified Module (AVM) following Well-Architected Framework principles.'

// Required parameters (maintaining backward compatibility)
param name string
param logAnalyticsWorkspaceId string

// Optional parameters aligned with WAF principles
param dashboardName string = ''
param location string = resourceGroup().location
param tags object = {}
param enableTelemetry bool = true

@minValue(30)
@maxValue(730)
param retentionInDays int = 365

@minValue(0)
@maxValue(100)
param samplingPercentage int = 100

@allowed([ 'Enabled', 'Disabled' ])
param publicNetworkAccessForIngestion string = 'Enabled'

@allowed([ 'Enabled', 'Disabled' ])
param publicNetworkAccessForQuery string = 'Enabled'

param disableLocalAuth bool = false
param diagnosticSettings array = []

param roleAssignments array = []

// 🔹 Application Insights deployment using AVM WAF
module appInsights 'br/public:avm/res/insights/component:0.6.0' = {
  name: substring('avm.res.insights.component.${name}', 0, (length('avm.res.insights.component.${name}') > 64) ? 64 : length('avm.res.insights.component.${name}'))
  params: {
    name: name
    location: location
    tags: tags

    // Core settings
    applicationType: 'web'
    kind: 'web'
    flowType: 'Bluefield'
    enableTelemetry: enableTelemetry
    retentionInDays: retentionInDays
    samplingPercentage: samplingPercentage
    publicNetworkAccessForIngestion: publicNetworkAccessForIngestion
    publicNetworkAccessForQuery: publicNetworkAccessForQuery
    disableLocalAuth: disableLocalAuth
    disableIpMasking: false

    // Monitoring integration
    workspaceResourceId: logAnalyticsWorkspaceId
    diagnosticSettings: !empty(logAnalyticsWorkspaceId) ? [
      {
        workspaceResourceId: logAnalyticsWorkspaceId
      }
    ] : diagnosticSettings

    roleAssignments: roleAssignments
  }
}

// 🔹 Outputs
output connectionString string = appInsights.outputs.connectionString
output instrumentationKey string = appInsights.outputs.instrumentationKey
output name string = appInsights.outputs.name
output id string = appInsights.outputs.resourceId
output applicationId string = appInsights.outputs.applicationId
output resourceGroupName string = appInsights.outputs.resourceGroupName

// preserve backward compatibility - indicate if a dashboard name was provided
output dashboardNameProvided bool = !empty(dashboardName)
