// ============================================================================
// main.bicep — Orchestrator
// Description: Pure orchestrator for Chat With Your Data V2.
//              All resource names are derived from params — no hardcoded names.
//              This file only calls modules; no inline resource definitions.
//              Supports WAF-aligned deployment via feature flags.
// ============================================================================
targetScope = 'resourceGroup'

// ============================================================================
// Parameters — Core
// ============================================================================

@minLength(3)
@maxLength(15)
@description('Required. Unique application/solution name. Drives every resource name. Cap is 15 chars to keep PostgreSQL Flexible Server names within limits.')
param solutionName string = 'cwyd'

@maxLength(5)
@description('Optional. Short unique suffix appended to global resource names. Defaults to a 5-char hash of subscription + RG + solution name.')
param solutionUniqueText string = take(uniqueString(subscription().id, resourceGroup().name, solutionName), 5)

@description('Required. Azure region for non-AI resources (Container Apps, App Service, Functions, Storage, Cosmos/Postgres). Restricted to the 4 regions where ALL three redundancy guarantees hold simultaneously: PostgreSQL Flexible Server ZoneRedundant HA (3 AZs), Cosmos DB automatic failover with paired-region replicas, and Storage GZRS. Independent of azureAiServiceLocation, which selects the model-availability region. Source: https://learn.microsoft.com/azure/reliability/regions-list and https://learn.microsoft.com/azure/postgresql/flexible-server/overview#azure-regions')
param location string

@description('Required. Region for AI Services / Foundry deployments. Restricted to regions with GPT-5.1 GlobalStandard availability.')
param azureAiServiceLocation string

// ============================================================================
// Parameters — Database & Ingestion
// ============================================================================

@description('Required. Selects BOTH the chat-history backend AND the vector index store. CosmosDB: Cosmos DB + Azure AI Search. PostgreSQL: PostgreSQL Flexible Server with pgvector (Azure AI Search is NOT deployed). Locked at deploy time.')
param databaseType string = 'cosmosdb'

@description('Optional. How an uploaded document is picked up for indexing. direct_enqueue: the backend admin upload enqueues the doc-processing message itself (works without an Event Grid subscription). event_grid: a storage Event Grid subscription fans BlobCreated/BlobDeleted to the blob-events queue and the blob_event Function translates each (create -> ingest, delete -> de-index), so the backend writes the blob only (no double-ingest). Flip to event_grid only after the blob_event Function blueprint is deployed.')
param ingestionTrigger string = 'direct_enqueue'

// ============================================================================
// Parameters — AI Configuration
// ============================================================================

@minLength(1)
@description('Optional. Primary chat model deployment name.')
param gptModelName string = 'gpt-5.4-mini'

@description('Optional. Primary chat model version.')
param gptModelVersion string = '2026-03-17'

@description('Optional. SKU for the primary chat model deployment.')
param gptModelDeploymentType string = 'GlobalStandard'

@minValue(1)
@description('Optional. Token capacity (thousands of TPM) for the primary chat model.')
param gptModelCapacity int = 50

@minLength(1)
@description('Optional. Reasoning model deployment name (surfaced via the SSE reasoning channel).')
param reasoningModelName string = 'gpt-5-mini'

@description('Optional. Reasoning model version.')
param reasoningModelVersion string = '2025-08-07'

@description('Optional. SKU for the reasoning model deployment.')
param reasoningModelDeploymentType string = 'GlobalStandard'

@minValue(1)
@description('Optional. Token capacity for the reasoning model.')
param reasoningModelCapacity int = 50

@minLength(1)
@description('Optional. Embedding model deployment name (used by Foundry IQ and the LangGraph indexer).')
param embeddingModelName string = 'text-embedding-3-large'

@description('Optional. Embedding model version.')
param embeddingModelVersion string = '1'

@description('Optional. SKU for the embedding model deployment.')
param embeddingModelDeploymentType string = 'Standard'

@minValue(1)
@description('Optional. Token capacity for the embedding model.')
param embeddingModelCapacity int = 100

@description('Optional. Azure OpenAI API version exposed via the OpenAI-compatible endpoint (used by the LangGraph orchestrator).')
param azureOpenAiApiVersion string = '2025-01-01-preview'

@description('Optional. Azure AI Agent API version (used by the Agent Framework orchestrator).')
param azureAiAgentApiVersion string = '2025-05-01'

@description('Optional. Foundry IQ knowledge base name the agent_framework orchestrator grounds on (cosmosdb mode). Must match the name seeded by post_provision.py and resolved through the Project-Search connection.')
param searchKnowledgeBaseName string = 'cwyd-kb'

@description('Optional. Foundry IQ knowledge source name backing the knowledge base (the search-index knowledge source seeded by post_provision.py).')
param searchKnowledgeSourceName string = 'cwyd-index-ks'

@description('Optional. Chat index name the azure_search provider reads/writes and post_provision.py creates. Single-sourced so the backend env binding and the azd output (consumed by the postdeploy seed self-check) cannot diverge.')
param searchIndexName string = 'cwyd-index'

@description('Optional. Foundry IQ knowledge base / knowledge source REST API version (operator-tunable so the KB protocol can advance without a new image).')
param searchKnowledgeBaseApiVersion string = '2025-11-01-preview'

// ============================================================================
// Parameters — Existing Resources
// ============================================================================

@description('Optional. Resource ID of an existing Log Analytics workspace. Empty creates a new one.')
param existingLogAnalyticsWorkspaceId string = ''

@description('Optional. Resource ID of an existing AI Foundry project. Empty creates a new one.')
param existingFoundryProjectResourceId string = ''

// ============================================================================
// Parameters — WAF Flags
// ============================================================================

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Optional. Deploy Log Analytics + Application Insights and wire diagnostic settings on every applicable resource.')
param enableMonitoring bool = false

@description('Optional. Higher SKUs and autoscaling on App Service Plan, Container Apps, Search, and PostgreSQL.')
param enableScalability bool = false

@description('Optional. Zone-redundant + paired-region failover on databases, App Service Plan, Container Apps, and Storage.')
param enableRedundancy bool = false

@description('Optional. Deploy a VNet, private endpoints, and disable public network access on data-plane resources. Wires the regional VNet (`modules/virtualNetwork.bicep`), private DNS zones, private endpoints for every data-plane resource, regional VNet integration for compute, and Bastion. Setting this to true is the WAF-aligned topology and requires no follow-up tasks; flipping it back to false re-enables public endpoints with default firewall rules.')
param enablePrivateNetworking bool = false

// ============================================================================
// Parameters — AVM-specific (ignored when deploymentFlavor = 'bicep')
// ============================================================================

@secure()
@description('Optional. VM admin username (AVM-WAF only, when private networking is enabled).')
param vmAdminUsername string?

@secure()
@description('Optional. VM admin password (AVM-WAF only, when private networking is enabled).')
param vmAdminPassword string?

@description('Optional. VM size for jumpbox (AVM-WAF only). Defaults to Standard_D2s_v5.')
param vmSize string = 'Standard_D2s_v5'

// ===================== //
// Tagging               //
// ===================== //

@description('Optional. Tags applied to every deployed resource.')
param tags object = {}

@description('Optional. Identifier of the user creating the deployment, recorded in the resource group tags.')
param createdBy string?

@allowed(['User', 'ServicePrincipal'])
@description('Optional. Principal type of the deploying user.')
param deployingUserPrincipalType string = 'User'

// ===================== //
// Variables             //
// ===================== //

var solutionSuffix = toLower(trim(replace(
  replace(
    replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''),
    ' ',
    ''
  ),
  '*',
  '')))

