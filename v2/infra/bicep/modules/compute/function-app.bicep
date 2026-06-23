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

@description('Resource ID of the storage account for function app.')
param storageAccountResourceId string

@description('Name of the storage account.')
param storageAccountName string

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

// ============================================================================
// Variables
// ===========================================================================
var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};AccountKey=${listKeys(storageAccountResourceId, '2023-05-01').keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
var linuxFxVersion = '${toUpper(runtimeStack)}|${runtimeVersion}'

var baseSettings = [
  { name: 'AzureWebJobsStorage', value: storageConnectionString }
  { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
  { name: 'FUNCTIONS_WORKER_RUNTIME', value: toLower(runtimeStack) }
  { name: 'WEBSITE_RUN_FROM_PACKAGE', value: '1' }
]

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
  kind: 'functionapp,linux'
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
