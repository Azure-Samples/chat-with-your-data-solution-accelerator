// ============================================================================
// Module: Azure Function App (AVM)
// AVM Module: avm/res/web/site:0.23.1
// ============================================================================

@description('Name of the function app.')
param name string

@description('Azure region for deployment.')
param location string

@description('Resource tags.')
param tags object = {}

@description('Resource ID of the App Service Plan.')
param serverFarmResourceId string

@description('Optional. Docker image name to use for container function apps.')
param dockerFullImageName string = ''

@description('Name of the storage account.')
param storageAccountName string

@description('Managed identity configuration.')
param managedIdentities object = {
  systemAssigned: true
}

@description('App settings as name-value pairs (array).')
param appSettings array = []

@description('Optional. Function app scale limit.')
param functionAppScaleLimit int = -1

@description('Optional. Minimum number of elastic instances for the function app.')
param minimumElasticInstanceCount int = -1

@description('Optional. Number of workers for the function app.')
param numberOfWorkers int = -1

@description('Optional. Whether to use 32-bit worker process for the function app.')
param use32BitWorkerProcess bool = false

@description('Site configuration object.')
param siteConfig object = {}

@description('Runtime stack.')
param runtimeStack string = 'python'

@description('Runtime version.')
param runtimeVersion string = '3.11'

@description('Resource kind for the site (e.g., functionapp,linux).')
param kind string = 'functionapp,linux'

@description('Enable Azure telemetry collection.')
param enableTelemetry bool = true

@description('Optional. Determines if the function app can integrate with a virtual network.')
param virtualNetworkSubnetId string = ''

@description('Optional. Enable end-to-end TLS encryption between the front end and worker. Requires Premium v2/v3 or Isolated v2 App Service Plan.')
param e2eEncryptionEnabled bool = false

@description('Optional. The client ID of the user assigned identity for the function app. This is required to set the AZURE_CLIENT_ID app setting so the function app can authenticate with the user assigned managed identity.')
param userAssignedIdentityClientId string = ''

@description('Optional. Resource ID of Application Insights for monitoring integration.')
param applicationInsightResourceId string = ''

// ============================================================================
// Variables
// ============================================================================
var useDocker = !empty(dockerFullImageName)
var baseAppSettings = union({
  WEBSITES_ENABLE_APP_SERVICE_STORAGE: 'false'
  FUNCTIONS_EXTENSION_VERSION: '~4'
  SCM_DO_BUILD_DURING_DEPLOYMENT: string(useDocker ? false : true)
  ENABLE_ORYX_BUILD: string(useDocker ? false : contains(kind, 'linux'))
  AZURE_RESOURCE_GROUP: resourceGroup().name
  AZURE_SUBSCRIPTION_ID: subscription().subscriptionId
  // Set the storage account settings to use user managed identity authentication
  AzureWebJobsStorage__accountName: storageAccountName
  AzureWebJobsStorage__credential: 'managedidentity'
  AzureWebJobsStorage__clientId: userAssignedIdentityClientId
},
  !useDocker ? { FUNCTIONS_WORKER_RUNTIME: runtimeStack } : {},
  runtimeStack == 'python' && !useDocker ? { PYTHON_ENABLE_GUNICORN_MULTIWORKERS: 'true' } : {}
)

var appSettingsObject = reduce(appSettings, {}, (cur, item) => union(cur, { '${item.name}': item.value }))
var mergedAppSettings = union(baseAppSettings, appSettingsObject)

var updatedSiteConfig = union(siteConfig, {
  functionAppScaleLimit: functionAppScaleLimit != -1 ? functionAppScaleLimit : null
  minimumElasticInstanceCount: minimumElasticInstanceCount != -1 ? minimumElasticInstanceCount : null
  numberOfWorkers: numberOfWorkers != -1 ? numberOfWorkers : null
  use32BitWorkerProcess: use32BitWorkerProcess
})

// ============================================================================
// Function App (AVM)
// ============================================================================
module functionApp 'br/public:avm/res/web/site:0.23.1' = {
  name: take('avm.res.web.site.func.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    kind: kind
    serverFarmResourceId: serverFarmResourceId
    storageAccountRequired: false
    managedIdentities: managedIdentities
    configs: [
      {
        name: 'appsettings'
        properties: mergedAppSettings
        applicationInsightResourceId: !empty(applicationInsightResourceId) ? applicationInsightResourceId : null
        storageAccountResourceId: resourceId('Microsoft.Storage/storageAccounts', storageAccountName)
        storageAccountUseIdentityAuthentication: true
        retainCurrentAppSettings: true
      }
    ]
    siteConfig: union({
      linuxFxVersion: !empty(dockerFullImageName) ? 'DOCKER|${dockerFullImageName}' : '${toUpper(runtimeStack)}|${runtimeVersion}'
    }, updatedSiteConfig)

    clientAffinityEnabled: false
    httpsOnly: true
    virtualNetworkSubnetResourceId: virtualNetworkSubnetId
    e2eEncryptionEnabled: e2eEncryptionEnabled
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('The name of the function app.')
output name string = functionApp.outputs.name

@description('The resource ID of the function app.')
output resourceId string = functionApp.outputs.resourceId

@description('The default hostname of the function app.')
output defaultHostName string = functionApp.outputs.defaultHostname

@description('The principal ID of the system-assigned managed identity.')
output principalId string = functionApp.outputs.?systemAssignedMIPrincipalId ?? ''
