param name string
param location string = ''
param appServicePlanId string 
param storageAccountName string = ''
param tags object = {}

@secure()
param appSettings object = {}
param serviceName string = 'function'
param runtimeName string
param runtimeVersion string

@secure()
param clientKey string
param azureOpenAIName string = ''
param azureCognitiveSearchName string = ''


module function '../core/host/functions.bicep' = {
  name: '${name}-app-module'
  params: {
    name: name
    location: location
    tags: union(tags, { 'azd-service-name': serviceName })
    appServicePlanId: appServicePlanId
    storageAccountName: storageAccountName
    runtimeName: runtimeName
    runtimeVersion: runtimeVersion
    appSettings: union(appSettings, {
      AZURE_OPENAI_KEY: openAI.listKeys().key1
      AZURE_SEARCH_KEY: search.listAdminKeys().primaryKey
    })
  }
}

resource openAI 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  name: azureOpenAIName
}

resource search 'Microsoft.Search/searchServices@2021-04-01-preview' existing = {
  name: azureCognitiveSearchName
}

resource functionNameDefaultClientKey 'Microsoft.Web/sites/host/functionKeys@2018-11-01' = {
  name: '${name}/default/clientKey'
  properties: {
    name: 'ClientKey'
    value: clientKey
  }
  dependsOn: [
    function
    waitFunctionDeploymentSection
  ]
}

resource waitFunctionDeploymentSection 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  kind: 'AzurePowerShell'
  name: 'WaitFunctionDeploymentSection'
  location: location
  properties: {
    azPowerShellVersion: '3.0'
    scriptContent: 'start-sleep -Seconds 300'
    cleanupPreference: 'Always'
    retentionInterval: 'PT1H'
  }
  dependsOn: [
    function
  ]
}
