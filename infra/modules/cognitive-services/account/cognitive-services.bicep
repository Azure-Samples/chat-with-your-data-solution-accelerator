metadata name = 'Cognitive Services'
metadata description = 'This module deploys a Cognitive Service.'

@description('Required. The name of Cognitive Services account.')
param name string

@description('Required. Kind of the Cognitive Services account. Use \'Get-AzCognitiveServicesAccountSku\' to determine a valid combinations of \'kind\' and \'SKU\' for your Azure region.')
@allowed([
  'AIServices'
  'AnomalyDetector'
  'CognitiveServices'
  'ComputerVision'
  'ContentModerator'
  'ContentSafety'
  'ConversationalLanguageUnderstanding'
  'CustomVision.Prediction'
  'CustomVision.Training'
  'Face'
  'FormRecognizer'
  'HealthInsights'
  'ImmersiveReader'
  'Internal.AllInOne'
  'LUIS'
  'LUIS.Authoring'
  'LanguageAuthoring'
  'MetricsAdvisor'
  'OpenAI'
  'Personalizer'
  'QnAMaker.v2'
  'SpeechServices'
  'TextAnalytics'
  'TextTranslation'
])
param kind string

@description('Optional. SKU of the Cognitive Services account. Use \'Get-AzCognitiveServicesAccountSku\' to determine a valid combinations of \'kind\' and \'SKU\' for your Azure region.')
@allowed([
  'C2'
  'C3'
  'C4'
  'F0'
  'F1'
  'S'
  'S0'
  'S1'
  'S10'
  'S2'
  'S3'
  'S4'
  'S5'
  'S6'
  'S7'
  'S8'
  'S9'
  'DC0'
])
param sku string = 'S0'

@description('Optional. Location for all Resources.')
param location string = resourceGroup().location

