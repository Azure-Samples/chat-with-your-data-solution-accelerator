metadata name = 'loganalytics-workspace'
metadata description = 'AVM WAF-compliant Log Analytics workspace wrapper using AVM module (br/public:avm/res/operational-insights/workspace).'

// ========== //
// Parameters //
// ========== //

@description('Required. Name of the Log Analytics workspace.')
param name string

@description('Required. Location for the Log Analytics workspace.')
param location string

@description('Optional. SKU of the workspace.')
@allowed([
  'PerGB2018'
])
param sku string = 'PerGB2018'

@description('Optional. Data retention in days.')
@minValue(30)
@maxValue(730)
param retentionInDays int = 30

@description('Optional. Daily ingestion quota (GB). -1 = unlimited.')
@minValue(-1)
param dailyQuotaGb int = -1

@description('Optional. Resource lock setting.')
@allowed([
  'CanNotDelete'
  'ReadOnly'
  'None'
])
param lockLevel string = 'None'

@description('Optional. Enable RBAC-only log access for compliance.')
param enableLogAccessUsingOnlyResourcePermissions bool = true

@description('Optional. Tags to apply to the workspace.')
param tags object = {}

// ========== //
// Resources  //
// ========== //

module avmWorkspace 'br/public:avm/res/operational-insights/workspace:0.12.0' = {
  name: '${name}-deploy'
  params: {
    name: name
    tags: tags
    location: location
    enableTelemetry: true
    skuName: sku
    dataRetention: retentionInDays
    features: {
      enableLogAccessUsingOnlyResourcePermissions: enableLogAccessUsingOnlyResourcePermissions
    }
    dailyQuotaGb: dailyQuotaGb
  }
}

// Apply a resource lock at deployment time if requested (keeps lock behavior explicit and AVM-module-agnostic)
resource workspaceLock 'Microsoft.Authorization/locks@2017-04-01' = if (lockLevel != 'None') {
  name: '${name}-lock'
  properties: {
    level: lockLevel
    notes: 'Lock applied per AVM WAF guidelines to help prevent accidental deletion or modification.'
  }
}

// ========== //
// Outputs    //
// ========== //

@description('Name of the Log Analytics workspace.')
output name string = avmWorkspace.outputs.name

@description('Resource ID of the Log Analytics workspace.')
output resourceId string = avmWorkspace.outputs.resourceId

@description('Resource ID of the Log Analytics workspace (alias).')
output workspaceResourceId string = avmWorkspace.outputs.resourceId

@description('Workspace identifier (customer/workspace ID) from AVM module outputs.')
output logAnalyticsWorkspaceId string = avmWorkspace.outputs.logAnalyticsWorkspaceId

@description('Resource Group where the workspace is deployed.')
output resourceGroupName string = resourceGroup().name

@description('Location of the workspace.')
output location string = location