var deployingUserPrincipalId = deployer().objectId
var useExistingAIProject = !empty(existingFoundryProjectResourceId)
var isCosmos = databaseType == 'cosmosdb'
var docProcessingQueueName = 'doc-processing'
var blobEventsQueueName = 'blob-events'
var documentsContainerName = 'documents'
var sampleContainerImage = 'mcr.microsoft.com/k8se/quickstart:latest'

var allTags = union(
  {
    'azd-env-name': solutionName
    TemplateName: 'CWYD-v2'
    Type: enablePrivateNetworking ? 'WAF' : 'Non-WAF'
    CreatedBy: createdBy
    DatabaseType: databaseType
  },
  tags
)

// Region pairs list based on article in [Azure Database for MySQL Flexible Server - Azure Regions](https://learn.microsoft.com/azure/mysql/flexible-server/overview#azure-regions) for supported high availability regions for CosmosDB.
var cosmosDbZoneRedundantHaRegionPairs = {
  australiaeast: 'uksouth'
  centralus: 'eastus2'
  eastasia: 'southeastasia'
  eastus: 'centralus'
  eastus2: 'centralus'
  japaneast: 'australiaeast'
  northeurope: 'westeurope'
  southeastasia: 'eastasia'
  uksouth: 'westeurope'
  westeurope: 'northeurope'
}
// Paired location calculated based on 'location' parameter. This location will be used by applicable resources if `enableScalability` is set to `true`
var cosmosDbHaLocation = cosmosDbZoneRedundantHaRegionPairs[location]

// Replica regions list based on article in [Azure regions list](https://learn.microsoft.com/azure/reliability/regions-list) and [Enhance resilience by replicating your Log Analytics workspace across regions](https://learn.microsoft.com/azure/azure-monitor/logs/workspace-replication#supported-regions) for supported regions for Log Analytics Workspace.
var replicaRegionPairs = {
  australiaeast: 'australiasoutheast'
  centralus: 'westus'
  eastasia: 'japaneast'
  eastus: 'centralus'
  eastus2: 'centralus'
  japaneast: 'eastasia'
  northeurope: 'westeurope'
  southeastasia: 'eastasia'
  uksouth: 'westeurope'
  westeurope: 'northeurope'
}
var replicaLocation = replicaRegionPairs[location]

// WAF: Diagnostic settings helper — reused across modules
var monitoringDiagnosticSettings = enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : []

var privateDnsZones = [
  'privatelink.cognitiveservices.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.services.ai.azure.com'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.queue.${environment().suffixes.storage}'
  'privatelink.file.${environment().suffixes.storage}'
  'privatelink.documents.azure.com'
  'privatelink.postgres.database.azure.com'
  'privatelink.azurecr.io'
]

var dnsZoneIndex = {
  cognitiveServices: 0
  openAI: 1
  aiServicesProject: 2
  blob: 3
  queue: 4
  file: 5
  cosmosDb: 6
  postgres: 7
  containerRegistry: 8
}

