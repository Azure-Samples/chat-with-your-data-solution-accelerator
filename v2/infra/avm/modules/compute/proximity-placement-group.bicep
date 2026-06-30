// ============================================================================
// Module: Proximity Placement Group
// Description: AVM wrapper for Azure Proximity Placement Group
// AVM Module: avm/res/compute/proximity-placement-group
// WAF: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/virtual-machines
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the proximity placement group.')
param name string = 'ppg-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Availability zone for the proximity placement group.')
param availabilityZone int = 1

@description('VM sizes intent for the proximity placement group.')
param vmSizes array = []

@description('Enable Azure telemetry collection.')
param enableTelemetry bool = true

// ============================================================================
// AVM Module Deployment
// ============================================================================
module proximityPlacementGroup 'br/public:avm/res/compute/proximity-placement-group:0.4.1' = {
  name: take('avm.res.compute.proximity-placement-group.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    availabilityZone: availabilityZone
    intent: !empty(vmSizes) ? { vmSizes: vmSizes } : null
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the proximity placement group.')
output resourceId string = proximityPlacementGroup.outputs.resourceId

@description('Name of the proximity placement group.')
output name string = proximityPlacementGroup.outputs.name
