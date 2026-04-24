// ========================================================================
// Pillar:  Stable Core
// Phase:   1 (Infrastructure + Project Skeleton)
// Purpose: Microsoft Foundry Project — child of an AI Services account
//          with `allowProjectManagement=true`. The Project endpoint is
//          what the Agent Framework orchestrator (and Foundry IQ
//          knowledge bases) bind to. The same parent account also
//          serves the OpenAI-compatible endpoint used by LangGraph, so
//          a single Project supports BOTH orchestrators.
//
//          Adapted from Microsoft Multi-Agent Custom Automation Engine
//          (read-only architectural reference). No AVM module exists
//          for projects/connections at the time of writing, so we
//          declare the raw resources here.
// ========================================================================

targetScope = 'resourceGroup'

@description('Required. Name of the parent AI Services account.')
param aiServicesAccountName string

@description('Required. Name of the Foundry Project (sub-resource of the account).')
param projectName string

@description('Required. Azure region; must match the parent account.')
param location string

@description('Optional. Display name shown in the Foundry portal.')
param projectDisplayName string = projectName

@description('Optional. Description shown in the Foundry portal.')
param projectDescription string = 'CWYD v2 Foundry project. Hosts agents (Agent Framework) and knowledge bases (Foundry IQ).'

@description('Optional. Tags applied to the Project.')
param tags object = {}

@description('Required. Principal ID of the user-assigned managed identity that consumes the Project.')
param uamiPrincipalId string

// Reference (not (re)deploy) the parent account so this module can be
// invoked after the account exists without taking a hard dependency on
// the AVM module's internal symbol layout.
resource aiServicesAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiServicesAccountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiServicesAccount
  name: projectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: projectDisplayName
    description: projectDescription
  }
}

// Azure AI User on the Project scope so the workload identity can read
// the Project, list agents/knowledge bases, and invoke them. The same
// role is also granted on the account scope (in main.bicep) so the
// OpenAI-compatible endpoint works for the LangGraph orchestrator.
resource projectAiUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: project
  name: guid(project.id, uamiPrincipalId, '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  properties: {
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
    // Azure AI User
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '53ca6127-db72-4b80-b1b0-d745d6d5456d'
    )
  }
}

@description('Resource ID of the Foundry Project.')
output resourceId string = project.id

@description('Name of the Foundry Project.')
output name string = project.name

@description('Foundry Project endpoint URL (used by Agent Framework + Foundry IQ).')
output projectEndpoint string = 'https://${aiServicesAccount.name}.services.ai.azure.com/api/projects/${project.name}'

@description('System-assigned principal ID of the Project (used to grant the Project access to downstream data sources).')
output projectPrincipalId string = project.identity.principalId
