// ============================================================================
// Module: AI Foundry Project (Account + Project) — Vanilla Bicep
// Description: Creates an Azure AI Services account and AI Foundry project.
//              Generic, reusable across GSAs — no app-specific parameters.
// ============================================================================

targetScope = 'resourceGroup'

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
@allowed(['SystemAssigned', 'UserAssigned', 'SystemAssigned, UserAssigned', 'None'])
param identityType string = 'SystemAssigned'

@description('Optional. Network ACLs default action.')
@allowed(['Allow', 'Deny'])
param networkAclsDefaultAction string = 'Allow'

// ============================================================================
// AI Services Account
// ============================================================================
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  kind: 'AIServices'
  identity: {
    type: identityType
  }
  properties: {
    allowProjectManagement: allowProjectManagement
    customSubDomainName: name
    networkAcls: {
      defaultAction: networkAclsDefaultAction
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: publicNetworkAccess
    disableLocalAuth: disableLocalAuth
  }
}

// ============================================================================
// AI Foundry Project
// ============================================================================
resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' = {
  parent: aiServices
  name: projectName
  location: location
  kind: 'AIServices'
  identity: {
    type: identityType
  }
  properties: {}
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
