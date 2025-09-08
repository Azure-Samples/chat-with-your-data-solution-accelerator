@description('The name of the Azure Function App to create.')
param name string

@description('Location for all resources.')
param location string = ''

@description('The resource ID of the app service plan to use.')
param serverFarmResourceId string

@description('The name of the storage account for the function app.')
param storageAccountName string = ''

@description('Tags for all resources.')
param tags object = {}

@description('App settings for the function app.')
@secure()
param appSettings object = {}

@description('The name of the Application Insights resource.')
param applicationInsightsName string = ''

@description('The runtime name for the function app.')
param runtimeName string = 'python'

@description('The runtime version for the function app.')
param runtimeVersion string = ''

@description('The client key for the function app.')
@secure()
param clientKey string

@description('The full name of the Docker image if using containers.')
param dockerFullImageName string = ''

// Import AVM type definitions
import { privateEndpointSingleServiceType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
import { diagnosticSettingFullType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'

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

@description('Optional. Configuration details for private endpoints.')
param privateEndpoints privateEndpointSingleServiceType[] = []

@description('Optional. The diagnostic settings of the service.')
param diagnosticSettings diagnosticSettingFullType[] = []

@description('Optional. The managed identity definition for this resource.')
param userAssignedIdentityResourceId string = ''

module function '../core/host/functions.bicep' = {
  name: '${name}-app-module'
  params: {
    name: name
    location: location
    tags: tags
    kind: 'functionapp,linux'
    appServicePlanId: serverFarmResourceId
    storageAccountName: storageAccountName
    applicationInsightsName: applicationInsightsName
    runtimeName: runtimeName
    runtimeVersion: runtimeVersion
    userAssignedIdentityResourceId: userAssignedIdentityResourceId
    allowedOrigins: []
    alwaysOn: true
    appCommandLine: empty(dockerFullImageName) ? '' : ''
    appSettings: union(
      appSettings,
      {
        FUNCTIONS_EXTENSION_VERSION: '~4'
      },
      !empty(dockerFullImageName) ? {} : { FUNCTIONS_WORKER_RUNTIME: runtimeName },
      { AzureWebJobsStorage__accountName: storageAccountName }
    )
    dockerFullImageName: dockerFullImageName
    // WAF aligned parameters
    virtualNetworkSubnetId: virtualNetworkSubnetId
    vnetContentShareEnabled: vnetContentShareEnabled
    vnetImagePullEnabled: vnetImagePullEnabled
    vnetRouteAllEnabled: vnetRouteAllEnabled
    publicNetworkAccess: publicNetworkAccess
    privateEndpoints: privateEndpoints
    diagnosticSettings: diagnosticSettings
  }
}

// This resource type warning is expected and can be ignored as it's not available in bicep registry
resource functionNameDefaultClientKey 'Microsoft.Web/sites/host/functionKeys@2022-09-01' = {
  name: '${name}/default/clientKey'
  properties: {
    name: 'ClientKey'
    value: clientKey
  }
  dependsOn: [
    function
    waitFunctionDeploymentSection
  ]
}

resource waitFunctionDeploymentSection 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  kind: 'AzurePowerShell'
  name: 'WaitFunctionDeploymentSection'
  location: location
  properties: {
    azPowerShellVersion: '11.0'
    scriptContent: 'start-sleep -Seconds 300'
    cleanupPreference: 'Always'
    retentionInterval: 'PT1H'
  }
  dependsOn: [
    function
  ]
}

output functionName string = function.outputs.name
output functionUri string = 'https://${function.outputs.uri}'
output AzureWebJobsStorage string = storageAccountName
