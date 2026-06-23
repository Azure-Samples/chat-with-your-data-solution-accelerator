// ============================================================================
// Module: Azure Container Registry (AVM)
// AVM Module: avm/res/container-registry/registry:0.12.1
// ============================================================================

@description('Solution name used for naming convention.')
param solutionName string

@description('Name of the container registry.')
param name string = replace('cr${solutionName}', '-', '')

@description('Azure region for deployment.')
param location string

@description('Resource tags.')
param tags object = {}

@description('SKU for the container registry.')
@allowed(['Basic', 'Standard', 'Premium'])
param sku string = 'Standard'

@description('Enable admin user for the registry.')
param adminUserEnabled bool = false

@description('Public network access setting.')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Enabled'

@description('Export policy status. Must be "enabled" when publicNetworkAccess is "Enabled".')
param exportPolicyStatus string = 'enabled'

@description('Principal IDs to assign AcrPull role.')
param acrPullPrincipalIds array = []

// Additive: AcrPush for deployer so post-deploy docker push works without manual RBAC.
@description('Principal IDs to assign AcrPush role (typically the deployer).')
param acrPushPrincipalIds array = []

@description('Principal type for AcrPush assignments (User for azd user, ServicePrincipal for CI).')
@allowed(['User', 'ServicePrincipal', 'Group'])
param acrPushPrincipalType string = 'User'

@description('Enable private networking.')
param enablePrivateNetworking bool = false

@description('Subnet resource ID for private endpoint.')
param privateEndpointSubnetId string = ''

@description('Private DNS zone resource IDs for private endpoint.')
param privateDnsZoneResourceIds array = []

@description('Default action for the network rule set. Use Allow when no private endpoint is in place; Deny for private-only.')
@allowed(['Allow', 'Deny'])
param networkRuleSetDefaultAction string = 'Allow'

@description('Enable Azure telemetry collection.')
param enableTelemetry bool = true

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

// ============================================================================
// Role Assignments
// ============================================================================
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var acrPushRoleId = '8311e382-0749-4cb8-b61a-304f252e45ec'

var pullRoleAssignments = [for principalId in acrPullPrincipalIds: {
  principalId: principalId
  roleDefinitionIdOrName: acrPullRoleId
  principalType: 'ServicePrincipal'
}]

var pushRoleAssignments = [for principalId in acrPushPrincipalIds: {
  principalId: principalId
  roleDefinitionIdOrName: acrPushRoleId
  principalType: acrPushPrincipalType
}]

var roleAssignments = concat(
  !empty(acrPullPrincipalIds) ? pullRoleAssignments : [],
  !empty(acrPushPrincipalIds) ? pushRoleAssignments : []
)

// ============================================================================
// Private Endpoint Config
// ============================================================================
var dnsZoneConfigs = [for (zoneId, i) in privateDnsZoneResourceIds: {
  name: 'config${i}'
  privateDnsZoneResourceId: zoneId
}]

var privateEndpointConfig = enablePrivateNetworking && !empty(privateEndpointSubnetId) ? [
  {
    subnetResourceId: privateEndpointSubnetId
    privateDnsZoneGroup: !empty(privateDnsZoneResourceIds) ? {
      privateDnsZoneGroupConfigs: dnsZoneConfigs
    } : null
  }
] : []

// ============================================================================
// Container Registry (AVM)
// ============================================================================
module containerRegistry 'br/public:avm/res/container-registry/registry:0.12.1' = {
  name: take('avm.res.containerregistry.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    acrSku: sku
    acrAdminUserEnabled: adminUserEnabled
    publicNetworkAccess: publicNetworkAccess
    exportPolicyStatus: exportPolicyStatus
    roleAssignments: !empty(roleAssignments) ? roleAssignments : []
    privateEndpoints: privateEndpointConfig
    networkRuleSetDefaultAction: networkRuleSetDefaultAction
    managedIdentities: managedIdentities
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('The name of the container registry.')
output name string = containerRegistry.outputs.name

@description('The login server URL.')
output loginServer string = containerRegistry.outputs.loginServer

@description('The resource ID of the container registry.')
output resourceId string = containerRegistry.outputs.resourceId
