metadata name = 'Virtual Machines'
metadata description = 'This module deploys a Virtual Machine with one or multiple NICs and optionally one or multiple public IPs.'

@description('Required. The name of the virtual machine to be created. You should use a unique prefix to reduce name collisions in Active Directory.')
param name string

@description('Optional. Can be used if the computer name needs to be different from the Azure VM resource name. If not used, the resource name will be used as computer name.')
param computerName string = name

@description('Required. Specifies the size for the VMs.')
param vmSize string

@description('Optional. This property can be used by user in the request to enable or disable the Host Encryption for the virtual machine. This will enable the encryption for all the disks including Resource/Temp disk at host itself. For security reasons, it is recommended to set encryptionAtHost to True. Restrictions: Cannot be enabled if Azure Disk Encryption (guest-VM encryption using bitlocker/DM-Crypt) is enabled on your VMs.')
param encryptionAtHost bool = true

@description('Optional. Specifies the SecurityType of the virtual machine. It has to be set to any specified value to enable UefiSettings. The default behavior is: UefiSettings will not be enabled unless this property is set.')
@allowed([
  ''
  'ConfidentialVM'
  'TrustedLaunch'
])
param securityType string = ''

@description('Optional. Specifies whether secure boot should be enabled on the virtual machine. This parameter is part of the UefiSettings. SecurityType should be set to TrustedLaunch to enable UefiSettings.')
param secureBootEnabled bool = false

@description('Optional. Specifies whether vTPM should be enabled on the virtual machine. This parameter is part of the UefiSettings.  SecurityType should be set to TrustedLaunch to enable UefiSettings.')
param vTpmEnabled bool = false

@description('Required. OS image reference. In case of marketplace images, it\'s the combination of the publisher, offer, sku, version attributes. In case of custom images it\'s the resource ID of the custom image.')
param imageReference imageReferenceType

@description('Optional. Specifies information about the marketplace image used to create the virtual machine. This element is only used for marketplace images. Before you can use a marketplace image from an API, you must enable the image for programmatic use.')
param plan planType?

@description('Required. Specifies the OS disk. For security reasons, it is recommended to specify DiskEncryptionSet into the osDisk object.  Restrictions: DiskEncryptionSet cannot be enabled if Azure Disk Encryption (guest-VM encryption using bitlocker/DM-Crypt) is enabled on your VMs.')
param osDisk osDiskType

@description('Optional. Specifies the data disks. For security reasons, it is recommended to specify DiskEncryptionSet into the dataDisk object. Restrictions: DiskEncryptionSet cannot be enabled if Azure Disk Encryption (guest-VM encryption using bitlocker/DM-Crypt) is enabled on your VMs.')
param dataDisks dataDiskType[]?

@description('Optional. The flag that enables or disables a capability to have one or more managed data disks with UltraSSD_LRS storage account type on the VM or VMSS. Managed disks with storage account type UltraSSD_LRS can be added to a virtual machine or virtual machine scale set only if this property is enabled.')
param ultraSSDEnabled bool = false

@description('Optional. The flag that enables or disables hibernation capability on the VM.')
param hibernationEnabled bool = false

@description('Required. Administrator username.')
@secure()
param adminUsername string

@description('Optional. When specifying a Windows Virtual Machine, this value should be passed.')
@secure()
param adminPassword string = ''

@description('Optional. UserData for the VM, which must be base-64 encoded. Customer should not pass any secrets in here.')
param userData string = ''

@description('Optional. Custom data associated to the VM, this value will be automatically converted into base64 to account for the expected VM format.')
param customData string = ''

@description('Optional. Specifies set of certificates that should be installed onto the virtual machine.')
param certificatesToBeInstalled vaultSecretGroupType[]?

@description('Optional. Specifies the priority for the virtual machine.')
@allowed([
  'Regular'
  'Low'
  'Spot'
])
param priority string?

@description('Optional. Specifies the eviction policy for the low priority virtual machine.')
@allowed([
  'Deallocate'
  'Delete'
])
param evictionPolicy string = 'Deallocate'

@description('Optional. Specifies the maximum price you are willing to pay for a low priority VM/VMSS. This price is in US Dollars.')
param maxPriceForLowPriorityVm string = ''

@description('Optional. Specifies resource ID about the dedicated host that the virtual machine resides in.')
param dedicatedHostId string = ''

@description('Optional. Specifies that the image or disk that is being used was licensed on-premises.')
@allowed([
  'RHEL_BYOS'
  'SLES_BYOS'
  'Windows_Client'
  'Windows_Server'
  ''
])
param licenseType string = ''

@description('Optional. The list of SSH public keys used to authenticate with linux based VMs.')
param publicKeys publicKeyType[] = []

