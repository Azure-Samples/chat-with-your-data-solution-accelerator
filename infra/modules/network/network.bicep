metadata name = 'Chat-with-your-data-solution-accelerator - Network Module'
metadata description = '''This module contains the network resources required to deploy the [Chat-with-your-data-solution-accelerator](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator) for both Sandbox environments and WAF aligned environments.
> **Note:** This module is not intended for broad, generic use, as it was designed by the Commercial Solution Areas CTO team, as a Microsoft Solution Accelerator. Feature requests and bug fix requests are welcome if they support the needs of this organization but may not be incorporated if they aim to make this module more generic than what it needs to be for its primary use case. This module will likely be updated to leverage AVM resource modules in the future. This may result in breaking changes in upcoming versions when these features are implemented.
'''

@minLength(6)
@maxLength(25)
@description('Required. Name used for naming all network resources.')
param resourcesName string

@minLength(3)
@description('Optional. Azure region for all services.')
param location string = resourceGroup().location

@description('Required. Resource ID of the Log Analytics Workspace for monitoring and diagnostics.')
param logAnalyticsWorkSpaceResourceId string

@description('Required. Networking address prefix for the VNET.')
param addressPrefixes array

import { subnetType } from 'virtualNetwork.bicep'
@description('Required. Array of subnets to be created within the VNET.')
param subnets subnetType[]

import { jumpBoxConfigurationType } from 'jumpbox.bicep'
@description('Optional. Configuration for the Jumpbox VM. Leave null to omit Jumpbox creation.')
param jumpboxConfiguration jumpBoxConfigurationType?

import { bastionHostConfigurationType } from 'bastionHost.bicep'
@description('Optional. Configuration for the Azure Bastion Host. Leave null to omit Bastion creation.')
param bastionConfiguration bastionHostConfigurationType?

@description('Optional. Tags to be applied to the resources.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// /****************************************************************************************************************************/
// Networking - NSGs, VNET and Subnets. Each subnet has its own NSG
// /****************************************************************************************************************************/

module virtualNetwork 'virtualNetwork.bicep' = {
  name: '${resourcesName}-virtualNetwork'
  params: {
    name: 'vnet-${resourcesName}'
    addressPrefixes: addressPrefixes
    subnets: subnets
    location: location
    tags: tags
    logAnalyticsWorkspaceId: logAnalyticsWorkSpaceResourceId
    enableTelemetry: enableTelemetry
  }
}

// /****************************************************************************************************************************/
// // Create Azure Bastion Subnet and Azure Bastion Host
// /****************************************************************************************************************************/

module bastionHost 'bastionHost.bicep' = if (!empty(bastionConfiguration)) {
  name: '${resourcesName}-bastionHost'
  params: {
    name: bastionConfiguration.?name ?? 'bas-${resourcesName}'
    vnetId: virtualNetwork.outputs.resourceId
    vnetName: virtualNetwork.outputs.name
    location: location
    logAnalyticsWorkspaceId: logAnalyticsWorkSpaceResourceId
    subnet: bastionConfiguration.?subnet
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// // /****************************************************************************************************************************/
// // // create Jumpbox NSG and Jumpbox Subnet, then create Jumpbox VM
// // /****************************************************************************************************************************/

module jumpbox 'jumpbox.bicep' = if (!empty(jumpboxConfiguration)) {
  name: '${resourcesName}-jumpbox'
  params: {
    name: jumpboxConfiguration.?name ?? 'vm-jumpbox-${resourcesName}'
    vnetName: virtualNetwork.outputs.name
    size: jumpboxConfiguration.?size ?? 'Standard_D2s_v3'
    logAnalyticsWorkspaceId: logAnalyticsWorkSpaceResourceId
    location: location
    subnet: jumpboxConfiguration.?subnet
    username: jumpboxConfiguration.?username ?? '' // required
    password: jumpboxConfiguration.?password ?? '' // required
    enableTelemetry: enableTelemetry
    tags: tags
  }
}

@description('Name of the virtual network created by the virtualNetwork module.')
output vnetName string = virtualNetwork.outputs.name

@description('Resource id of the virtual network created by the virtualNetwork module.')
output vnetResourceId string = virtualNetwork.outputs.resourceId

import { subnetOutputType } from 'virtualNetwork.bicep'
@description('Array of subnet outputs from the virtualNetwork module. Each element includes subnet id, name, address prefix(es), and associated NSG/route table information.')
output subnets subnetOutputType[] = virtualNetwork.outputs.subnets // This one holds critical info for subnets, including NSGs

@description('Resource id of the subnet used by the Azure Bastion Host, if Bastion is deployed.')
output bastionSubnetId string = bastionHost!.outputs.subnetId

@description('Name of the subnet used by the Azure Bastion Host, if Bastion is deployed.')
output bastionSubnetName string = bastionHost!.outputs.subnetName

@description('Resource id of the Azure Bastion Host deployment, if Bastion is deployed.')
output bastionHostId string = bastionHost!.outputs.resourceId

@description('Name of the Azure Bastion Host deployment, if Bastion is deployed.')
output bastionHostName string = bastionHost!.outputs.name

@description('Name of the subnet used by the Jumpbox VM, if Jumpbox is deployed.')
output jumpboxSubnetName string = jumpbox!.outputs.subnetName

@description('Resource id of the subnet used by the Jumpbox VM, if Jumpbox is deployed.')
output jumpboxSubnetId string = jumpbox!.outputs.subnetId

@description('Name of the Jumpbox virtual machine, if Jumpbox is deployed.')
output jumpboxName string = jumpbox!.outputs.name

@description('Resource id of the Jumpbox virtual machine, if Jumpbox is deployed.')
output jumpboxResourceId string = jumpbox!.outputs.resourceId
