// ============================================================================
// Module: Azure Container Instance (AVM)
// AVM Module: avm/res/container-instance/container-group:0.7.0
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

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

@description('Image registry credentials.')
param imageRegistryCredentials array = []

@description('Subnet resource ID for VNet integration. If empty, public IP is used.')
param subnetResourceId string = ''

@description('Availability zone for the container group. Use -1 for no zone.')
param availabilityZone int = -1

@description('Enable Azure telemetry collection.')
param enableTelemetry bool = true

// ============================================================================
// Variables
// ============================================================================
var isPrivateNetworking = !empty(subnetResourceId)

var containers = [
  {
    name: name
    properties: {
      image: containerImage
      resources: {
        requests: {
          cpu: cpu
          memoryInGB: string(memoryInGB)
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

// ============================================================================
// Container Instance (AVM)
// ============================================================================
module containerGroup 'br/public:avm/res/container-instance/container-group:0.7.0' = {
  name: take('avm.res.containerinstance.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    containers: containers
    osType: osType
    restartPolicy: restartPolicy
    managedIdentities: managedIdentities
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
    imageRegistryCredentials: !empty(imageRegistryCredentials) ? imageRegistryCredentials : []
    subnets: isPrivateNetworking ? [{ subnetResourceId: subnetResourceId }] : []
    availabilityZone: availabilityZone
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('The name of the container group.')
output name string = containerGroup.outputs.name

@description('The resource ID of the container group.')
output resourceId string = containerGroup.outputs.resourceId

@description('The IP address of the container group.')
output ipAddress string = containerGroup.outputs.?iPv4Address ?? ''
