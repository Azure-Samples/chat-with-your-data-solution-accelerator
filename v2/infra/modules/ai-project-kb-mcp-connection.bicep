// ========================================================================
// Pillar:  Stable Core
// Phase:   4 (MACAE infra parity)
// Purpose: Foundry Project RemoteTool connection 'cwyd-kb-mcp'. This is
//          the connection MCPTool.project_connection_id points at; Foundry
//          runs knowledge-base retrieval server-side under the Project's
//          system identity using this connection's ProjectManagedIdentity
//          auth + the search.azure.com audience. It replaces the
//          CognitiveSearch connection for the KB MCP path -- the latter
//          carries no usable bearer on /knowledgebases/.../mcp and 401s
//          (BUG-0025 / BUG-0059).
//
//          Deployed only in databaseType=='cosmosdb' mode. In postgresql
//          mode the backend grounds over pgvector and has no KB MCP.
// ========================================================================

targetScope = 'resourceGroup'

@description('Required. Name of the parent AI Services account.')
param aiServicesAccountName string

@description('Required. Name of the Foundry Project (sub-resource of the account).')
param projectName string

@description('Required. Azure AI Search endpoint, e.g. https://<svc>.search.windows.net (no trailing slash).')
param searchEndpoint string

@description('Optional. Foundry IQ knowledge base name this connection fronts (matches SearchSettings.knowledge_base_name).')
param knowledgeBaseName string = 'cwyd-kb'

@description('Optional. KB MCP API version embedded in the connection target URL (matches SearchSettings.knowledge_base_api_version).')
param knowledgeBaseApiVersion string = '2025-11-01-preview'

@description('Optional. Friendly connection name. MUST match AZURE_AI_SEARCH_CONNECTION_NAME. Lower-case, 3-33 chars.')
param connectionName string = '${knowledgeBaseName}-mcp'

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  name: '${aiServicesAccountName}/${projectName}'
}

resource kbMcpConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: connectionName
  // any() is required: authType 'ProjectManagedIdentity' and the top-level
  // 'audience' are accepted by the ARM control plane at this api-version but
  // are not in the typed Bicep schema (mirrors the MACAE reusable
  // ai-foundry-connection module). The control plane validates the bag.
  properties: any({
    category: 'RemoteTool'
    target: '${searchEndpoint}/knowledgebases/${knowledgeBaseName}/mcp?api-version=${knowledgeBaseApiVersion}'
    authType: 'ProjectManagedIdentity'
    useWorkspaceManagedIdentity: true
    isSharedToAll: true
    audience: 'https://search.azure.com'
    metadata: {
      ApiType: 'Azure'
    }
  })
}

@description('Friendly name of the KB MCP connection. Flows to AZURE_AI_SEARCH_CONNECTION_NAME.')
output name string = kbMcpConnection.name

@description('Resource ID of the KB MCP connection.')
output resourceId string = kbMcpConnection.id
