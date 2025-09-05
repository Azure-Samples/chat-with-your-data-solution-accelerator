@description('Required. Name of the site.')
param name string

@description('Optional. Location for all Resources.')
param location string = resourceGroup().location

@description('Required. Type of site to deploy.')
@allowed([
  'functionapp' // function app windows os
  'functionapp,linux' // function app linux os
  'functionapp,workflowapp' // logic app workflow
  'functionapp,workflowapp,linux' // logic app docker container
  'functionapp,linux,container' // function app linux container
  'functionapp,linux,container,azurecontainerapps' // function app linux container azure container apps
  'app,linux' // linux web app
  'app' // windows web app
  'linux,api' // linux api app
  'api' // windows api app
  'app,linux,container' // linux container app
  'app,container,windows' // windows container app
])
param kind string

@description('Required. The resource ID of the app service plan to use for the site.')
param serverFarmResourceId string

@description('Optional. Azure Resource Manager ID of the customers selected Managed Environment on which to host this app.')
param managedEnvironmentId string?

@description('Optional. Configures a site to accept only HTTPS requests. Issues redirect for HTTP requests.')
param httpsOnly bool = true

@description('Optional. If client affinity is enabled.')
param clientAffinityEnabled bool = true

@description('Optional. The resource ID of the app service environment to use for this resource.')
param appServiceEnvironmentResourceId string?

