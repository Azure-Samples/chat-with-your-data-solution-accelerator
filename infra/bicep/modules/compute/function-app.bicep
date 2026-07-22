// ============================================================================
// Module: Azure Function App
// Description: Creates an Azure Function App on Linux
// API: Microsoft.Web/sites@2024-04-01
// ============================================================================

@description('Name of the function app.')
param name string

@description('Azure region for deployment.')
param location string

@description('Resource tags.')
param tags object = {}

@description('Resource ID of the App Service Plan.')
param serverFarmResourceId string

@description('Name of the storage account.')
param storageAccountName string

@description('Client ID of the user-assigned managed identity used for identity-based AzureWebJobsStorage access.')
param userAssignedIdentityClientId string = ''

@description('Optional. Managed identity configuration for the resource.')
param identity object = { type: 'SystemAssigned' }

@description('App settings as name-value pairs.')
param appSettings array = []

@description('Site configuration object.')
param siteConfig object = {}

@description('Runtime stack.')
param runtimeStack string = 'python'

@description('Runtime version.')
param runtimeVersion string = '3.11'

@description('Resource kind for the site. Use functionapp,linux for code/zip or functionapp,linux,container for a container image.')
param kind string = 'functionapp,linux'

@description('Optional. Full docker image reference (registry/repo:tag) for container-hosted function apps. When set, the app runs from this image instead of a code/zip package.')
param dockerFullImageName string = ''

// ============================================================================
// Variables
// ===========================================================================
var useDocker = !empty(dockerFullImageName)
var linuxFxVersion = useDocker ? 'DOCKER|${dockerFullImageName}' : '${toUpper(runtimeStack)}|${runtimeVersion}'

// Identity-based AzureWebJobsStorage (no account keys): the host authenticates to
// the storage account with the user-assigned managed identity. Code/zip-only
// settings (worker runtime + run-from-package) are dropped in container mode:
// the image provides the runtime and there is no zip package.
var baseSettings = concat(
  [
    { name: 'AzureWebJobsStorage__accountName', value: storageAccountName }
    { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
    { name: 'AzureWebJobsStorage__clientId', value: userAssignedIdentityClientId }
    { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
    { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: string(useDocker ? false : true) }
    { name: 'ENABLE_ORYX_BUILD', value: string(useDocker ? false : contains(kind, 'linux')) }
    { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false' }
  ],
  useDocker
    ? []
    : [
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: toLower(runtimeStack) }
        { name: 'WEBSITE_RUN_FROM_PACKAGE', value: '1' }
      ]
)

var mergedSettings = concat(baseSettings, appSettings)

var defaultSiteConfig = {
  linuxFxVersion: linuxFxVersion
  ftpsState: 'Disabled'
  minTlsVersion: '1.2'
  appSettings: mergedSettings
}

var effectiveSiteConfig = union(defaultSiteConfig, siteConfig)

// ============================================================================
// Resource Deployment
// ============================================================================
resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: name
  location: location
  tags: tags
  kind: kind
  identity: identity
  properties: {
    serverFarmId: serverFarmResourceId
    siteConfig: effectiveSiteConfig
    httpsOnly: true
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('The name of the function app.')
output name string = functionApp.name

@description('The resource ID of the function app.')
output resourceId string = functionApp.id

@description('The default hostname of the function app.')
output defaultHostName string = functionApp.properties.defaultHostName

@description('The principal ID of the system-assigned managed identity.')
output principalId string = contains(functionApp.identity, 'principalId') ? functionApp.identity.principalId : ''
