@description('Wrapper for AVM Azure Cognitive Search module')
param name string
param location string
param tags object = {}
param enableTelemetry bool = true
param enableMonitoring bool = false
param logAnalyticsWorkspaceResourceId string = ''
param enablePrivateNetworking bool = false
param subnetResourceId string = ''
param avmPrivateDnsZones array = []
param dnsZoneIndex object = {}

// Search-specific parameters
param sku string = 'standard'
param authOptions object = {
  aadOrApiKey: {
    aadAuthFailureMode: 'http401WithBearerChallenge'
  }
}
param disableLocalAuth bool = false
param hostingMode string = 'default'
param networkRuleSet object = {
  bypass: 'AzureServices'
  ipRules: []
}
param partitionCount int = 1
param replicaCount int = 1
@allowed([
  'disabled'
  'free'
  'standard'
])
param semanticSearch string = 'disabled'
param userAssignedResourceId string = ''
param roleAssignments array = []

// // Define DNS zone group configs as a variable
// var privateDnsZoneGroupConfigs = [for zoneId in privateDnsZoneResourceIds: {
//   privateDnsZoneResourceId: zoneId
// }]

var searchResourceName = name

module avmSearch 'br/public:avm/res/search/search-service:0.11.1' = {
  name: take('avm.res.search.search-service.${searchResourceName}', 64)
  params: {
    // Required parameters
    name: searchResourceName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    sku: sku

    // WAF aligned configuration
    authOptions: authOptions
    disableLocalAuth: disableLocalAuth
    hostingMode: hostingMode
    networkRuleSet: networkRuleSet
    partitionCount: partitionCount
    replicaCount: replicaCount
    semanticSearch: semanticSearch

    // WAF aligned configuration for Monitoring
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : []

    // WAF aligned configuration for Private Networking
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${searchResourceName}'
            customNetworkInterfaceName: 'nic-${searchResourceName}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                { privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex.searchService]!.outputs.resourceId }
              ]
            }
            // privateDnsZoneGroup: !empty(privateDnsZoneResourceIds)
            //   ? {
            //       privateDnsZoneGroupConfigs: privateDnsZoneGroupConfigs
            //     }
            //   : null
            service: 'searchService'
            subnetResourceId: subnetResourceId
          }
        ]
      : []

    managedIdentities: { systemAssigned: true, userAssignedResourceIds: [userAssignedResourceId] }
    roleAssignments: roleAssignments
  }
}

output searchOutput object = {
  name: avmSearch.outputs.name
  endpoint: avmSearch.outputs.endpoint
  identityPrincipalId: avmSearch.outputs.systemAssignedMIPrincipalId!
  resourceId: avmSearch.outputs.resourceId
}