import { managedIdentityAllType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. The managed identity definition for this resource.')
param managedIdentities managedIdentityAllType?

@description('Optional. The resource ID of the assigned identity to be used to access a key vault with.')
param keyVaultAccessIdentityResourceId string?

@description('Optional. Checks if Customer provided storage account is required.')
param storageAccountRequired bool = false

@description('Optional. Azure Resource Manager ID of the Virtual network and subnet to be joined by Regional VNET Integration. This must be of the form /subscriptions/{subscriptionName}/resourceGroups/{resourceGroupName}/providers/Microsoft.Network/virtualNetworks/{vnetName}/subnets/{subnetName}.')
param virtualNetworkSubnetId string?

@description('Optional. To enable accessing content over virtual network.')
param vnetContentShareEnabled bool = false

@description('Optional. To enable pulling image over Virtual Network.')
param vnetImagePullEnabled bool = false

@description('Optional. Virtual Network Route All enabled. This causes all outbound traffic to have Virtual Network Security Groups and User Defined Routes applied.')
param vnetRouteAllEnabled bool = false

@description('Optional. Stop SCM (KUDU) site when the app is stopped.')
param scmSiteAlsoStopped bool = false

@description('Optional. The site config object. The defaults are set to the following values: alwaysOn: true, minTlsVersion: \'1.2\', ftpsState: \'FtpsOnly\'.')
param siteConfig resourceInput<'Microsoft.Web/sites@2024-04-01'>.properties.siteConfig = {
  alwaysOn: true
  minTlsVersion: '1.2'
  ftpsState: 'FtpsOnly'
}

@description('Optional. The web site config.')
param configs appSettingsConfigType[]?

@description('Optional. The Function App configuration object.')
param functionAppConfig resourceInput<'Microsoft.Web/sites@2024-04-01'>.properties.functionAppConfig?

import { privateEndpointSingleServiceType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. Configuration details for private endpoints. For security reasons, it is recommended to use private endpoints whenever possible.')
param privateEndpoints privateEndpointSingleServiceType[]?

@description('Optional. Tags of the resource.')
param tags object?

import { diagnosticSettingFullType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. The diagnostic settings of the service.')
param diagnosticSettings diagnosticSettingFullType[]?

@description('Optional. To enable client certificate authentication (TLS mutual authentication).')
param clientCertEnabled bool = false

@description('Optional. Client certificate authentication comma-separated exclusion paths.')
param clientCertExclusionPaths string?

@description('''
Optional. This composes with ClientCertEnabled setting.
- ClientCertEnabled=false means ClientCert is ignored.
- ClientCertEnabled=true and ClientCertMode=Required means ClientCert is required.
- ClientCertEnabled=true and ClientCertMode=Optional means ClientCert is optional or accepted.
''')
@allowed([
  'Optional'
  'OptionalInteractiveUser'
  'Required'
])
param clientCertMode string = 'Optional'

@description('Optional. If specified during app creation, the app is cloned from a source app.')
param cloningInfo resourceInput<'Microsoft.Web/sites@2024-04-01'>.properties.cloningInfo?

@description('Optional. Size of the function container.')
param containerSize int?

@description('Optional. Maximum allowed daily memory-time quota (applicable on dynamic apps only).')
param dailyMemoryTimeQuota int?

@description('Optional. Setting this value to false disables the app (takes the app offline).')
param enabled bool = true

@description('Optional. Hostname SSL states are used to manage the SSL bindings for app\'s hostnames.')
param hostNameSslStates resourceInput<'Microsoft.Web/sites@2024-04-01'>.properties.hostNameSslStates?

@description('Optional. Hyper-V sandbox.')
param hyperV bool = false

@description('Optional. Site redundancy mode.')
@allowed([
  'ActiveActive'
  'Failover'
  'GeoRedundant'
  'Manual'
  'None'
])
param redundancyMode string = 'None'

@description('Optional. Whether or not public network access is allowed for this resource. For security reasons it should be disabled. If not specified, it will be disabled by default if private endpoints are set.')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string?

@description('Optional. End to End Encryption Setting.')
param e2eEncryptionEnabled bool?

@description('Optional. Property to configure various DNS related settings for a site.')
param dnsConfiguration resourceInput<'Microsoft.Web/sites@2024-04-01'>.properties.dnsConfiguration?

@description('Optional. Specifies the scope of uniqueness for the default hostname during resource creation.')
@allowed([
  'NoReuse'
  'ResourceGroupReuse'
  'SubscriptionReuse'
  'TenantReuse'
])
param autoGeneratedDomainNameLabelScope string?

var formattedUserAssignedIdentities = reduce(
  map((managedIdentities.?userAssignedResourceIds ?? []), (id) => { '${id}': {} }),
  {},
  (cur, next) => union(cur, next)
) // Converts the flat array to an object like { '${id1}': {}, '${id2}': {} }

var identity = !empty(managedIdentities)
  ? {
      type: (managedIdentities.?systemAssigned ?? false)
        ? (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'SystemAssigned, UserAssigned' : 'SystemAssigned')
        : (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'UserAssigned' : 'None')
      userAssignedIdentities: !empty(formattedUserAssignedIdentities) ? formattedUserAssignedIdentities : null
    }
  : null

resource app 'Microsoft.Web/sites@2024-04-01' = {
  name: name
  location: location
  kind: kind
  tags: tags
  identity: identity
  properties: {
    managedEnvironmentId: !empty(managedEnvironmentId) ? managedEnvironmentId : null
    serverFarmId: serverFarmResourceId
    clientAffinityEnabled: clientAffinityEnabled
    httpsOnly: httpsOnly
    hostingEnvironmentProfile: !empty(appServiceEnvironmentResourceId)
      ? {
          id: appServiceEnvironmentResourceId
        }
      : null
    storageAccountRequired: storageAccountRequired
    keyVaultReferenceIdentity: keyVaultAccessIdentityResourceId
    virtualNetworkSubnetId: virtualNetworkSubnetId
    siteConfig: siteConfig
    functionAppConfig: functionAppConfig
    clientCertEnabled: clientCertEnabled
    clientCertExclusionPaths: clientCertExclusionPaths
    clientCertMode: clientCertMode
    cloningInfo: cloningInfo
    containerSize: containerSize
    dailyMemoryTimeQuota: dailyMemoryTimeQuota
    enabled: enabled
    hostNameSslStates: hostNameSslStates
    hyperV: hyperV
    redundancyMode: redundancyMode
    publicNetworkAccess: !empty(publicNetworkAccess)
      ? any(publicNetworkAccess)
      : (!empty(privateEndpoints) ? 'Disabled' : 'Enabled')
    vnetContentShareEnabled: vnetContentShareEnabled
    vnetImagePullEnabled: vnetImagePullEnabled
    vnetRouteAllEnabled: vnetRouteAllEnabled
    scmSiteAlsoStopped: scmSiteAlsoStopped
    endToEndEncryptionEnabled: e2eEncryptionEnabled
    dnsConfiguration: dnsConfiguration
    autoGeneratedDomainNameLabelScope: autoGeneratedDomainNameLabelScope
  }
}

module app_config 'web-sites.config.bicep' = [
  for (config, index) in (configs ?? []): {
    name: '${uniqueString(deployment().name, location)}-Site-Config-${index}'
    params: {
      appName: app.name
      name: config.name
      applicationInsightResourceId: config.?applicationInsightResourceId
      storageAccountResourceId: config.?storageAccountResourceId
      storageAccountUseIdentityAuthentication: config.?storageAccountUseIdentityAuthentication
      properties: config.?properties
      currentAppSettings: config.?retainCurrentAppSettings ?? true && config.name == 'appsettings'
        ? list('${app.id}/config/appsettings', '2023-12-01').properties
        : {}
    }
  }
]

#disable-next-line use-recent-api-versions
resource app_diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = [
  for (diagnosticSetting, index) in (diagnosticSettings ?? []): {
    name: diagnosticSetting.?name ?? '${name}-diagnosticSettings'
    properties: {
      storageAccountId: diagnosticSetting.?storageAccountResourceId
      workspaceId: diagnosticSetting.?workspaceResourceId
      eventHubAuthorizationRuleId: diagnosticSetting.?eventHubAuthorizationRuleResourceId
      eventHubName: diagnosticSetting.?eventHubName
      metrics: [
        for group in (diagnosticSetting.?metricCategories ?? [{ category: 'AllMetrics' }]): {
          category: group.category
          enabled: group.?enabled ?? true
          timeGrain: null
        }
      ]
      logs: [
        for group in (diagnosticSetting.?logCategoriesAndGroups ?? [{ categoryGroup: 'allLogs' }]): {
          categoryGroup: group.?categoryGroup
          category: group.?category
          enabled: group.?enabled ?? true
        }
      ]
      marketplacePartnerId: diagnosticSetting.?marketplacePartnerResourceId
      logAnalyticsDestinationType: diagnosticSetting.?logAnalyticsDestinationType
    }
    scope: app
  }
]

module app_privateEndpoints 'br/public:avm/res/network/private-endpoint:0.11.0' = [
  for (privateEndpoint, index) in (privateEndpoints ?? []): {
    name: '${uniqueString(deployment().name, location)}-app-PrivateEndpoint-${index}'
    scope: resourceGroup(
      split(privateEndpoint.?resourceGroupResourceId ?? resourceGroup().id, '/')[2],
      split(privateEndpoint.?resourceGroupResourceId ?? resourceGroup().id, '/')[4]
    )
    params: {
      name: privateEndpoint.?name ?? 'pep-${last(split(app.id, '/'))}-${privateEndpoint.?service ?? 'sites'}-${index}'
      privateLinkServiceConnections: privateEndpoint.?isManualConnection != true
        ? [
            {
              name: privateEndpoint.?privateLinkServiceConnectionName ?? '${last(split(app.id, '/'))}-${privateEndpoint.?service ?? 'sites'}-${index}'
              properties: {
                privateLinkServiceId: app.id
                groupIds: [
                  privateEndpoint.?service ?? 'sites'
                ]
              }
            }
          ]
        : null
      manualPrivateLinkServiceConnections: privateEndpoint.?isManualConnection == true
        ? [
            {
              name: privateEndpoint.?privateLinkServiceConnectionName ?? '${last(split(app.id, '/'))}-${privateEndpoint.?service ?? 'sites'}-${index}'
              properties: {
                privateLinkServiceId: app.id
                groupIds: [
                  privateEndpoint.?service ?? 'sites'
                ]
                requestMessage: privateEndpoint.?manualConnectionRequestMessage ?? 'Manual approval required.'
              }
            }
          ]
        : null
      subnetResourceId: privateEndpoint.subnetResourceId
      enableTelemetry: false //As per https://azure.github.io/Azure-Verified-Modules/spec/BCPFR7/
      location: privateEndpoint.?location ?? reference(
        split(privateEndpoint.subnetResourceId, '/subnets/')[0],
        '2020-06-01',
        'Full'
      ).location
      lock: privateEndpoint.?lock ?? null
      privateDnsZoneGroup: privateEndpoint.?privateDnsZoneGroup
      roleAssignments: privateEndpoint.?roleAssignments
      tags: privateEndpoint.?tags ?? tags
      customDnsConfigs: privateEndpoint.?customDnsConfigs
      ipConfigurations: privateEndpoint.?ipConfigurations
      applicationSecurityGroupResourceIds: privateEndpoint.?applicationSecurityGroupResourceIds
      customNetworkInterfaceName: privateEndpoint.?customNetworkInterfaceName
    }
  }
]

@description('The name of the site.')
output name string = app.name

@description('The resource ID of the site.')
output resourceId string = app.id

@description('The resource group the site was deployed into.')
output resourceGroupName string = resourceGroup().name

@description('The principal ID of the system assigned identity.')
output systemAssignedMIPrincipalId string? = app.?identity.?principalId

@description('The location the resource was deployed into.')
output location string = app.location

@description('Default hostname of the app.')
output defaultHostname string = app.properties.defaultHostName

@description('Unique identifier that verifies the custom domains assigned to the app. Customer will add this ID to a txt record for verification.')
output customDomainVerificationId string = app.properties.customDomainVerificationId

@description('The outbound IP addresses of the app.')
output outboundIpAddresses string = app.properties.outboundIpAddresses

// ================ //
// Definitions      //
// ================ //
@export()
@description('The type of an app settings configuration.')
type appSettingsConfigType = {
  @description('Required. The type of config.')
  name: 'appsettings'

  @description('Optional. If the provided storage account requires Identity based authentication (\'allowSharedKeyAccess\' is set to false). When set to true, the minimum role assignment required for the App Service Managed Identity to the storage account is \'Storage Blob Data Owner\'.')
  storageAccountUseIdentityAuthentication: bool?

  @description('Optional. Required if app of kind functionapp. Resource ID of the storage account to manage triggers and logging function executions.')
  storageAccountResourceId: string?

  @description('Optional. Resource ID of the application insight to leverage for this resource.')
  applicationInsightResourceId: string?

  @description('Optional. The retain the current app settings. Defaults to true.')
  retainCurrentAppSettings: bool?

  @description('Optional. The app settings key-value pairs except for AzureWebJobsStorage, AzureWebJobsDashboard, APPINSIGHTS_INSTRUMENTATIONKEY and APPLICATIONINSIGHTS_CONNECTION_STRING.')
  properties: {
    @description('Required. An app settings key-value pair.')
    *: string
  }?
}