var aiModelDeployments = [
  {
    name: gptModelName
    model: {
      format: 'OpenAI'
      name: gptModelName
      version: gptModelVersion
    }
    sku: {
      name: gptModelDeploymentType
      capacity: gptModelCapacity
    }
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  {
    name: reasoningModelName
    model: {
      format: 'OpenAI'
      name: reasoningModelName
      version: reasoningModelVersion
    }
    sku: {
      name: reasoningModelDeploymentType
      capacity: reasoningModelCapacity
    }
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  {
    name: embeddingModelName
    model: {
      format: 'OpenAI'
      name: embeddingModelName
      version: embeddingModelVersion
    }
    sku: {
      name: embeddingModelDeploymentType
      capacity: embeddingModelCapacity
    }
    raiPolicyName: 'Microsoft.DefaultV2'
  }
]

// ===================== //
// Resources             //
// ===================== //

resource resourceGroupTags 'Microsoft.Resources/tags@2025-04-01' = {
  name: 'default'
  properties: {
    tags: union(resourceGroup().tags ?? {}, allTags)
  }
}

// ========== Managed Identity ========== //
module userAssignedIdentity './modules/identity/managed-identity.bicep' = {
  name: take('module.managed-identity.user-assigned-identity.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    enableTelemetry: enableTelemetry
  }
}

#disable-next-line no-deployments-resources
resource avmTelemetry 'Microsoft.Resources/deployments@2024-03-01' = if (enableTelemetry) {
  name: '46d3xbcp.ptn.sa-chatwithyourdata.${replace('-..--..-', '.', '-')}.${substring(uniqueString(deployment().name, location), 0, 4)}'
  properties: {
    mode: 'Incremental'
    template: {
      '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#'
      contentVersion: '1.0.0.0'
      resources: []
      outputs: {
        telemetry: {
          type: 'String'
          value: 'For more information, see https://aka.ms/avm/TelemetryInfo'
        }
      }
    }
  }
}

// ============================================================================
// Module: Monitoring
// ============================================================================

var useExistingLogAnalytics = !empty(existingLogAnalyticsWorkspaceId)

// Existing workspace reference (for cross-subscription support)
resource existingLogAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2025-07-01' existing = if (useExistingLogAnalytics) {
  name: split(existingLogAnalyticsWorkspaceId, '/')[8]
  scope: resourceGroup(split(existingLogAnalyticsWorkspaceId, '/')[2], split(existingLogAnalyticsWorkspaceId, '/')[4])
}

module logAnalyticsWorkspace './modules/monitoring/log-analytics.bicep' = if (enableMonitoring && !useExistingLogAnalytics) {
  name: take('module.log-analytics.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    enableTelemetry: enableTelemetry
    retentionInDays: enableRedundancy ? 90 : 30
    publicNetworkAccessForIngestion: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    publicNetworkAccessForQuery: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    enableReplication: enableRedundancy
    replicationLocation: replicaLocation
    dailyQuotaGb: enableRedundancy ? '10' : ''
    dataSources: enablePrivateNetworking
      ? [
          {
            tags: tags
            eventLogName: 'Application'
            eventTypes: [
              {
                eventType: 'Error'
              }
              {
                eventType: 'Warning'
              }
              {
                eventType: 'Information'
              }
            ]
            kind: 'WindowsEvent'
            name: 'applicationEvent'
          }
          {
            counterName: '% Processor Time'
            instanceName: '*'
            intervalSeconds: 60
            kind: 'WindowsPerformanceCounter'
            name: 'windowsPerfCounter1'
            objectName: 'Processor'
          }
          {
            kind: 'IISLogs'
            name: 'sampleIISLog1'
            state: 'OnPremiseEnabled'
          }
        ]
      : null
  }
}

// Resolve workspace resource ID and name — existing or new
var logAnalyticsWorkspaceResourceId = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspace.id
  : (enableMonitoring ? logAnalyticsWorkspace!.outputs.resourceId : '')
var logAnalyticsWorkspaceName = useExistingLogAnalytics
  ? split(existingLogAnalyticsWorkspaceId, '/')[8]
  : (enableMonitoring ? logAnalyticsWorkspace!.outputs.name : '')

module applicationInsights './modules/monitoring/app-insights.bicep' = if (enableMonitoring) {
  name: take('module.app-insights.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    enableTelemetry: enableTelemetry
    workspaceResourceId: logAnalyticsWorkspaceResourceId
  }
}

// ============================================================================
// Module: Networking (WAF — conditional on enablePrivateNetworking)
// ============================================================================

module virtualNetwork './modules/networking/virtual-network.bicep' = if (enablePrivateNetworking) {
  name: take('module.virtualNetwork.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    addressPrefixes: ['10.0.0.0/20'] // 4096 addresses (enough for 8 /23 subnets or 16 /24)
    logAnalyticsWorkspaceId: (enableMonitoring || useExistingLogAnalytics) ? logAnalyticsWorkspaceResourceId : ''
    resourceSuffix: solutionSuffix
    enableTelemetry: enableTelemetry
  }
}

// Bastion Host — secure access to jumpbox VM
module bastionHost './modules/networking/bastion-host.bicep' = if (enablePrivateNetworking) {
  name: take('module.bastion-host.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    enableTelemetry: enableTelemetry
    skuName: 'Standard'
    virtualNetworkResourceId: virtualNetwork!.outputs.resourceId
    publicIPDiagnosticSettings: monitoringDiagnosticSettings
    diagnosticSettings: monitoringDiagnosticSettings
  }
}


// WAF: Maintenance Configuration for VM patching
module maintenanceConfiguration './modules/compute/maintenance-configuration.bicep' = if (enablePrivateNetworking) {
  name: take('module.maintenance-configuration.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// WAF: Data Collection Rules for VM monitoring
var dataCollectionRulesLocation = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspace!.location
  : (enableMonitoring ? logAnalyticsWorkspace!.outputs.location : location)
module windowsVmDataCollectionRules './modules/monitoring/data-collection-rule.bicep' = if (enablePrivateNetworking && enableMonitoring) {
  name: take('module.data-collection-rule.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: dataCollectionRulesLocation
    tags: tags
    enableTelemetry: enableTelemetry
    logAnalyticsWorkspaceResourceId: logAnalyticsWorkspaceResourceId
  }
}

// WAF: Proximity Placement Group for VM
var virtualMachineAvailabilityZone = 1
module proximityPlacementGroup './modules/compute/proximity-placement-group.bicep' = if (enablePrivateNetworking) {
  name: take('module.proximity-placement-group.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    availabilityZone: virtualMachineAvailabilityZone
    vmSizes: [vmSize]
  }
}

// Jumpbox VM — administration access when private networking is enabled
module jumpboxVM './modules/compute/virtual-machine.bicep' = if (enablePrivateNetworking) {
  name: take('module.virtual-machine.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    imageReference: {
      offer: 'WindowsServer'
      publisher: 'MicrosoftWindowsServer'
      sku: '2019-datacenter'
      version: 'latest'
    }
    vmSize: vmSize
    availabilityZone: virtualMachineAvailabilityZone
    adminUsername: vmAdminUsername ?? 'testvmuser'
    adminPassword: vmAdminPassword ?? 'Vm!${uniqueString(subscription().subscriptionId, solutionName)}${guid(subscription().subscriptionId, solutionName, 'vm-admin-password')}'
    subnetResourceId: virtualNetwork!.outputs.administrationSubnetResourceId
    deployingUserPrincipalId: deployingUserPrincipalId
    deployingUserPrincipalType: deployingUserPrincipalType
    roleAssignments: [
      {
        roleDefinitionIdOrName: '1c0163c0-47e6-4577-8991-ea5c82e286e4' // Virtual Machine Administrator Login
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
    ]
    diagnosticSettings: monitoringDiagnosticSettings
    maintenanceConfigurationResourceId: maintenanceConfiguration!.outputs.resourceId
    proximityPlacementGroupResourceId: proximityPlacementGroup!.outputs.resourceId
    extensionMonitoringAgentConfig: enableMonitoring ? {
      dataCollectionRuleAssociations: [
        {
          dataCollectionRuleResourceId: windowsVmDataCollectionRules!.outputs.resourceId
          name: 'send-${logAnalyticsWorkspaceName}'
        }
      ]
      enabled: true
      tags: allTags
    } : null
  }
}


@batchSize(5)
module privateDnsZoneDeployments './modules/networking/private-dns-zone.bicep' = [
  for (zone, i) in privateDnsZones: if (enablePrivateNetworking) {
    name: take('module.private-dns-zone.${split(zone, '.')[1]}.${solutionName}', 64)
    params: {
      name: zone
      tags: allTags
      enableTelemetry: enableTelemetry
      virtualNetworkLinks: [
        {
          name: take('vnetlink-${virtualNetwork!.outputs.name}-${split(zone, '.')[1]}', 80)
          virtualNetworkResourceId: virtualNetwork!.outputs.resourceId
        }
      ]
    }
  }
]

// ============================================================================
// Module: AI Services (conditional — skip if using existing project)
// ============================================================================

// ========== Existing AI Foundry reference (for cross-subscription support when using existing project) ========== //
var aiFoundryResourceGroupName = useExistingAIProject
  ? split(existingFoundryProjectResourceId, '/')[4]
  : resourceGroup().name
var aiFoundrySubscriptionId = useExistingAIProject
  ? split(existingFoundryProjectResourceId, '/')[2]
  : subscription().subscriptionId
var aiFoundryResourceName = useExistingAIProject
  ? split(existingFoundryProjectResourceId, '/')[8]
  : aiProject!.outputs.name
var aiProjectResourceName = useExistingAIProject
  ? (length(split(existingFoundryProjectResourceId, '/')) > 10 ? split(existingFoundryProjectResourceId, '/')[10] : '')
  : aiProject!.outputs.projectName

// ========== Reference existing AI Foundry project (identity only) ========== //
module existingAIProject './modules/ai/existing-project-setup.bicep' = if (useExistingAIProject) {
  name: take('module.existing-project-setup.${solutionName}', 64)
  scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
  params: {
    name: aiFoundryResourceName
    projectName: aiProjectResourceName
  }
}

module aiProject './modules/ai/ai-foundry-project.bicep' = if (!useExistingAIProject) {
  name: take('module.ai-foundry-project.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: azureAiServiceLocation
    tags: allTags
    enableTelemetry: enableTelemetry
    disableLocalAuth: true
    diagnosticSettings: monitoringDiagnosticSettings
  }
}

// ========== AI outputs (ternary: existing vs new) ========== //
var aiFoundryEndpoint = useExistingAIProject ? existingAIProject!.outputs.endpoint : aiProject!.outputs.endpoint
var aiCognitiveServicesEndpoint = useExistingAIProject ? existingAIProject!.outputs.cognitiveServicesEndpoint : aiProject!.outputs.cognitiveServicesEndpoint
var projectEndpoint = useExistingAIProject ? existingAIProject!.outputs.projectEndpoint : aiProject!.outputs.projectEndpoint
var aiFoundryResourceId = useExistingAIProject ? existingAIProject!.outputs.resourceId : aiProject!.outputs.resourceId
var aiProjectPrincipalId = useExistingAIProject ? existingAIProject!.outputs.projectIdentityPrincipalId : aiProject!.outputs.projectIdentityPrincipalId
var aiFoundryPrincipalId = useExistingAIProject ? existingAIProject!.outputs.principalId : aiProject!.outputs.principalId

// ========== Model deployments (single loop for both existing and new paths) ========== //
@batchSize(1)
module model_deployments './modules/ai/ai-foundry-model-deployment.bicep' = [for (deployment, i) in aiModelDeployments: {
  name: take('module.model-deployment-${i}.${solutionName}', 64)
  scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
  params: {
    aiServicesAccountName: aiFoundryResourceName
    deploymentName: deployment.name
    modelName: deployment.model.name
    modelVersion: deployment.model.version
    raiPolicyName: deployment.raiPolicyName
    skuName: deployment.sku.name
    skuCapacity: deployment.sku.capacity
  }
}]

// ========== Separate PE for AI Foundry to avoid AccountProvisioningStateInvalid race condition ========== //
module aiProjectPrivateEndpoint './modules/networking/private-endpoint.bicep' = if (!useExistingAIProject && enablePrivateNetworking) {
  name: take('module.pe-ai-foundry.${solutionName}', 64)
  dependsOn: [privateDnsZoneDeployments]
  params: {
    name: 'pep-aif-${solutionSuffix}'
    location: location
    tags: allTags
    customNetworkInterfaceName: 'nic-aif-${solutionSuffix}'
    subnetResourceId: virtualNetwork!.outputs.backendSubnetResourceId
    privateLinkServiceConnections: [
      {
        name: 'pep-aif-${solutionSuffix}-connection'
        properties: {
          privateLinkServiceId: aiFoundryResourceId
          groupIds: ['account']
        }
      }
    ]
    privateDnsZoneGroup: {
      privateDnsZoneGroupConfigs: [
        {
          name: 'cognitiveservices'
          privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
        }
        {
          name: 'openai'
          privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.openAI]!.outputs.resourceId
        }
        {
          name: 'aiServicesProject'
          privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.aiServicesProject]!.outputs.resourceId
        }
      ]
    }
  }
}

module speechService './modules/ai/ai-services.bicep' = {
  name: take('module.ai-services.SpeechServices.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    namePrefix: 'spch'
    customSubDomainName: 'spch${uniqueString(resourceGroup().id, solutionSuffix, 'SpeechServices')}'
    location: azureAiServiceLocation
    tags: allTags
    enableTelemetry: enableTelemetry
    kind: 'SpeechServices'
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Cognitive Services Speech User — data-plane role for STS
        roleDefinitionIdOrName: 'f2dc8367-1007-4938-bd23-fe263f013447'
      }
    ]
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-spch-${solutionSuffix}'
            customNetworkInterfaceName: 'nic-spch-${solutionSuffix}'
            subnetResourceId: virtualNetwork!.outputs.backendSubnetResourceId
            service: 'account'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'cognitiveservices'
                  privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
                }
              ]
            }
          }
        ]
      : []
  }
}