import { managedIdentityAllType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. The managed identity definition for this resource. The system-assigned managed identity will automatically be enabled if extensionAadJoinConfig.enabled = "True".')
param managedIdentities managedIdentityAllType?

@description('Optional. Whether boot diagnostics should be enabled on the Virtual Machine. Boot diagnostics will be enabled with a managed storage account if no bootDiagnosticsStorageAccountName value is provided. If bootDiagnostics and bootDiagnosticsStorageAccountName values are not provided, boot diagnostics will be disabled.')
param bootDiagnostics bool = false

@description('Optional. Custom storage account used to store boot diagnostic information. Boot diagnostics will be enabled with a custom storage account if a value is provided.')
param bootDiagnosticStorageAccountName string = ''

@description('Optional. Storage account boot diagnostic base URI.')
param bootDiagnosticStorageAccountUri string = '.blob.${environment().suffixes.storage}/'

@description('Optional. Resource ID of a proximity placement group.')
param proximityPlacementGroupResourceId string = ''

@description('Optional. Resource ID of a virtual machine scale set, where the VM should be added.')
param virtualMachineScaleSetResourceId string = ''

@description('Optional. Resource ID of an availability set. Cannot be used in combination with availability zone nor scale set.')
param availabilitySetResourceId string = ''

@description('Optional. Specifies the gallery applications that should be made available to the VM/VMSS.')
param galleryApplications vmGalleryApplicationType[]?

@description('Required. If set to 1, 2 or 3, the availability zone for all VMs is hardcoded to that value. If zero, then availability zones is not used. Cannot be used in combination with availability set nor scale set.')
@allowed([
  0
  1
  2
  3
])
param zone int

// External resources
@description('Required. Configures NICs and PIPs.')
param nicConfigurations nicConfigurationType[]

@description('Optional. The resource Id of a maintenance configuration for this VM.')
param maintenanceConfigurationResourceId string = ''

// Child resources
@description('Optional. Specifies whether extension operations should be allowed on the virtual machine. This may only be set to False when no extensions are present on the virtual machine.')
param allowExtensionOperations bool = true

@description('Optional. The configuration for the [AAD Join] extension. Must at least contain the ["enabled": true] property to be executed. To enroll in Intune, add the setting mdmId: "0000000a-0000-0000-c000-000000000000".')
param extensionAadJoinConfig object = {
  enabled: false
}

@description('Optional. The configuration for the [Anti Malware] extension. Must at least contain the ["enabled": true] property to be executed.')
param extensionAntiMalwareConfig object = osType == 'Windows'
  ? {
      enabled: true
    }
  : { enabled: false }

@description('Optional. The configuration for the [Guest Configuration] extension. Must at least contain the ["enabled": true] property to be executed. Needs a managed identy.')
param extensionGuestConfigurationExtension object = {
  enabled: false
}

@description('Optional. The guest configuration for the virtual machine. Needs the Guest Configuration extension to be enabled.')
param guestConfiguration object = {}

@description('Optional. An object that contains the extension specific protected settings.')
@secure()
param extensionGuestConfigurationExtensionProtectedSettings object = {}

// Shared parameters
@description('Optional. Location for all resources.')
param location string = resourceGroup().location

import { lockType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. The lock settings of the service.')
param lock lockType?

import { roleAssignmentType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. Array of role assignments to create.')
param roleAssignments roleAssignmentType[]?

@description('Optional. Tags of the resource.')
param tags object?

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Required. The chosen OS type.')
@allowed([
  'Windows'
  'Linux'
])
param osType string

@description('Optional. Specifies whether password authentication should be disabled.')
#disable-next-line secure-secrets-in-params // Not a secret
param disablePasswordAuthentication bool = false

@description('Optional. Indicates whether virtual machine agent should be provisioned on the virtual machine. When this property is not specified in the request body, default behavior is to set it to true. This will ensure that VM Agent is installed on the VM so that extensions can be added to the VM later.')
param provisionVMAgent bool = true

@description('Optional. Indicates whether Automatic Updates is enabled for the Windows virtual machine. Default value is true. When patchMode is set to Manual, this parameter must be set to false. For virtual machine scale sets, this property can be updated and updates will take effect on OS reprovisioning.')
param enableAutomaticUpdates bool = true

@description('Optional. VM guest patching orchestration mode. \'AutomaticByOS\' & \'Manual\' are for Windows only, \'ImageDefault\' for Linux only. Refer to \'https://learn.microsoft.com/en-us/azure/virtual-machines/automatic-vm-guest-patching\'.')
@allowed([
  'AutomaticByPlatform'
  'AutomaticByOS'
  'Manual'
  'ImageDefault'
  ''
])
param patchMode string = ''

@description('Optional. Enables customer to schedule patching without accidental upgrades.')
param bypassPlatformSafetyChecksOnUserSchedule bool = true

@description('Optional. Specifies the reboot setting for all AutomaticByPlatform patch installation operations.')
@allowed([
  'Always'
  'IfRequired'
  'Never'
  'Unknown'
])
param rebootSetting string = 'IfRequired'

@description('Optional. VM guest patching assessment mode. Set it to \'AutomaticByPlatform\' to enable automatically check for updates every 24 hours.')
@allowed([
  'AutomaticByPlatform'
  'ImageDefault'
])
param patchAssessmentMode string = 'ImageDefault'

@description('Optional. Enables customers to patch their Azure VMs without requiring a reboot. For enableHotpatching, the \'provisionVMAgent\' must be set to true and \'patchMode\' must be set to \'AutomaticByPlatform\'.')
param enableHotpatching bool = false

@description('Optional. Specifies the time zone of the virtual machine. e.g. \'Pacific Standard Time\'. Possible values can be `TimeZoneInfo.id` value from time zones returned by `TimeZoneInfo.GetSystemTimeZones`.')
param timeZone string = ''

@description('Optional. Specifies additional XML formatted information that can be included in the Unattend.xml file, which is used by Windows Setup. Contents are defined by setting name, component name, and the pass in which the content is applied.')
param additionalUnattendContent additionalUnattendContentType[]?

@description('Optional. Specifies the Windows Remote Management listeners. This enables remote Windows PowerShell.')
param winRMListeners winRMListenerType[]?

var enableReferencedModulesTelemetry = false

var publicKeysFormatted = [
  for publicKey in publicKeys: {
    path: publicKey.path
    keyData: publicKey.keyData
  }
]

var linuxConfiguration = {
  disablePasswordAuthentication: disablePasswordAuthentication
  ssh: {
    publicKeys: publicKeysFormatted
  }
  provisionVMAgent: provisionVMAgent
  patchSettings: (provisionVMAgent && (patchMode =~ 'AutomaticByPlatform' || patchMode =~ 'ImageDefault'))
    ? {
        patchMode: patchMode
        assessmentMode: patchAssessmentMode
        automaticByPlatformSettings: (patchMode =~ 'AutomaticByPlatform')
          ? {
              bypassPlatformSafetyChecksOnUserSchedule: bypassPlatformSafetyChecksOnUserSchedule
              rebootSetting: rebootSetting
            }
          : null
      }
    : null
}

var additionalUnattendContentFormatted = [
  for (unattendContent, index) in additionalUnattendContent ?? []: {
    settingName: unattendContent.settingName
    content: unattendContent.content
    componentName: 'Microsoft-Windows-Shell-Setup'
    passName: 'OobeSystem'
  }
]

var windowsConfiguration = {
  provisionVMAgent: provisionVMAgent
  enableAutomaticUpdates: enableAutomaticUpdates
  patchSettings: (provisionVMAgent && (patchMode =~ 'AutomaticByPlatform' || patchMode =~ 'AutomaticByOS' || patchMode =~ 'Manual'))
    ? {
        patchMode: patchMode
        assessmentMode: patchAssessmentMode
        enableHotpatching: (patchMode =~ 'AutomaticByPlatform') ? enableHotpatching : false
        automaticByPlatformSettings: (patchMode =~ 'AutomaticByPlatform')
          ? {
              bypassPlatformSafetyChecksOnUserSchedule: bypassPlatformSafetyChecksOnUserSchedule
              rebootSetting: rebootSetting
            }
          : null
      }
    : null
  timeZone: empty(timeZone) ? null : timeZone
  additionalUnattendContent: empty(additionalUnattendContent) ? null : additionalUnattendContentFormatted
  winRM: !empty(winRMListeners)
    ? {
        listeners: winRMListeners
      }
    : null
}

var formattedUserAssignedIdentities = reduce(
  map((managedIdentities.?userAssignedResourceIds ?? []), (id) => { '${id}': {} }),
  {},
  (cur, next) => union(cur, next)
) // Converts the flat array to an object like { '${id1}': {}, '${id2}': {} }

// If AADJoin Extension is enabled then we automatically enable SystemAssigned (required by AADJoin), otherwise we follow the usual logic.
var identity = !empty(managedIdentities)
  ? {
      type: (extensionAadJoinConfig.enabled ? true : (managedIdentities.?systemAssigned ?? false))
        ? (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'SystemAssigned, UserAssigned' : 'SystemAssigned')
        : (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'UserAssigned' : null)
      userAssignedIdentities: !empty(formattedUserAssignedIdentities) ? formattedUserAssignedIdentities : null
    }
  : null

var builtInRoleNames = {
  Contributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
  'Data Operator for Managed Disks': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '959f8984-c045-4866-89c7-12bf9737be2e'
  )
  'Desktop Virtualization Power On Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '489581de-a3bd-480d-9518-53dea7416b33'
  )
  'Desktop Virtualization Power On Off Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '40c5ff49-9181-41f8-ae61-143b0e78555e'
  )
  'Desktop Virtualization Virtual Machine Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'a959dbd1-f747-45e3-8ba6-dd80f235f97c'
  )
  'DevTest Labs User': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '76283e04-6283-4c54-8f91-bcf1374a3c64'
  )
  'Disk Backup Reader': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '3e5e47e6-65f7-47ef-90b5-e5dd4d455f24'
  )
  'Disk Pool Operator': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '60fc6e62-5479-42d4-8bf4-67625fcc2840'
  )
  'Disk Restore Operator': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'b50d9833-a0cb-478e-945f-707fcc997c13'
  )
  'Disk Snapshot Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '7efff54f-a5b4-42b5-a1c5-5411624893ce'
  )
  Owner: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8e3af657-a8ff-443c-a75c-2fe8c4bcb635')
  Reader: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'acdd72a7-3385-48ef-bd42-f606fba81ae7')
  'Role Based Access Control Administrator': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'f58310d9-a9f6-439a-9e8d-f62e7b41a168'
  )
  'User Access Administrator': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '18d7d88d-d35e-4fb5-a5c3-7773c20a72d9'
  )
  'Virtual Machine Administrator Login': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '1c0163c0-47e6-4577-8991-ea5c82e286e4'
  )
  'Virtual Machine Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '9980e02c-c2be-4d73-94e8-173b1dc7cf3c'
  )
  'Virtual Machine User Login': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'fb879df8-f326-4884-b1cf-06f3ad86be52'
  )
  'VM Scanner Operator': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'd24ecba3-c1f4-40fa-a7bb-4588a071e8fd'
  )
}

