// ============================================================================
// Module: Azure Container App
// Description: Creates an Azure Container App
// API: Microsoft.App/containerApps@2024-10-02-preview
// ============================================================================

@description('Name of the container app.')
param name string

@description('Azure region for deployment.')
param location string

@description('Resource tags.')
param tags object = {}

@description('Resource ID of the Container Apps Environment.')
param environmentResourceId string

@description('Container definitions.')
param containers array

@description('Enable external ingress.')
param ingressExternal bool = true

@description('Target port for ingress.')
param ingressTargetPort int = 80

@description('Ingress transport protocol.')
@allowed(['auto', 'http', 'http2', 'tcp'])
param ingressTransport string = 'auto'

@description('Whether to allow insecure ingress connections.')
param ingressAllowInsecure bool = false

@description('Disable ingress entirely (for background workers).')
param disableIngress bool = false

@description('Container registry configurations.')
param registries array?

@description('Secret definitions.')
param secrets array?

@description('Managed identity configuration.')
param managedIdentities object = {}

@description('CORS policy configuration.')
param corsPolicy object = {}

@description('Active revision mode.')
@allowed(['Single', 'Multiple'])
param activeRevisionsMode string = 'Single'

@description('Scale settings (maxReplicas, minReplicas, rules).')
param scaleSettings object = {
  maxReplicas: 10
  minReplicas: 0
}

@description('Workload profile name.')
param workloadProfileName string?

// ============================================================================
// Resource Deployment
// ============================================================================
var identityConfig = empty(managedIdentities) ? { type: 'None' } : {
  type: contains(managedIdentities, 'userAssignedResourceIds') ? (contains(managedIdentities, 'systemAssigned') && managedIdentities.systemAssigned ? 'SystemAssigned,UserAssigned' : 'UserAssigned') : 'SystemAssigned'
  userAssignedIdentities: contains(managedIdentities, 'userAssignedResourceIds') ? reduce(managedIdentities.userAssignedResourceIds, {}, (cur, id) => union(cur, { '${id}': {} })) : null
}

var ingressConfig = disableIngress ? null : {
  external: ingressExternal
  targetPort: ingressTargetPort
  transport: ingressTransport
  allowInsecure: ingressAllowInsecure
  corsPolicy: !empty(corsPolicy) ? corsPolicy : null
}

resource containerApp 'Microsoft.App/containerApps@2024-10-02-preview' = {
  name: name
  location: location
  tags: tags
  identity: identityConfig
  properties: {
    managedEnvironmentId: environmentResourceId
    workloadProfileName: workloadProfileName
    configuration: {
      activeRevisionsMode: activeRevisionsMode
      ingress: ingressConfig
      registries: registries
      secrets: secrets
    }
    template: {
      containers: containers
      scale: {
        minReplicas: scaleSettings.minReplicas
        maxReplicas: scaleSettings.maxReplicas
        rules: contains(scaleSettings, 'rules') ? scaleSettings.rules : null
      }
    }
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('The name of the container app.')
output name string = containerApp.name

@description('The resource ID of the container app.')
output resourceId string = containerApp.id

@description('The FQDN of the container app.')
output fqdn string = !disableIngress ? containerApp.properties.configuration.ingress.fqdn : ''

@description('System-assigned identity principal ID.')
output principalId string = contains(containerApp.identity.type, 'SystemAssigned') ? containerApp.identity.principalId : ''
