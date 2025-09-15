@minLength(6)
@maxLength(25)
@description('Name used for naming all network resources.')
param resourcesName string

@minLength(3)
@description('Azure region for all services.')
param location string

@description('Resource ID of the Log Analytics Workspace for monitoring and diagnostics.')
param logAnalyticsWorkSpaceResourceId string

@description('Networking address prefix for the VNET.')
param addressPrefixes array

import { subnetType } from 'virtualNetwork.bicep'
@description('Array of subnets to be created within the VNET.')
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

// /****************************************************************************************************************************/
// // create Jumpbox NSG and Jumpbox Subnet, then create Jumpbox VM
// /****************************************************************************************************************************/

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

output vnetName string = virtualNetwork.outputs.name
output vnetResourceId string = virtualNetwork.outputs.resourceId

import { subnetOutputType } from 'virtualNetwork.bicep'
output subnets subnetOutputType[] = virtualNetwork.outputs.subnets // This one holds critical info for subnets, including NSGs

output bastionSubnetId string = bastionHost.outputs.subnetId
output bastionSubnetName string = bastionHost.outputs.subnetName
output bastionHostId string = bastionHost.outputs.resourceId
output bastionHostName string = bastionHost.outputs.name

output jumpboxSubnetName string = jumpbox.outputs.subnetName
output jumpboxSubnetId string = jumpbox.outputs.subnetId
output jumpboxName string = jumpbox.outputs.name
output jumpboxResourceId string = jumpbox.outputs.resourceId
