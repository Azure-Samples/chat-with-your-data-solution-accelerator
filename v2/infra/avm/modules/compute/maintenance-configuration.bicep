// ============================================================================
// Module: Maintenance Configuration
// Description: AVM wrapper for Azure Maintenance Configuration
// AVM Module: avm/res/maintenance/maintenance-configuration
// WAF: https://learn.microsoft.com/en-us/azure/well-architected/service-guides/virtual-machines
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Name of the maintenance configuration.')
param name string = 'mc-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Maintenance scope.')
param maintenanceScope string = 'InGuestPatch'

@description('Visibility of the configuration.')
param visibility string = 'Custom'

@description('Extension properties.')
param extensionProperties object = {
  InGuestPatchMode: 'User'
}

@description('Maintenance window configuration.')
param maintenanceWindow object = {
  startDateTime: '2024-06-16 00:00'
  duration: '03:55'
  timeZone: 'W. Europe Standard Time'
  recurEvery: '1Day'
}

@description('Install patches configuration.')
param installPatches object = {
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

@description('Enable Azure telemetry collection.')
param enableTelemetry bool = true

// ============================================================================
// AVM Module Deployment
// ============================================================================
module maintenanceConfiguration 'br/public:avm/res/maintenance/maintenance-configuration:0.4.0' = {
  name: take('avm.res.maintenance.maintenance-configuration.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    extensionProperties: extensionProperties
    maintenanceScope: maintenanceScope
    maintenanceWindow: maintenanceWindow
    visibility: visibility
    installPatches: installPatches
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the maintenance configuration.')
output resourceId string = maintenanceConfiguration.outputs.resourceId

@description('Name of the maintenance configuration.')
output name string = maintenanceConfiguration.outputs.name
