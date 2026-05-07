metadata name = 'Site App Settings'
metadata description = 'This module deploys a Site App Setting.'

@description('Conditional. The name of the parent site resource. Required if the template is used in a standalone deployment.')
param appName string

@description('Required. The name of the config.')
@allowed([
  'appsettings'
  'authsettings'
  'authsettingsV2'
  'azurestorageaccounts'
  'backup'
  'connectionstrings'
  'logs'
  'metadata'
  'pushsettings'
  'slotConfigNames'
  'web'
])
param name string

@description('Optional. The properties of the config. Note: This parameter is highly dependent on the config type, defined by its name.')
param properties object = {}

// Parameters only relevant for the config type 'appsettings'
@description('Optional. If the provided storage account requires Identity based authentication (\'allowSharedKeyAccess\' is set to false). When set to true, the minimum role assignment required for the App Service Managed Identity to the storage account is \'Storage Blob Data Owner\'.')
param storageAccountUseIdentityAuthentication bool = false

@description('Optional. Required if app of kind functionapp. Resource ID of the storage account to manage triggers and logging function executions.')
param storageAccountResourceId string?

@description('Optional. Resource ID of the application insight to leverage for this resource.')
param applicationInsightResourceId string?

@description('Optional. The current app settings.')
param currentAppSettings {
  @description('Required. The key-values pairs of the current app settings.')
  *: string
} = {}

var azureWebJobsValues = !empty(storageAccountResourceId) && !storageAccountUseIdentityAuthentication
  ? {
      AzureWebJobsStorage: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount!.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
    }
  : !empty(storageAccountResourceId) && storageAccountUseIdentityAuthentication
      ? {
          AzureWebJobsStorage__accountName: storageAccount.name
          AzureWebJobsStorage__blobServiceUri: storageAccount!.properties.primaryEndpoints.blob
          AzureWebJobsStorage__queueServiceUri: storageAccount!.properties.primaryEndpoints.queue
          AzureWebJobsStorage__tableServiceUri: storageAccount!.properties.primaryEndpoints.table
        }
      : {}

var appInsightsValues = !empty(applicationInsightResourceId)
  ? {
      APPLICATIONINSIGHTS_CONNECTION_STRING: applicationInsights!.properties.ConnectionString
    }
  : {}

var expandedProperties = union(currentAppSettings, properties, azureWebJobsValues, appInsightsValues)

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = if (!empty(applicationInsightResourceId)) {
  name: last(split(applicationInsightResourceId!, '/'))
  scope: resourceGroup(split(applicationInsightResourceId!, '/')[2], split(applicationInsightResourceId!, '/')[4])
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' existing = if (!empty(storageAccountResourceId)) {
  name: last(split(storageAccountResourceId!, '/'))
  scope: resourceGroup(split(storageAccountResourceId!, '/')[2], split(storageAccountResourceId!, '/')[4])
}

resource app 'Microsoft.Web/sites@2023-12-01' existing = {
  name: appName
}

resource config 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: app
  #disable-next-line BCP225
  name: name
  properties: expandedProperties
}

@description('The name of the site config.')
output name string = config.name

@description('The resource ID of the site config.')
output resourceId string = config.id

@description('The resource group the site config was deployed into.')
output resourceGroupName string = resourceGroup().name
