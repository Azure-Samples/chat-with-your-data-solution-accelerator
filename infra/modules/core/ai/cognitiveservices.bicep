// ========== Cognitive Services (AVM + WAF aligned) Wrapper ========== //
metadata name = 'cognitiveservices'
metadata description = 'Wrapper for Azure Cognitive Services account with AVM + WAF aligned defaults: private access by default, explicit private endpoints or IP rules allowed, system-assigned identity enabled, local auth disabled, and diagnostics enabled.'

// -------- Parameters -------- //
@description('Name of the Cognitive Services account.')
param name string

@description('Location for the Cognitive Services account.')
param location string = resourceGroup().location

@description('Tags to apply to the resource.')
param tags object = {}

@description('Array of deployments for the Cognitive Services account.')
param deployments array = []

@description('Kind of Cognitive Services account (e.g., OpenAI, SpeechServices, ComputerVision, FormRecognizer, ContentSafety).')
param kind string = 'OpenAI'

@description('SKU name for the Cognitive Services account.')
@allowed(['S0', 'S1', 'S2', 'S3'])
param sku string = 'S0'

@description('Enable system-assigned managed identity.')
param managedIdentity bool = true

@description('Enable/disable public network access. Default is Disabled (WAF best practice).')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Disabled'

@description('Resource ID of Log Analytics workspace for diagnostics.')
param logAnalyticsWorkspaceId string = ''

@description('Enable private networking for the Cognitive Services account.')
param enablePrivateNetworking bool = false

@description('Subnet resource ID for private endpoints if private networking is enabled.')
param subnetResourceId string = ''

@description('Virtual Network resource ID for linking private DNS zones if private networking is enabled.')
param virtualNetworkResourceId string = ''

@description('Enable/disable wrapper telemetry.')
param enableTelemetry bool = true

// -------- Private DNS Zones -------- //
var cognitiveServicesSubResource = 'account'
var cognitiveServicesPrivateDnsZones = {
  'privatelink.cognitiveservices.azure.com': cognitiveServicesSubResource
  'privatelink.openai.azure.com': cognitiveServicesSubResource
  'privatelink.services.ai.azure.com': cognitiveServicesSubResource
}

module privateDnsZonesCognitiveServices 'br/public:avm/res/network/private-dns-zone:0.7.1' = [
  for zone in objectKeys(cognitiveServicesPrivateDnsZones): if (enablePrivateNetworking && !empty(virtualNetworkResourceId)) {
    name: take('avm.res.network.private-dns-zone.cognitiveservices.${uniqueString(name, zone)}', 64)
    params: {
      name: zone
      tags: tags
      enableTelemetry: enableTelemetry
      virtualNetworkLinks: [
        {
          name: 'dnslink-${replace(zone, '.', '-')}'
          virtualNetworkResourceId: virtualNetworkResourceId
        }
      ]
    }
  }
]

// -------- Build DNS Zone Group Configs -------- //
var privateDnsZoneGroupConfigs = [
  for zone in objectKeys(cognitiveServicesPrivateDnsZones): {
    name: replace(zone, '.', '-')
    privateDnsZoneResourceId: resourceId('Microsoft.Network/privateDnsZones', zone)
  }
]

// -------- Cognitive Services Account (AVM) -------- //
module cognitiveServices 'br/public:avm/res/cognitive-services/account:0.10.2' = {
  name: take('avm.res.cognitive-services.account.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    kind: kind
    sku: sku
    customSubDomainName: name
    publicNetworkAccess: publicNetworkAccess
    disableLocalAuth: true
    managedIdentities: {
      systemAssigned: managedIdentity
    }

    diagnosticSettings: empty(logAnalyticsWorkspaceId)
      ? []
      : [
          {
            workspaceResourceId: logAnalyticsWorkspaceId
          }
        ]

    // Private endpoints only if private networking enabled
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-${name}'
            customNetworkInterfaceName: 'nic-${name}'
            subnetResourceId: subnetResourceId
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: privateDnsZoneGroupConfigs
            }
          }
        ]
      : []

    deployments: deployments
  }
}

// -------- Outputs -------- //
output endpoint string = cognitiveServices.outputs.endpoint
output systemAssignedMIPrincipalId string = managedIdentity ? cognitiveServices.outputs.systemAssignedMIPrincipalId : ''
output resourceId string = cognitiveServices.outputs.resourceId
output name string = cognitiveServices.outputs.name
output location string = location
