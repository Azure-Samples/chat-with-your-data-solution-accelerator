// ============================================================================
// Module: App Service
// Description: Creates an Azure App Service (Web App)
// API: Microsoft.Web/sites@2025-05-01
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the App Service.')
param name string = solutionName

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Resource ID of the App Service Plan.')
param serverFarmResourceId string

@description('Docker image name (e.g., DOCKER|registry.azurecr.io/image:tag).')
param linuxFxVersion string

@description('Application settings key-value pairs.')
param appSettings object = {}

@description('Whether to enable Always On.')
param alwaysOn bool = true

@description('Optional. Health check path for the app.')
param healthCheckPath string = ''

@description('Optional. Whether to enable WebSockets.')
param webSocketsEnabled bool = false

@description('Optional. Command line for the application.')
param appCommandLine string = ''

@description('Required. Type of site to deploy.')
@allowed([
  'functionapp' // function app windows os
  'functionapp,linux' // function app linux os
  'functionapp,workflowapp' // logic app workflow
  'functionapp,workflowapp,linux' // logic app docker container
  'functionapp,linux,container' // function app linux container
  'functionapp,linux,container,azurecontainerapps' // function app linux container azure container apps
  'app,linux' // linux web app
  'app' // windows web app
  'linux,api' // linux api app
  'api' // windows api app
  'app,linux,container' // linux container app
  'app,container,windows' // windows container app
])
param kind string = 'app,linux'

@description('Public network access setting.')
param publicNetworkAccess string = 'Enabled'

@description('Optional. Managed identity configuration for the resource.')
param identity object = { type: 'SystemAssigned' }

// ============================================================================
// Resource Deployment
// ============================================================================
resource appService 'Microsoft.Web/sites@2025-05-01' = {
  name: name
  location: location
  tags: tags
  kind: kind
  identity: identity
  properties: {
    serverFarmId: serverFarmResourceId
    publicNetworkAccess: publicNetworkAccess
    siteConfig: {
      alwaysOn: alwaysOn
      ftpsState: 'Disabled'
      linuxFxVersion: linuxFxVersion
      minTlsVersion: '1.2'
      healthCheckPath: !empty(healthCheckPath) ? healthCheckPath : null
      webSocketsEnabled: webSocketsEnabled
      appCommandLine: appCommandLine
    }
    endToEndEncryptionEnabled: true
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

resource configAppSettings 'Microsoft.Web/sites/config@2025-05-01' = {
  name: 'appsettings'
  parent: appService
  properties: appSettings
}

resource configLogs 'Microsoft.Web/sites/config@2025-05-01' = {
  name: 'logs'
  parent: appService
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
@description('Resource ID of the App Service.')
output resourceId string = appService.id

@description('Name of the App Service.')
output name string = appService.name

@description('Default hostname of the App Service.')
output defaultHostname string = appService.properties.defaultHostName

@description('URL of the App Service.')
output appUrl string = 'https://${appService.properties.defaultHostName}'

@description('System-assigned identity principal ID.')
output identityPrincipalId string = appService.identity.principalId
