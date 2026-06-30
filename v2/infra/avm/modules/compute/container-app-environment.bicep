// ============================================================================
// Module: Azure Container Apps Environment (AVM)
// AVM Module: avm/res/app/managed-environment:0.13.3
// ============================================================================

@description('Solution name used for naming convention.')
param solutionName string

@description('Name of the Container Apps Environment.')
param name string = 'cae-${solutionName}'

@description('Azure region for deployment.')
param location string

@description('Resource tags.')
param tags object = {}

@description('Resource ID of the Log Analytics workspace (required when enableMonitoring is true).')
param logAnalyticsWorkspaceResourceId string = ''

@description('Subnet resource ID for VNet integration (required when enablePrivateNetworking is true).')
param infrastructureSubnetId string = ''

@description('Enable zone redundancy.')
param zoneRedundant bool = false

@description('Enable Azure telemetry collection.')
param enableTelemetry bool = true

@description('Enable private networking (internal environment, public access disabled).')
param enablePrivateNetworking bool = false

@description('Enable monitoring (Log Analytics + App Insights).')
param enableMonitoring bool = true

@description('Application Insights connection string (optional, for App Insights integration).')
param appInsightsConnectionString string = ''

@description('Enable redundancy (dedicated workload profiles + infra resource group).')
param enableRedundancy bool = false

@description('Infrastructure resource group name (used when zone redundancy is enabled). Defaults to "{resourceGroup}-infra" if empty.')
param infrastructureResourceGroupName string = '${resourceGroup().name}-infra'

@description('Workload profiles configuration (e.g., Consumption or dedicated D4 profiles).')
param workloadProfiles array = [
  {
    name: 'Consumption'
    workloadProfileType: 'Consumption'
  }
]

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

// ============================================================================
// Container Apps Environment (AVM)
// ============================================================================
module managedEnvironment 'br/public:avm/res/app/managed-environment:0.13.3' = {
  name: take('avm.res.app.managedenvironment.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    // WAF: Private networking
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    internal: enablePrivateNetworking
    infrastructureSubnetResourceId: !empty(infrastructureSubnetId) ? infrastructureSubnetId : null
    // WAF: Monitoring
    appLogsConfiguration: enableMonitoring && !empty(logAnalyticsWorkspaceResourceId)
      ? {
          destination: 'log-analytics'
          logAnalyticsWorkspaceResourceId: logAnalyticsWorkspaceResourceId
        }
      : null
    appInsightsConnectionString: !empty(appInsightsConnectionString) ? appInsightsConnectionString : null
    // WAF: Redundancy
    zoneRedundant: zoneRedundant || enableRedundancy
    infrastructureResourceGroupName: !empty(infrastructureResourceGroupName) ? infrastructureResourceGroupName : null
    workloadProfiles: workloadProfiles
    managedIdentities: managedIdentities
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('The name of the Container Apps Environment.')
output name string = managedEnvironment.outputs.name

@description('The resource ID of the Container Apps Environment.')
output resourceId string = managedEnvironment.outputs.resourceId

@description('The default domain of the Container Apps Environment.')
output defaultDomain string = managedEnvironment.outputs.defaultDomain

@description('The static IP of the Container Apps Environment.')
output staticIp string = managedEnvironment.outputs.staticIp
