// ============================================================================
// Module: AI Foundry Project (Account + Project)
// Description: AVM wrapper for Azure AI Services account creation and
//              AI Foundry project provisioning. Generic, reusable across GSAs.
// AVM Module: avm/res/cognitive-services/account
// WAF: https://learn.microsoft.com/azure/well-architected/service-guides/azure-openai
// ============================================================================

@description('Required. Solution name suffix used to generate resource names.')
param solutionName string

@description('Optional. Override name for the AI Services account. Defaults to aif-{solutionName}.')
param name string = 'aif-${solutionName}'

@description('Optional. Override name for the AI Foundry project. Defaults to proj-{solutionName}.')
param projectName string = 'proj-${solutionName}'

@description('Required. Azure region for the resources.')
param location string

@description('Optional. Tags to apply to resources.')
param tags object = {}

@description('Optional. SKU name for the AI Services account.')
param skuName string = 'S0'

@description('Optional. Whether to disable local (key-based) authentication.')
param disableLocalAuth bool = true

@description('Optional. Whether to allow project management (AI Foundry hub).')
param allowProjectManagement bool = true

@description('Optional. Public network access setting.')
param publicNetworkAccess string = 'Enabled'

@description('Optional. Managed identity type for the resources.')
param identity object = { type: 'SystemAssigned' }

@description('Optional. Network ACLs default action.')
@allowed(['Allow', 'Deny'])
param networkAclsDefaultAction string = 'Allow'

@description('Optional. Array of deployments about cognitive service accounts to create.')
param deployments array?

// --- WAF: Monitoring ---
@description('Optional. Diagnostic settings for the resource.')
param diagnosticSettings array?

import { privateEndpointSingleServiceType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. Configuration details for private endpoints. For security reasons, it is recommended to use private endpoints whenever possible.')
param privateEndpoints privateEndpointSingleServiceType[]?

// --- WAF: Telemetry ---
@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// --- Role Assignments ---
@description('Optional. Array of role assignments to create on the AI Services account.')
param roleAssignments array?

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

// ============================================================================
// AI Services Account (AVM Module)
// ============================================================================
module aiServicesAccount 'br/public:avm/res/cognitive-services/account:0.14.2' = {
  name: take('avm.res.cognitive-services.account.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    sku: skuName
    kind: 'AIServices'
    disableLocalAuth: disableLocalAuth
    allowProjectManagement: allowProjectManagement
    customSubDomainName: name
    networkAcls: {
      defaultAction: networkAclsDefaultAction
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: publicNetworkAccess
    managedIdentities: managedIdentities
    diagnosticSettings: diagnosticSettings
    deployments: deployments
    roleAssignments: roleAssignments
    // Private endpoints deployed separately to avoid AccountProvisioningStateInvalid
    privateEndpoints: privateEndpoints
  }
}

// ============================================================================
// AI Foundry Project
// ============================================================================
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: name
  dependsOn: [aiServicesAccount]
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' = {
  parent: aiServices
  name: projectName
  location: location
  tags: tags
  kind: 'AIServices'
  identity: identity
  properties: {}
  dependsOn: [aiServicesAccount]
}

// ============================================================================
// Outputs
// ============================================================================

@description('Resource ID of the AI Services account.')
output resourceId string = aiServices.id

@description('Name of the AI Services account.')
output name string = aiServices.name

@description('Endpoint of the AI Services account (OpenAI Language Model Instance API).')
output endpoint string = aiServices.properties.endpoints['OpenAI Language Model Instance API']

@description('Endpoint of the AI Services account (Cognitive Services).')
output cognitiveServicesEndpoint string = aiServices.properties.endpoint

@description('Azure OpenAI Content Understanding endpoint URL.')
output azureOpenAiCuEndpoint string = aiServices.properties.endpoints['Content Understanding']

@description('System-assigned identity principal ID of the AI Services account.')
output principalId string = aiServices.identity.principalId

@description('Resource ID of the AI Foundry project.')
output projectResourceId string = aiProject.id

@description('Name of the AI Foundry project.')
output projectName string = aiProject.name

@description('AI Foundry project endpoint.')
output projectEndpoint string = aiProject.properties.endpoints['AI Foundry API']

@description('System-assigned identity principal ID of the project.')
output projectIdentityPrincipalId string = aiProject.identity.principalId
