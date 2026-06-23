// ============================================================================
// Module: Application Insights
// Description: Vanilla Bicep module for Application Insights
// Resource: Microsoft.Insights/components@2020-02-02
// Docs: https://learn.microsoft.com/azure/templates/microsoft.insights/components
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

@description('Retention period in days.')
param retentionInDays int = 365

@description('Disable IP masking for security.')
param disableIpMasking bool = false

@description('Flow type for Application Insights.')
param flowType string = 'Bluefield'

@description('Kind of Application Insights resource.')
param kind string = 'web'

// ============================================================================
// Resource
// ============================================================================

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: name
  location: location
  tags: tags
  kind: kind
  properties: {
    Application_Type: applicationType
    Flow_Type: flowType
    WorkspaceResourceId: workspaceResourceId
    RetentionInDays: retentionInDays
    DisableIpMasking: disableIpMasking
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Resource ID of the Application Insights instance.')
output resourceId string = appInsights.id

@description('Name of the Application Insights instance.')
output name string = appInsights.name

@description('Instrumentation key for the Application Insights instance.')
output instrumentationKey string = appInsights.properties.InstrumentationKey

@description('Connection string for the Application Insights instance.')
output connectionString string = appInsights.properties.ConnectionString

@description('Application ID of the Application Insights instance.')
output applicationId string = appInsights.properties.AppId
