// ============================================================================
// Module: Log Analytics Workspace
// Description: AVM wrapper for Log Analytics Workspace with WAF alignment
// AVM Module: avm/res/operational-insights/workspace:0.15.0
// WAF: https://learn.microsoft.com/azure/well-architected/service-guides/azure-log-analytics
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

@description('Retention period in days. WAF recommends 365.')
param retentionInDays int = 365

@description('SKU name for the workspace.')
param skuName string = 'PerGB2018'

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// --- WAF: Private Networking ---
@description('Public network access for ingestion.')
param publicNetworkAccessForIngestion string = 'Enabled'

@description('Public network access for query.')
param publicNetworkAccessForQuery string = 'Enabled'

// --- WAF: Redundancy ---
@description('Enable workspace replication for redundancy.')
param enableReplication bool = false

@description('Replication location (paired region).')
param replicationLocation string = ''

@description('Daily quota in GB. WAF recommends 150 GB/day as starting point.')
param dailyQuotaGb string = ''

// --- WAF: Monitoring (VM data sources for private networking) ---
@description('Data sources for VM monitoring (Windows events, perf counters).')
param dataSources array = []

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

// ============================================================================
// AVM Module Deployment
// ============================================================================
module workspace 'br/public:avm/res/operational-insights/workspace:0.15.0' = {
  name: take('avm.res.operational-insights.workspace.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    dataRetention: retentionInDays
    skuName: skuName
    enableTelemetry: enableTelemetry
    managedIdentities: managedIdentities
    features: { enableLogAccessUsingOnlyResourcePermissions: true }
    diagnosticSettings: [{ useThisWorkspace: true }]
    publicNetworkAccessForIngestion: publicNetworkAccessForIngestion
    publicNetworkAccessForQuery: publicNetworkAccessForQuery
    dailyQuotaGb: !empty(dailyQuotaGb) ? dailyQuotaGb : null
    replication: enableReplication ? {
      enabled: true
      location: replicationLocation
    } : null
    dataSources: !empty(dataSources) ? dataSources : null
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the Log Analytics workspace.')
output resourceId string = workspace.outputs.resourceId

@description('Name of the Log Analytics workspace.')
output name string = workspace.outputs.name

@description('Location of the workspace.')
output location string = location

@description('Log Analytics workspace customer ID.')
output logAnalyticsWorkspaceId string = workspace.outputs.logAnalyticsWorkspaceId
