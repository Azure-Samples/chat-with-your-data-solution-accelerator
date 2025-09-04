// ========== Cognitive Services (AVM + WAF aligned, Cosmos-style, dynamic DNS) ========== //
param name string
param location string
param tags object = {}
param enableTelemetry bool = true
param enableMonitoring bool = false
param logAnalyticsWorkspaceId string = ''
param enablePrivateNetworking bool = false
param subnetResourceId string = 'null'
param avmPrivateDnsZones array = []
param dnsZoneIndex object = {}
param managedIdentity bool = true
param kind string = 'OpenAI'
@allowed(['S0', 'S1', 'S2', 'S3'])
param sku string = 'S0'
param deployments array = []

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
    customSubDomainName: name
    disableLocalAuth: true

    managedIdentities: {
      systemAssigned: managedIdentity
    }

    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceId }] : null

    networkAcls: enablePrivateNetworking ? { defaultAction: 'Deny', publicNetworkAccess: 'Disabled' } : { defaultAction: 'Allow', publicNetworkAccess: 'Enabled' }

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
output endpoint string = cognitiveServices.outputs.endpoint
output resourceId string = cognitiveServices.outputs.resourceId
output name string = cognitiveServices.outputs.name
output location string = location
var systemAssignedMIPrincipalIdValue = contains(cognitiveServices.outputs, 'systemAssignedMIPrincipalId') ? cognitiveServices.outputs.systemAssignedMIPrincipalId : ''
output systemAssignedMIPrincipalId string = string(systemAssignedMIPrincipalIdValue)
