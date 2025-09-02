metadata description = 'AVM WAF-compliant Azure AI Search instance.'

@description('Name of the Search service.')
param name string

@description('Location for the Search service.')
param location string = resourceGroup().location

@description('Tags to apply to the resource.')
param tags object = {}

param sku object = {
  name: 'standard'
}

@description('Authentication options for the Search service.')
param authOptions object = {}
@description('Disable local auth for the Search service.')
param disableLocalAuth bool = false
@description('Disabled data exfiltration options.')
param disabledDataExfiltrationOptions array = []
@description('Encryption with CMK options.')
param encryptionWithCmk object = {
  enforcement: 'Unspecified'
}
@allowed([
  'default'
  'highDensity'
])
param hostingMode string = 'default'

@description('Network rule set (bypass + ipRules).')
param networkRuleSet object = {
  bypass: 'None'
  ipRules: []
}

param partitionCount int = 1
@allowed([
  'enabled'
  'disabled'
])
param publicNetworkAccess string = 'enabled'
param replicaCount int = 1
@allowed([
  'disabled'
  'free'
  'standard'
])
param semanticSearch string = 'disabled'

// AVM/WAF-aligned optional parameters
@description('Optional. Enable private networking and create private endpoints when provided.')
param enablePrivateNetworking bool = false

@description('Optional array of private endpoint configurations. Each item should at least contain name and subnetId.')
param privateEndpoints array = []

@description('Optional Log Analytics workspace resource id for diagnostics (leave blank to disable).')
param logAnalyticsWorkspaceId string = ''

@description('Optional AVM-managed identity object (outputs from the managed identity module) used for role assignments.')
param avmManagedIdentity object = {}

@description('Optional AVM virtual network module output used to pick subnet for private endpoints.')
param avmVirtualNetwork object = {}

// If privateEndpoints not provided, and AVM virtual network is supplied and private networking is requested,
// create a simple default private endpoint mapping that targets the peps subnet in the AVM virtual network outputs.
var privateEndpointsToCreate = !empty(privateEndpoints)
  ? privateEndpoints
  : (enablePrivateNetworking && !empty(avmVirtualNetwork) && contains(avmVirtualNetwork, 'outputs') && avmVirtualNetwork.outputs.subnetPrivateEndpointsResourceId != ''
      ? [
          {
            name: '${name}-pep'
            subnetId: avmVirtualNetwork.outputs.subnetPrivateEndpointsResourceId
          }
        ]
      : [])

// Search service
resource search 'Microsoft.Search/searchServices@2021-04-01-preview' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    authOptions: authOptions
    disableLocalAuth: disableLocalAuth
    disabledDataExfiltrationOptions: disabledDataExfiltrationOptions
    encryptionWithCmk: encryptionWithCmk
    hostingMode: hostingMode
    networkRuleSet: networkRuleSet
    partitionCount: partitionCount
    // If private networking is requested, default to disabling public network access unless explicitly overridden
    publicNetworkAccess: enablePrivateNetworking ? 'disabled' : publicNetworkAccess
    replicaCount: replicaCount
    semanticSearch: semanticSearch
  }
  sku: sku
}

// Private Endpoints (created only when privateEndpoints or AVM virtual network mapping is provided)
resource privateEndpoint 'Microsoft.Network/privateEndpoints@2021-05-01' = [
  for pe in privateEndpointsToCreate: {
    name: pe.name
    location: location
    properties: {
      subnet: {
        id: pe.subnetId
      }
      privateLinkServiceConnections: [
        {
          name: '${pe.name}-link'
          properties: {
            privateLinkServiceId: search.id
            // groupIds for Azure Search private link connection. When supplying privateEndpoints, ensure this value is correct for your environment.
            groupIds: [
              'search'
            ]
          }
        }
      ]
    }
  }
]

// Diagnostics: forward metrics to Log Analytics if a workspace id is provided
resource diagnostic 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: '${name}-diag'
  scope: search
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// Optional: if an AVM-managed identity module output is provided, grant it Search Service Contributor (AVM WAF flow may rely on this)
resource avmRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(avmManagedIdentity) && contains(
  avmManagedIdentity,
  'outputs'
) && avmManagedIdentity.outputs.principalId != '') {
  name: guid(
    subscription().id,
    resourceGroup().id,
    avmManagedIdentity.outputs.principalId,
    '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  )
  scope: search
  properties: {
    principalId: avmManagedIdentity.outputs.principalId
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
    principalType: 'ServicePrincipal'
  }
}

// Outputs (keep same contract)
output id string = search.id
output endpoint string = 'https://${name}.search.windows.net/'
output name string = search.name
output identityPrincipalId string = search.identity.principalId