module contentSafety './modules/ai/ai-services.bicep' = {
  name: take('module.ai-services.ContentSafety.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    namePrefix: 'cs'
    customSubDomainName: 'cs${uniqueString(resourceGroup().id, solutionSuffix, 'ContentSafety')}'
    location: azureAiServiceLocation
    tags: allTags
    enableTelemetry: false
    kind: 'ContentSafety'
    disableLocalAuth: true
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Cognitive Services User — data-plane role for the AnalyzeText
        roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908'
      }
    ]
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-cs-${solutionSuffix}'
            customNetworkInterfaceName: 'nic-cs-${solutionSuffix}'
            subnetResourceId: virtualNetwork!.outputs.backendSubnetResourceId
            service: 'account'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'cognitiveservices'
                  privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
                }
              ]
            }
          }
        ]
      : []
  }
}

module aiSearch './modules/ai/ai-search.bicep' = if (isCosmos) {
  name: take('module.ai-search.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    enableTelemetry: enableTelemetry
    skuName: enableScalability ? 'standard' : 'basic'
    replicaCount: enableRedundancy ? 3 : 1
    publicNetworkAccess: 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Search Index Data Contributor (data-plane CRUD on docs)
        roleDefinitionIdOrName: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
      }
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Search Service Contributor (control-plane: indexes, indexers, skillsets)
        roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
      }
      {
        principalId: aiProjectPrincipalId
        principalType: 'ServicePrincipal'
        // Search Index Data Reader — lets the Foundry Project (and Foundry IQ) query indexes through the connection.
        roleDefinitionIdOrName: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
      }
      {
        principalId: aiProjectPrincipalId
        principalType: 'ServicePrincipal'
        // Search Index Data Contributor — Foundry Project identity needs data-plane write for KB MCP endpoint.
        roleDefinitionIdOrName: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
      }
      {
        principalId: aiProjectPrincipalId
        principalType: 'ServicePrincipal'
        // Search Service Contributor — Foundry Project identity for KB management.
        roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
      }
      {
        principalId: aiFoundryPrincipalId
        principalType: 'ServicePrincipal'
        // Search Index Data Contributor — AI Services account identity for MCP auth.
        roleDefinitionIdOrName: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
      }
      {
        principalId: aiFoundryPrincipalId
        principalType: 'ServicePrincipal'
        // Search Index Data Reader — AI Services account identity.
        roleDefinitionIdOrName: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
      }
      {
        principalId: aiFoundryPrincipalId
        principalType: 'ServicePrincipal'
        // Search Service Contributor — AI Services account identity for KB management.
        roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
      }
    ]
  }
}

// Foundry Project ↔ Search connection (CosmosDB mode only).
module aiProjectSearchConnection './modules/ai/ai-foundry-connection.bicep' = if (isCosmos) {
  name: take('module.foundry-search-conn.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    aiServicesAccountName: aiFoundryResourceName
    projectName: aiProjectResourceName
    target: aiSearch!.outputs.endpoint
    category: 'CognitiveSearch'
    authType: 'AAD'
    useWorkspaceManagedIdentity: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: aiSearch!.outputs.resourceId
      knowledgeBaseName: searchKnowledgeBaseName
    }
  }
}

module storageAccount './modules/data/storage-account.bicep' = {
  name: take('module.storage-account.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    enableTelemetry: false
    kind: 'StorageV2'
    skuName: enableRedundancy ? 'Standard_ZRS' : 'Standard_LRS'
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    containers: [
      {
        name: documentsContainerName
        publicAccess: 'None'
      }
      {
        name: 'config'
        publicAccess: 'None'
      }
      {
        name: 'deployment-package'
        publicAccess: 'None'
      }
    ]
    queueServices: {
      queues: [
        { name: 'doc-processing' }
        { name: 'doc-processing-poison' }
        { name: 'blob-events' }
        { name: 'blob-events-poison' }
        { name: 'add-url' }
        { name: 'add-url-poison' }
      ]
    }
    roleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Storage Blob Data Contributor (read/write uploaded documents)
        roleDefinitionIdOrName: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
      }
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Storage Queue Data Contributor (enqueue + consume indexing messages)
        roleDefinitionIdOrName: '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
      }
      {
        principalId: userAssignedIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        // Storage Account Contributor (Function App host storage management)
        roleDefinitionIdOrName: '17d1049b-9a84-46fb-8f53-869881c3d3ab'
      }
    ]
    privateEndpoints: enablePrivateNetworking
      ? [
          {
            name: 'pep-blob-${solutionSuffix}'
            customNetworkInterfaceName: 'nic-blob-${solutionSuffix}'
            subnetResourceId: virtualNetwork!.outputs.backendSubnetResourceId
            service: 'blob'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'blob'
                  privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.blob]!.outputs.resourceId
                }
              ]
            }
          }
          {
            name: 'pep-queue-${solutionSuffix}'
            customNetworkInterfaceName: 'nic-queue-${solutionSuffix}'
            subnetResourceId: virtualNetwork!.outputs.backendSubnetResourceId
            service: 'queue'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'queue'
                  privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.queue]!.outputs.resourceId
                }
              ]
            }
          }
          {
            name: 'pep-file-${solutionSuffix}'
            customNetworkInterfaceName: 'nic-file-${solutionSuffix}'
            subnetResourceId: virtualNetwork!.outputs.backendSubnetResourceId
            service: 'file'
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  name: 'file'
                  privateDnsZoneResourceId: privateDnsZoneDeployments[dnsZoneIndex.file]!.outputs.resourceId
                }
              ]
            }
          }
        ]
      : []
  }
}

