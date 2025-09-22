// ========== Cognitive Services (AVM + WAF aligned, Cosmos-style, dynamic DNS) ========== //
@description('The name of the Cognitive Services resource.')
param name string

@description('The Azure region where the Cognitive Services resource will be deployed.')
param location string

@description('Optional. Tags to be applied to the Cognitive Services resource.')
param tags object = {}

@description('Optional. The custom subdomain name used to access the API. Defaults to the value of the name parameter.')
param customSubDomainName string = name

@description('Optional. Flag to enable monitoring diagnostics.')
param enableMonitoring bool = false

@description('Optional. Resource ID of the Log Analytics workspace to send diagnostics to.')
param logAnalyticsWorkspaceId string = ''

@description('Optional. Flag to enable telemetry collection.')
param enableTelemetry bool = false

@description('Optional. Flag to enable private networking for the Cognitive Services resource.')
param enablePrivateNetworking bool = false

@description('Optional. Resource ID of the subnet to deploy the Cognitive Services resource to. Required when enablePrivateNetworking is true.')
param subnetResourceId string = 'null'

@description('Optional. Resource ID of the private DNS zone for the Cognitive Services resource.')
param privateDnsZoneResourceId string = ''

@description('Optional. Resource ID of the user-assigned managed identity to be used by the Cognitive Services resource.')
param userAssignedResourceId string = ''

@description('Optional. Flag to enable a system-assigned managed identity for the Cognitive Services resource.')
param enableSystemAssigned bool = false

@description('Optional. Flag to disable local authentication for the Cognitive Services resource.')
param disableLocalAuth bool = true

@description('Optional. Flag to restrict outbound network access for the Cognitive Services resource.')
param restrictOutboundNetworkAccess bool = true

@description('Optional. List of allowed FQDN.')
param allowedFqdnList array?

@description('Optional. The kind of Cognitive Services resource to deploy.')
param kind string = 'OpenAI'

@description('Optional. The SKU of the Cognitive Services resource.')
@allowed(['F0', 'S0', 'S1', 'S2', 'S3'])
param sku string = 'S0'

@description('Optional. The deployments to create in the Cognitive Services resource.')
param deployments array = []

@description('Optional. Array of role assignments to create for the Cognitive Services resource.')
param roleAssignments array = []

// Resource variables
var cognitiveResourceName = name

module cognitiveServices '../../cognitive-services/account/cognitive-services.bicep' = {
  name: take('avm.res.cognitive-services.account.${cognitiveResourceName}', 64)
  params: {
    name: cognitiveResourceName
    location: location
    tags: tags
    kind: kind
    sku: sku
    customSubDomainName: customSubDomainName
    disableLocalAuth: disableLocalAuth
    managedIdentities: { systemAssigned: enableSystemAssigned, userAssignedResourceIds: [userAssignedResourceId] }
    roleAssignments: roleAssignments
    restrictOutboundNetworkAccess: restrictOutboundNetworkAccess
    allowedFqdnList: restrictOutboundNetworkAccess ? (allowedFqdnList ?? []) : []
    enableTelemetry: enableTelemetry
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceId }] : null
    networkAcls: {
      bypass: kind == 'OpenAI' || kind == 'AIServices' ? 'AzureServices' : null
      defaultAction: enablePrivateNetworking ? 'Deny' : 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    privateEndpoints: enablePrivateNetworking && !empty(privateDnsZoneResourceId)
      ? [
          {
            name: 'pep-${cognitiveResourceName}'
            customNetworkInterfaceName: 'nic-${cognitiveResourceName}'
            service: 'account'
            subnetResourceId: subnetResourceId
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                { privateDnsZoneResourceId: privateDnsZoneResourceId }
              ]
            }
            // privateDnsZoneResourceIds: [
            //   privateDnsZoneResourceId
            // ]
          }
        ]
      : []
    deployments: deployments
  }
}

// -------- Outputs -------- //
@description('The endpoint URL of the Cognitive Services resource.')
output endpoint string = cognitiveServices.outputs.endpoint

@description('The resource ID of the Cognitive Services resource.')
output resourceId string = cognitiveServices.outputs.resourceId

@description('The name of the Cognitive Services resource.')
output name string = cognitiveServices.outputs.name

@description('The Azure region where the Cognitive Services resource is deployed.')
output location string = location

@description('The principal ID of the system-assigned managed identity, if enabled.')
output systemAssignedMIPrincipalId string = enableSystemAssigned ? cognitiveServices.outputs.systemAssignedMIPrincipalId : ''