import { diagnosticSettingFullType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. The diagnostic settings of the service.')
param diagnosticSettings diagnosticSettingFullType[]?

@description('Optional. Whether or not public network access is allowed for this resource. For security reasons it should be disabled. If not specified, it will be disabled by default if private endpoints are set and networkAcls are not set.')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string?

@description('Conditional. Subdomain name used for token-based authentication. Required if \'networkAcls\' or \'privateEndpoints\' are set.')
param customSubDomainName string?

@description('Optional. A collection of rules governing the accessibility from specific network locations.')
param networkAcls object?

@description('Optional. Specifies in AI Foundry where virtual network injection occurs to secure scenarios like Agents entirely within a private network.')
param networkInjections networkInjectionType?

import { privateEndpointSingleServiceType } from 'br/public:avm/utl/types/avm-common-types:0.6.1'
@description('Optional. Configuration details for private endpoints. For security reasons, it is recommended to use private endpoints whenever possible.')
param privateEndpoints privateEndpointSingleServiceType[]?

import { lockType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. The lock settings of the service.')
param lock lockType?

import { roleAssignmentType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. Array of role assignments to create.')
param roleAssignments roleAssignmentType[]?

@description('Optional. Tags of the resource.')
param tags object?

@description('Optional. List of allowed FQDN.')
param allowedFqdnList array?

@description('Optional. The API properties for special APIs.')
param apiProperties object?

@description('Optional. Allow only Azure AD authentication. Should be enabled for security reasons.')
param disableLocalAuth bool = true

import { customerManagedKeyType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. The customer managed key definition.')
param customerManagedKey customerManagedKeyType?

@description('Optional. The flag to enable dynamic throttling.')
param dynamicThrottlingEnabled bool = false

@secure()
@description('Optional. Resource migration token.')
param migrationToken string?

@description('Optional. Restore a soft-deleted cognitive service at deployment time. Will fail if no such soft-deleted resource exists.')
param restore bool = false

@description('Optional. Restrict outbound network access.')
param restrictOutboundNetworkAccess bool = true

@description('Optional. The storage accounts for this resource.')
param userOwnedStorage resourceInput<'Microsoft.CognitiveServices/accounts@2025-04-01-preview'>.properties.userOwnedStorage?

import { managedIdentityAllType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. The managed identity definition for this resource.')
param managedIdentities managedIdentityAllType?

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Optional. Array of deployments about cognitive service accounts to create.')
param deployments deploymentType[]?

@description('Optional. Enable/Disable project management feature for AI Foundry.')
param allowProjectManagement bool?

@description('Optional. Commitment plans to deploy for the cognitive services account.')
param commitmentPlans commitmentPlanType[]?

var enableReferencedModulesTelemetry = false

var formattedUserAssignedIdentities = reduce(
  map((managedIdentities.?userAssignedResourceIds ?? []), (id) => { '${id}': {} }),
  {},
  (cur, next) => union(cur, next)
) // Converts the flat array to an object like { '${id1}': {}, '${id2}': {} }
var identity = !empty(managedIdentities)
  ? {
      type: (managedIdentities.?systemAssigned ?? false)
        ? (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'SystemAssigned, UserAssigned' : 'SystemAssigned')
        : (!empty(managedIdentities.?userAssignedResourceIds ?? {}) ? 'UserAssigned' : null)
      userAssignedIdentities: !empty(formattedUserAssignedIdentities) ? formattedUserAssignedIdentities : null
    }
  : null

var builtInRoleNames = {
  'Cognitive Services Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68'
  )
  'Cognitive Services Custom Vision Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'c1ff6cc2-c111-46fe-8896-e0ef812ad9f3'
  )
  'Cognitive Services Custom Vision Deployment': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '5c4089e1-6d96-4d2f-b296-c1bc7137275f'
  )
  'Cognitive Services Custom Vision Labeler': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '88424f51-ebe7-446f-bc41-7fa16989e96c'
  )
  'Cognitive Services Custom Vision Reader': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '93586559-c37d-4a6b-ba08-b9f0940c2d73'
  )
  'Cognitive Services Custom Vision Trainer': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '0a5ae4ab-0d65-4eeb-be61-29fc9b54394b'
  )
  'Cognitive Services Data Reader (Preview)': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'b59867f0-fa02-499b-be73-45a86b5b3e1c'
  )
  'Cognitive Services Face Recognizer': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '9894cab4-e18a-44aa-828b-cb588cd6f2d7'
  )
  'Cognitive Services Immersive Reader User': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'b2de6794-95db-4659-8781-7e080d3f2b9d'
  )
  'Cognitive Services Language Owner': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'f07febfe-79bc-46b1-8b37-790e26e6e498'
  )
  'Cognitive Services Language Reader': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '7628b7b8-a8b2-4cdc-b46f-e9b35248918e'
  )
  'Cognitive Services Language Writer': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'f2310ca1-dc64-4889-bb49-c8e0fa3d47a8'
  )
  'Cognitive Services LUIS Owner': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'f72c8140-2111-481c-87ff-72b910f6e3f8'
  )
  'Cognitive Services LUIS Reader': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '18e81cdc-4e98-4e29-a639-e7d10c5a6226'
  )
  'Cognitive Services LUIS Writer': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '6322a993-d5c9-4bed-b113-e49bbea25b27'
  )
  'Cognitive Services Metrics Advisor Administrator': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'cb43c632-a144-4ec5-977c-e80c4affc34a'
  )
  'Cognitive Services Metrics Advisor User': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '3b20f47b-3825-43cb-8114-4bd2201156a8'
  )
  'Cognitive Services OpenAI Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'a001fd3d-188f-4b5d-821b-7da978bf7442'
  )
  'Cognitive Services OpenAI User': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  )
  'Cognitive Services QnA Maker Editor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'f4cc2bf9-21be-47a1-bdf1-5c5804381025'
  )
  'Cognitive Services QnA Maker Reader': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '466ccd10-b268-4a11-b098-b4849f024126'
  )
  'Cognitive Services Speech Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '0e75ca1e-0464-4b4d-8b93-68208a576181'
  )
  'Cognitive Services Speech User': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'f2dc8367-1007-4938-bd23-fe263f013447'
  )
  'Cognitive Services User': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'a97b65f3-24c7-4388-baec-2e87135dc908'
  )
  'Azure AI Developer': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '64702f94-c441-49e6-a78b-ef80e0188fee'
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
  name: '46d3xbcp.res.cognitiveservices-account.${replace('-..--..-', '.', '-')}.${substring(uniqueString(deployment().name, location), 0, 4)}'
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

