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

@description('Optional. Array of private DNS zones for the Cognitive Services resource.')
param avmPrivateDnsZones array = []

@description('Optional. Index object for DNS zone lookup.')
param dnsZoneIndex object = {}

@description('Optional. Resource ID of the user-assigned managed identity to be used by the Cognitive Services resource.')
param userAssignedResourceId string = ''

@description('Optional. Flag to restrict outbound network access for the Cognitive Services resource.')
param restrictOutboundNetworkAccess bool = true

@description('Optional. List of allowed FQDN.')
param allowedFqdnList array?

@description('Optional. The kind of Cognitive Services resource to deploy.')
param kind string = 'OpenAI'

@description('Optional. The SKU of the Cognitive Services resource.')
@allowed(['S0', 'S1', 'S2', 'S3'])
param sku string = 'S0'

@description('Optional. The deployments to create in the Cognitive Services resource.')
param deployments array = []

@description('Optional. Array of role assignments to create for the Cognitive Services resource.')
param roleAssignments array = []

// Resource variables
var cognitiveResourceName = name

// Dynamically select DNS zone key based on kind
var dnsZoneKey = (kind == 'OpenAI') ? 'openAI' : 'cognitiveServices'

module cognitiveServices 'br/public:avm/res/cognitive-services/account:0.10.2' = {
  name: take('avm.res.cognitive-services.account.${cognitiveResourceName}', 64)
  params: {
    name: cognitiveResourceName
    location: location
    tags: tags
    kind: kind
    sku: sku
    customSubDomainName: customSubDomainName
    disableLocalAuth: true
    managedIdentities: { systemAssigned: true, userAssignedResourceIds: [userAssignedResourceId] }
    roleAssignments: roleAssignments
    restrictOutboundNetworkAccess: restrictOutboundNetworkAccess
    allowedFqdnList: restrictOutboundNetworkAccess ? (allowedFqdnList ?? []) : []
    enableTelemetry: enableTelemetry
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceId }] : null
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: enablePrivateNetworking ? 'Deny' : 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${cognitiveResourceName}'
            customNetworkInterfaceName: 'nic-${cognitiveResourceName}'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  privateDnsZoneResourceId: avmPrivateDnsZones[dnsZoneIndex[dnsZoneKey]]!.outputs.resourceId.value
                }
              ]
            }
            subnetResourceId: subnetResourceId
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
