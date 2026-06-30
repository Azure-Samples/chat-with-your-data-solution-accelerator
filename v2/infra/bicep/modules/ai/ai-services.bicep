// ============================================================================
// Module: Azure AI Services (Generic)
// Description: Deploys Cognitive Services — supports Content Safety,
//              Speech, Computer Vision, Document Intelligence, and others.
// API: Microsoft.CognitiveServices/accounts@2025-04-01
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

@description('Optional. Managed identity configuration for the resource.')
param identity object = { type: 'SystemAssigned' }

var effectiveSubDomain = !empty(customSubDomainName) ? customSubDomainName : name

// ============================================================================
// Resource
// ============================================================================
resource aiService 'Microsoft.CognitiveServices/accounts@2025-12-01' = {
  name: name
  location: location
  tags: tags
  kind: kind
  sku: {
    name: sku
  }
  identity: identity
  properties: {
    customSubDomainName: effectiveSubDomain
    publicNetworkAccess: publicNetworkAccess
    disableLocalAuth: disableLocalAuth
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Name of the AI Services account.')
output name string = aiService.name

@description('Resource ID of the AI Services account.')
output resourceId string = aiService.id

@description('Endpoint of the AI Services account.')
output endpoint string = aiService.properties.endpoint

@description('System-assigned identity principal ID.')
output identityPrincipalId string = aiService.identity.principalId