resource cMKKeyVault 'Microsoft.KeyVault/vaults@2024-11-01' existing = if (!empty(customerManagedKey.?keyVaultResourceId)) {
  name: last(split(customerManagedKey.?keyVaultResourceId!, '/'))
  scope: resourceGroup(
    split(customerManagedKey.?keyVaultResourceId!, '/')[2],
    split(customerManagedKey.?keyVaultResourceId!, '/')[4]
  )

  resource cMKKey 'keys@2024-11-01' existing = if (!empty(customerManagedKey.?keyVaultResourceId) && !empty(customerManagedKey.?keyName)) {
    name: customerManagedKey.?keyName!
  }
}

resource cMKUserAssignedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2025-01-31-preview' existing = if (!empty(customerManagedKey.?userAssignedIdentityResourceId)) {
  name: last(split(customerManagedKey.?userAssignedIdentityResourceId!, '/'))
  scope: resourceGroup(
    split(customerManagedKey.?userAssignedIdentityResourceId!, '/')[2],
    split(customerManagedKey.?userAssignedIdentityResourceId!, '/')[4]
  )
}

resource cognitiveService 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: name
  kind: kind
  identity: identity
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    allowProjectManagement: allowProjectManagement // allows project management for Cognitive Services accounts in AI Foundry - FDP updates
    customSubDomainName: customSubDomainName
    networkAcls: !empty(networkAcls ?? {})
      ? {
          defaultAction: networkAcls.?defaultAction
          virtualNetworkRules: networkAcls.?virtualNetworkRules ?? []
          ipRules: networkAcls.?ipRules ?? []
          bypass: networkAcls.?bypass ?? null
        }
      : null
    #disable-next-line BCP036
    networkInjections: !empty(networkInjections)
      ? [
          {
            scenario: networkInjections.?scenario
            subnetArmId: networkInjections.?subnetResourceId
            useMicrosoftManagedNetwork: networkInjections.?useMicrosoftManagedNetwork ?? false
          }
        ]
      : null
    publicNetworkAccess: publicNetworkAccess != null
      ? publicNetworkAccess
      : (!empty(networkAcls) ? 'Enabled' : 'Disabled')
    allowedFqdnList: allowedFqdnList
    apiProperties: apiProperties
    disableLocalAuth: disableLocalAuth
    encryption: !empty(customerManagedKey)
      ? {
          keySource: 'Microsoft.KeyVault'
          keyVaultProperties: {
            identityClientId: !empty(customerManagedKey.?userAssignedIdentityResourceId ?? '')
              ? cMKUserAssignedIdentity!.properties.clientId
              : null
            keyVaultUri: cMKKeyVault!.properties.vaultUri
            keyName: customerManagedKey!.keyName
            keyVersion: !empty(customerManagedKey.?keyVersion ?? '')
              ? customerManagedKey!.?keyVersion
              : last(split(cMKKeyVault::cMKKey!.properties.keyUriWithVersion, '/'))
          }
        }
      : null
    migrationToken: migrationToken
    restore: restore
    restrictOutboundNetworkAccess: restrictOutboundNetworkAccess
    userOwnedStorage: !empty(userOwnedStorage) ? userOwnedStorage : null // Accounting for [ ] not being a supported value
    dynamicThrottlingEnabled: dynamicThrottlingEnabled
  }
}

@batchSize(1)
resource cognitiveService_deployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [
  for (deployment, index) in (deployments ?? []): {
    parent: cognitiveService
    name: deployment.?name ?? '${name}-deployments'
    properties: {
      model: deployment.model
      raiPolicyName: deployment.?raiPolicyName
      versionUpgradeOption: deployment.?versionUpgradeOption
    }
    sku: deployment.?sku ?? {
      name: sku
      capacity: sku.?capacity
      tier: sku.?tier
      size: sku.?size
      family: sku.?family
    }
  }
]

