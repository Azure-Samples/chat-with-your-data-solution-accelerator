@description('Required. The geo-location where the resource lives.')
param location string

@description('Required. The name of the machine learning workspace.')
param workspaceName string

@description('Required. The resource ID of the storage account associated with the workspace.')
param storageAccountId string

@description('Required. The resource ID of the application insights associated with the workspace.')
param applicationInsightsId string

@description('Optional. The name of the Azure AI Search service to connect to the workspace.')
param azureAISearchName string = ''

@description('Optional. The endpoint of the Azure AI Search service.')
param azureAISearchEndpoint string = ''

@description('Required. The name of the Azure OpenAI service to connect to the workspace.')
param azureOpenAIName string

@description('Required. The endpoint of the Azure OpenAI service.')
param azureOpenAIEndpoint string

@description('Optional. The SKU of the workspace.')
@allowed([
  'Basic'
  'Free'
  'Premium'
  'Standard'
])
param sku string = 'Standard'

@description('Optional. The tags to be applied to the workspace.')
param tags object = {}

@description('Optional. Enable telemetry via a Globally Unique Identifier (GUID).')
param enableTelemetry bool = true

@description('Optional. The settings for network isolation mode in workspace.')
param enablePrivateNetworking bool = false

@description('Optional. The resource ID of the Log Analytics workspace to which Diagnostic Logs should be sent.')
param logAnalyticsWorkspaceId string = ''

@description('Optional. Resource ID of the subnet to which private endpoints should be deployed.')
param subnetResourceId string = ''

@description('Optional. Resource IDs of the private DNS zones where private endpoints should be created.')
param privateDnsZoneResourceIds array = []

// Use the AVM module for Machine Learning Workspace
module workspace 'br/public:avm/res/machine-learning-services/workspace:0.3.0' = {
  name: 'avm-${workspaceName}-deployment'
  params: {
    // Required parameters
    name: workspaceName
    location: location
    associatedApplicationInsightsResourceId: applicationInsightsId
    associatedStorageAccountResourceId: storageAccountId
    sku: contains(['Basic', 'Standard'], sku) ? sku : 'Standard'

    // Optional parameters
    enableTelemetry: enableTelemetry
    tags: tags

    // Identity configuration
    managedIdentities: {
      systemAssigned: true
    }

    // Private networking configuration
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'

    // WAF aligned settings
    hbiWorkspace: !enableTelemetry // HBI workspace disables telemetry (WAF aligned)

    // Diagnostic settings
    diagnosticSettings: !empty(logAnalyticsWorkspaceId)
      ? [
          {
            name: '${workspaceName}-diagnostics'
            workspaceResourceId: logAnalyticsWorkspaceId
            logCategoriesAndGroups: [
              {
                category: 'AmlComputeClusterEvent'
              }
              {
                category: 'AmlComputeClusterNodeEvent'
              }
              {
                category: 'AmlComputeJobEvent'
              }
              {
                category: 'AmlComputeCpuGpuUtilization'
              }
              {
                category: 'AmlRunStatusChangedEvent'
              }
              {
                category: 'QuotaUtilization'
              }
            ]
            metricCategories: [
              {
                category: 'AllMetrics'
              }
            ]
          }
        ]
      : []

    // Private endpoints
    privateEndpoints: enablePrivateNetworking && !empty(subnetResourceId)
      ? [
          {
            name: '${workspaceName}-pe'
            subnetResourceId: subnetResourceId
            privateDnsZoneResourceIds: privateDnsZoneResourceIds
            groupIds: [
              'amlworkspace'
            ]
          }
        ]
      : []
  }
}

// Calculate Azure OpenAI resource ID
var azureOpenAIId = resourceId(
  subscription().subscriptionId,
  resourceGroup().name,
  'Microsoft.CognitiveServices/accounts',
  azureOpenAIName
)

// Create Azure OpenAI connection
resource openai_connection 'Microsoft.MachineLearningServices/workspaces/connections@2024-01-01-preview' = {
  name: '${workspaceName}/openai_connection'
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
  dependsOn: [
    workspace
  ]
}

// Create Azure AI Search connection if Azure AI Search is provided
resource aisearch_connection 'Microsoft.MachineLearningServices/workspaces/connections@2024-01-01-preview' = if (azureAISearchName != '') {
  name: '${workspaceName}/aisearch_connection'
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
  dependsOn: [
    workspace
  ]
}

// Outputs to maintain compatibility with the previous implementation
output workspaceName string = workspaceName
output workspaceId string = workspace.outputs.resourceId
output principalId string = workspace.outputs.systemAssignedMIPrincipalId
