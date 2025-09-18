metadata name = 'Machine Learning Services Workspaces'
metadata description = 'This module deploys a Machine Learning Services Workspace.'

// ================ //
// Parameters       //
// ================ //
@sys.description('Required. The name of the machine learning workspace.')
param name string

@sys.description('Optional. The friendly name of the machine learning workspace.')
param friendlyName string?

@sys.description('Optional. Location for all resources.')
param location string = resourceGroup().location

@sys.description('Required. Specifies the SKU, also referred as \'edition\' of the Azure Machine Learning workspace.')
@allowed([
  'Free'
  'Basic'
  'Standard'
  'Premium'
])
param sku string

@sys.description('Optional. The type of Azure Machine Learning workspace to create.')
@allowed([
  'Default'
  'Project'
  'Hub'
  'FeatureStore'
])
param kind string = 'Default'

@sys.description('Conditional. The resource ID of the associated Storage Account. Required if \'kind\' is \'Default\', \'FeatureStore\' or \'Hub\'.')
param associatedStorageAccountResourceId string?

@sys.description('Conditional. The resource ID of the associated Key Vault. Required if \'kind\' is \'Default\' or \'FeatureStore\'. If not provided, the key vault will be managed by Microsoft.')
param associatedKeyVaultResourceId string?

@sys.description('Conditional. The resource ID of the associated Application Insights. Required if \'kind\' is \'Default\' or \'FeatureStore\'.')
param associatedApplicationInsightsResourceId string?

@sys.description('Optional. The resource ID of the associated Container Registry.')
param associatedContainerRegistryResourceId string?

@sys.description('Optional. Enable service-side encryption.')
param enableServiceSideCMKEncryption bool?