var formattedRoleAssignments = [
  for (roleAssignment, index) in (roleAssignments ?? []): union(roleAssignment, {
    roleDefinitionId: builtInRoleNames[?roleAssignment.roleDefinitionIdOrName] ?? (contains(
        roleAssignment.roleDefinitionIdOrName,
        '/providers/Microsoft.Authorization/roleDefinitions/'
      )
      ? roleAssignment.roleDefinitionIdOrName
      : subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAssignment.roleDefinitionIdOrName))
  })
]

#disable-next-line no-deployments-resources
resource avmTelemetry 'Microsoft.Resources/deployments@2024-03-01' = if (enableTelemetry) {
  name: '46d3xbcp.res.compute-virtualmachine.${replace('0.15.0', '.', '-')}.${substring(uniqueString(deployment().name, location), 0, 4)}'
  properties: {
    mode: 'Incremental'
    template: {
      '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#'
      contentVersion: '1.0.0.0'
      resources: []
      outputs: {
        telemetry: {
          type: 'String'
          value: 'For more information, see https://aka.ms/avm/TelemetryInfo'
        }
      }
    }
  }
}

module vm_nic 'nic-configuration/nic-configuration.bicep' = [
  for (nicConfiguration, index) in nicConfigurations: {
    name: '${uniqueString(deployment().name, location)}-VM-Nic-${index}'
    params: {
      networkInterfaceName: nicConfiguration.?name ?? '${name}${nicConfiguration.?nicSuffix}'
      virtualMachineName: name
      location: location
      enableIPForwarding: nicConfiguration.?enableIPForwarding ?? false
      enableAcceleratedNetworking: nicConfiguration.?enableAcceleratedNetworking ?? true
      dnsServers: contains(nicConfiguration, 'dnsServers')
        ? (!empty(nicConfiguration.?dnsServers) ? nicConfiguration.?dnsServers : [])
        : []
      networkSecurityGroupResourceId: nicConfiguration.?networkSecurityGroupResourceId ?? ''
      ipConfigurations: nicConfiguration.ipConfigurations
      lock: nicConfiguration.?lock ?? lock
      tags: nicConfiguration.?tags ?? tags
      diagnosticSettings: nicConfiguration.?diagnosticSettings
      roleAssignments: nicConfiguration.?roleAssignments
      enableTelemetry: enableReferencedModulesTelemetry
    }
  }
]

