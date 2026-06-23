// ============================================================================
// Module: Azure Container Instance
// Description: Creates an Azure Container Instance group
// API: Microsoft.ContainerInstance/containerGroups@2025-09-01
// ============================================================================

@description('Name of the container group.')
param name string

@description('Azure region for deployment.')
param location string

@description('Resource tags.')
param tags object = {}

@description('Container image to deploy.')
param containerImage string

@description('CPU cores for the container.')
param cpu int = 2

@description('Memory in GB for the container.')
param memoryInGB int = 4

@description('Port to expose.')
param port int = 8000

@description('Environment variables for the container.')
param environmentVariables array = []

@description('Operating system type.')
@allowed(['Linux', 'Windows'])
param osType string = 'Linux'

@description('Restart policy.')
@allowed(['Always', 'OnFailure', 'Never'])
param restartPolicy string = 'Always'

@description('Managed identity configuration.')
param managedIdentities object = {}

@description('Image registry credentials.')
param imageRegistryCredentials array = []

@description('Subnet resource ID for VNet integration. If empty, public IP is used.')
param subnetResourceId string = ''

@description('Availability zone for the container group. Use -1 for no zone.')
param availabilityZone int = -1

// ============================================================================
// Variables
// ============================================================================
var isPrivateNetworking = !empty(subnetResourceId)

var identityConfig = empty(managedIdentities) ? { type: 'None' } : {
  type: contains(managedIdentities, 'userAssignedResourceIds') ? 'UserAssigned' : 'SystemAssigned'
  userAssignedIdentities: contains(managedIdentities, 'userAssignedResourceIds') ? reduce(managedIdentities.userAssignedResourceIds, {}, (cur, id) => union(cur, { '${id}': {} })) : null
}

// ============================================================================
// Resource Deployment
// ============================================================================
resource containerGroup 'Microsoft.ContainerInstance/containerGroups@2025-09-01' = {
  name: name
  location: location
  tags: tags
  identity: identityConfig
  zones: availabilityZone != -1 ? [string(availabilityZone)] : null
  properties: {
    osType: osType
    restartPolicy: restartPolicy
    containers: [
      {
        name: name
        properties: {
          image: containerImage
          resources: {
            requests: {
              cpu: cpu
              memoryInGB: memoryInGB
            }
          }
          ports: [
            {
              port: port
              protocol: 'TCP'
            }
          ]
          environmentVariables: environmentVariables
        }
      }
    ]
    imageRegistryCredentials: imageRegistryCredentials
    subnetIds: isPrivateNetworking ? [{ id: subnetResourceId }] : null
    ipAddress: {
      type: isPrivateNetworking ? 'Private' : 'Public'
      ports: [
        {
          port: port
          protocol: 'TCP'
        }
      ]
      dnsNameLabel: isPrivateNetworking ? null : name
    }
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('The name of the container group.')
output name string = containerGroup.name

@description('The resource ID of the container group.')
output resourceId string = containerGroup.id

@description('The IP address of the container group.')
output ipAddress string = containerGroup.properties.ipAddress.ip
