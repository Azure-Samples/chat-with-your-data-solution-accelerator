@description('Required. Name of the function app.')
param name string

@description('Optional. Location for all resources.')
param location string = resourceGroup().location

@description('Optional. Tags of the resource.')
param tags object = {}

// Reference Properties
@description('Optional. The name of the application insights instance to use with the function app.')
param applicationInsightsName string = ''

@description('Required. The resource ID of the app service plan to use for the function app.')
param serverFarmResourceId string

@description('Optional. The resource ID of the user assigned identity for the function app.')
param userAssignedIdentityResourceId string = ''

@description('Optional. The client ID of the user assigned identity for the function app. This is required to set the AZURE_CLIENT_ID app setting so the function app can authenticate with the user assigned managed identity.')
param userAssignedIdentityClientId string = ''

@description('Optional. The name of the storage account to use for the function app.')
param storageAccountName string

// Runtime Properties
@description('Optional. Runtime name to use for the function app.')
@allowed([
  'dotnet'
  'dotnetcore'
  'dotnet-isolated'
  'node'
  'python'
  'java'
  'powershell'
  'custom'
])
param runtimeName string

@description('Optional. Runtime version to use for the function app.')
param runtimeVersion string

// Function Settings
@description('Optional. Function app extension version.')
@allowed([
  '~4'
  '~3'
  '~2'
  '~1'
])
param extensionVersion string = '~4'

// Microsoft.Web/sites Properties
@description('Optional. Type of site to deploy.')
@allowed([
  'functionapp' // function app windows os
  'functionapp,linux' // function app linux os
  'functionapp,workflowapp' // logic app workflow
  'functionapp,workflowapp,linux' // logic app docker container
  'functionapp,linux,container' // function app linux container
  'functionapp,linux,container,azurecontainerapps' // function app linux container azure container apps
])
param kind string = 'functionapp,linux'

// Microsoft.Web/sites/config
@description('Optional. Allowed origins for the function app.')
param allowedOrigins array = []

@description('Optional. Whether the function app should always be running.')
param alwaysOn bool = true

@description('Optional. Command line to use when starting the function app.')
param appCommandLine string = ''

@description('Optional. Settings for the function app.')
@secure()
param appSettings object = {}

@description('Optional. Whether client affinity is enabled for the function app.')
param clientAffinityEnabled bool = false

@description('Optional. Function app scale limit.')
param functionAppScaleLimit int = -1

@description('Optional. Minimum number of elastic instances for the function app.')
param minimumElasticInstanceCount int = -1

@description('Optional. Number of workers for the function app.')
param numberOfWorkers int = -1

@description('Optional. Whether to use 32-bit worker process for the function app.')
param use32BitWorkerProcess bool = false

@description('Optional. Health check path for the function app.')
param healthCheckPath string = ''

@description('Optional. Docker image name to use for container function apps.')
param dockerFullImageName string = ''

@description('Optional. Whether to use Docker for the function app.')
param useDocker bool = dockerFullImageName != ''

@description('Optional. Whether to enable Oryx build for the function app. This is disabled when using Docker.')
param enableOryxBuild bool = useDocker ? false : contains(kind, 'linux')

@description('Optional. Determines if build should be done during deployment. This is disabled when using Docker.')
param scmDoBuildDuringDeployment bool = useDocker ? false : true

@description('Optional. Determines if HTTPS is required for the function app. When true, HTTP requests are redirected to HTTPS.')
param httpsOnly bool = true

@description('Optional. Determines if the function app can integrate with a virtual network.')
param virtualNetworkSubnetId string = ''

@description('Optional. To enable accessing content over virtual network.')
param vnetContentShareEnabled bool = false

@description('Optional. To enable pulling image over Virtual Network.')
param vnetImagePullEnabled bool = false

@description('Optional. Virtual Network Route All enabled. This causes all outbound traffic to have Virtual Network Security Groups and User Defined Routes applied.')
param vnetRouteAllEnabled bool = false

@description('Optional. Configuration details for private endpoints. For security reasons, it is recommended to use private endpoints whenever possible.')
param privateEndpoints array = []

@description('Optional. The diagnostic settings of the service.')
param diagnosticSettings array = []

@description('Optional. Whether or not public network access is allowed for this resource. For security reasons it should be disabled when using private endpoints.')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

var appConfigs = [
  {
    name: 'appsettings'
    properties: union(
      appSettings,
      {
        FUNCTIONS_EXTENSION_VERSION: extensionVersion
        SCM_DO_BUILD_DURING_DEPLOYMENT: string(scmDoBuildDuringDeployment)
        ENABLE_ORYX_BUILD: string(enableOryxBuild)
        AZURE_RESOURCE_GROUP: resourceGroup().name
        AZURE_SUBSCRIPTION_ID: subscription().subscriptionId
        // Set the storage account settings to use user managed identity authentication
        AzureWebJobsStorage__accountName: storageAccountName
        AzureWebJobsStorage__credential: 'managedidentity'
        AzureWebJobsStorage__clientId: userAssignedIdentityClientId
      },
      !useDocker ? { FUNCTIONS_WORKER_RUNTIME: runtimeName } : {},
      runtimeName == 'python' && !useDocker ? { PYTHON_ENABLE_GUNICORN_MULTIWORKERS: 'true' } : {}
    )
    applicationInsightResourceId: empty(applicationInsightsName)
      ? null
      : resourceId('Microsoft.Insights/components', applicationInsightsName)
    storageAccountResourceId: resourceId('Microsoft.Storage/storageAccounts', storageAccountName)
    storageAccountUseIdentityAuthentication: true
    retainCurrentAppSettings: true
  }
]

module functions 'appservice.bicep' = {
  name: '${name}-functions'
  params: {
    name: name
    location: location
    tags: tags
    siteConfig: {
      alwaysOn: alwaysOn
      appCommandLine: useDocker ? '' : appCommandLine
      linuxFxVersion: empty(dockerFullImageName)
        ? '${toUpper(runtimeName)}|${runtimeVersion}'
        : 'DOCKER|${dockerFullImageName}'
      functionAppScaleLimit: functionAppScaleLimit != -1 ? functionAppScaleLimit : null
      minimumElasticInstanceCount: minimumElasticInstanceCount != -1 ? minimumElasticInstanceCount : null
      numberOfWorkers: numberOfWorkers != -1 ? numberOfWorkers : null
      use32BitWorkerProcess: use32BitWorkerProcess
      cors: {
        allowedOrigins: allowedOrigins
      }
      healthCheckPath: healthCheckPath
      minTlsVersion: '1.2'
      ftpsState: 'FtpsOnly'
    }
    serverFarmResourceId: serverFarmResourceId
    configs: appConfigs
    clientAffinityEnabled: clientAffinityEnabled
    kind: kind
    managedIdentities: {
      systemAssigned: false
      userAssignedResourceIds: !empty(userAssignedIdentityResourceId)
        ? [
            userAssignedIdentityResourceId
          ]
        : []
    }
    httpsOnly: httpsOnly
    virtualNetworkSubnetId: virtualNetworkSubnetId
    vnetContentShareEnabled: vnetContentShareEnabled
    vnetImagePullEnabled: vnetImagePullEnabled
    vnetRouteAllEnabled: vnetRouteAllEnabled
    privateEndpoints: privateEndpoints
    diagnosticSettings: diagnosticSettings
    publicNetworkAccess: publicNetworkAccess
  }
}

output name string = functions.outputs.name
output uri string = functions.outputs.defaultHostname
output azureWebJobsStorage string = storageAccountName
