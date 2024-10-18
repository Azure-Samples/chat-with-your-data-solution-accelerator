metadata description = 'Creates an Azure Function in an existing Azure App Service plan.'
param name string
param location string = resourceGroup().location
param tags object = {}

// Reference Properties
param applicationInsightsName string = ''
param appServicePlanId string
param keyVaultName string = ''
param managedIdentity bool = !empty(keyVaultName)
param storageAccountName string
param useKeyVault bool

// Runtime Properties
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
param runtimeNameAndVersion string = '${runtimeName}|${runtimeVersion}'
param runtimeVersion string

// Function Settings
@allowed([
  '~4'
  '~3'
  '~2'
  '~1'
])
param extensionVersion string = '~4'

// Microsoft.Web/sites Properties
param kind string = 'functionapp,linux'

// Microsoft.Web/sites/config
param allowedOrigins array = []
param alwaysOn bool = true
param appCommandLine string = ''
@secure()
param appSettings object = {}
param clientAffinityEnabled bool = false
param functionAppScaleLimit int = -1
param minimumElasticInstanceCount int = -1
param numberOfWorkers int = -1
param use32BitWorkerProcess bool = false
param healthCheckPath string = ''
param dockerFullImageName string = ''
param useDocker bool = dockerFullImageName != ''
param enableOryxBuild bool = useDocker ? false : contains(kind, 'linux')

module functions 'appservice.bicep' = {
  name: '${name}-functions'
  params: {
    name: name
    location: location
    tags: tags
    allowedOrigins: allowedOrigins
    alwaysOn: alwaysOn
    appCommandLine: useDocker ? '' : appCommandLine
    applicationInsightsName: applicationInsightsName
    appServicePlanId: appServicePlanId
    appSettings: union(
      appSettings,
      {
        FUNCTIONS_EXTENSION_VERSION: extensionVersion
      },
      !useDocker ? { FUNCTIONS_WORKER_RUNTIME: runtimeName } : {},
      useKeyVault
        ? {
            AzureWebJobsStorage: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
          }
        : { AzureWebJobsStorage__accountName: storage.name }
    )
    clientAffinityEnabled: clientAffinityEnabled
    enableOryxBuild: enableOryxBuild
    functionAppScaleLimit: functionAppScaleLimit
    healthCheckPath: healthCheckPath
    keyVaultName: keyVaultName
    kind: kind
    managedIdentity: managedIdentity
    minimumElasticInstanceCount: minimumElasticInstanceCount
    numberOfWorkers: numberOfWorkers
    runtimeName: runtimeName
    runtimeVersion: runtimeVersion
    runtimeNameAndVersion: runtimeNameAndVersion
    scmDoBuildDuringDeployment: useDocker ? false : true
    use32BitWorkerProcess: use32BitWorkerProcess
    dockerFullImageName: dockerFullImageName
  }
}

module storageBlobRoleFunction '../security/role.bicep' = {
  name: 'storage-blob-role-function'
  params: {
    principalId: functions.outputs.identityPrincipalId
    roleDefinitionId: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    principalType: 'ServicePrincipal'
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2021-09-01' existing = {
  name: storageAccountName
}

output identityPrincipalId string = managedIdentity ? functions.outputs.identityPrincipalId : ''
output name string = functions.outputs.name
output uri string = functions.outputs.uri
