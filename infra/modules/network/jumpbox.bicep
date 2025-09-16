// /****************************************************************************************************************************/
// Create Jumpbox NSG and Jumpbox Subnet, then create Jumpbox VM
// /****************************************************************************************************************************/

@description('Name of the Jumpbox Virtual Machine.')
param name string

@description('Azure region to deploy resources.')
param location string = resourceGroup().location

@description('Name of the Virtual Network where the Jumpbox VM will be deployed.')
param vnetName string

@description('Size of the Jumpbox Virtual Machine.')
param size string

import { subnetType } from 'virtualNetwork.bicep'
@description('Optional. Subnet configuration for the Jumpbox VM.')
param subnet subnetType?

@description('Username to access the Jumpbox VM.')
param username string

@secure()
@description('Password to access the Jumpbox VM.')
param password string

@description('Optional. Tags to apply to the resources.')
param tags object = {}

@description('Log Analytics Workspace Resource ID for VM diagnostics.')
param logAnalyticsWorkspaceId string

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// 1. Create Jumpbox NSG
// using AVM Network Security Group module
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/network/network-security-group
module nsg 'br/public:avm/res/network/network-security-group:0.5.1' = if (!empty(subnet)) {
  name: '${vnetName}-${subnet.?networkSecurityGroup.name}'
  params: {
    name: '${subnet.?networkSecurityGroup.name}-${vnetName}'
    location: location
    securityRules: subnet.?networkSecurityGroup.securityRules
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// 2. Create Jumpbox subnet as part of the existing VNet
// using AVM Virtual Network Subnet module
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/network/virtual-network/subnet
module subnetResource 'br/public:avm/res/network/virtual-network/subnet:0.1.2' = if (!empty(subnet)) {
  name: subnet.?name ?? '${vnetName}-jumpbox-subnet'
  params: {
    virtualNetworkName: vnetName
    name: subnet.?name ?? ''
    addressPrefixes: subnet.?addressPrefixes
    networkSecurityGroupResourceId: nsg.outputs.resourceId
    enableTelemetry: enableTelemetry
  }
}

// 3. Create Jumpbox VM
// using AVM Virtual Machine module
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/compute/virtual-machine
var vmName = take(name, 15) // Shorten VM name to 15 characters to avoid Azure limits

module vm '../compute/virtual-machine/main.bicep' = {
  name: take('${vmName}-jumpbox', 64)
  params: {
    name: vmName
    vmSize: size
    location: location
    adminUsername: username
    adminPassword: password
    tags: tags
    zone: 0
    imageReference: {
      offer: 'WindowsServer'
      publisher: 'MicrosoftWindowsServer'
      sku: '2019-datacenter'
      version: 'latest'
    }
    osType: 'Windows'
    osDisk: {
      name: 'osdisk-${vmName}'
      managedDisk: {
        storageAccountType: 'Standard_LRS'
      }
    }
    encryptionAtHost: false // Some Azure subscriptions do not support encryption at host
    nicConfigurations: [
      {
        name: 'nic-${vmName}'
        ipConfigurations: [
          {
            name: 'ipconfig1'
            subnetResourceId: subnetResource.outputs.resourceId
          }
        ]
        networkSecurityGroupResourceId: nsg.outputs.resourceId
        diagnosticSettings: [
          {
            name: 'jumpboxDiagnostics'
            workspaceResourceId: logAnalyticsWorkspaceId
            logCategoriesAndGroups: [
              {
                categoryGroup: 'allLogs'
                enabled: true
              }
            ]
            metricCategories: [
              {
                category: 'AllMetrics'
                enabled: true
              }
            ]
          }
        ]
      }
    ]
    enableTelemetry: enableTelemetry
  }
}

output resourceId string = vm.outputs.resourceId
output name string = vm.outputs.name
output location string = vm.outputs.location

output subnetId string = subnetResource.outputs.resourceId
output subnetName string = subnetResource.outputs.name
output nsgId string = nsg.outputs.resourceId
output nsgName string = nsg.outputs.name

@export()
@description('Custom type definition for establishing Jumpbox Virtual Machine and its associated resources.')
type jumpBoxConfigurationType = {
  @description('The name of the Virtual Machine.')
  name: string

  @description('The size of the VM.')
  size: string?

  @description('Username to access VM.')
  username: string

  @secure()
  @description('Password to access VM.')
  password: string

  @description('Optional. Subnet configuration for the Jumpbox VM.')
  subnet: subnetType?
}
