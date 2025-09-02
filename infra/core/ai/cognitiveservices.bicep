metadata name = 'cognitiveservices'
metadata description = 'Creates an Azure Cognitive Services instance with AVM + WAF aligned defaults: private access by default, explicit private endpoints or IP rules allowed, and system-assigned identity enabled.'

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

@description('Kind of Cognitive Services account (e.g., OpenAI, SpeechServices, etc.).')
param kind string = 'OpenAI'

@description('Enable or disable public network access.')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Disabled'

@description('The SKU configuration (name and capacity).')
param sku object = {
  name: 'S0'
  capacity: 1
}

@description('Whether to enable managed identity (system-assigned).')
param managedIdentity bool = true

@description('Optional array of allowed IP rules.')
param allowedIpRules array = []

@description('Optional array of private endpoint configurations.')
param privateEndpoints array = []

@description('Resource ID of a Log Analytics workspace for diagnostics (leave blank to disable).')
param logAnalyticsWorkspaceId string = ''

// Configure network ACLs: deny by default, optionally allow IP rules when provided
param networkAcls object = empty(allowedIpRules)
  ? {
      defaultAction: 'Deny'
    }
  : {
      ipRules: allowedIpRules
      defaultAction: 'Deny'
    }

// Cognitive Services Account
resource account 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: name
  location: location
  tags: tags
  kind: kind
  properties: {
    customSubDomainName: customSubDomainName
    publicNetworkAccess: publicNetworkAccess
    networkAcls: networkAcls
  }
  sku: sku
  identity: {
    type: managedIdentity ? 'SystemAssigned' : 'None'
  }
}

// Deployments
@batchSize(1)
resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = [
  for deployment in deployments: {
    parent: account
    name: deployment.name
    properties: {
      model: deployment.model
      raiPolicyName: contains(deployment, 'raiPolicyName') ? deployment['raiPolicyName'] : null
    }
    sku: contains(deployment, 'sku')
      ? deployment['sku']
      : {
          name: 'Standard'
          capacity: 20
        }
  }
]

// Private Endpoints
resource privateEndpoint 'Microsoft.Network/privateEndpoints@2021-05-01' = [
  for pe in privateEndpoints: {
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
            privateLinkServiceId: account.id
            groupIds: [
              'account'
            ]
          }
        }
      ]
    }
  }
]

// Diagnostics
resource diagnostic 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: '${name}-diag'
  scope: account
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'Audit'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// Outputs
output endpoint string = account.properties.endpoint
output identityPrincipalId string = managedIdentity ? account.identity.principalId : ''
output id string = account.id
output name string = account.name
output location string = location
