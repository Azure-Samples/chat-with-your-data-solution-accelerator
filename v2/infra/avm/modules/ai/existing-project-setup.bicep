// ============================================================================
// Module: Existing AI Foundry Project Reference
// Description: References an existing AI Services account and project to
//              retrieve their identities. No deployments, no connections.
//              Use generic ai-foundry-connection and ai-foundry-model-deployment
//              modules for those concerns.
// ============================================================================

@description('Required. The name of the existing Cognitive Services account.')
param name string

@description('Required. The name of the existing AI project.')
param projectName string

// ============================================================================
// Existing Resource References
// ============================================================================
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: name
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' existing = {
  parent: aiServices
  name: projectName
}

// ============================================================================
// Outputs (aligned with ai-foundry-project.bicep)
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

@description('System-assigned identity principal ID of the AI Services account (empty if none).')
output principalId string = aiServices.identity.?principalId ?? ''

@description('Resource ID of the AI Foundry project.')
output projectResourceId string = aiProject.id

@description('Name of the AI Foundry project.')
output projectName string = aiProject.name

@description('AI Foundry project endpoint.')
output projectEndpoint string = aiProject.properties.endpoints['AI Foundry API']

@description('System-assigned identity principal ID of the project (empty if none).')
output projectIdentityPrincipalId string = aiProject.identity.?principalId ?? ''