resource cognitiveService_lock 'Microsoft.Authorization/locks@2020-05-01' = if (!empty(lock ?? {}) && lock.?kind != 'None') {
  name: lock.?name ?? 'lock-${name}'
  properties: {
    level: lock.?kind ?? ''
    notes: lock.?notes ?? (lock.?kind == 'CanNotDelete'
      ? 'Cannot delete resource or child resources.'
      : 'Cannot delete or modify the resource or child resources.')
  }
  scope: cognitiveService
}

resource cognitiveService_commitmentPlans 'Microsoft.CognitiveServices/accounts/commitmentPlans@2025-06-01' = [
  for plan in (commitmentPlans ?? []): {
    parent: cognitiveService
    name: '${plan.hostingModel}-${plan.planType}'
    properties: plan
  }
]

#disable-next-line use-recent-api-versions
resource cognitiveService_diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = [
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
    scope: cognitiveService
  }
]

module cognitiveService_privateEndpoints 'br/public:avm/res/network/private-endpoint:0.11.0' = [
  for (privateEndpoint, index) in (privateEndpoints ?? []): {
    name: '${uniqueString(deployment().name, location)}-cognitiveService-PrivateEndpoint-${index}'
    scope: resourceGroup(
      split(privateEndpoint.?resourceGroupResourceId ?? resourceGroup().id, '/')[2],
      split(privateEndpoint.?resourceGroupResourceId ?? resourceGroup().id, '/')[4]
    )
    params: {
      name: privateEndpoint.?name ?? 'pep-${last(split(cognitiveService.id, '/'))}-${privateEndpoint.?service ?? 'account'}-${index}'
      privateLinkServiceConnections: privateEndpoint.?isManualConnection != true
        ? [
            {
              name: privateEndpoint.?privateLinkServiceConnectionName ?? '${last(split(cognitiveService.id, '/'))}-${privateEndpoint.?service ?? 'account'}-${index}'
              properties: {
                privateLinkServiceId: cognitiveService.id
                groupIds: [
                  privateEndpoint.?service ?? 'account'
                ]
              }
            }
          ]
        : null
      manualPrivateLinkServiceConnections: privateEndpoint.?isManualConnection == true
        ? [
            {
              name: privateEndpoint.?privateLinkServiceConnectionName ?? '${last(split(cognitiveService.id, '/'))}-${privateEndpoint.?service ?? 'account'}-${index}'
              properties: {
                privateLinkServiceId: cognitiveService.id
                groupIds: [
                  privateEndpoint.?service ?? 'account'
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

resource cognitiveService_roleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for (roleAssignment, index) in (formattedRoleAssignments ?? []): {
    name: roleAssignment.?name ?? guid(cognitiveService.id, roleAssignment.principalId, roleAssignment.roleDefinitionId)
    properties: {
      roleDefinitionId: roleAssignment.roleDefinitionId
      principalId: roleAssignment.principalId
      description: roleAssignment.?description
      principalType: roleAssignment.?principalType
      condition: roleAssignment.?condition
      conditionVersion: !empty(roleAssignment.?condition) ? (roleAssignment.?conditionVersion ?? '2.0') : null // Must only be set if condtion is set
      delegatedManagedIdentityResourceId: roleAssignment.?delegatedManagedIdentityResourceId
    }
    scope: cognitiveService
  }
]

@description('The name of the cognitive services account.')
output name string = cognitiveService.name

@description('The resource ID of the cognitive services account.')
output resourceId string = cognitiveService.id

@description('The resource group the cognitive services account was deployed into.')
output resourceGroupName string = resourceGroup().name

@description('The service endpoint of the cognitive services account.')
output endpoint string = cognitiveService.properties.endpoint

@description('All endpoints available for the cognitive services account, types depends on the cognitive service kind.')
output endpoints endpointType = cognitiveService.properties.endpoints

@description('The principal ID of the system assigned identity.')
output systemAssignedMIPrincipalId string? = cognitiveService.?identity.?principalId

@description('The location the resource was deployed into.')
output location string = cognitiveService.location

@description('The private endpoints of the congitive services account.')
output privateEndpoints privateEndpointOutputType[] = [
  for (pe, index) in (privateEndpoints ?? []): {
    name: cognitiveService_privateEndpoints[index].outputs.name
    resourceId: cognitiveService_privateEndpoints[index].outputs.resourceId
    groupId: cognitiveService_privateEndpoints[index].outputs.?groupId!
    customDnsConfigs: cognitiveService_privateEndpoints[index].outputs.customDnsConfigs
    networkInterfaceResourceIds: cognitiveService_privateEndpoints[index].outputs.networkInterfaceResourceIds
  }
]

// ================ //
// Definitions      //
// ================ //

@export()
@description('The type for the private endpoint output.')
type privateEndpointOutputType = {
  @description('The name of the private endpoint.')
  name: string

  @description('The resource ID of the private endpoint.')
  resourceId: string

  @description('The group Id for the private endpoint Group.')
  groupId: string?

  @description('The custom DNS configurations of the private endpoint.')
  customDnsConfigs: {
    @description('FQDN that resolves to private endpoint IP address.')
    fqdn: string?

    @description('A list of private IP addresses of the private endpoint.')
    ipAddresses: string[]
  }[]

  @description('The IDs of the network interfaces associated with the private endpoint.')
  networkInterfaceResourceIds: string[]
}

@export()
@description('The type for a cognitive services account deployment.')
type deploymentType = {
  @description('Optional. Specify the name of cognitive service account deployment.')
  name: string?

  @description('Required. Properties of Cognitive Services account deployment model.')
  model: {
    @description('Required. The name of Cognitive Services account deployment model.')
    name: string

    @description('Required. The format of Cognitive Services account deployment model.')
    format: string

    @description('Optional. The version of Cognitive Services account deployment model.')
    version: string?
  }

  @description('Optional. The resource model definition representing SKU.')
  sku: {
    @description('Required. The name of the resource model definition representing SKU.')
    name: string

    @description('Optional. The capacity of the resource model definition representing SKU.')
    capacity: int?

    @description('Optional. The tier of the resource model definition representing SKU.')
    tier: string?

    @description('Optional. The size of the resource model definition representing SKU.')
    size: string?

    @description('Optional. The family of the resource model definition representing SKU.')
    family: string?
  }?

  @description('Optional. The name of RAI policy.')
  raiPolicyName: string?

  @description('Optional. The version upgrade option.')
  versionUpgradeOption: string?
}

@export()
@description('The type for a cognitive services account endpoint.')
type endpointType = {
  @description('Type of the endpoint.')
  name: string?
  @description('The endpoint URI.')
  endpoint: string?
}

@export()
@description('The type for a disconnected container commitment plan.')
type commitmentPlanType = {
  @description('Required. Whether the plan should auto-renew at the end of the current commitment period.')
  autoRenew: bool

  @description('Required. The current commitment configuration.')
  current: {
    @description('Required. The number of committed instances (e.g., number of containers or cores).')
    count: int

    @description('Required. The tier of the commitment plan (e.g., T1, T2).')
    tier: string
  }

  @description('Required. The hosting model for the commitment plan. (e.g., DisconnectedContainer, ConnectedContainer, ProvisionedWeb, Web).')
  hostingModel: string

  @description('Required. The plan type indicating which capability the plan applies to (e.g., NTTS, STT, CUSTOMSTT, ADDON).')
  planType: string

  @description('Optional. The unique identifier of an existing commitment plan to update. Set to null to create a new plan.')
  commitmentPlanGuid: string?

  @description('Optional. The configuration of the next commitment period, if scheduled.')
  next: {
    @description('Required. The number of committed instances for the next period.')
    count: int

    @description('Required. The tier for the next commitment period.')
    tier: string
  }?
}

@export()
@description('Type for network configuration in AI Foundry where virtual network injection occurs to secure scenarios like Agents entirely within a private network.')
type networkInjectionType = {
  @description('Required. The scenario for the network injection.')
  scenario: 'agent' | 'none'

  @description('Required. The Resource ID of the subnet on the Virtual Network on which to inject.')
  subnetResourceId: string

  @description('Optional. Whether to use Microsoft Managed Network. Defaults to false.')
  useMicrosoftManagedNetwork: bool?
}
