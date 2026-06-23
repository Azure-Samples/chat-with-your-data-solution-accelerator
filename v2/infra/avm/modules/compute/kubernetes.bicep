// ============================================================================
// Module: Azure Kubernetes Service (AKS)
// Description: AVM wrapper for Azure Kubernetes Service Managed Cluster
// AVM Module: avm/res/container-service/managed-cluster:0.13.1
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
    name: 'agentpool'
    vmSize: 'Standard_D4ds_v5'
    count: 2
    minCount: 1
    maxCount: 2
    enableAutoScaling: true
    osType: 'Linux'
    mode: 'System'
    type: 'VirtualMachineScaleSets'
    scaleSetEvictionPolicy: 'Delete'
    scaleSetPriority: 'Regular'
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

// --- WAF: Networking ---
@description('Public network access setting.')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Enabled'

@description('Enable private cluster (API server not publicly accessible).')
param enablePrivateCluster bool = false

@description('Subnet resource ID for the agent pool (for VNet integration).')
param agentPoolSubnetId string = ''

@description('Enable Microsoft Defender for Containers.')
param enableDefender bool = false

@description('Diagnostic settings for monitoring.')
param diagnosticSettings array = []

@description('Role assignments for the cluster.')
param roleAssignments array = []

@description('Enable Azure telemetry collection.')
param enableTelemetry bool = true

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

// ============================================================================
// Variables
// ============================================================================
var effectiveDnsPrefix = !empty(dnsPrefix) ? dnsPrefix : name
var enableMonitoring = !empty(logAnalyticsWorkspaceResourceId)

var effectiveAgentPools = [for pool in agentPools: union(pool, !empty(agentPoolSubnetId) ? { vnetSubnetResourceId: agentPoolSubnetId } : {})]

// ============================================================================
// AVM Module Deployment
// ============================================================================
module aksCluster 'br/public:avm/res/container-service/managed-cluster:0.13.1' = {
  name: take('avm.res.container-service.managed-cluster.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    kubernetesVersion: kubernetesVersion
    primaryAgentPoolProfiles: effectiveAgentPools
    enableRBAC: enableRBAC
    disableLocalAccounts: disableLocalAccounts
    networkPlugin: networkPlugin
    networkPolicy: networkPolicy
    dnsPrefix: effectiveDnsPrefix
    skuTier: skuTier
    serviceCidr: serviceCidr
    dnsServiceIP: dnsServiceIP
    publicNetworkAccess: publicNetworkAccess
    apiServerAccessProfile: {
      enablePrivateCluster: enablePrivateCluster
    }
    autoUpgradeProfile: {
      upgradeChannel: autoUpgradeChannel
      nodeOSUpgradeChannel: 'Unmanaged'
    }
    managedIdentities: managedIdentities
    omsAgentEnabled: enableMonitoring
    monitoringWorkspaceResourceId: enableMonitoring ? logAnalyticsWorkspaceResourceId : null
    diagnosticSettings: !empty(diagnosticSettings) ? diagnosticSettings : []
    securityProfile: enableDefender && enableMonitoring ? {
      defender: {
        logAnalyticsWorkspaceResourceId: logAnalyticsWorkspaceResourceId
        securityMonitoring: {
          enabled: true
        }
      }
    } : {}
    roleAssignments: roleAssignments
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Name of the AKS cluster.')
output name string = aksCluster.outputs.name

@description('Resource ID of the AKS cluster.')
output resourceId string = aksCluster.outputs.resourceId

@description('FQDN of the AKS cluster.')
output fqdn string = aksCluster.outputs.?fqdn ?? ''

@description('Object ID of the AKS kubelet system-assigned managed identity (used by pods at runtime via IMDS).')
output kubeletIdentityObjectId string = aksCluster.outputs.?kubeletIdentityObjectId ?? ''

@description('Principal ID of the AKS control-plane system-assigned managed identity.')
output systemAssignedMIPrincipalId string = aksCluster.outputs.?systemAssignedMIPrincipalId ?? ''
