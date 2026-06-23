// ========== deploy_app_service_custom.bicep ========== //
// Code-deploy variant of deploy_app_service.bicep.
// Deploys an App Service using a language runtime (Oryx build) instead of a pre-built Docker image.
targetScope = 'resourceGroup'

@description('Solution Name (also used as the App Service name).')
param solutionName string

@description('Solution Location')
param solutionLocation string

@description('Application settings for the App Service.')
@secure()
param appSettings object = {}

@description('The resource ID of the App Service Plan.')
param appServicePlanId string

@description('The Linux framework version (e.g., PYTHON|3.11 or NODE|18-lts).')
param linuxFxVersion string

@description('Startup command for the App Service.')
param appCommandLine string = ''

@description('The resource ID of the user-assigned managed identity. Leave empty to use system-assigned only.')
param userassignedIdentityId string = ''

@description('When true, assigns a system-managed identity to the App Service.')
param enableSystemAssignedIdentity bool = true

@description('AZD service name tag value for azd deploy integration (e.g., api or webapp).')
param azdServiceName string = ''

@description('Optional. Resource ID of the Log Analytics Workspace for diagnostic settings.')
param logAnalyticsWorkspaceId string = ''

var identityConfig = !enableSystemAssignedIdentity ? {
  type: 'None'
} : userassignedIdentityId == '' ? {
  type: 'SystemAssigned'
} : {
  type: 'SystemAssigned, UserAssigned'
  userAssignedIdentities: {
    '${userassignedIdentityId}': {}
  }
}

resource appService 'Microsoft.Web/sites@2022-03-01' = {
  name: solutionName
  location: solutionLocation
  kind: 'app,linux'
  tags: !empty(azdServiceName) ? { 'azd-service-name': azdServiceName } : {}
  identity: identityConfig
  properties: {
    serverFarmId: appServicePlanId
    siteConfig: {
      alwaysOn: true
      ftpsState: 'Disabled'
      linuxFxVersion: linuxFxVersion
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

resource configAppSettings 'Microsoft.Web/sites/config@2022-03-01' = {
  name: 'appsettings'
  parent: appService
  properties: appSettings
}

resource configLogs 'Microsoft.Web/sites/config@2022-03-01' = {
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

resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: '${solutionName}-diagnostics'
  scope: appService
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      { category: 'AppServiceHTTPLogs', enabled: true }
      { category: 'AppServiceConsoleLogs', enabled: true }
      { category: 'AppServiceAppLogs', enabled: true }
    ]
    metrics: [
      { category: 'AllMetrics', enabled: true }
    ]
  }
}

@description('The principal ID of the App Service system-assigned managed identity (empty if identity disabled).')
output identityPrincipalId string = enableSystemAssignedIdentity ? appService.identity.principalId : ''

@description('The URL of the deployed App Service.')
output appUrl string = 'https://${solutionName}.azurewebsites.net'
