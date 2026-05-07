metadata name = 'Machine Learning Services Workspaces Computes'
metadata description = '''This module deploys a Machine Learning Services Workspaces Compute.

Attaching a compute is not idempotent and will fail in case you try to redeploy over an existing compute in AML (see parameter `deployCompute`).'''

// ================ //
// Parameters       //
// ================ //

@sys.description('Conditional. The name of the parent Machine Learning Workspace. Required if the template is used in a standalone deployment.')
param machineLearningWorkspaceName string

@sys.description('Required. Name of the compute.')
@minLength(2)
@maxLength(16)
param name string

@sys.description('Optional. Specifies the location of the resource.')
param location string = resourceGroup().location

@sys.description('Optional. Specifies the sku, also referred as "edition". Required for creating a compute resource.')
@allowed([
  'Basic'
  'Free'
  'Premium'
  'Standard'
])
param sku string?

@sys.description('Optional. Contains resource tags defined as key-value pairs. Ignored when attaching a compute resource, i.e. when you provide a resource ID.')
param tags object?

@sys.description('Optional. Flag to specify whether to deploy the compute. Required only for attach (i.e. providing a resource ID), as in this case the operation is not idempotent, i.e. a second deployment will fail. Therefore, this flag needs to be set to "false" as long as the compute resource exists.')
param deployCompute bool = true

@sys.description('Optional. Location for the underlying compute. Ignored when attaching a compute resource, i.e. when you provide a resource ID.')
param computeLocation string = resourceGroup().location

@sys.description('Optional. The description of the Machine Learning compute.')
param description string?

@sys.description('Optional. Opt-out of local authentication and ensure customers can use only MSI and AAD exclusively for authentication.')
param disableLocalAuth bool = false

@sys.description('Optional. ARM resource ID of the underlying compute.')
param resourceId string?

@sys.description('Required. Set the object type.')
@allowed([
  'AKS'
  'AmlCompute'
  'ComputeInstance'
  'Databricks'
  'DataFactory'
  'DataLakeAnalytics'
  'HDInsight'
  'Kubernetes'
  'SynapseSpark'
  'VirtualMachine'
])
param computeType string

@sys.description('Optional. The properties of the compute. Will be ignored in case "resourceId" is set.')
param properties object?

import { managedIdentityAllType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@sys.description('Optional. The managed identity definition for this resource.')
param managedIdentities managedIdentityAllType?

// ================//
// Variables       //
// ================//

var formattedUserAssignedIdentities = reduce(
  map((managedIdentities.?userAssignedResourceIds ?? []), (id) => { '${id}': {} }),
  {},
  (cur, next) => union(cur, next)
) // Converts the flat array to an object like { '${id1}': {}, '${id2}': {} }

var identity = !empty(managedIdentities)
  ? {
      type: (managedIdentities.?systemAssigned ?? false)
        ? (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'SystemAssigned,UserAssigned' : 'SystemAssigned')
        : (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'UserAssigned' : null)
      userAssignedIdentities: !empty(formattedUserAssignedIdentities) ? formattedUserAssignedIdentities : null
    }
  : null

// ============================= //
// Existing resources references //
// ============================= //

resource machineLearningWorkspace 'Microsoft.MachineLearningServices/workspaces@2022-10-01' existing = {
  name: machineLearningWorkspaceName
}

// ============ //
// Deployments  //
// ============ //

resource compute 'Microsoft.MachineLearningServices/workspaces/computes@2024-10-01' = if (deployCompute == true) {
  name: name
  location: location
  tags: empty(resourceId) ? tags : any(null)
  sku: empty(resourceId)
    ? {
        name: sku
        tier: sku
      }
    : any(null)
  parent: machineLearningWorkspace
  identity: empty(resourceId) ? identity : any(null)
  properties: union(
    {
      description: description
      disableLocalAuth: disableLocalAuth
      computeType: computeType
    },
    (!empty(resourceId)
      ? {
          resourceId: resourceId
        }
      : {
          computeLocation: computeLocation
          properties: properties
        })
  )
}

// =========== //
// Outputs     //
// =========== //

@sys.description('The name of the compute.')
output name string = compute.name

@sys.description('The resource ID of the compute.')
output resourceId string = compute.id

@sys.description('The resource group the compute was deployed into.')
output resourceGroupName string = resourceGroup().name

@sys.description('The principal ID of the system assigned identity.')
output systemAssignedMIPrincipalId string? = compute.?identity.?principalId

@sys.description('The location the resource was deployed into.')
output location string = compute.location