import { lockType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@sys.description('Optional. The lock settings of the service.')
param lock lockType?

@sys.description('Optional. The flag to signal HBI data in the workspace and reduce diagnostic data collected by the service.')
param hbiWorkspace bool = false

@sys.description('Conditional. The resource ID of the hub to associate with the workspace. Required if \'kind\' is set to \'Project\'.')
param hubResourceId string?

import { roleAssignmentType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@sys.description('Optional. Array of role assignments to create.')
param roleAssignments roleAssignmentType[]?

import { privateEndpointSingleServiceType } from 'br/public:avm/utl/types/avm-common-types:0.6.1'
@sys.description('Optional. Configuration details for private endpoints. For security reasons, it is recommended to use private endpoints whenever possible.')
param privateEndpoints privateEndpointSingleServiceType[]?

@sys.description('Optional. Connections to create in the workspace.')
param connections connectionType[]?

@sys.description('Optional. Resource tags.')
param tags object?

@sys.description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

import { managedIdentityAllType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@sys.description('Optional. The managed identity definition for this resource. At least one identity type is required.')
param managedIdentities managedIdentityAllType = {
  systemAssigned: true
}

// @sys.description('Conditional. Settings for feature store type workspaces. Required if \'kind\' is set to \'FeatureStore\'.')
// param featureStoreSettings featureStoreSettingType?

@sys.description('Optional. List of IPv4 addresse ranges that are allowed to access the workspace.')
param ipAllowlist string[]?

// @sys.description('Optional. Managed Network settings for a machine learning workspace.')
// param managedNetworkSettings managedNetworkSettingType?

@sys.description('Optional. Trigger the provisioning of the managed virtual network when creating the workspace.')
param provisionNetworkNow bool?

// @sys.description('Optional. Settings for serverless compute created in the workspace.')
// param serverlessComputeSettings serverlessComputeSettingType?

@sys.description('Optional. The authentication mode used by the workspace when connecting to the default storage account.')
@allowed([
  'AccessKey'
  'Identity'
  'UserDelegationSAS'
])
param systemDatastoresAuthMode string?

//@sys.description('Optional. Configuration for workspace hub settings.')
//param workspaceHubConfig workspaceHubConfigType?

// Diagnostic Settings
import { diagnosticSettingFullType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@sys.description('Optional. The diagnostic settings of the service.')
param diagnosticSettings diagnosticSettingFullType[]?

@sys.description('Optional. The description of this workspace.')
param description string?

@sys.description('Optional. URL for the discovery service to identify regional endpoints for machine learning experimentation services.')
param discoveryUrl string?

import { customerManagedKeyType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@sys.description('Optional. The customer managed key definition.')
param customerManagedKey customerManagedKeyType?

@sys.description('Optional. The compute name for image build.')
param imageBuildCompute string?

@sys.description('Conditional. The user assigned identity resource ID that represents the workspace identity. Required if \'userAssignedIdentities\' is not empty and may not be used if \'systemAssignedIdentity\' is enabled.')
param primaryUserAssignedIdentity string?

@sys.description('Optional. The service managed resource settings.')
param serviceManagedResourcesSettings object?

@sys.description('Optional. The list of shared private link resources in this workspace. Note: This property is not idempotent.')
param sharedPrivateLinkResources array?

@sys.description('Optional. Whether or not public network access is allowed for this resource. For security reasons it should be disabled.')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Disabled'

// ================//
// Variables       //
// ================//

var enableReferencedModulesTelemetry = false

var formattedUserAssignedIdentities = reduce(
  map((managedIdentities.?userAssignedResourceIds ?? []), (id) => { '${id}': {} }),
  {},
  (cur, next) => union(cur, next)
) // Converts the flat array to an object like { '${id1}': {}, '${id2}': {} }

var identity = !empty(managedIdentities)
  ? {
      type: (managedIdentities.?systemAssigned ?? false)
        ? (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'SystemAssigned,UserAssigned' : 'SystemAssigned')
        : (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'UserAssigned' : 'None')
      userAssignedIdentities: !empty(formattedUserAssignedIdentities) ? formattedUserAssignedIdentities : null
    }
  : null

// ================//
// Deployments     //
// ================//
var builtInRoleNames = {
  'AzureML Compute Operator': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'e503ece1-11d0-4e8e-8e2c-7a6c3bf38815'
  )
  'AzureML Data Scientist': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'f6c7c914-8db3-469d-8ca1-694a8f32e121'
  )
  'AzureML Metrics Writer (preview)': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '635dd51f-9968-44d3-b7fb-6d9a6bd613ae'
  )
  'AzureML Registry User': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '1823dd4f-9b8c-4ab6-ab4e-7397a3684615'
  )
  Contributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
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
  name: '46d3xbcp.res.machinelearningservices-workspace.${replace('-..--..-', '.', '-')}.${substring(uniqueString(deployment().name, location), 0, 4)}'
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

resource cMKKeyVault 'Microsoft.KeyVault/vaults@2023-02-01' existing = if (!empty(customerManagedKey.?keyVaultResourceId)) {
  name: last(split((customerManagedKey.?keyVaultResourceId!), '/'))
  scope: resourceGroup(
    split(customerManagedKey.?keyVaultResourceId!, '/')[2],
    split(customerManagedKey.?keyVaultResourceId!, '/')[4]
  )

  resource cMKKey 'keys@2023-02-01' existing = if (!empty(customerManagedKey.?keyVaultResourceId) && !empty(customerManagedKey.?keyName)) {
    name: customerManagedKey.?keyName!
  }
}

resource cMKUserAssignedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = if (!empty(customerManagedKey.?userAssignedIdentityResourceId)) {
  name: last(split(customerManagedKey.?userAssignedIdentityResourceId!, '/'))
  scope: resourceGroup(
    split(customerManagedKey.?userAssignedIdentityResourceId!, '/')[2],
    split(customerManagedKey.?userAssignedIdentityResourceId!, '/')[4]
  )
}

resource workspace 'Microsoft.MachineLearningServices/workspaces@2024-10-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
    tier: sku
  }
  identity: identity
  properties: {
    friendlyName: friendlyName ?? name
    storageAccount: associatedStorageAccountResourceId
    keyVault: associatedKeyVaultResourceId
    applicationInsights: associatedApplicationInsightsResourceId
    containerRegistry: associatedContainerRegistryResourceId
    hbiWorkspace: hbiWorkspace
    description: description
    discoveryUrl: discoveryUrl
    encryption: !empty(customerManagedKey)
      ? {
          status: 'Enabled'
          identity: !empty(customerManagedKey.?userAssignedIdentityResourceId)
            ? {
                userAssignedIdentity: cMKUserAssignedIdentity.id
              }
            : null
          keyVaultProperties: {
            keyVaultArmId: cMKKeyVault.id
            keyIdentifier: !empty(customerManagedKey.?keyVersion ?? '')
              ? '${cMKKeyVault::cMKKey!.properties.keyUri}/${customerManagedKey!.keyVersion}'
              : cMKKeyVault::cMKKey!.properties.keyUriWithVersion
          }
        }
      : null
    enableServiceSideCMKEncryption: enableServiceSideCMKEncryption
    imageBuildCompute: imageBuildCompute
    primaryUserAssignedIdentity: primaryUserAssignedIdentity
    systemDatastoresAuthMode: systemDatastoresAuthMode
    publicNetworkAccess: publicNetworkAccess
    ipAllowlist: ipAllowlist
    serviceManagedResourcesSettings: serviceManagedResourcesSettings
    // featureStoreSettings: featureStoreSettings
    hubResourceId: hubResourceId
    // managedNetwork: managedNetworkSettings
    provisionNetworkNow: provisionNetworkNow
    // serverlessComputeSettings: serverlessComputeSettings
    // workspaceHubConfig: workspaceHubConfig
    // Parameters only added if not empty
    ...(!empty(sharedPrivateLinkResources)
      ? {
          sharedPrivateLinkResources: sharedPrivateLinkResources
        }
      : {})
  }
  kind: kind
}

