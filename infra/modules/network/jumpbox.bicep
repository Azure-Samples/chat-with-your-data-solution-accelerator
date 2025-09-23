// /****************************************************************************************************************************/
// Create Jumpbox NSG and Jumpbox Subnet, then create Jumpbox VM
// /****************************************************************************************************************************/

@description('Required. The name of the Jumpbox Virtual Machine.')
param name string

@description('Required. The Azure region to deploy resources.')
param location string = resourceGroup().location

@description('Required. The name of the Virtual Network where the Jumpbox VM will be deployed.')
param vnetName string

@description('Required. The size of the Jumpbox Virtual Machine.')
param size string

import { subnetType } from 'virtualNetwork.bicep'
@description('Optional. The Subnet configuration for the Jumpbox VM.')
param subnet subnetType?

@description('Required. The username to access the Jumpbox VM.')
param username string

@secure()
@description('Required. The password to access the Jumpbox VM.')
param password string

@description('Optional. Tags to apply to the resources.')
param tags object = {}

@description('Optional. Log Analytics Workspace Resource ID for VM diagnostics.')
param logAnalyticsWorkspaceId string

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// 1. Create Jumpbox NSG
// using AVM Network Security Group module
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/network/network-security-group
module nsg '../network-security-group/network-security-group.bicep' = if (!empty(subnet)) {
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
    networkSecurityGroupResourceId: nsg!.outputs.resourceId
    enableTelemetry: enableTelemetry
  }
}

// 3. Create Jumpbox VM
// using AVM Virtual Machine module
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/compute/virtual-machine
var vmName = take(name, 15) // Shorten VM name to 15 characters to avoid Azure limits

module vm '../compute/virtual-machine/virtual-machine.bicep' = {
  name: take('${vmName}-jumpbox', 64)
  params: {
    name: vmName
    vmSize: size
    location: location
    adminUsername: username
    adminPassword: password
    tags: tags
    zone: 0
    maintenanceConfigurationResourceId: maintenanceConfiguration.outputs.resourceId
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
        storageAccountType: 'Premium_LRS'
      }
    }
    patchMode: 'AutomaticByPlatform'
    bypassPlatformSafetyChecksOnUserSchedule: true
    enableAutomaticUpdates: true
    encryptionAtHost: false // Some Azure subscriptions do not support encryption at host
    nicConfigurations: [
      {
        name: 'nic-${vmName}'
        ipConfigurations: [
          {
            name: 'ipconfig1'
            subnetResourceId: subnetResource!.outputs.resourceId
          }
        ]
        networkSecurityGroupResourceId: nsg!.outputs.resourceId
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

// 4. Create Maintenance Configuration for VM
// Required for PSRule.Rules.Azure compliance: Azure.VM.MaintenanceConfig
// using AVM Virtual Machine module
// https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/compute/virtual-machine

module maintenanceConfiguration 'br/public:avm/res/maintenance/maintenance-configuration:0.3.1' = {
  name: take('${vmName}-jumpbox-maintenance-config', 64)
  params: {
    name: 'mc-${vmName}'
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    extensionProperties: {
      InGuestPatchMode: 'User'
    }
    maintenanceScope: 'InGuestPatch'
    maintenanceWindow: {
      startDateTime: '2024-06-16 00:00'
      duration: '03:55'
      timeZone: 'W. Europe Standard Time'
      recurEvery: '1Day'
    }
    visibility: 'Custom'
    installPatches: {
      rebootSetting: 'IfRequired'
      windowsParameters: {
        classificationsToInclude: [
          'Critical'
          'Security'
        ]
      }
      linuxParameters: {
        classificationsToInclude: [
          'Critical'
          'Security'
        ]
      }
    }
  }
}

@description('Resource ID of the Jumpbox virtual machine.')
output resourceId string = vm.outputs.resourceId

@description('Name of the Jumpbox virtual machine.')
output name string = vm.outputs.name

@description('Azure region where the Jumpbox virtual machine is deployed.')
output location string = vm.outputs.location

@description('Resource ID of the subnet used by the Jumpbox VM, if created.')
output subnetId string = subnetResource!.outputs.resourceId

@description('Name of the subnet used by the Jumpbox VM, if created.')
output subnetName string = subnetResource!.outputs.name

@description('Resource ID of the Network Security Group associated with the Jumpbox subnet, if created.')
output nsgId string = nsg!.outputs.resourceId

@description('Name of the Network Security Group associated with the Jumpbox subnet, if created.')
output nsgName string = nsg!.outputs.name

@export()
@description('Custom type definition for establishing Jumpbox Virtual Machine and its associated resources.')
type jumpBoxConfigurationType = {
  @description('Required. The name of the Virtual Machine.')
  name: string

  @description('Optional. The size of the VM.')
  size: string?

  @description('Required. The Username to access VM.')
  username: string

  @secure()
  @description('Required. The Password to access VM.')
  password: string

  @description('Optional. Subnet configuration for the Jumpbox VM.')
  subnet: subnetType?
}
