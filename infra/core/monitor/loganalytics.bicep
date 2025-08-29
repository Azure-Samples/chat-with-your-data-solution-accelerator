metadata description = 'Creates a Log Analytics workspace.'
param name string
param location string = resourceGroup().location
param tags object = {}

param existingLogAnalyticsWorkspaceId string = ''

@description('Number of days to retain data in the Log Analytics workspace.  Pick a cost/retention tradeoff suitable for your environment.')
param retentionInDays int = 30

@description('The SKU name for the Log Analytics workspace (e.g. PerGB2018, CapacityReservation, Free).')
param skuName string = 'PerGB2018'

var useExisting = !empty(existingLogAnalyticsWorkspaceId)
var existingLawSubscriptionId = useExisting ? split(existingLogAnalyticsWorkspaceId, '/')[2] : ''
var existingLawResourceGroup = useExisting ? split(existingLogAnalyticsWorkspaceId, '/')[4] : ''
var existingLawName = useExisting ? split(existingLogAnalyticsWorkspaceId, '/')[8] : ''

resource existingLogAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2020-08-01' existing = if (useExisting) {
  name: existingLawName
  scope: resourceGroup(existingLawSubscriptionId, existingLawResourceGroup)
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (!useExisting) {
  name: name
  location: location
  tags: tags
  properties: any({
    retentionInDays: retentionInDays
    features: {
      searchVersion: 1
    }
    sku: {
      name: skuName
    }
  })
}

output id string = useExisting ? existingLogAnalyticsWorkspace.id : logAnalytics.id
output name string = useExisting ? existingLogAnalyticsWorkspace.name : logAnalytics.name
