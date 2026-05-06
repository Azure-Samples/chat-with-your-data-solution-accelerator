metadata name = 'Virtual Machine Extensions'
metadata description = 'This module deploys a Virtual Machine Extension.'

@description('Conditional. The name of the parent virtual machine that extension is provisioned for. Required if the template is used in a standalone deployment.')
param virtualMachineName string

@description('Required. The name of the virtual machine extension.')
param name string

@description('Optional. The location the extension is deployed to.')
param location string = resourceGroup().location

@description('Required. The name of the extension handler publisher.')
param publisher string

@description('Required. Specifies the type of the extension; an example is "CustomScriptExtension".')
param type string

@description('Required. Specifies the version of the script handler.')
param typeHandlerVersion string

@description('Required. Indicates whether the extension should use a newer minor version if one is available at deployment time. Once deployed, however, the extension will not upgrade minor versions unless redeployed, even with this property set to true.')
param autoUpgradeMinorVersion bool

@description('Optional. How the extension handler should be forced to update even if the extension configuration has not changed.')
param forceUpdateTag string = ''

@description('Optional. Any object that contains the extension specific settings.')
param settings object = {}

@description('Optional. Any object that contains the extension specific protected settings.')
@secure()
param protectedSettings object = {}

@description('Optional. Indicates whether failures stemming from the extension will be suppressed (Operational failures such as not connecting to the VM will not be suppressed regardless of this value). The default is false.')
param supressFailures bool = false

@description('Required. Indicates whether the extension should be automatically upgraded by the platform if there is a newer version of the extension available.')
param enableAutomaticUpgrade bool

@description('Optional. Tags of the resource.')
param tags object?

resource virtualMachine 'Microsoft.Compute/virtualMachines@2022-11-01' existing = {
  name: virtualMachineName
}

resource extension 'Microsoft.Compute/virtualMachines/extensions@2022-11-01' = {
  name: name
  parent: virtualMachine
  location: location
  tags: tags
  properties: {
    publisher: publisher
    type: type
    typeHandlerVersion: typeHandlerVersion
    autoUpgradeMinorVersion: autoUpgradeMinorVersion
    enableAutomaticUpgrade: enableAutomaticUpgrade
    forceUpdateTag: !empty(forceUpdateTag) ? forceUpdateTag : null
    settings: !empty(settings) ? settings : null
    protectedSettings: !empty(protectedSettings) ? protectedSettings : null
    suppressFailures: supressFailures
  }
}

@description('The name of the extension.')
output name string = extension.name

@description('The resource ID of the extension.')
output resourceId string = extension.id

@description('The name of the Resource Group the extension was created in.')
output resourceGroupName string = resourceGroup().name

@description('The location the resource was deployed into.')
output location string = extension.location
