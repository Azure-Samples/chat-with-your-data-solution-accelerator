param location string
param workspaceName string
param storageAccountId string
param keyVaultId string
param applicationInsightsId string
param azureAISearchName string
param azureAISearchEndpoint string
param azureOpenAIName string
param azureOpenAIEndpoint string

resource machineLearningWorkspace 'Microsoft.MachineLearningServices/workspaces@2023-06-01-preview' = {
  name: workspaceName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    storageAccount: storageAccountId
    keyVault: keyVaultId
    applicationInsights: applicationInsightsId
  }
}

resource aisearch_connection 'Microsoft.MachineLearningServices/workspaces/connections@2024-01-01-preview' = {
  parent: machineLearningWorkspace
  name: 'aisearch_connection'
  properties: {
    authType: 'ApiKey'
    credentials: {
      key: listAdminKeys(
        resourceId(
          subscription().subscriptionId,
          resourceGroup().name,
          'Microsoft.Search/searchServices',
          azureAISearchName
        ),
        '2023-11-01'
      ).primaryKey
    }
    category: 'CognitiveSearch'
    target: azureAISearchEndpoint
  }
}

var azureOpenAIId = resourceId(subscription().subscriptionId, resourceGroup().name, 'Microsoft.CognitiveServices/accounts', azureOpenAIName)

resource openai_connection 'Microsoft.MachineLearningServices/workspaces/connections@2024-01-01-preview' = {
  parent: machineLearningWorkspace
  name: 'openai_connection'
  properties: {
    authType: 'ApiKey'
    credentials: {
      key: listKeys(azureOpenAIId, '2023-05-01').key1
    }
    category: 'AzureOpenAI'
    target: azureOpenAIEndpoint
    metadata: {
      apiType: 'azure'
      resourceId: azureOpenAIId
    }
  }
}

output workspaceName string = machineLearningWorkspace.name