// ========== Cognitive Services (AVM + WAF aligned) ========== //
metadata name = 'cognitiveservices'
metadata description = 'Creates an Azure Cognitive Services instance with AVM + WAF aligned defaults: private access by default, explicit private endpoints or IP rules allowed, system-assigned identity enabled, local auth disabled, and diagnostics enabled.'

// -------- Parameters -------- //
@description('Name of the Cognitive Services account.')
param name string

@description('Location for the Cognitive Services account.')
param location string = resourceGroup().location

@description('Tags to apply to the resource.')
param tags object = {}

@description('The custom subdomain name used to access the API. Defaults to the value of the name parameter.')
param customSubDomainName string = name

@description('Array of deployments for the Cognitive Services account.')
param deployments array = []

@description('Kind of Cognitive Services account (e.g., OpenAI, SpeechServices, AIServices).')
param kind string = 'OpenAI'

@description('Enable or disable public network access. Default is Disabled (WAF best practice).')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Disabled'

@description('The SKU (tier).')
@allowed(['S0', 'S1', 'S2', 'S3'])
param sku string = 'S0'

@description('Whether to enable system-assigned managed identity.')
param managedIdentity bool = true

@description('Disable local key-based auth (WAF best practice).')
param disableLocalAuth bool = true

@description('Enable or disable telemetry.')
param enableTelemetry bool = true

@description('Resource ID of a Log Analytics workspace for diagnostics (leave blank to disable).')
param logAnalyticsWorkspaceId string = ''

@description('Enable private endpoints by linking to a virtual network.')
param virtualNetworkEnabled bool = false

@description('Subnet resource ID to use when creating private endpoints.')
param subnetResourceId string = ''

@description('Virtual Network resource ID (parent VNet) to link private DNS zones. Must be provided when virtualNetworkEnabled is true.')
param virtualNetworkResourceId string = ''

// --------- Private DNS Zones --------- //
var cognitiveServicesSubResource = 'account'
var cognitiveServicesPrivateDnsZones = {
  'privatelink.cognitiveservices.azure.com': cognitiveServicesSubResource
  'privatelink.openai.azure.com': cognitiveServicesSubResource
  'privatelink.services.ai.azure.com': cognitiveServicesSubResource
}

module privateDnsZonesCognitiveServices 'br/public:avm/res/network/private-dns-zone:0.7.1' = [
  for zone in objectKeys(cognitiveServicesPrivateDnsZones): if (virtualNetworkEnabled && !empty(virtualNetworkResourceId)) {
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

// --------- Build DNS Zone Group Configs (fix for BCP138) --------- //
var privateDnsZoneGroupConfigs = [
  for zone in objectKeys(cognitiveServicesPrivateDnsZones): {
    name: replace(zone, '.', '-')
    privateDnsZoneResourceId: resourceId('Microsoft.Network/privateDnsZones', zone)
  }
]

// --------- Cognitive Services Account (AVM) --------- //
module cognitiveServices 'br/public:avm/res/cognitive-services/account:0.10.2' = {
  name: take('avm.res.cognitive-services.account.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    kind: kind
    sku: sku
    customSubDomainName: customSubDomainName
    publicNetworkAccess: publicNetworkAccess
    disableLocalAuth: disableLocalAuth
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

    privateEndpoints: virtualNetworkEnabled
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

// --------- Outputs --------- //
output endpoint string = cognitiveServices.outputs.endpoint
output systemAssignedMIPrincipalId string = managedIdentity ? cognitiveServices.outputs.systemAssignedMIPrincipalId : ''
output resourceId string = cognitiveServices.outputs.resourceId
output name string = cognitiveServices.outputs.name
output location string = location
