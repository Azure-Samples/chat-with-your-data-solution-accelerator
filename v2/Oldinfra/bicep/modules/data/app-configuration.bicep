// ============================================================================
// Module: Azure App Configuration
// Description: Creates an Azure App Configuration store
// API: Microsoft.AppConfiguration/configurationStores@2023-03-01
// ============================================================================

@description('Solution name used for naming convention.')
param solutionName string

@description('Name of the App Configuration store.')
param name string = 'appcs-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('SKU for the configuration store.')
@allowed(['Free', 'Standard'])
param sku string = 'Standard'

@description('Disable local (key-based) authentication.')
param disableLocalAuth bool = true

@description('Key-value pairs to store in the configuration.')
param keyValues array = []

// ============================================================================
// Resource Deployment
// ============================================================================
resource appConfiguration 'Microsoft.AppConfiguration/configurationStores@2023-03-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    disableLocalAuth: disableLocalAuth
    publicNetworkAccess: 'Enabled'
  }
}

resource configurationKeyValues 'Microsoft.AppConfiguration/configurationStores/keyValues@2023-03-01' = [for keyValue in keyValues: {
  name: keyValue.name
  parent: appConfiguration
  properties: {
    value: keyValue.value
  }
}]

// ============================================================================
// Outputs
// ============================================================================
@description('The name of the App Configuration store.')
output name string = appConfiguration.name

@description('The endpoint of the App Configuration store.')
output endpoint string = appConfiguration.properties.endpoint

@description('The resource ID of the App Configuration store.')
output resourceId string = appConfiguration.id
