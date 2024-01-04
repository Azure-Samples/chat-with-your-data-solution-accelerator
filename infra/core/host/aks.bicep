metadata description = 'Creates an Azure Kubernetes Service (AKS) cluster with a system agent pool as well as an additional user agent pool.'
@description('The name for the AKS managed cluster')
param name string

@description('The name for the Azure container registry (ACR)')
param containerRegistryName string

@description('The name of the connected log analytics workspace')
param logAnalyticsName string = ''

@description('The name of the keyvault to grant access')
param keyVaultName string

@description('The Azure region/location for the AKS resources')
param location string = resourceGroup().location

@description('Custom tags to apply to the AKS resources')
param tags object = {}

@description('AKS add-ons configuration')
param addOns object = {
  azurePolicy: {
    enabled: true
    config: {
      version: 'v2'
    }
  }
  keyVault: {
    enabled: true
    config: {
      enableSecretRotation: 'true'
      rotationPollInterval: '2m'
    }
  }
  openServiceMesh: {
    enabled: false
    config: {}
  }
  omsAgent: {
    enabled: true
    config: {}
  }
  applicationGateway: {
    enabled: false
    config: {}
  }
}

@allowed([
  'CostOptimised'
  'Standard'
  'HighSpec'
  'Custom'
])
@description('The System Pool Preset sizing')
param systemPoolType string = 'CostOptimised'

@allowed([
  ''
  'CostOptimised'
  'Standard'
  'HighSpec'
  'Custom'
])
@description('The User Pool Preset sizing')
param agentPoolType string = ''

// Configure system / user agent pools
@description('Custom configuration of system node pool')
param systemPoolConfig object = {}
@description('Custom configuration of user node pool')
param agentPoolConfig object = {}

// Configure AKS add-ons
var omsAgentConfig = (!empty(logAnalyticsName) && !empty(addOns.omsAgent) && addOns.omsAgent.enabled) ? union(
  addOns.omsAgent,
  {
    config: {
      logAnalyticsWorkspaceResourceID: logAnalytics.id
    }
  }
) : {}

var addOnsConfig = union(
  (!empty(addOns.azurePolicy) && addOns.azurePolicy.enabled) ? { azurepolicy: addOns.azurePolicy } : {},
  (!empty(addOns.keyVault) && addOns.keyVault.enabled) ? { azureKeyvaultSecretsProvider: addOns.keyVault } : {},
  (!empty(addOns.openServiceMesh) && addOns.openServiceMesh.enabled) ? { openServiceMesh: addOns.openServiceMesh } : {},
  (!empty(addOns.omsAgent) && addOns.omsAgent.enabled) ? { omsagent: omsAgentConfig } : {},
  (!empty(addOns.applicationGateway) && addOns.applicationGateway.enabled) ? { ingressApplicationGateway: addOns.applicationGateway } : {}
)

// Link to existing log analytics workspace when available
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2021-12-01-preview' existing = if (!empty(logAnalyticsName)) {
  name: logAnalyticsName
}

var systemPoolSpec = !empty(systemPoolConfig) ? systemPoolConfig : nodePoolPresets[systemPoolType]

// Create the primary AKS cluster resources and system node pool
module managedCluster 'aks-managed-cluster.bicep' = {
  name: 'managed-cluster'
  params: {
    name: name
    location: location
    tags: tags
    systemPoolConfig: union(
      { name: 'npsystem', mode: 'System' },
      nodePoolBase,
      systemPoolSpec
    )
    addOns: addOnsConfig
    workspaceId: !empty(logAnalyticsName) ? logAnalytics.id : ''
  }
}

var hasAgentPool = !empty(agentPoolConfig) || !empty(agentPoolType)
var agentPoolSpec = hasAgentPool && !empty(agentPoolConfig) ? agentPoolConfig : empty(agentPoolType) ? {} : nodePoolPresets[agentPoolType]

// Create additional user agent pool when specified
module agentPool 'aks-agent-pool.bicep' = if (hasAgentPool) {
  name: 'aks-node-pool'
  params: {
    clusterName: managedCluster.outputs.clusterName
    name: 'npuserpool'
    config: union({ name: 'npuser', mode: 'User' }, nodePoolBase, agentPoolSpec)
  }
}

// Creates container registry (ACR)
module containerRegistry 'container-registry.bicep' = {
  name: 'container-registry'
  params: {
    name: containerRegistryName
    location: location
    tags: tags
    workspaceId: !empty(logAnalyticsName) ? logAnalytics.id : ''
  }
}

// Grant ACR Pull access from cluster managed identity to container registry
module containerRegistryAccess '../security/registry-access.bicep' = {
  name: 'cluster-container-registry-access'
  params: {
    containerRegistryName: containerRegistry.outputs.name
    principalId: managedCluster.outputs.clusterIdentity.objectId
  }
}

// Give the AKS Cluster access to KeyVault
module clusterKeyVaultAccess '../security/keyvault-access.bicep' = {
  name: 'cluster-keyvault-access'
  params: {
    keyVaultName: keyVaultName
    principalId: managedCluster.outputs.clusterIdentity.objectId
  }
}

// Helpers for node pool configuration
var nodePoolBase = {
  osType: 'Linux'
  maxPods: 30
  type: 'VirtualMachineScaleSets'
  upgradeSettings: {
    maxSurge: '33%'
  }
}

var nodePoolPresets = {
  CostOptimised: {
    vmSize: 'Standard_B4ms'
    count: 1
    minCount: 1
    maxCount: 3
    enableAutoScaling: true
    availabilityZones: []
  }
  Standard: {
    vmSize: 'Standard_DS2_v2'
    count: 3
    minCount: 3
    maxCount: 5
    enableAutoScaling: true
    availabilityZones: [
      '1'
      '2'
      '3'
    ]
  }
  HighSpec: {
    vmSize: 'Standard_D4s_v3'
    count: 3
    minCount: 3
    maxCount: 5
    enableAutoScaling: true
    availabilityZones: [
      '1'
      '2'
      '3'
    ]
  }
}

// Module outputs
@description('The resource name of the AKS cluster')
output clusterName string = managedCluster.outputs.clusterName

@description('The AKS cluster identity')
output clusterIdentity object = managedCluster.outputs.clusterIdentity

@description('The resource name of the ACR')
output containerRegistryName string = containerRegistry.outputs.name

@description('The login server for the container registry')
output containerRegistryLoginServer string = containerRegistry.outputs.loginServer