resource managedDataDisks 'Microsoft.Compute/disks@2024-03-02' = [
  for (dataDisk, index) in dataDisks ?? []: if (empty(dataDisk.managedDisk.?id)) {
    location: location
    name: dataDisk.?name ?? '${name}-disk-data-${padLeft((index + 1), 2, '0')}'
    sku: {
      name: dataDisk.managedDisk.?storageAccountType
    }
    properties: {
      diskSizeGB: dataDisk.diskSizeGB
      creationData: {
        createOption: dataDisk.?createoption ?? 'Empty'
      }
      diskIOPSReadWrite: dataDisk.?diskIOPSReadWrite
      diskMBpsReadWrite: dataDisk.?diskMBpsReadWrite
    }
    zones: zone != 0 && !contains(dataDisk.managedDisk.?storageAccountType, 'ZRS') ? array(string(zone)) : null
    tags: dataDisk.?tags ?? tags
  }
]

resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: name
  location: location
  identity: identity
  tags: tags
  zones: zone != 0 ? array(string(zone)) : null
  plan: plan
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    securityProfile: {
      encryptionAtHost: encryptionAtHost ? encryptionAtHost : null
      securityType: securityType
      uefiSettings: securityType == 'TrustedLaunch'
        ? {
            secureBootEnabled: secureBootEnabled
            vTpmEnabled: vTpmEnabled
          }
        : null
    }
    storageProfile: {
      imageReference: imageReference
      osDisk: {
        name: osDisk.?name ?? '${name}-disk-os-01'
        createOption: osDisk.?createOption ?? 'FromImage'
        deleteOption: osDisk.?deleteOption ?? 'Delete'
        diffDiskSettings: empty(osDisk.?diffDiskSettings ?? {})
          ? null
          : {
              option: 'Local'
              placement: osDisk.diffDiskSettings!.placement
            }
        diskSizeGB: osDisk.?diskSizeGB
        caching: osDisk.?caching ?? 'ReadOnly'
        managedDisk: {
          storageAccountType: osDisk.managedDisk.?storageAccountType
          diskEncryptionSet: {
            id: osDisk.managedDisk.?diskEncryptionSetResourceId
          }
        }
      }
      dataDisks: [
        for (dataDisk, index) in dataDisks ?? []: {
          lun: dataDisk.?lun ?? index
          name: !empty(dataDisk.managedDisk.?id)
            ? last(split(dataDisk.managedDisk.id ?? '', '/'))
            : dataDisk.?name ?? '${name}-disk-data-${padLeft((index + 1), 2, '0')}'
          createOption: (managedDataDisks[index].?id != null || !empty(dataDisk.managedDisk.?id))
            ? 'Attach'
            : dataDisk.?createoption ?? 'Empty'
          deleteOption: !empty(dataDisk.managedDisk.?id) ? 'Detach' : dataDisk.?deleteOption ?? 'Delete'
          caching: !empty(dataDisk.managedDisk.?id) ? 'None' : dataDisk.?caching ?? 'ReadOnly'
          managedDisk: {
            id: dataDisk.managedDisk.?id ?? managedDataDisks[index].?id
            diskEncryptionSet: contains(dataDisk.managedDisk, 'diskEncryptionSet')
              ? {
                  id: dataDisk.managedDisk.diskEncryptionSet.id
                }
              : null
          }
        }
      ]
    }
    additionalCapabilities: {
      ultraSSDEnabled: ultraSSDEnabled
      hibernationEnabled: hibernationEnabled
    }
    osProfile: {
      computerName: computerName
      adminUsername: adminUsername
      adminPassword: adminPassword
      customData: !empty(customData) ? base64(customData) : null
      windowsConfiguration: osType == 'Windows' ? windowsConfiguration : null
      linuxConfiguration: osType == 'Linux' ? linuxConfiguration : null
      secrets: certificatesToBeInstalled
      allowExtensionOperations: allowExtensionOperations
    }
    networkProfile: {
      networkInterfaces: [
        for (nicConfiguration, index) in nicConfigurations: {
          properties: {
            deleteOption: nicConfiguration.?deleteOption ?? 'Delete'
            primary: index == 0 ? true : false
          }
          #disable-next-line use-resource-id-functions // It's a reference from inside a loop which makes resolving it using a resource reference particulary difficult.
          id: az.resourceId(
            'Microsoft.Network/networkInterfaces',
            nicConfiguration.?name ?? '${name}${nicConfiguration.?nicSuffix}'
          )
        }
      ]
    }
    diagnosticsProfile: {
      bootDiagnostics: {
        enabled: !empty(bootDiagnosticStorageAccountName) ? true : bootDiagnostics
        storageUri: !empty(bootDiagnosticStorageAccountName)
          ? 'https://${bootDiagnosticStorageAccountName}${bootDiagnosticStorageAccountUri}'
          : null
      }
    }
    applicationProfile: !empty(galleryApplications)
      ? {
          galleryApplications: galleryApplications
        }
      : null
    availabilitySet: !empty(availabilitySetResourceId)
      ? {
          id: availabilitySetResourceId
        }
      : null
    proximityPlacementGroup: !empty(proximityPlacementGroupResourceId)
      ? {
          id: proximityPlacementGroupResourceId
        }
      : null
    virtualMachineScaleSet: !empty(virtualMachineScaleSetResourceId)
      ? {
          id: virtualMachineScaleSetResourceId
        }
      : null
    priority: priority
    evictionPolicy: !empty(priority) && priority != 'Regular' ? evictionPolicy : null
    #disable-next-line BCP036
    billingProfile: !empty(priority) && !empty(maxPriceForLowPriorityVm)
      ? {
          maxPrice: json(maxPriceForLowPriorityVm)
        }
      : null
    host: !empty(dedicatedHostId)
      ? {
          id: dedicatedHostId
        }
      : null
    licenseType: !empty(licenseType) ? licenseType : null
    userData: !empty(userData) ? base64(userData) : null
  }
  dependsOn: [
    vm_nic
  ]
}

