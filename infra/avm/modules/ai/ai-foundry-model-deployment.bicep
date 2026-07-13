// ============================================================================
// Module: Model Deployment
// Description: Deploys a single AI model to an existing AI Services account.
//              Called repetitively from main.bicep for each model in the array.
//              Generic, reusable across GSAs.
// ============================================================================

@description('Required. Name of the parent AI Services account.')
param aiServicesAccountName string

@description('Required. Name for this model deployment.')
param deploymentName string

@description('Optional. Model format (e.g., OpenAI).')
param modelFormat string = 'OpenAI'

@description('Required. Model name (e.g., gpt-4o, text-embedding-ada-002).')
param modelName string

@description('Optional. Model version. Empty string means latest.')
param modelVersion string = ''

@description('Optional. RAI policy name.')
param raiPolicyName string = 'Microsoft.Default'

@description('Required. SKU name (e.g., Standard, GlobalStandard).')
param skuName string

@description('Required. SKU capacity (tokens per minute in thousands).')
param skuCapacity int

// ============================================================================
// Model Deployment
// ============================================================================
resource aiServicesAccount 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: aiServicesAccountName
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-12-01' = {
  parent: aiServicesAccount
  name: deploymentName
  properties: {
    model: {
      format: modelFormat
      name: modelName
      version: !empty(modelVersion) ? modelVersion : null
    }
    raiPolicyName: raiPolicyName
  }
  sku: {
    name: skuName
    capacity: skuCapacity
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Name of the deployed model.')
output name string = modelDeployment.name

@description('Resource ID of the model deployment.')
output resourceId string = modelDeployment.id