// ============================================================================
// Module: Data
// ============================================================================

module cosmosDb './modules/data/cosmos-db-nosql.bicep' = if (isCosmos) {
  name: take('module.cosmos-db-nosql.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    enableTelemetry: enableTelemetry
    databaseName: 'cwyd'
    haLocation: cosmosDbHaLocation
    enableAutomaticFailover: enableRedundancy
    zoneRedundant: enableRedundancy
    diagnosticSettings: monitoringDiagnosticSettings
    sqlRoleAssignments: [
      {
        principalId: userAssignedIdentity.outputs.principalId
        // Cosmos DB Built-in Data Contributor (data-plane CRUD)
        roleDefinitionId: '00000000-0000-0000-0000-000000000002'
      }
    ]
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    enablePrivateNetworking: enablePrivateNetworking
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.cosmosDb]!.outputs.resourceId
    ] : []
  }
}

module postgresServer './modules/data/postgresql-flexible-server.bicep' = if (!isCosmos) {
  name: take('module.postgre-sql.flexible-server.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    enableTelemetry: enableTelemetry
    skuName: enableScalability ? 'Standard_D4ds_v5' : 'Standard_B2s'
    skuTier: enableScalability ? 'GeneralPurpose' : 'Burstable'
    availabilityZone: enableRedundancy ? 1 : -1
    highAvailability: enableRedundancy ? 'ZoneRedundant' : 'Disabled'
    highAvailabilityZone: enableRedundancy ? 2 : -1
    administrators: union(
      [
        {
          objectId: userAssignedIdentity.outputs.principalId
          principalName: userAssignedIdentity.outputs.name
          principalType: 'ServicePrincipal'
        }
      ],
      // Always add the deploying user so post_provision.py can connect
      contains(deployer(), 'userPrincipalName')
        ? [
            {
              objectId: deployingUserPrincipalId
              principalName: deployer().userPrincipalName
              principalType: deployingUserPrincipalType
            }
          ]
        : []
    )
    databases: [
      {
        name: 'cwyd'
        charset: 'UTF8'
        collation: 'en_US.utf8'
      }
    ]
    configurations: [
      {
        name: 'azure.extensions'
        value: 'VECTOR'
        source: 'user-override'
      }
    ]
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    enablePrivateNetworking: enablePrivateNetworking
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.postgres]!.outputs.resourceId
    ] : []
    diagnosticSettings: monitoringDiagnosticSettings
  }
}

// ========== Container Registry ========== //
// Provisions the ACR and grants AcrPull to the shared managed identity (used by
// both the frontend App Service and the backend Container Instance). Application
// images are built and pushed to this ACR by a post-deployment step.
module containerRegistry './modules/compute/container-registry.bicep' = {
  name: take('module.container-registry.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    sku: enablePrivateNetworking ? 'Premium' : 'Basic'
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    networkRuleSetDefaultAction: enablePrivateNetworking ? 'Deny' : 'Allow'
    enablePrivateNetworking: enablePrivateNetworking
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.containerRegistry]!.outputs.resourceId
    ] : []
    managedIdentities: {
      userAssignedResourceIds: [
        userAssignedIdentity.outputs.resourceId
      ]
    }
    acrPullPrincipalIds: [
      userAssignedIdentity.outputs.principalId
    ]
  }
}

// ========== Container App Environment ========== //
module containerAppsEnv './modules/compute/container-app-environment.bicep' = {
  name: take('module.container-app-environment.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    enableTelemetry: enableTelemetry
    zoneRedundant: enableRedundancy
    enableMonitoring: enableMonitoring
    logAnalyticsWorkspaceResourceId: enableMonitoring ? logAnalyticsWorkspace!.outputs.resourceId : ''
    infrastructureSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.containerSubnetResourceId : null
  }
}

var postgresLibpqUri = !isCosmos
  ? 'postgresql://${postgresServer!.outputs.serverFqdn!}:5432/cwyd?sslmode=require'
  : ''
var indexStoreValue = isCosmos ? 'AzureSearch' : 'pgvector'
module backendContainerApp './modules/compute/container-app.bicep' = {
  name: take('module.container-app-api.${solutionSuffix}', 64)
  params: {
    name: 'ca-backend-${solutionSuffix}'
    location: location
    tags: union(allTags, { 'azd-service-name': 'backend' })
    enableTelemetry: enableTelemetry
    environmentResourceId: containerAppsEnv.outputs.resourceId
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: userAssignedIdentity.outputs.resourceId
      }
    ]
    managedIdentities: {
      systemAssigned: true, userAssignedResourceIds: [userAssignedIdentity.outputs.resourceId]
    }
    workloadProfileName: 'Consumption'
    ingressTargetPort: 8000
    scaleSettings: {
      minReplicas: enableScalability ? 1 : 0
      maxReplicas: enableScalability ? 10 : 3
    }
    containers: [
      {
        name: 'backend'
        // image: '${containerRegistryEndpoint}/rag-backend:${imageTag}'
        image: sampleContainerImage
        resources: {
          cpu: any(enableScalability ? '1.0' : '0.5')
          memory: enableScalability ? '2.0Gi' : '1.0Gi'
        }
        env: concat(
          [
            { name: 'AZURE_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
            { name: 'AZURE_UAMI_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
            { name: 'AZURE_TENANT_ID', value: subscription().tenantId }
            { name: 'AZURE_ENVIRONMENT', value: 'production' }
            { name: 'AZURE_AI_PROJECT_ENDPOINT', value: projectEndpoint }
            { name: 'AZURE_OPENAI_ENDPOINT', value: aiFoundryEndpoint }
            { name: 'AZURE_AI_SERVICES_ENDPOINT', value: aiCognitiveServicesEndpoint }
            { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
            { name: 'AZURE_AI_AGENT_API_VERSION', value: azureAiAgentApiVersion }
            { name: 'AZURE_OPENAI_GPT_DEPLOYMENT', value: gptModelName }
            { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
            { name: 'AZURE_DB_TYPE', value: databaseType }
            { name: 'AZURE_INDEX_STORE', value: indexStoreValue }
            { name: 'AZURE_COSMOS_ENDPOINT', value: isCosmos ? cosmosDb!.outputs.endpoint : '' }
            { name: 'AZURE_AI_SEARCH_ENDPOINT', value: isCosmos ? aiSearch!.outputs.endpoint : '' }
            { name: 'AZURE_AI_SEARCH_INDEX', value: isCosmos ? searchIndexName : '' }
            { name: 'AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME', value: searchKnowledgeBaseName }
            { name: 'AZURE_AI_SEARCH_KNOWLEDGE_SOURCE_NAME', value: searchKnowledgeSourceName }
            { name: 'AZURE_AI_SEARCH_KNOWLEDGE_BASE_API_VERSION', value: searchKnowledgeBaseApiVersion }
            { name: 'AZURE_AI_SEARCH_CONNECTION_NAME', value: isCosmos ? aiProjectSearchConnection!.outputs.connectionName : '' }
            { name: 'AZURE_POSTGRES_ENDPOINT', value: postgresLibpqUri }
            { name: 'AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME', value: !isCosmos ? userAssignedIdentity.outputs.name : '' }
            { name: 'AZURE_SPEECH_SERVICE_NAME', value: speechService.outputs.name }
            { name: 'AZURE_SPEECH_SERVICE_REGION', value: azureAiServiceLocation }
            { name: 'AZURE_SPEECH_ACCOUNT_RESOURCE_ID', value: speechService.outputs.resourceId }
            { name: 'AZURE_CONTENT_SAFETY_ENABLED', value: 'true' }
            { name: 'AZURE_CONTENT_SAFETY_ENDPOINT', value: contentSafety.outputs.endpoint }
            { name: 'CWYD_ORCHESTRATOR_NAME', value: databaseType == 'postgresql' ? 'langgraph' : 'agent_framework' }
            { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storageAccount.outputs.name }
            { name: 'AZURE_DOCUMENTS_CONTAINER', value: documentsContainerName }
            { name: 'AZURE_DOC_PROCESSING_QUEUE', value: docProcessingQueueName }
            { name: 'AZURE_INGESTION_TRIGGER', value: ingestionTrigger }
          ],
          enableMonitoring
          ? [
              { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: applicationInsights!.outputs.connectionString }
            ]
          : []
        )
      }
    ]
  }
}

module frontendContainerApp './modules/compute/container-app.bicep' = {
  name: take('module.container-app-frontend.${solutionName}', 64)
  params: {
    name: 'ca-frontend-${solutionSuffix}'
    location: location
    tags: union(allTags, { 'azd-service-name': 'frontend' })
    enableTelemetry: enableTelemetry
    environmentResourceId: containerAppsEnv.outputs.resourceId
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: userAssignedIdentity.outputs.resourceId
      }
    ]
    managedIdentities: {
      systemAssigned: true, userAssignedResourceIds: [userAssignedIdentity.outputs.resourceId]
    }
    workloadProfileName: 'Consumption'
    ingressTargetPort: 80
    scaleSettings: {
      minReplicas: 1
      maxReplicas: enableScalability ? 5 : 3
    }
    containers: [
      {
        name: 'frontend'
        // image: '${containerRegistryEndpoint}/rag-frontend:${imageTag}'
        image: sampleContainerImage
        resources: {
          cpu: any('0.5')
          memory: '1.0Gi'
        }
        env: concat(
          [
            { name: 'VITE_BACKEND_URL', value: 'https://${backendContainerApp.outputs.fqdn}' }
            { name: 'BACKEND_API_URL', value: 'https://${backendContainerApp.outputs.fqdn}' }
          ],
          enableMonitoring
          ? [
              { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: applicationInsights!.outputs.connectionString }
            ]
          : []
        )
      }
    ]
  }
}