resource vm_configurationAssignment 'Microsoft.Maintenance/configurationAssignments@2023-04-01' = if (!empty(maintenanceConfigurationResourceId)) {
  name: '${vm.name}assignment'
  location: location
  properties: {
    maintenanceConfigurationId: maintenanceConfigurationResourceId
    resourceId: vm.id
  }
  scope: vm
}

module vm_microsoftAntiMalwareExtension 'extension/extension.bicep' = if (extensionAntiMalwareConfig.enabled) {
  name: '${uniqueString(deployment().name, location)}-VM-MicrosoftAntiMalware'
  params: {
    virtualMachineName: vm.name
    name: extensionAntiMalwareConfig.?name ?? 'MicrosoftAntiMalware'
    location: location
    publisher: 'Microsoft.Azure.Security'
    type: 'IaaSAntimalware'
    typeHandlerVersion: extensionAntiMalwareConfig.?typeHandlerVersion ?? '1.3'
    autoUpgradeMinorVersion: extensionAntiMalwareConfig.?autoUpgradeMinorVersion ?? true
    enableAutomaticUpgrade: extensionAntiMalwareConfig.?enableAutomaticUpgrade ?? false
    settings: extensionAntiMalwareConfig.?settings ?? {
      AntimalwareEnabled: 'true'
      Exclusions: {}
      RealtimeProtectionEnabled: 'true'
      ScheduledScanSettings: {
        day: '7'
        isEnabled: 'true'
        scanType: 'Quick'
        time: '120'
      }
    }
    supressFailures: extensionAntiMalwareConfig.?supressFailures ?? false
    tags: extensionAntiMalwareConfig.?tags ?? tags
  }
}

