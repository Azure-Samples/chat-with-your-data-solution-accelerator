// ============================================================================
// Module: Azure Kubernetes Service (AKS)
// Description: Deploys Azure Kubernetes Service Managed Cluster
// API: Microsoft.ContainerService/managedClusters@2025-03-01
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the AKS cluster.')
param name string = 'aks-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Kubernetes version for the cluster.')
param kubernetesVersion string = '1.34'

@description('Agent pool configurations. Each entry requires name, vmSize, count, mode (System/User).')
param agentPools array = [
  {
    name: 'systempool'
    vmSize: 'Standard_D4ds_v5'
    count: 2
    minCount: 1
    maxCount: 3
    enableAutoScaling: true
    osType: 'Linux'
    mode: 'System'
  }
]

@description('Enable Kubernetes RBAC.')
param enableRBAC bool = true

@description('Disable local accounts (enforce AAD-only).')
param disableLocalAccounts bool = false

@description('Network plugin for the cluster.')
@allowed(['azure', 'kubenet', 'none'])
param networkPlugin string = 'azure'

@description('Network policy for the cluster.')
@allowed(['azure', 'calico', ''])
param networkPolicy string = 'azure'

@description('DNS prefix for the cluster.')
param dnsPrefix string = ''

@description('SKU tier for the cluster.')
@allowed(['Free', 'Standard', 'Premium'])
param skuTier string = 'Standard'

@description('Service CIDR for Kubernetes services.')
param serviceCidr string = '10.20.0.0/16'

@description('DNS service IP (must be within serviceCidr).')
param dnsServiceIP string = '10.20.0.10'

@description('Auto-upgrade channel for the cluster.')
@allowed(['none', 'patch', 'rapid', 'stable', 'node-image'])
param autoUpgradeChannel string = 'stable'

@description('Log Analytics workspace resource ID for monitoring.')
param logAnalyticsWorkspaceResourceId string = ''

// ============================================================================
// Variables
// ============================================================================
var effectiveDnsPrefix = !empty(dnsPrefix) ? dnsPrefix : name

// ============================================================================
// Resource Deployment
// ============================================================================
resource aksCluster 'Microsoft.ContainerService/managedClusters@2025-03-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'Base'
    tier: skuTier
  }
  properties: {
    kubernetesVersion: kubernetesVersion
    dnsPrefix: effectiveDnsPrefix
    enableRBAC: enableRBAC
    disableLocalAccounts: disableLocalAccounts
    agentPoolProfiles: [for pool in agentPools: {
      name: pool.name
      vmSize: pool.vmSize
      count: pool.count
      minCount: pool.?enableAutoScaling == true ? pool.?minCount : null
      maxCount: pool.?enableAutoScaling == true ? pool.?maxCount : null
      enableAutoScaling: pool.?enableAutoScaling ?? false
      osType: pool.?osType ?? 'Linux'
      mode: pool.mode
    }]
    networkProfile: {
      networkPlugin: networkPlugin
      networkPolicy: !empty(networkPolicy) ? networkPolicy : null
      serviceCidr: serviceCidr
      dnsServiceIP: dnsServiceIP
    }
    autoUpgradeProfile: {
      upgradeChannel: autoUpgradeChannel
    }
    addonProfiles: !empty(logAnalyticsWorkspaceResourceId) ? {
      omsagent: {
        enabled: true
        config: {
          logAnalyticsWorkspaceResourceID: logAnalyticsWorkspaceResourceId
        }
      }
    } : {}
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Name of the AKS cluster.')
output name string = aksCluster.name

@description('Resource ID of the AKS cluster.')
output resourceId string = aksCluster.id

@description('FQDN of the AKS cluster.')
output fqdn string = aksCluster.properties.fqdn
