@description('The name of the web app to create.')
param name string

@description('Location for all resources.')
param location string = resourceGroup().location

@description('Tags for all resources.')
param tags object = {}

@description('Origin URLs allowed to call this web app.')
param allowedOrigins array = []

@description('Command to run when starting the web app.')
param appCommandLine string = ''

@description('The resource ID of the app service plan to use for the web app.')
param serverFarmResourceId string

@description('The name of the Application Insights resource.')
param applicationInsightsName string = ''

@description('The runtime name for the web app.')
param runtimeName string = 'python'

@description('The runtime version for the web app.')
param runtimeVersion string = ''

@description('The name of the Key Vault where secrets should be stored.')
param keyVaultName string = ''

@description('The app settings to be applied to the web app.')
@secure()
param appSettings object = {}

@description('The full name of the Docker image if using containers.')
param dockerFullImageName string = ''

@description('Whether to use Docker for this web app.')
param useDocker bool = dockerFullImageName != ''

@description('The health check path for the web app.')
param healthCheckPath string = ''

// AVM WAF parameters
@description('The kind of web app to create')
param kind string = 'app,linux'

@description('Optional. The managed identity definition for this resource.')
param userAssignedIdentity object = {}

@description('Optional. Diagnostic settings for the resource.')
param diagnosticSettings array = []

@description('Optional. To enable pulling image over Virtual Network.')
param vnetImagePullEnabled bool = false

@description('Optional. Virtual Network Route All enabled.')
param vnetRouteAllEnabled bool = false

@description('Optional. Azure Resource Manager ID of the Virtual network subnet.')
param virtualNetworkSubnetId string = ''

@description('Optional. Whether or not public network access is allowed for this resource.')
param publicNetworkAccess string = ''

@description('Optional. Configuration details for private endpoints.')
param privateEndpoints array = []

// Import AVM types - not using the imports directly but the types are compatible with the parameters

// Calculate the linuxFxVersion based on runtime or docker settings
var linuxFxVersion = useDocker
  ? 'DOCKER|${dockerFullImageName}'
  : (empty(runtimeVersion) ? toUpper(runtimeName) : '${toUpper(runtimeName)}|${runtimeVersion}')

// Site configuration
var siteConfig = {
  linuxFxVersion: linuxFxVersion
  appCommandLine: useDocker ? '' : appCommandLine
  healthCheckPath: healthCheckPath
  cors: {
    allowedOrigins: allowedOrigins
  }
  minTlsVersion: '1.2'
}

// Build the configs array expected by the child module (appsettings config)
var appConfigs = [
  {
    name: 'appsettings'
    properties: appSettings
    applicationInsightResourceId: empty(applicationInsightsName) ? null : applicationInsightsName
    storageAccountResourceId: null
    storageAccountUseIdentityAuthentication: null
    retainCurrentAppSettings: true
  }
]

module web '../core/host/appservice.bicep' = {
  name: '${name}-app-module'
  params: {
    name: name
    location: location
    tags: tags
    kind: kind
    serverFarmResourceId: serverFarmResourceId
    siteConfig: siteConfig
    configs: appConfigs
    diagnosticSettings: diagnosticSettings
    vnetImagePullEnabled: vnetImagePullEnabled
    vnetRouteAllEnabled: vnetRouteAllEnabled
    virtualNetworkSubnetId: virtualNetworkSubnetId
    publicNetworkAccess: empty(publicNetworkAccess) ? null : publicNetworkAccess
    privateEndpoints: privateEndpoints
    managedIdentities: userAssignedIdentity
  }
}

// Resolve a principalId to grant KeyVault access (prefer systemAssigned, fallback to first userAssigned if provided)
var firstUserAssignedIdentityResourceId = (!empty(userAssignedIdentity) && contains(
    userAssignedIdentity,
    'userAssignedResourceIds'
  ) && length(userAssignedIdentity.userAssignedResourceIds) > 0)
  ? userAssignedIdentity.userAssignedResourceIds[0]
  : (!empty(userAssignedIdentity) && contains(userAssignedIdentity, 'id') ? userAssignedIdentity.id : '')

var firstUserAssignedPrincipalId = !empty(firstUserAssignedIdentityResourceId)
  ? reference(firstUserAssignedIdentityResourceId, '2018-11-30', 'Full').principalId
  : ''

var keyVaultPrincipalId = !empty(web.outputs.?systemAssignedMIPrincipalId)
  ? web.outputs.?systemAssignedMIPrincipalId
  : (!empty(firstUserAssignedPrincipalId) ? firstUserAssignedPrincipalId : '')

// Key Vault access (grant to the identity returned by the appservice wrapper)
module webaccess '../core/security/keyvault-access.bicep' = if (!empty(keyVaultName)) {
  name: 'web-keyvault-access'
  params: {
    keyVaultName: keyVaultName
    principalId: keyVaultPrincipalId
  }
}

output FRONTEND_API_IDENTITY_PRINCIPAL_ID string? = !empty(web.outputs.?systemAssignedMIPrincipalId)
  ? web.outputs.?systemAssignedMIPrincipalId
  : (!empty(firstUserAssignedPrincipalId) ? firstUserAssignedPrincipalId : null)
output FRONTEND_API_NAME string = web.outputs.name
output FRONTEND_API_URI string = 'https://${web.outputs.defaultHostname}'
