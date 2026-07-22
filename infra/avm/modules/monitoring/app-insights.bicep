// ============================================================================
// Module: Application Insights
// Description: AVM wrapper for Application Insights with WAF alignment
// AVM Module: avm/res/insights/component:0.7.1
// WAF: https://learn.microsoft.com/azure/well-architected/service-guides/application-insights
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Optional. Override name for the Application Insights instance. Defaults to appi-{solutionName}.')
param name string = 'appi-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Resource ID of the Log Analytics workspace to link to.')
param workspaceResourceId string

@description('Application type.')
param applicationType string = 'web'

@description('Retention period in days. WAF recommends 365.')
param retentionInDays int = 365

@description('Disable IP masking for security. WAF recommends false.')
param disableIpMasking bool = false

@description('Flow type for Application Insights.')
param flowType string = 'Bluefield'

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Kind of Application Insights resource.')
param kind string = 'web'

// ============================================================================
// AVM Module Deployment
// ============================================================================
module appInsights 'br/public:avm/res/insights/component:0.7.1' = {
  name: take('avm.res.insights.component.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    workspaceResourceId: workspaceResourceId
    kind: kind
    applicationType: applicationType
    enableTelemetry: enableTelemetry
    retentionInDays: retentionInDays
    disableIpMasking: disableIpMasking
    flowType: flowType
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the Application Insights instance.')
output resourceId string = appInsights.outputs.resourceId

@description('Name of the Application Insights instance.')
output name string = appInsights.outputs.name

@description('Instrumentation key for the Application Insights instance.')
output instrumentationKey string = appInsights.outputs.instrumentationKey

@description('Connection string for the Application Insights instance.')
output connectionString string = appInsights.outputs.connectionString

@description('Application ID of the Application Insights instance.')
output applicationId string = appInsights.outputs.applicationId
