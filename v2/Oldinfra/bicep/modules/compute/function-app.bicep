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

@description('App settings as name-value pairs.')
param appSettings object = {}

@description('Runtime stack.')
param runtimeStack string = 'python'

@description('Runtime version.')
param runtimeVersion string = '3.11'

@description('Optional. Docker image name to use for container function apps.')
param dockerFullImageName string = ''

@description('Name of the Application Insights instance.')
param applicationInsightsName string = ''

@description('Resource ID of a user-assigned managed identity to attach to the Function App.')
param userAssignedIdentityId string = ''

@description('Optional. The client ID of the user assigned identity for the function app. This is required to set the AZURE_CLIENT_ID app setting so the function app can authenticate with the user assigned managed identity.')
param userAssignedIdentityClientId string = ''

@description('Resource kind for the site (e.g., functionapp,linux).')
param kind string = 'functionapp,linux'

@description('Number of workers (instances) to allocate. Set to -1 to use default.')
param functionAppScaleLimit int = -1

@description('Number of workers (instances) to allocate. Set to -1 to use default.')
param minimumElasticInstanceCount int = -1

@description('Custom application command line (for Linux apps).')
param appCommandLine string = ''

@description('Number of workers (instances) to allocate. Set to -1 to use default.')
param numberOfWorkers int = -1

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
  runtimeStack == 'python' && !useDocker ? { PYTHON_ENABLE_GUNICORN_MULTIWORKERS: 'true' } : {},
  !empty(applicationInsightsName)
      ? { APPLICATIONINSIGHTS_CONNECTION_STRING: applicationInsights!.properties.ConnectionString }
      : {}
)
var configSettings = union(baseAppSettings, appSettings)
var identityConfig = userAssignedIdentityId == ''
  ? { type: 'SystemAssigned' }
  : {
      type: 'SystemAssigned, UserAssigned'
      userAssignedIdentities: {
        '${userAssignedIdentityId}': {}
      }
    }

// ============================================================================
// Resource Deployment
// ============================================================================

resource functionApp 'Microsoft.Web/sites@2025-03-01' = {
  name: name
  location: location
  tags: tags
  kind: kind
  identity: identityConfig
  properties: {
    serverFarmId: serverFarmResourceId
    siteConfig: {
      linuxFxVersion: !empty(dockerFullImageName) ? 'DOCKER|${dockerFullImageName}' : '${toUpper(runtimeStack)}|${runtimeVersion}'
      alwaysOn: true
      ftpsState: 'FtpsOnly'
      minTlsVersion: '1.2'
      appCommandLine: appCommandLine
      numberOfWorkers: numberOfWorkers != -1 ? numberOfWorkers : null
      minimumElasticInstanceCount: minimumElasticInstanceCount != -1 ? minimumElasticInstanceCount : null
      use32BitWorkerProcess: false
      functionAppScaleLimit: functionAppScaleLimit != -1 ? functionAppScaleLimit : null
      cors: {
        allowedOrigins: ['https://portal.azure.com', 'https://ms.portal.azure.com']
      }
    }
    clientAffinityEnabled: false
    httpsOnly: true
  }

  resource basicPublishingCredentialsPoliciesFtp 'basicPublishingCredentialsPolicies' = {
    name: 'ftp'
    properties: {
      allow: false
    }
  }

  resource basicPublishingCredentialsPoliciesScm 'basicPublishingCredentialsPolicies' = {
    name: 'scm'
    properties: {
      allow: false
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = if (!empty(applicationInsightsName)) {
  name: applicationInsightsName
}

resource configAppSettings 'Microsoft.Web/sites/config@2025-03-01' = {
  name: 'appsettings'
  parent: functionApp
  properties: configSettings
}

resource configLogs 'Microsoft.Web/sites/config@2025-03-01' = {
  name: 'logs'
  parent: functionApp
  properties: {
    applicationLogs: { fileSystem: { level: 'Verbose' } }
    detailedErrorMessages: { enabled: true }
    failedRequestsTracing: { enabled: true }
    httpLogs: { fileSystem: { enabled: true, retentionInDays: 1, retentionInMb: 35 } }
  }
  dependsOn: [configAppSettings]
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
