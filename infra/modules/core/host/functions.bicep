metadata description = 'Creates an Azure Function in an existing Azure App Service plan.'
param name string
param location string = resourceGroup().location
param tags object = {}

// Import the type definition for managed identities
import { managedIdentityAllType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'

// Reference Properties
param applicationInsightsName string = ''
param appServicePlanId string
param keyVaultName string = ''
param managedIdentity bool = true
param userAssignedIdentity managedIdentityAllType = {}
param storageAccountName string

// Runtime Properties
@allowed([
  'dotnet'
  'dotnetcore'
  'dotnet-isolated'
  'node'
  'python'
  'java'
  'powershell'
  'custom'
])
param runtimeName string
param runtimeVersion string

// Function Settings
@allowed([
  '~4'
  '~3'
  '~2'
  '~1'
])
param extensionVersion string = '~4'

// Microsoft.Web/sites Properties
param kind string = 'functionapp,linux'

// Microsoft.Web/sites/config
param allowedOrigins array = []
param alwaysOn bool = true
param appCommandLine string = ''
@secure()
param appSettings object = {}
param clientAffinityEnabled bool = false
param functionAppScaleLimit int = -1
param minimumElasticInstanceCount int = -1
param numberOfWorkers int = -1
param use32BitWorkerProcess bool = false
param healthCheckPath string = ''
param dockerFullImageName string = ''
param useDocker bool = dockerFullImageName != ''

// WAF aligned parameters
@description('Optional. Azure Resource Manager ID of the Virtual network and subnet to be joined by Regional VNET Integration.')
param virtualNetworkSubnetId string = ''

@description('Optional. To enable accessing content over virtual network.')
param vnetContentShareEnabled bool = false

@description('Optional. To enable pulling image over Virtual Network.')
param vnetImagePullEnabled bool = false

@description('Optional. Virtual Network Route All enabled. This causes all outbound traffic to have Virtual Network Security Groups and User Defined Routes applied.')
param vnetRouteAllEnabled bool = false

@description('Optional. Whether or not public network access is allowed for this resource.')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

import { privateEndpointSingleServiceType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. Configuration details for private endpoints.')
param privateEndpoints privateEndpointSingleServiceType[] = []

import { diagnosticSettingFullType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. The diagnostic settings of the service.')
param diagnosticSettings diagnosticSettingFullType[] = []

module functions 'appservice.bicep' = {
  name: '${name}-functions'
  params: {
    name: name
    location: location
    tags: tags
    kind: kind
    serverFarmResourceId: appServicePlanId
    siteConfig: {
      alwaysOn: alwaysOn
      appCommandLine: useDocker ? '' : appCommandLine
      linuxFxVersion: empty(dockerFullImageName)
        ? '${toUpper(runtimeName)}|${runtimeVersion}'
        : 'DOCKER|${dockerFullImageName}'
      functionAppScaleLimit: functionAppScaleLimit
      minimumElasticInstanceCount: minimumElasticInstanceCount
      numberOfWorkers: numberOfWorkers
      use32BitWorkerProcess: use32BitWorkerProcess
      cors: {
        allowedOrigins: allowedOrigins
      }
      healthCheckPath: healthCheckPath
      minTlsVersion: '1.2'
      ftpsState: 'FtpsOnly'
    }
    clientAffinityEnabled: clientAffinityEnabled
    storageAccountRequired: true
    // WAF aligned configurations
    virtualNetworkSubnetId: virtualNetworkSubnetId
    vnetContentShareEnabled: vnetContentShareEnabled
    vnetImagePullEnabled: vnetImagePullEnabled
    vnetRouteAllEnabled: vnetRouteAllEnabled
    publicNetworkAccess: publicNetworkAccess
    privateEndpoints: privateEndpoints
    diagnosticSettings: diagnosticSettings
    managedIdentities: union(
      {
        systemAssigned: managedIdentity
      },
      !empty(userAssignedIdentity) ? userAssignedIdentity : {}
    )
    keyVaultAccessIdentityResourceId: !empty(keyVaultName)
      ? '${resourceGroup().id}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${keyVaultName}'
      : null
    configs: [
      {
        name: 'appsettings'
        properties: union(
          appSettings,
          {
            FUNCTIONS_EXTENSION_VERSION: extensionVersion
          },
          !useDocker ? { FUNCTIONS_WORKER_RUNTIME: runtimeName } : {},
          { AzureWebJobsStorage__accountName: storage.name }
        )
        applicationInsightResourceId: !empty(applicationInsightsName)
          ? resourceId('Microsoft.Insights/components', applicationInsightsName)
          : null
      }
    ]
  }
}

// Simplify the user assigned identity handling
var userAssignedResourceId = !empty(userAssignedIdentity) && !empty(userAssignedIdentity.?userAssignedResourceIds) && length(userAssignedIdentity.?userAssignedResourceIds ?? []) > 0
  ? (userAssignedIdentity.?userAssignedResourceIds[0] ?? '')
  : ''

// We'll get the principal ID in the module role assignment if needed
module storageBlobRoleFunction '../security/role.bicep' = {
  name: 'storage-blob-role-function'
  params: {
    principalId: managedIdentity ? (functions.outputs.?systemAssignedMIPrincipalId ?? '') : userAssignedResourceId
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    principalType: 'ServicePrincipal'
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2021-09-01' existing = {
  name: storageAccountName
}

output identityPrincipalId string = managedIdentity
  ? (functions.outputs.?systemAssignedMIPrincipalId ?? '')
  : userAssignedResourceId
output name string = functions.outputs.name
output uri string = functions.outputs.defaultHostname
output azureWebJobsStorage string = storage.name
