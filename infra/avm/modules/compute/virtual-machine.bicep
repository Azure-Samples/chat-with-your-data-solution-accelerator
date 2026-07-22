// ============================================================================
// Module: Virtual Machine (Jumpbox)
// Description: AVM wrapper for Azure Virtual Machine with Entra ID authentication
// AVM Module: avm/res/compute/virtual-machine
// Ref: https://learn.microsoft.com/azure/bastion/bastion-entra-id-authentication
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the virtual machine.')
param name string = 'vm-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('VM size.')
param vmSize string = 'Standard_D2s_v5'

@secure()
@description('Local admin username. Required by Azure at provisioning time but not used for login when Entra ID is enabled.')
param adminUsername string

@secure()
@description('Local admin password. Required by Azure at provisioning time but not used for login when Entra ID is enabled.')
param adminPassword string

@description('Resource ID of the subnet for the VM NIC.')
param subnetResourceId string

@description('OS type for the VM.')
param osType string = 'Windows'

@description('Availability zone for the VM.')
param availabilityZone int = 1

@description('Image reference for the VM.')
param imageReference object = {
  publisher: 'microsoft-dsvm'
  offer: 'dsvm-win-2022'
  sku: 'winserver-2022'
  version: 'latest'
}

@description('OS disk size in GB.')
param osDiskSizeGB int = 128

@description('Resource ID of the maintenance configuration.')
param maintenanceConfigurationResourceId string?

@description('Resource ID of the proximity placement group.')
param proximityPlacementGroupResourceId string?

@description('Monitoring agent extension configuration (data collection rule associations).')
param extensionMonitoringAgentConfig object?

@description('Diagnostic settings for the resource.')
param diagnosticSettings array?

@description('Enable Azure telemetry collection.')
param enableTelemetry bool = true

@description('Deploying user principal ID. Used for default role assignment to grant the deploying user login access to the VM. This is required because with Entra ID authentication enabled, local accounts cannot be used to access the VM, including the local admin account created at provisioning.')
param deployingUserPrincipalId string

@description('Deploying user principal type. Used for default role assignment to grant the deploying user login access to the VM. This is required because with Entra ID authentication enabled, local accounts cannot be used to access the VM, including the local admin account created at provisioning.')
param deployingUserPrincipalType string = 'User'

@description('Role assignments to apply to the virtual machine.')
param roleAssignments array = [
  {
    roleDefinitionIdOrName: '1c0163c0-47e6-4577-8991-ea5c82e286e4' // Virtual Machine Administrator Login
    principalId: deployingUserPrincipalId
    principalType: deployingUserPrincipalType
  }
]

@description('Optional. Managed identities for the resource.')
param managedIdentities object = { systemAssigned: true }

// ============================================================================
// AVM Module Deployment
// ============================================================================
module virtualMachine 'br/public:avm/res/compute/virtual-machine:0.22.0' = {
  name: take('avm.res.compute.virtual-machine.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    computerName: take(name, 15)
    osType: osType
    vmSize: vmSize
    adminUsername: adminUsername
    adminPassword: adminPassword
    managedIdentities: managedIdentities
    patchMode: 'AutomaticByPlatform'
    bypassPlatformSafetyChecksOnUserSchedule: true
    maintenanceConfigurationResourceId: maintenanceConfigurationResourceId
    enableAutomaticUpdates: true
    encryptionAtHost: true
    availabilityZone: availabilityZone
    proximityPlacementGroupResourceId: proximityPlacementGroupResourceId
    imageReference: imageReference
    osDisk: {
      name: 'osdisk-${name}'
      caching: 'ReadWrite'
      createOption: 'FromImage'
      deleteOption: 'Delete'
      diskSizeGB: osDiskSizeGB
      managedDisk: { storageAccountType: 'Premium_LRS' }
    }
    nicConfigurations: [
      {
        name: 'nic-${name}'
        tags: tags
        deleteOption: 'Delete'
        diagnosticSettings: diagnosticSettings
        ipConfigurations: [
          {
            name: '${name}-nic01-ipconfig01'
            subnetResourceId: subnetResourceId
            diagnosticSettings: diagnosticSettings
          }
        ]
      }
    ]
    roleAssignments: roleAssignments
    extensionAadJoinConfig: {
      enabled: true
      tags: tags
      typeHandlerVersion: '2.0'
      settings: { mdmId: '' }
    }
    extensionAntiMalwareConfig: {
      enabled: true
      settings: {
        AntimalwareEnabled: 'true'
        Exclusions: {}
        RealtimeProtectionEnabled: 'true'
        ScheduledScanSettings: { day: '7', isEnabled: 'true', scanType: 'Quick', time: '120' }
      }
      tags: tags
    }
    extensionMonitoringAgentConfig: extensionMonitoringAgentConfig
    extensionNetworkWatcherAgentConfig: { enabled: true, tags: tags }
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the virtual machine.')
output resourceId string = virtualMachine.outputs.resourceId

@description('Name of the virtual machine.')
output name string = virtualMachine.outputs.name
