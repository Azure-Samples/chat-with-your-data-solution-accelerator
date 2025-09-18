@description('Wrapper for AVM Azure Cognitive Search module')
param name string
param location string
param tags object = {}
param enableTelemetry bool = true
param enableMonitoring bool = false
param logAnalyticsWorkspaceResourceId string = ''
param enablePrivateNetworking bool = false
param subnetResourceId string = ''
param privateDnsZoneResourceIds array = []

// Define DNS zone group configs as a variable
var privateDnsZoneGroupConfigs = [
  for zoneId in privateDnsZoneResourceIds: {
    privateDnsZoneResourceId: zoneId
  }
]

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
@description('Optional. Flag to enable a system-assigned managed identity for the Cognitive Services resource.')
param enableSystemAssigned bool = false
@description('Optional. Array of role assignments to apply to the system-assigned identity at the search service scope. Each item: { roleDefinitionId: "<GUID or built-in role definition id>" }')
param systemAssignedRoleAssignments array = []

// // Define DNS zone group configs as a variable
// var privateDnsZoneGroupConfigs = [for zoneId in privateDnsZoneResourceIds: {
//   privateDnsZoneResourceId: zoneId
// }]

var searchResourceName = name
// // Only compute DNS-related values when private networking is enabled. When disabled, set safe defaults so these vars won't reference arrays or objects.
// var searchDnsIndex = enablePrivateNetworking ? (dnsZoneIndex.searchService ?? 0) : 0
// var hasSearchDnsConfig = enablePrivateNetworking ? (length(avmPrivateDnsZones) > searchDnsIndex) : false
// var searchPrivateDnsZoneGroupConfigs = enablePrivateNetworking && hasSearchDnsConfig
//   ? [
//       { privateDnsZoneResourceId: avmPrivateDnsZones[searchDnsIndex].outputs.resourceId }
//     ]
//   : []

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
              privateDnsZoneGroupConfigs: !empty(privateDnsZoneResourceIds) ? privateDnsZoneGroupConfigs : []
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

    // Configure managed identity: user-assigned for production, system-assigned allowed for local development with integrated vectorization
    managedIdentities: { systemAssigned: enableSystemAssigned, userAssignedResourceIds: [userAssignedResourceId] }
    roleAssignments: roleAssignments
  }
}

// --- System-assigned identity role assignments for local development with integrated vectorization (optional) --- //
@description('Role assignments applied to the system-assigned identity via AVM module. Objects can include: roleDefinitionId (req), roleName, principalType, resourceId.')
module systemAssignedIdentityRoleAssignments 'br/public:avm/ptn/authorization/resource-role-assignment:0.1.2' = [
  for assignment in systemAssignedRoleAssignments: if (enableSystemAssigned && !empty(systemAssignedRoleAssignments)) {
    name: take('avm.ptn.authorization.resource-role-assignment.${uniqueString(searchResourceName, assignment.roleDefinitionId, assignment.resourceId)}', 64)
    params: {
      roleDefinitionId: assignment.roleDefinitionId
      principalId: avmSearch.outputs.systemAssignedMIPrincipalId
      resourceId: assignment.resourceId
      roleName: assignment.roleName
      principalType: assignment.principalType
    }
  }
]

output searchName string = avmSearch.outputs.name
output searchEndpoint string = avmSearch.outputs.endpoint
output searchResourceId string = avmSearch.outputs.resourceId
// output identityPrincipalId string = avmSearch.outputs.systemAssignedMIPrincipalId!
// output identityResourceId string = avmSearch.outputs.resourceId