module vm_azureGuestConfigurationExtension 'extension/extension.bicep' = if (extensionGuestConfigurationExtension.enabled) {
  name: '${uniqueString(deployment().name, location)}-VM-GuestConfiguration'
  params: {
    virtualMachineName: vm.name
    name: extensionGuestConfigurationExtension.?name ?? osType == 'Windows'
      ? 'AzurePolicyforWindows'
      : 'AzurePolicyforLinux'
    location: location
    publisher: 'Microsoft.GuestConfiguration'
    type: osType == 'Windows' ? 'ConfigurationforWindows' : 'ConfigurationForLinux'
    typeHandlerVersion: extensionGuestConfigurationExtension.?typeHandlerVersion ?? (osType == 'Windows' ? '1.0' : '1.0')
    autoUpgradeMinorVersion: extensionGuestConfigurationExtension.?autoUpgradeMinorVersion ?? true
    enableAutomaticUpgrade: extensionGuestConfigurationExtension.?enableAutomaticUpgrade ?? true
    forceUpdateTag: extensionGuestConfigurationExtension.?forceUpdateTag ?? '1.0'
    settings: extensionGuestConfigurationExtension.?settings ?? {}
    supressFailures: extensionGuestConfigurationExtension.?supressFailures ?? false
    protectedSettings: extensionGuestConfigurationExtensionProtectedSettings
    tags: extensionGuestConfigurationExtension.?tags ?? tags
  }
}

resource AzureWindowsBaseline 'Microsoft.GuestConfiguration/guestConfigurationAssignments@2020-06-25' = if (!empty(guestConfiguration)) {
  name: guestConfiguration.?name ?? 'AzureWindowsBaseline'
  scope: vm
  dependsOn: [
    vm_azureGuestConfigurationExtension
  ]
  location: location
  properties: {
    guestConfiguration: guestConfiguration
  }
}

resource vm_roleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for (roleAssignment, index) in (formattedRoleAssignments ?? []): {
    name: roleAssignment.?name ?? guid(vm.id, roleAssignment.principalId, roleAssignment.roleDefinitionId)
    properties: {
      roleDefinitionId: roleAssignment.roleDefinitionId
      principalId: roleAssignment.principalId
      description: roleAssignment.?description
      principalType: roleAssignment.?principalType
      condition: roleAssignment.?condition
      conditionVersion: !empty(roleAssignment.?condition) ? (roleAssignment.?conditionVersion ?? '2.0') : null // Must only be set if condtion is set
      delegatedManagedIdentityResourceId: roleAssignment.?delegatedManagedIdentityResourceId
    }
    scope: vm
  }
]

@description('The name of the VM.')
output name string = vm.name

@description('The resource ID of the VM.')
output resourceId string = vm.id

@description('The location the resource was deployed into.')
output location string = vm.location

// =============== //
//   Definitions   //
// =============== //
import { networkInterfaceIPConfigurationOutputType } from 'br/public:avm/res/network/network-interface:0.5.1'

