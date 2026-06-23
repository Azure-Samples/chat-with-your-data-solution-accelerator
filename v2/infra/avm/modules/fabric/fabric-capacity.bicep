// ============================================================================
// Module: Fabric Capacity
// Description: AVM wrapper for Microsoft Fabric Capacity
// AVM Module: avm/res/fabric/capacity:0.1.2
// Docs: https://learn.microsoft.com/azure/templates/microsoft.fabric/capacities
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Optional. Override name for the Fabric capacity. Defaults to fc{solutionName}.')
param name string = 'fc${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('SKU tier of the Fabric capacity.')
@allowed([
  'F2'
  'F4'
  'F8'
  'F16'
  'F32'
  'F64'
  'F128'
  'F256'
  'F512'
  'F1024'
  'F2048'
])
param skuName string = 'F2'

@description('List of admin members (UPNs for users, object IDs for service principals).')
param adminMembers array

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// ============================================================================
// AVM Module Reference
// ============================================================================

module fabricCapacity 'br/public:avm/res/fabric/capacity:0.1.2' = {
  name: take('avm.res.fabric.capacity.${name}', 64)
  params: {
    name: name
    location: location
    skuName: skuName
    adminMembers: adminMembers
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('The name of the deployed Fabric capacity.')
output name string = fabricCapacity.outputs.name

@description('The resource ID of the deployed Fabric capacity.')
output resourceId string = fabricCapacity.outputs.resourceId

@description('The resource group name.')
output resourceGroupName string = fabricCapacity.outputs.resourceGroupName

@description('The location of the deployed Fabric capacity.')
output location string = fabricCapacity.outputs.location
