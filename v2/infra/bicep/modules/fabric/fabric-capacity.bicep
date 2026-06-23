// ============================================================================
// Module: Fabric Capacity
// Description: Vanilla Bicep module for Microsoft Fabric Capacity
// Resource: Microsoft.Fabric/capacities@2023-11-01
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

// ============================================================================
// Resource
// ============================================================================

resource fabricCapacity 'Microsoft.Fabric/capacities@2023-11-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: 'Fabric'
  }
  properties: {
    administration: {
      members: adminMembers
    }
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('The name of the deployed Fabric capacity.')
output name string = fabricCapacity.name

@description('The resource ID of the deployed Fabric capacity.')
output resourceId string = fabricCapacity.id

@description('The resource group name.')
output resourceGroupName string = resourceGroup().name

@description('The location of the deployed Fabric capacity.')
output location string = fabricCapacity.location