@export()
@description('The type describing an OS disk.')
type osDiskType = {
  @description('Optional. The disk name.')
  name: string?

  @description('Optional. Specifies the size of an empty data disk in gigabytes.')
  diskSizeGB: int?

  @description('Optional. Specifies how the virtual machine should be created.')
  createOption: 'Attach' | 'Empty' | 'FromImage'?

  @description('Optional. Specifies whether data disk should be deleted or detached upon VM deletion.')
  deleteOption: 'Delete' | 'Detach'?

  @description('Optional. Specifies the caching requirements.')
  caching: 'None' | 'ReadOnly' | 'ReadWrite'?

  @description('Optional. Specifies the ephemeral Disk Settings for the operating system disk.')
  diffDiskSettings: {
    @description('Required. Specifies the ephemeral disk placement for the operating system disk.')
    placement: ('CacheDisk' | 'NvmeDisk' | 'ResourceDisk')
  }?

  @description('Required. The managed disk parameters.')
  managedDisk: {
    @description('Optional. Specifies the storage account type for the managed disk.')
    storageAccountType:
      | 'PremiumV2_LRS'
      | 'Premium_LRS'
      | 'Premium_ZRS'
      | 'StandardSSD_LRS'
      | 'StandardSSD_ZRS'
      | 'Standard_LRS'
      | 'UltraSSD_LRS'?

    @description('Optional. Specifies the customer managed disk encryption set resource id for the managed disk.')
    diskEncryptionSetResourceId: string?
  }
}

@export()
@description('The type describing a data disk.')
type dataDiskType = {
  @description('Optional. The disk name. When attaching a pre-existing disk, this name is ignored and the name of the existing disk is used.')
  name: string?

  @description('Optional. Specifies the logical unit number of the data disk.')
  lun: int?

  @description('Optional. Specifies the size of an empty data disk in gigabytes. This property is ignored when attaching a pre-existing disk.')
  diskSizeGB: int?

  @description('Optional. Specifies how the virtual machine should be created. This property is automatically set to \'Attach\' when attaching a pre-existing disk.')
  createOption: 'Attach' | 'Empty' | 'FromImage'?

  @description('Optional. Specifies whether data disk should be deleted or detached upon VM deletion. This property is automatically set to \'Detach\' when attaching a pre-existing disk.')
  deleteOption: 'Delete' | 'Detach'?

  @description('Optional. Specifies the caching requirements. This property is automatically set to \'None\' when attaching a pre-existing disk.')
  caching: 'None' | 'ReadOnly' | 'ReadWrite'?

  @description('Optional. The number of IOPS allowed for this disk; only settable for UltraSSD disks. One operation can transfer between 4k and 256k bytes. Ignored when attaching a pre-existing disk.')
  diskIOPSReadWrite: int?

  @description('Optional. The bandwidth allowed for this disk; only settable for UltraSSD disks. MBps means millions of bytes per second - MB here uses the ISO notation, of powers of 10. Ignored when attaching a pre-existing disk.')
  diskMBpsReadWrite: int?

  @description('Required. The managed disk parameters.')
  managedDisk: {
    @description('Optional. Specifies the storage account type for the managed disk. Ignored when attaching a pre-existing disk.')
    storageAccountType:
      | 'PremiumV2_LRS'
      | 'Premium_LRS'
      | 'Premium_ZRS'
      | 'StandardSSD_LRS'
      | 'StandardSSD_ZRS'
      | 'Standard_LRS'
      | 'UltraSSD_LRS'?

    @description('Optional. Specifies the customer managed disk encryption set resource id for the managed disk.')
    diskEncryptionSetResourceId: string?

    @description('Optional. Specifies the resource id of a pre-existing managed disk. If the disk should be created, this property should be empty.')
    id: string?
  }

  @description('Optional. The tags of the public IP address. Valid only when creating a new managed disk.')
  tags: object?
}

type publicKeyType = {
  @description('Required. Specifies the SSH public key data used to authenticate through ssh.')
  keyData: string

  @description('Required. Specifies the full path on the created VM where ssh public key is stored. If the file already exists, the specified key is appended to the file.')
  path: string
}

