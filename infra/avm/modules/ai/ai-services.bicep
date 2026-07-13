// ============================================================================
// Module: Azure AI Services (Generic)
// Description: AVM wrapper for Cognitive Services — supports Content Safety,
//              Speech, Computer Vision, Document Intelligence, and others.
// AVM Module: avm/res/cognitive-services/account:0.14.2
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name prefix for the resource (e.g., cs, speech, cv, docintel).')
param namePrefix string

@description('The kind of Cognitive Service to deploy.')
@allowed([
  'ContentSafety'
  'SpeechServices'
  'ComputerVision'
  'FormRecognizer'
  'TextAnalytics'
  'TextTranslation'
  'Face'
  'OpenAI'
  'AIServices'
])
param kind string

@description('Optional. Override name for the resource. Defaults to {namePrefix}-{solutionName}.')
param name string = '${namePrefix}-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = false

@description('SKU for the Cognitive Services account.')
@allowed(['F0', 'S0', 'S1'])
param sku string = 'S0'

@description('Custom subdomain name for the account.')
param customSubDomainName string = ''

@description('Disable local (key-based) authentication.')
param disableLocalAuth bool = true

@description('Public network access setting.')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Enabled'

@description('Whether to enable private networking.')
param enablePrivateNetworking bool = false

@description('Diagnostic settings for monitoring.')
param diagnosticSettings array = []

@description('Optional. Role assignments for the resource.')
param roleAssignments array = []

@description('Optional. List of allowed FQDN.')
param allowedFqdnList array?

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

@description('Optional. Enable/Disable project management feature for AI Foundry.')
param allowProjectManagement bool?

import { privateEndpointSingleServiceType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. Configuration details for private endpoints. For security reasons, it is recommended to use private endpoints whenever possible.')
param privateEndpoints privateEndpointSingleServiceType[]?

var effectiveSubDomain = !empty(customSubDomainName) ? customSubDomainName : name

// ============================================================================
// AVM Module Deployment
// ============================================================================
module aiService 'br/public:avm/res/cognitive-services/account:0.14.2' = {
  name: take('avm.res.cognitive-services.${namePrefix}.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    kind: kind
    sku: sku
    customSubDomainName: effectiveSubDomain
    allowProjectManagement: allowProjectManagement
    disableLocalAuth: disableLocalAuth
    managedIdentities: managedIdentities
    publicNetworkAccess: publicNetworkAccess
    diagnosticSettings: !empty(diagnosticSettings) ? diagnosticSettings : []
    roleAssignments: !empty(roleAssignments) ? roleAssignments : []
    allowedFqdnList: allowedFqdnList
    networkAcls: {
      bypass: kind == 'OpenAI' || kind == 'AIServices' ? 'AzureServices' : null
      defaultAction: enablePrivateNetworking ? 'Deny' : 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    privateEndpoints: privateEndpoints
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Name of the AI Services account.')
output name string = aiService.outputs.name

@description('Resource ID of the AI Services account.')
output resourceId string = aiService.outputs.resourceId

@description('Endpoint of the AI Services account.')
output endpoint string = aiService.outputs.endpoint

@description('System-assigned identity principal ID.')
output identityPrincipalId string = aiService.outputs.?systemAssignedMIPrincipalId ?? ''