module functionContainerApp './modules/compute/container-app.bicep' = {
  name: take('module.container-app-function.${solutionName}', 64)
  params: {
    name: 'ca-function-${solutionSuffix}'
    location: location
    tags: union(allTags, { 'azd-service-name': 'function' })
    kind: 'functionapp'
    enableTelemetry: enableTelemetry
    environmentResourceId: containerAppsEnv.outputs.resourceId
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        identity: userAssignedIdentity.outputs.resourceId
      }
    ]
    managedIdentities: {
      systemAssigned: true, userAssignedResourceIds: [userAssignedIdentity.outputs.resourceId]
    }
    workloadProfileName: 'Consumption'
    ingressTargetPort: 80
    scaleSettings: {
      minReplicas: 1
      maxReplicas: enableScalability ? 5 : 3
    }
    containers: [
      {
        name: 'function'
        image: sampleContainerImage
        resources: {
          cpu: json(enableScalability ? '1.0' : '0.5')
          memory: enableScalability ? '2.0Gi' : '1.0Gi'
        }
        env: concat(
          [
            { name: 'AzureWebJobsStorage__accountName', value: storageAccount.outputs.name }
            { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
            { name: 'AzureWebJobsStorage__clientId', value: userAssignedIdentity.outputs.clientId }
            { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false' }
            { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
            { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
            { name: 'AZURE_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
            { name: 'AZURE_UAMI_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
            { name: 'AZURE_TENANT_ID', value: subscription().tenantId }
            { name: 'AZURE_ENVIRONMENT', value: 'production' }
            { name: 'AZURE_AI_PROJECT_ENDPOINT', value: projectEndpoint }
            { name: 'AZURE_OPENAI_ENDPOINT', value: aiFoundryEndpoint }
            { name: 'AZURE_AI_SERVICES_ENDPOINT', value: aiCognitiveServicesEndpoint }
            { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
            { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
            { name: 'AZURE_DB_TYPE', value: databaseType }
            { name: 'AZURE_INDEX_STORE', value: indexStoreValue }
            { name: 'AZURE_COSMOS_ENDPOINT', value: isCosmos ? cosmosDb!.outputs.endpoint : '' }
            { name: 'AZURE_AI_SEARCH_ENDPOINT', value: isCosmos ? aiSearch!.outputs.endpoint : '' }
            { name: 'AZURE_POSTGRES_ENDPOINT', value: postgresLibpqUri }
            { name: 'AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME', value: !isCosmos ? userAssignedIdentity.outputs.name : '' }
            { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storageAccount!.outputs.name }
            { name: 'AZURE_DOCUMENTS_CONTAINER', value: documentsContainerName }
            { name: 'AZURE_DOC_PROCESSING_QUEUE', value: docProcessingQueueName }
          ],
          enableMonitoring
          ? [
              { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: applicationInsights!.outputs.connectionString }
            ]
          : []
        )
      }
    ]
  }
}

// var functionName = 'func-${solutionSuffix}'
// var hostingModel = 'container'
// module functionApp './modules/compute/function-app.bicep' = {
//   name: hostingModel == 'container' ? '${functionName}-docker' : functionName
//   params: {
//     name: hostingModel == 'container' ? '${functionName}-docker' : functionName
//     location: location
//     tags: union(allTags, { 'azd-service-name': 'function' })
//     enableTelemetry: enableTelemetry
//     kind: hostingModel == 'container' ? 'functionapp,linux,container' : 'functionapp,linux'
//     serverFarmResourceId: appServicePlan.outputs.resourceId
//     managedIdentities: {
//       systemAssigned: true, userAssignedResourceIds: [userAssignedIdentity.outputs.resourceId]
//     }
//     applicationInsightResourceId: enableMonitoring ? applicationInsights!.outputs.resourceId : ''
//     storageAccountName: storageAccount.outputs.name
//     userAssignedIdentityClientId: userAssignedIdentity.outputs.clientId
//     runtimeStack: 'python'
//     runtimeVersion: '3.11'
//     dockerFullImageName: hostingModel == 'container' ? sampleContainerImage : ''
//     virtualNetworkSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.webserverfarmSubnetResourceId : null
//     appSettings: concat(
//       [
//         { name: 'AZURE_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
//         { name: 'AZURE_UAMI_CLIENT_ID', value: userAssignedIdentity.outputs.clientId }
//         { name: 'AZURE_TENANT_ID', value: subscription().tenantId }
//         { name: 'DOCKER_REGISTRY_SERVER_URL', value: 'https://${containerRegistry.outputs.loginServer}' }
//         { name: 'AZURE_ENVIRONMENT', value: 'production' }
//         { name: 'AZURE_AI_PROJECT_ENDPOINT', value: projectEndpoint }
//         { name: 'AZURE_OPENAI_ENDPOINT', value: aiFoundryEndpoint }
//         { name: 'AZURE_AI_SERVICES_ENDPOINT', value: aiCognitiveServicesEndpoint }
//         { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
//         { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingModelName }
//         { name: 'AZURE_DB_TYPE', value: databaseType }
//         { name: 'AZURE_INDEX_STORE', value: indexStoreValue }
//         { name: 'AZURE_COSMOS_ENDPOINT', value: isCosmos ? cosmosDb!.outputs.endpoint : '' }
//         { name: 'AZURE_AI_SEARCH_ENDPOINT', value: isCosmos ? aiSearch!.outputs.endpoint : '' }
//         { name: 'AZURE_POSTGRES_ENDPOINT', value: postgresLibpqUri }
//         { name: 'AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME', value: !isCosmos ? userAssignedIdentity.outputs.name : '' }
//         { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storageAccount!.outputs.name }
//         { name: 'AZURE_DOCUMENTS_CONTAINER', value: documentsContainerName }
//         { name: 'AZURE_DOC_PROCESSING_QUEUE', value: docProcessingQueueName }
//       ],
//       enableMonitoring
//         ? [
//             { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: applicationInsights!.outputs.connectionString }
//           ]
//         : []
//     )
//   }
// }

module eventGridSystemTopic './modules/data/event-grid.bicep' = {
  name: take('modules.event-grid.system-topic.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: allTags
    enableTelemetry: enableTelemetry
    source: storageAccount!.outputs.resourceId
    topicType: 'Microsoft.Storage.StorageAccounts'
    storageAccountName: storageAccount!.outputs.name
    eventSubscriptions: [
      {
        name: 'blob-created-to-doc-processing'
        deliveryWithResourceIdentity: {
          identity: {
            type: 'SystemAssigned'
          }
          destination: {
            endpointType: 'StorageQueue'
            properties: {
              resourceId: storageAccount!.outputs.resourceId
              queueName: blobEventsQueueName
            }
          }
        }
        filter: {
          includedEventTypes: [
            'Microsoft.Storage.BlobCreated'
            'Microsoft.Storage.BlobDeleted'
          ]
          subjectBeginsWith: '/blobServices/default/containers/${documentsContainerName}/'
          enableAdvancedFilteringOnArrays: true
        }
        eventDeliverySchema: 'EventGridSchema'
        retryPolicy: {
          maxDeliveryAttempts: 30
          eventTimeToLiveInMinutes: 1440
        }
      }
    ]
  }
}

// ============================================================================
// Cross-service system-assigned identity role assignments
// (centralized via role-assignments.bicep — mirrors Oldinfra pattern)
// ============================================================================

var systemAssignedRoleAssignments = union(
  isCosmos
    ? [
        {
          principalId: aiSearch.?outputs.identityPrincipalId
          resourceId: storageAccount.outputs.resourceId
          roleName: 'Storage Blob Data Contributor'
          roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
          principalType: 'ServicePrincipal'
        }
        {
          principalId: aiSearch.?outputs.identityPrincipalId
          resourceId: aiFoundryResourceId
          roleName: 'Cognitive Services User'
          roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908'
          principalType: 'ServicePrincipal'
        }
        {
          principalId: aiSearch.?outputs.identityPrincipalId
          resourceId: aiFoundryResourceId
          roleName: 'Cognitive Services OpenAI User'
          roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
          principalType: 'ServicePrincipal'
        }
      ]
    : [],
  [
    {
      principalId: aiProjectPrincipalId
      resourceId: storageAccount.outputs.resourceId
      roleName: 'Storage Blob Data Contributor'
      roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
      principalType: 'ServicePrincipal'
    }
    // Function App SI needs blob/queue/account roles for the host lock lease
    // and queue trigger bindings (allowSharedKeyAccess=false forces identity auth)
    {
      principalId: frontendContainerApp.outputs.principalId
      resourceId: storageAccount.outputs.resourceId
      roleName: 'Storage Blob Data Owner'
      roleDefinitionId: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
      principalType: 'ServicePrincipal'
    }
    {
      principalId: frontendContainerApp.outputs.principalId
      resourceId: storageAccount.outputs.resourceId
      roleName: 'Storage Queue Data Contributor'
      roleDefinitionId: '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
      principalType: 'ServicePrincipal'
    }
    {
      principalId: frontendContainerApp.outputs.principalId
      resourceId: storageAccount.outputs.resourceId
      roleName: 'Storage Account Contributor'
      roleDefinitionId: '17d1049b-9a84-46fb-8f53-869881c3d3ab'
      principalType: 'ServicePrincipal'
    }
    {
      principalId: userAssignedIdentity.outputs.principalId
      resourceId: aiFoundryResourceId
      roleName: 'Cognitive Services OpenAI User'
      roleDefinitionId: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
      principalType: 'ServicePrincipal'
    }
    {
      principalId: userAssignedIdentity.outputs.principalId
      resourceId: aiFoundryResourceId
      roleName: 'Cognitive Services User'
      roleDefinitionId: 'a97b65f3-24c7-4388-baec-2e87135dc908'
      principalType: 'ServicePrincipal'
    }
    {
      principalId: userAssignedIdentity.outputs.principalId
      resourceId: aiFoundryResourceId
      roleName: 'Azure AI User'
      roleDefinitionId: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
      principalType: 'ServicePrincipal'
    }
  ]
)

@description('Role assignments applied to system-assigned identities via AVM resource-role-assignment pattern. Objects: { principalId, resourceId, roleName, roleDefinitionId, principalType }.')
module systemAssignedIdentityRoleAssignments './modules/identity/role-assignments.bicep' = {
  name: take('module.resource-role-assignment.system-assigned', 64)
  params: {
    roleAssignments: systemAssignedRoleAssignments
  }
}

// ===================== //
// Outputs               //
// ===================== //

// --- Identity / region / suffix ---

@description('Lower-cased solution suffix used in every downstream resource name.')
output AZURE_SOLUTION_SUFFIX string = solutionSuffix

@description('Resource group containing the deployment.')
output AZURE_RESOURCE_GROUP string = resourceGroup().name

@description('Location of the non-AI resources (Container Apps, App Service, Functions, Storage, Cosmos/Postgres).')
output AZURE_LOCATION string = location

@description('Location of the AI Services account + model deployments (independent of AZURE_LOCATION).')
output AZURE_AI_SERVICE_LOCATION string = azureAiServiceLocation

@description('Tenant ID for the deployment subscription.')
output AZURE_TENANT_ID string = subscription().tenantId

@description('Client ID of the user-assigned managed identity shared by all v2 workloads.')
output AZURE_UAMI_CLIENT_ID string = userAssignedIdentity.outputs.clientId

@description('Principal (object) ID of the user-assigned managed identity.')
output AZURE_UAMI_PRINCIPAL_ID string = userAssignedIdentity.outputs.principalId

@description('Resource ID of the user-assigned managed identity.')
output AZURE_UAMI_RESOURCE_ID string = userAssignedIdentity.outputs.resourceId

// --- Database routing flag (mirrored as env on every workload) ---

@description('Selected database engine for chat history + vector index (locked at deploy).')
output AZURE_DB_TYPE string = databaseType

@description('Logical name of the configured vector index store: "AzureSearch" (CosmosDB mode) or "pgvector" (PostgreSQL mode).')
output AZURE_INDEX_STORE string = indexStoreValue

// --- Foundry substrate ---

@description('Unified AI Services (Cognitive Services) endpoint. Used by Document Intelligence and other non-OpenAI AI Services APIs.')
output AZURE_AI_SERVICES_ENDPOINT string = aiCognitiveServicesEndpoint

@description('Effective Azure OpenAI endpoint backends call for chat + reasoning + embedding deployments. When `existingOpenAiName` is set this points at the reused v1 OpenAI account; otherwise it equals AZURE_AI_SERVICES_ENDPOINT (deployments live on the v2 Foundry account).')
output AZURE_OPENAI_ENDPOINT string = aiFoundryEndpoint

@description('Foundry Project endpoint (https://<account>.services.ai.azure.com/api/projects/<project>). Required by the Microsoft Agent Framework SDK.')
output AZURE_AI_PROJECT_ENDPOINT string = projectEndpoint

@description('OpenAI-compatible API version pinned for the GPT + reasoning deployments.')
output AZURE_OPENAI_API_VERSION string = azureOpenAiApiVersion

@description('Azure AI Agents API version pinned for the Foundry Project endpoint.')
output AZURE_AI_AGENT_API_VERSION string = azureAiAgentApiVersion

@description('Deployment name of the chat-completions GPT model.')
output AZURE_OPENAI_GPT_DEPLOYMENT string = gptModelName

@description('Deployment name of the o-series reasoning model (output flows on the SSE `reasoning` channel).')
output AZURE_OPENAI_REASONING_DEPLOYMENT string = reasoningModelName

@description('Deployment name of the embedding model used by the indexing pipeline.')
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = embeddingModelName

// --- Speech (S1 / SPEECH-MVP) ---

@description('Speech account name (kind=SpeechServices). Backend reads via SpeechSettings.service_name; not used directly by the SDK.')
output AZURE_SPEECH_SERVICE_NAME string = speechService.outputs.name

@description('Speech account region. Browser SDK passes this to SpeechConfig.fromAuthorizationToken(token, region) and the backend uses it to build the regional sts/v1.0/issueToken URL.')
output AZURE_SPEECH_SERVICE_REGION string = azureAiServiceLocation

@description('Speech account ARM resource id. Required as the x-ms-cognitiveservices-resource-id header on the AAD-bearer STS issueToken POST.')
output AZURE_SPEECH_ACCOUNT_RESOURCE_ID string = speechService.outputs.resourceId

// --- Content Safety ---

@description('Content Safety account endpoint. Backend reads via ContentSafetySettings.endpoint; lifespan gates client construction on this + AZURE_CONTENT_SAFETY_ENABLED.')
output AZURE_CONTENT_SAFETY_ENDPOINT string = contentSafety.outputs.endpoint

@description('Content Safety account name (kind=ContentSafety). Diagnostic surface only — backend builds the client from the endpoint.')
output AZURE_CONTENT_SAFETY_NAME string = contentSafety.outputs.name

// --- Conditional: Azure AI Search (CosmosDB mode only) ---

@description('AI Search service endpoint. Empty in PostgreSQL mode.')
output AZURE_AI_SEARCH_ENDPOINT string = isCosmos ? aiSearch!.outputs.endpoint : ''

@description('AI Search service name. Empty in PostgreSQL mode.')
output AZURE_AI_SEARCH_NAME string = isCosmos ? aiSearch!.outputs.name : ''

@description('Chat index name. Exported so the postdeploy seed hook can run its index-population self-check; empty in postgresql mode (no AI Search).')
output AZURE_AI_SEARCH_INDEX string = databaseType == 'cosmosdb' ? searchIndexName : ''

// --- Conditional: Cosmos DB (CosmosDB mode only) ---

@description('Cosmos DB account endpoint (DocumentEndpoint). Empty in PostgreSQL mode.')
output AZURE_COSMOS_ENDPOINT string = isCosmos ? cosmosDb!.outputs.endpoint : ''

@description('Cosmos DB account name. Empty in PostgreSQL mode.')
output AZURE_COSMOS_ACCOUNT_NAME string = isCosmos ? cosmosDb!.outputs.name : ''

// --- Conditional: PostgreSQL Flexible Server (PostgreSQL mode only) ---

@description('PostgreSQL Flexible Server FQDN (clients add :5432 themselves). Empty in CosmosDB mode.')
output AZURE_POSTGRES_HOST string = !isCosmos ? postgresServer!.outputs.serverFqdn! : ''

@description('Full libpq connection URI for the PostgreSQL Flexible Server (no credentials — the workload supplies an Entra token; the user comes from AZURE_UAMI_CLIENT_ID). Mirrors AZURE_COSMOS_ENDPOINT shape so AzurePostgresSettings reads one var. Empty in CosmosDB mode.')
output AZURE_POSTGRES_ENDPOINT string = postgresLibpqUri

@description('PostgreSQL Flexible Server resource name. Empty in CosmosDB mode.')
output AZURE_POSTGRES_NAME string = !isCosmos ? postgresServer!.outputs.name : ''

@description('UAMI principal name used by the runtime apps to connect to Postgres. Empty in CosmosDB mode.')
output AZURE_POSTGRES_ADMIN_PRINCIPAL_NAME string = !isCosmos ? userAssignedIdentity.outputs.name : ''

@description('Deployer principal name registered as Postgres Entra admin (for post_provision.py). Empty in CosmosDB mode or when deployer has no UPN.')
output AZURE_POSTGRES_DEPLOYER_PRINCIPAL_NAME string = !isCosmos && contains(deployer(), 'userPrincipalName') ? deployer().userPrincipalName : ''

// --- Storage (blobs + queues + Function deployment package) ---

@description('Storage account name (shared by RAG document store, indexing queues, and the Function App deployment package).')
output AZURE_STORAGE_ACCOUNT_NAME string = storageAccount!.outputs.name

@description('Primary blob endpoint of the shared storage account (https URL ending in /). Hostname follows the storage cloud-specific suffix.')
output AZURE_STORAGE_BLOB_ENDPOINT string = storageAccount!.outputs.blobEndpoint

@description('Container holding documents to be indexed (Event Grid filter + batch_start source).')
output AZURE_DOCUMENTS_CONTAINER string = documentsContainerName

@description('Storage Queue name fed by Event Grid BlobCreated and consumed by the batch_push Function blueprint.')
output AZURE_DOC_PROCESSING_QUEUE string = docProcessingQueueName

@description('Ingestion trigger mode for the backend admin upload path: direct_enqueue (backend enqueues) or event_grid (Event Grid + blob_event Function own the push).')
output AZURE_INGESTION_TRIGGER string = ingestionTrigger

// --- Hosting endpoints (consumed by azd hooks, Vite build, smoke tests) ---

@description('Public URL of the backend Container App (FastAPI + LangGraph/Agent Framework).')
output AZURE_BACKEND_URL string = 'https://${backendContainerApp.outputs.fqdn}'

@description('Public URL of the frontend Container App (React/Vite SPA proxy). Backend CORS must allow this origin.')
output AZURE_FRONTEND_URL string = 'https://${frontendContainerApp.outputs.fqdn}'

@description('Public URL of the Function App hosting the indexing pipeline.')
output AZURE_FUNCTION_APP_URL string = 'https://${functionContainerApp.outputs.fqdn}'

@description('Function App resource name (used by azd to deploy the function package).')
output AZURE_FUNCTION_APP_NAME string = functionContainerApp.outputs.name

@description('Container Registry login server.')
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer

@description('Container Registry resource name.')
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.name

// --- Conditional: monitoring ---

@description('Application Insights connection string. Empty when enableMonitoring=false.')
output AZURE_APP_INSIGHTS_CONNECTION_STRING string = enableMonitoring ? applicationInsights!.outputs.connectionString : ''

// --- Conditional: private networking (enablePrivateNetworking only) ---

@description('VNet name. Empty when enablePrivateNetworking=false.')
output AZURE_VNET_NAME string = enablePrivateNetworking ? virtualNetwork!.outputs.name : ''

@description('VNet resource ID. Empty when enablePrivateNetworking=false.')
output AZURE_VNET_RESOURCE_ID string = enablePrivateNetworking ? virtualNetwork!.outputs.resourceId : ''

@description('Bastion host name (for `az network bastion tunnel`). Empty when enablePrivateNetworking=false.')
output AZURE_BASTION_NAME string = enablePrivateNetworking ? bastionHost!.outputs.name : ''