import { ipConfigurationType } from 'nic-configuration/nic-configuration.bicep'
import { diagnosticSettingFullType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
import { subResourceType } from 'br/public:avm/res/network/network-interface:0.5.1'

@export()
@description('The type for the NIC configuration.')
type nicConfigurationType = {
  @description('Optional. The name of the NIC configuration.')
  name: string?

  @description('Optional. The suffix to append to the NIC name.')
  nicSuffix: string?

  @description('Optional. Indicates whether IP forwarding is enabled on this network interface.')
  enableIPForwarding: bool?

  @description('Optional. If the network interface is accelerated networking enabled.')
  enableAcceleratedNetworking: bool?

  @description('Optional. Specify what happens to the network interface when the VM is deleted.')
  deleteOption: 'Delete' | 'Detach'?

  @description('Optional. List of DNS servers IP addresses. Use \'AzureProvidedDNS\' to switch to azure provided DNS resolution. \'AzureProvidedDNS\' value cannot be combined with other IPs, it must be the only value in dnsServers collection.')
  dnsServers: string[]?

  @description('Optional. The network security group (NSG) to attach to the network interface.')
  networkSecurityGroupResourceId: string?

  @description('Required. The IP configurations of the network interface.')
  ipConfigurations: ipConfigurationType[]

  @description('Optional. The lock settings of the service.')
  lock: lockType?

  @description('Optional. The tags of the public IP address.')
  tags: object?

  @description('Optional. Enable/Disable usage telemetry for the module.')
  enableTelemetry: bool?

  @description('Optional. The diagnostic settings of the IP configuration.')
  diagnosticSettings: diagnosticSettingFullType[]?

  @description('Optional. Array of role assignments to create.')
  roleAssignments: roleAssignmentType[]?
}

@export()
@description('The type describing the image reference.')
type imageReferenceType = {
  @description('Optional. Specified the community gallery image unique id for vm deployment. This can be fetched from community gallery image GET call.')
  communityGalleryImageId: string?

  @description('Optional. The resource Id of the image reference.')
  id: string?

  @description('Optional. Specifies the offer of the platform image or marketplace image used to create the virtual machine.')
  offer: string?

  @description('Optional. The image publisher.')
  publisher: string?

  @description('Optional. The SKU of the image.')
  sku: string?

  @description('Optional. Specifies the version of the platform image or marketplace image used to create the virtual machine. The allowed formats are Major.Minor.Build or \'latest\'. Even if you use \'latest\', the VM image will not automatically update after deploy time even if a new version becomes available.')
  version: string?

  @description('Optional. Specified the shared gallery image unique id for vm deployment. This can be fetched from shared gallery image GET call.')
  sharedGalleryImageId: string?
}

@export()
@description('Specifies information about the marketplace image used to create the virtual machine.')
type planType = {
  @description('Optional. The name of the plan.')
  name: string?

  @description('Optional. Specifies the product of the image from the marketplace.')
  product: string?

  @description('Optional. The publisher ID.')
  publisher: string?

  @description('Optional. The promotion code.')
  promotionCode: string?
}

@export()
@description('The type describing the set of certificates that should be installed onto the virtual machine.')
type vaultSecretGroupType = {
  @description('Optional. The relative URL of the Key Vault containing all of the certificates in VaultCertificates.')
  sourceVault: subResourceType?

  @description('Optional. The list of key vault references in SourceVault which contain certificates.')
  vaultCertificates: {
    @description('Optional. For Windows VMs, specifies the certificate store on the Virtual Machine to which the certificate should be added. The specified certificate store is implicitly in the LocalMachine account. For Linux VMs, the certificate file is placed under the /var/lib/waagent directory, with the file name <UppercaseThumbprint>.crt for the X509 certificate file and <UppercaseThumbprint>.prv for private key. Both of these files are .pem formatted.')
    certificateStore: string?

    @description('Optional. This is the URL of a certificate that has been uploaded to Key Vault as a secret.')
    certificateUrl: string?
  }[]?
}

@export()
@description('The type describing the gallery application that should be made available to the VM/VMSS.')
type vmGalleryApplicationType = {
  @description('Required. Specifies the GalleryApplicationVersion resource id on the form of /subscriptions/{SubscriptionId}/resourceGroups/{ResourceGroupName}/providers/Microsoft.Compute/galleries/{galleryName}/applications/{application}/versions/{version}.')
  packageReferenceId: string

  @description('Optional. Specifies the uri to an azure blob that will replace the default configuration for the package if provided.')
  configurationReference: string?

  @description('Optional. If set to true, when a new Gallery Application version is available in PIR/SIG, it will be automatically updated for the VM/VMSS.')
  enableAutomaticUpgrade: bool?

  @description('Optional. Specifies the order in which the packages have to be installed.')
  order: int?

  @description('Optional. Specifies a passthrough value for more generic context.')
  tags: string?

  @description('Optional. If true, any failure for any operation in the VmApplication will fail the deployment.')
  treatFailureAsDeploymentFailure: bool?
}

@export()
@description('The type describing additional base-64 encoded XML formatted information that can be included in the Unattend.xml file, which is used by Windows Setup.')
type additionalUnattendContentType = {
  @description('Optional. Specifies the name of the setting to which the content applies.')
  settingName: 'FirstLogonCommands' | 'AutoLogon'?

  @description('Optional. Specifies the XML formatted content that is added to the unattend.xml file for the specified path and component. The XML must be less than 4KB and must include the root element for the setting or feature that is being inserted.')
  content: string?
}

@export()
@description('The type describing a Windows Remote Management listener.')
type winRMListenerType = {
  @description('Optional. The URL of a certificate that has been uploaded to Key Vault as a secret.')
  certificateUrl: string?

  @description('Optional. Specifies the protocol of WinRM listener.')
  protocol: 'Http' | 'Https'?
}

@export()
@description('The type describing the network interface configuration output.')
type nicConfigurationOutputType = {
  @description('Required. The name of the NIC configuration.')
  name: string

  @description('Required. List of IP configurations of the NIC configuration.')
  ipConfigurations: networkInterfaceIPConfigurationOutputType[]
}