module workspace_connections 'connection/main.bicep' = [
  for connection in (connections ?? []): {
    name: '${workspace.name}-${connection.name}-connection'
    params: {
      machineLearningWorkspaceName: workspace.name
      name: connection.name
      category: connection.category
      expiryTime: connection.?expiryTime
      isSharedToAll: connection.?isSharedToAll
      metadata: connection.?metadata
      sharedUserList: connection.?sharedUserList
      target: connection.target
      value: connection.?value
      connectionProperties: connection.connectionProperties
    }
  }
]

resource workspace_diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = [
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
    scope: workspace
  }
]

module workspace_privateEndpoints 'br/public:avm/res/network/private-endpoint:0.10.1' = [
  for (privateEndpoint, index) in (privateEndpoints ?? []): {
    name: '${uniqueString(deployment().name, location)}-workspace-PrivateEndpoint-${index}'
    scope: resourceGroup(
      split(privateEndpoint.?resourceGroupResourceId ?? resourceGroup().id, '/')[2],
      split(privateEndpoint.?resourceGroupResourceId ?? resourceGroup().id, '/')[4]
    )
    params: {
      name: privateEndpoint.?name ?? 'pep-${last(split(workspace.id, '/'))}-${privateEndpoint.?service ?? 'amlworkspace'}-${index}'
      privateLinkServiceConnections: privateEndpoint.?isManualConnection != true
        ? [
            {
              name: privateEndpoint.?privateLinkServiceConnectionName ?? '${last(split(workspace.id, '/'))}-${privateEndpoint.?service ?? 'amlworkspace'}-${index}'
              properties: {
                privateLinkServiceId: workspace.id
                groupIds: [
                  privateEndpoint.?service ?? 'amlworkspace'
                ]
              }
            }
          ]
        : null
      manualPrivateLinkServiceConnections: privateEndpoint.?isManualConnection == true
        ? [
            {
              name: privateEndpoint.?privateLinkServiceConnectionName ?? '${last(split(workspace.id, '/'))}-${privateEndpoint.?service ?? 'amlworkspace'}-${index}'
              properties: {
                privateLinkServiceId: workspace.id
                groupIds: [
                  privateEndpoint.?service ?? 'amlworkspace'
                ]
                requestMessage: privateEndpoint.?manualConnectionRequestMessage ?? 'Manual approval required.'
              }
            }
          ]
        : null
      subnetResourceId: privateEndpoint.subnetResourceId
      enableTelemetry: enableReferencedModulesTelemetry
      location: privateEndpoint.?location ?? reference(
        split(privateEndpoint.subnetResourceId, '/subnets/')[0],
        '2020-06-01',
        'Full'
      ).location
      lock: privateEndpoint.?lock ?? lock
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

resource workspace_roleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for (roleAssignment, index) in (formattedRoleAssignments ?? []): {
    name: roleAssignment.?name ?? guid(workspace.id, roleAssignment.principalId, roleAssignment.roleDefinitionId)
    properties: {
      roleDefinitionId: roleAssignment.roleDefinitionId
      principalId: roleAssignment.principalId
      description: roleAssignment.?description
      principalType: roleAssignment.?principalType
      condition: roleAssignment.?condition
      conditionVersion: !empty(roleAssignment.?condition) ? (roleAssignment.?conditionVersion ?? '2.0') : null // Must only be set if condtion is set
      delegatedManagedIdentityResourceId: roleAssignment.?delegatedManagedIdentityResourceId
    }
    scope: workspace
  }
]

// ================//
// Outputs         //
// ================//

@sys.description('The resource ID of the machine learning service.')
output resourceId string = workspace.id

@sys.description('The resource group the machine learning service was deployed into.')
output resourceGroupName string = resourceGroup().name

@sys.description('The name of the machine learning service.')
output name string = workspace.name

@sys.description('The principal ID of the system assigned identity.')
output systemAssignedMIPrincipalId string? = workspace.?identity.?principalId

@sys.description('The location the resource was deployed into.')
output location string = workspace.location

// =============== //
//   Definitions   //
// =============== //

// @export()
// @sys.description('The type for the private endpoint output.')
// type privateEndpointOutputType = {
//   @sys.description('The name of the private endpoint.')
//   name: string

//   @sys.description('The resource ID of the private endpoint.')
//   resourceId: string

//   @sys.description('The group Id for the private endpoint Group.')
//   groupId: string?

//   @sys.description('The custom DNS configurations of the private endpoint.')
//   customDnsConfigs: {
//     @sys.description('FQDN that resolves to private endpoint IP address.')
//     fqdn: string?

//     @sys.description('A list of private IP addresses of the private endpoint.')
//     ipAddresses: string[]
//   }[]

//   @sys.description('The IDs of the network interfaces associated with the private endpoint.')
//   networkInterfaceResourceIds: string[]
// }

// @export()
// @sys.description('The type for the feature store setting.')
// type featureStoreSettingType = {
//   @sys.description('Optional. Compute runtime config for feature store type workspace.')
//   computeRuntime: {
//     @sys.description('Optional. The spark runtime version.')
//     sparkRuntimeVersion: string?
//   }?

//   @sys.description('Optional. The offline store connection name.')
//   offlineStoreConnectionName: string?

//   @sys.description('Optional. The online store connection name.')
//   onlineStoreConnectionName: string?
// }

// @export()
// @discriminator('type')
// @sys.description('The type for the outbound rule.')
// type outboundRuleType = fqdnoutboundRuleType | privateEndpointoutboundRuleType | serviceTagoutboundRuleType

// @export()
// @sys.description('The type for the FQDN outbound rule.')
// type fqdnoutboundRuleType = {
//   @sys.description('Required. Type of a managed network Outbound Rule of a machine learning workspace. Only supported when \'isolationMode\' is \'AllowOnlyApprovedOutbound\'.')
//   type: 'FQDN'

//   @sys.description('Required. Fully Qualified Domain Name to allow for outbound traffic.')
//   destination: string

//   @sys.description('Optional. Category of a managed network Outbound Rule of a machine learning workspace.')
//   category: 'Dependency' | 'Recommended' | 'Required' | 'UserDefined'?
// }

// @export()
// @sys.description('The type for the private endpoint outbound rule.')
// type privateEndpointoutboundRuleType = {
//   @sys.description('Required. Type of a managed network Outbound Rule of a machine learning workspace. Only supported when \'isolationMode\' is \'AllowOnlyApprovedOutbound\' or \'AllowInternetOutbound\'.')
//   type: 'PrivateEndpoint'

//   @sys.description('Required. Service Tag destination for a Service Tag Outbound Rule for the managed network of a machine learning workspace.')
//   destination: {
//     @sys.description('Required. The resource ID of the target resource for the private endpoint.')
//     serviceResourceId: string

//     @sys.description('Optional. Whether the private endpoint can be used by jobs running on Spark.')
//     sparkEnabled: bool?

//     @sys.description('Required. The sub resource to connect for the private endpoint.')
//     subresourceTarget: string
//   }

//   @sys.description('Optional. Category of a managed network Outbound Rule of a machine learning workspace.')
//   category: 'Dependency' | 'Recommended' | 'Required' | 'UserDefined'?
// }

// @export()
// @sys.description('The type for the service tag outbound rule.')
// type serviceTagoutboundRuleType = {
//   @sys.description('Required. Type of a managed network Outbound Rule of a machine learning workspace. Only supported when \'isolationMode\' is \'AllowOnlyApprovedOutbound\'.')
//   type: 'ServiceTag'

//   @sys.description('Required. Service Tag destination for a Service Tag Outbound Rule for the managed network of a machine learning workspace.')
//   destination: {
//     @sys.description('Required. The name of the service tag to allow.')
//     portRanges: string

//     @sys.description('Required. The protocol to allow. Provide an asterisk(*) to allow any protocol.')
//     protocol: 'TCP' | 'UDP' | 'ICMP' | '*'

//     @sys.description('Required. Which ports will be allow traffic by this rule. Provide an asterisk(*) to allow any port.')
//     serviceTag: string
//   }

//   @sys.description('Optional. Category of a managed network Outbound Rule of a machine learning workspace.')
//   category: 'Dependency' | 'Recommended' | 'Required' | 'UserDefined'?
// }

// @export()
// @sys.description('The type for the managed network setting.')
// type managedNetworkSettingType = {
//   @sys.description('Required. Isolation mode for the managed network of a machine learning workspace.')
//   isolationMode: 'AllowInternetOutbound' | 'AllowOnlyApprovedOutbound' | 'Disabled'

//   @sys.description('Optional. Outbound rules for the managed network of a machine learning workspace.')
//   outboundRules: {
//     @sys.description('Required. The outbound rule. The name of the rule is the object key.')
//     *: outboundRuleType
//   }?

//   @sys.description('Optional. The firewall SKU used for FQDN rules.')
//   firewallSku: 'Basic' | 'Standard'?
// }

// @export()
// @sys.description('The type for the serverless compute setting.')
// type serverlessComputeSettingType = {
//   @sys.description('Optional. The resource ID of an existing virtual network subnet in which serverless compute nodes should be deployed.')
//   serverlessComputeCustomSubnet: string?

//   @sys.description('Optional. The flag to signal if serverless compute nodes deployed in custom vNet would have no public IP addresses for a workspace with private endpoint.')
//   serverlessComputeNoPublicIP: bool?
// }

// @export()
// @sys.description('The type for the workspace hub configuration.')
// type workspaceHubConfigType = {
//   @sys.description('Optional. The resource IDs of additional storage accounts to attach to the workspace.')
//   additionalWorkspaceStorageAccounts: string[]?

//   @sys.description('Optional. The resource ID of the default resource group for projects created in the workspace hub.')
//   defaultWorkspaceResourceGroup: string?
// }

import { categoryType, connectionPropertyType } from 'connection/main.bicep'

@export()
@sys.description('The type for the workspace connection.')
type connectionType = {
  @sys.description('Required. Name of the connection to create.')
  name: string

  @sys.description('Required. Category of the connection.')
  category: categoryType

  @sys.description('Optional. The expiry time of the connection.')
  expiryTime: string?

  @sys.description('Optional. Indicates whether the connection is shared to all users in the workspace.')
  isSharedToAll: bool?

  @sys.description('Optional. User metadata for the connection.')
  metadata: {
    @sys.description('Required. The metadata key-value pairs.')
    *: string
  }?

  @sys.description('Optional. The shared user list of the connection.')
  sharedUserList: string[]?

  @sys.description('Required. The target of the connection.')
  target: string

  @sys.description('Optional. Value details of the workspace connection.')
  value: string?

  @sys.description('Required. The properties of the connection, specific to the auth type.')
  connectionProperties: connectionPropertyType
}

// @export()
// @sys.description('The type for the workspace connection.')
// type datastoreType = {
//   @sys.description('Required. Name of the datastore to create.')
//   name: string

//   @sys.description('Required. The properties of the datastore.')
//   properties: resourceInput<'Microsoft.MachineLearningServices/workspaces/datastores@2024-10-01'>.properties
// }
