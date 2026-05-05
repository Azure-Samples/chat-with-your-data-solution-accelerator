metadata name = 'Storage Accounts'
metadata description = 'This module deploys a Storage Account.'

@maxLength(24)
@description('Required. Name of the Storage Account. Must be lower-case.')
param name string

@description('Optional. Location for all resources.')
param location string = resourceGroup().location

import { roleAssignmentType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. Array of role assignments to create.')
param roleAssignments roleAssignmentType[]?

import { managedIdentityAllType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. The managed identity definition for this resource.')
param managedIdentities managedIdentityAllType?

@allowed([
  'Storage'
  'StorageV2'
  'BlobStorage'
  'FileStorage'
  'BlockBlobStorage'
])
@description('Optional. Type of Storage Account to create.')
param kind string = 'StorageV2'

@allowed([
  'Standard_LRS'
  'Standard_ZRS'
  'Standard_GRS'
  'Standard_GZRS'
  'Standard_RAGRS'
  'Standard_RAGZRS'
  'StandardV2_LRS'
  'StandardV2_ZRS'
  'StandardV2_GRS'
  'StandardV2_GZRS'
  'Premium_LRS'
  'Premium_ZRS'
  'PremiumV2_LRS'
  'PremiumV2_ZRS'
])
@description('Optional. Storage Account Sku Name - note: certain V2 SKUs require the use of: kind = FileStorage.')
param skuName string = 'Standard_GRS'

@allowed([
  'Premium'
  'Hot'
  'Cool'
  'Cold'
])
@description('Conditional. Required if the Storage Account kind is set to BlobStorage. The access tier is used for billing. The "Premium" access tier is the default value for premium block blobs storage account type and it cannot be changed for the premium block blobs storage account type.')
param accessTier string = 'Hot'

@allowed([
  'Disabled'
  'Enabled'
])
@description('Optional. Allow large file shares if set to \'Enabled\'. It cannot be disabled once it is enabled. Only supported on locally redundant and zone redundant file shares. It cannot be set on FileStorage storage accounts (storage accounts for premium file shares).')
param largeFileSharesState string = 'Disabled'

@description('Optional. Provides the identity based authentication settings for Azure Files.')
param azureFilesIdentityBasedAuthentication resourceInput<'Microsoft.Storage/storageAccounts@2024-01-01'>.properties.azureFilesIdentityBasedAuthentication?

@description('Optional. A boolean flag which indicates whether the default authentication is OAuth or not.')
param defaultToOAuthAuthentication bool = false

@description('Optional. Indicates whether the storage account permits requests to be authorized with the account access key via Shared Key. If false, then all requests, including shared access signatures, must be authorized with Azure Active Directory (Azure AD). The default value is null, which is equivalent to true.')
param allowSharedKeyAccess bool = true

import { privateEndpointMultiServiceType } from 'br/public:avm/utl/types/avm-common-types:0.6.1'
@description('Optional. Configuration details for private endpoints. For security reasons, it is recommended to use private endpoints whenever possible.')
param privateEndpoints privateEndpointMultiServiceType[]?

@description('Optional. Networks ACLs, this value contains IPs to whitelist and/or Subnet information. If in use, bypass needs to be supplied. For security reasons, it is recommended to set the DefaultAction Deny.')
param networkAcls networkAclsType?

@description('Optional. A Boolean indicating whether or not the service applies a secondary layer of encryption with platform managed keys for data at rest. For security reasons, it is recommended to set it to true.')
param requireInfrastructureEncryption bool = true

@description('Optional. Allow or disallow cross AAD tenant object replication.')
param allowCrossTenantReplication bool = false

@description('Optional. Sets the custom domain name assigned to the storage account. Name is the CNAME source.')
param customDomainName string = ''

@description('Optional. Indicates whether indirect CName validation is enabled. This should only be set on updates.')
param customDomainUseSubDomainName bool = false

@description('Optional. Allows you to specify the type of endpoint. Set this to AzureDNSZone to create a large number of accounts in a single subscription, which creates accounts in an Azure DNS Zone and the endpoint URL will have an alphanumeric DNS Zone identifier.')
@allowed([
  'AzureDnsZone'
  'Standard'
])
param dnsEndpointType string?

@description('Optional. Blob service and containers to deploy.')
param blobServices object = kind != 'FileStorage'
  ? {
      containerDeleteRetentionPolicyEnabled: true
      containerDeleteRetentionPolicyDays: 7
      deleteRetentionPolicyEnabled: true
      deleteRetentionPolicyDays: 6
    }
  : {}

@description('Optional. Queue service and queues to create.')
param queueServices object = {}

@description('Optional. Indicates whether public access is enabled for all blobs or containers in the storage account. For security reasons, it is recommended to set it to false.')
param allowBlobPublicAccess bool = false

@allowed([
  'TLS1_2'
])
@description('Optional. Set the minimum TLS version on request to storage. The TLS versions 1.0 and 1.1 are deprecated and not supported anymore.')
param minimumTlsVersion string = 'TLS1_2'

@description('Conditional. If true, enables Hierarchical Namespace for the storage account. Required if enableSftp or enableNfsV3 is set to true.')
param enableHierarchicalNamespace bool?

@description('Optional. If true, enables Secure File Transfer Protocol for the storage account. Requires enableHierarchicalNamespace to be true.')
param enableSftp bool = false

@description('Optional. Enables local users feature, if set to true.')
param isLocalUserEnabled bool = false

@description('Optional. If true, enables NFS 3.0 support for the storage account. Requires enableHierarchicalNamespace to be true.')
param enableNfsV3 bool = false

import { diagnosticSettingMetricsOnlyType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. The diagnostic settings of the service.')
param diagnosticSettings diagnosticSettingMetricsOnlyType[]?

import { lockType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. The lock settings of the service.')
param lock lockType?

@description('Optional. Tags of the resource.')
param tags resourceInput<'Microsoft.Storage/storageAccounts@2024-01-01'>.tags?

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Optional. Restrict copy to and from Storage Accounts within an AAD tenant or with Private Links to the same VNet.')
@allowed([
  'AAD'
  'PrivateLink'
])
param allowedCopyScope string?

@description('Optional. Whether or not public network access is allowed for this resource. For security reasons it should be disabled. If not specified, it will be disabled by default if private endpoints are set and networkAcls are not set.')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string?

@description('Optional. Allows HTTPS traffic only to storage service if sets to true.')
param supportsHttpsTrafficOnly bool = true

import { customerManagedKeyWithAutoRotateType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. The customer managed key definition.')
param customerManagedKey customerManagedKeyWithAutoRotateType?

@description('Optional. The SAS expiration period. DD.HH:MM:SS.')
param sasExpirationPeriod string = ''

@description('Optional. The SAS expiration action. Allowed values are Block and Log.')
@allowed(['Block', 'Log'])
param sasExpirationAction string = 'Log'

@description('Optional. The keyType to use with Queue & Table services.')
@allowed([
  'Account'
  'Service'
])
param keyType string?

var enableReferencedModulesTelemetry = false

var supportsBlobService = kind == 'BlockBlobStorage' || kind == 'BlobStorage' || kind == 'StorageV2' || kind == 'Storage'
var supportsFileService = kind == 'FileStorage' || kind == 'StorageV2' || kind == 'Storage'

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

var builtInRoleNames = {
  Contributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
  Owner: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8e3af657-a8ff-443c-a75c-2fe8c4bcb635')
  Reader: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'acdd72a7-3385-48ef-bd42-f606fba81ae7')
  'Reader and Data Access': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'c12c1c16-33a1-487b-954d-41c89c60f349'
  )
  'Role Based Access Control Administrator': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'f58310d9-a9f6-439a-9e8d-f62e7b41a168'
  )
  'Storage Account Backup Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'e5e2a7ff-d759-4cd2-bb51-3152d37e2eb1'
  )
  'Storage Account Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '17d1049b-9a84-46fb-8f53-869881c3d3ab'
  )
  'Storage Account Key Operator Service Role': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '81a9662b-bebf-436f-a333-f67b29880f12'
  )
  'Storage Blob Data Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  )
  'Storage Blob Data Owner': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  )
  'Storage Blob Data Reader': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
  )
  'Storage Blob Delegator': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'db58b8e5-c6ad-4a2a-8342-4190687cbf4a'
  )
  'Storage File Data Privileged Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '69566ab7-960f-475b-8e7c-b3118f30c6bd'
  )
  'Storage File Data Privileged Reader': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'b8eda974-7b85-4f76-af95-65846b26df6d'
  )
  'Storage File Data SMB Share Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '0c867c2a-1d8c-454a-a3db-ab2ea1bdc8bb'
  )
  'Storage File Data SMB Share Elevated Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'a7264617-510b-434b-a828-9731dc254ea7'
  )
  'Storage File Data SMB Share Reader': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'aba4ae5f-2193-4029-9191-0cb91df5e314'
  )
  'Storage Queue Data Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  )
  'Storage Queue Data Message Processor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '8a0f0c08-91a1-4084-bc3d-661d67233fed'
  )
  'Storage Queue Data Message Sender': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a'
  )
  'Storage Queue Data Reader': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '19e7f393-937e-4f77-808e-94535e297925'
  )
  'Storage Table Data Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
  )
  'Storage Table Data Reader': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '76199698-9eea-4c19-bc75-cec21354c6b6'
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
  name: '46d3xbcp.res.storage-storageaccount.${replace('-..--..-', '.', '-')}.${substring(uniqueString(deployment().name, location), 0, 4)}'
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
  name: last(split((customerManagedKey.?keyVaultResourceId!), '/'))
  scope: resourceGroup(
    split(customerManagedKey.?keyVaultResourceId!, '/')[2],
    split(customerManagedKey.?keyVaultResourceId!, '/')[4]
  )

  resource cMKKey 'keys@2024-11-01' existing = if (!empty(customerManagedKey.?keyVaultResourceId) && !empty(customerManagedKey.?keyName)) {
    name: customerManagedKey.?keyName!
  }
}

resource cMKUserAssignedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' existing = if (!empty(customerManagedKey.?userAssignedIdentityResourceId)) {
  name: last(split(customerManagedKey.?userAssignedIdentityResourceId!, '/'))
  scope: resourceGroup(
    split(customerManagedKey.?userAssignedIdentityResourceId!, '/')[2],
    split(customerManagedKey.?userAssignedIdentityResourceId!, '/')[4]
  )
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: name
  location: location
  kind: kind
  sku: {
    name: skuName
  }
  identity: identity
  tags: tags
  properties: {
    allowSharedKeyAccess: allowSharedKeyAccess
    defaultToOAuthAuthentication: defaultToOAuthAuthentication
    allowCrossTenantReplication: allowCrossTenantReplication
    allowedCopyScope: allowedCopyScope
    customDomain: {
      name: customDomainName
      useSubDomainName: customDomainUseSubDomainName
    }
    dnsEndpointType: dnsEndpointType
    isLocalUserEnabled: isLocalUserEnabled
    encryption: union(
      {
        keySource: !empty(customerManagedKey) ? 'Microsoft.Keyvault' : 'Microsoft.Storage'
        services: {
          blob: supportsBlobService
            ? {
                enabled: true
              }
            : null
          file: supportsFileService
            ? {
                enabled: true
              }
            : null
          table: {
            enabled: true
            keyType: keyType
          }
          queue: {
            enabled: true
            keyType: keyType
          }
        }
        keyvaultproperties: !empty(customerManagedKey)
          ? {
              keyname: customerManagedKey!.keyName
              keyvaulturi: cMKKeyVault!.properties.vaultUri
              keyversion: !empty(customerManagedKey.?keyVersion)
                ? customerManagedKey!.keyVersion!
                : (customerManagedKey.?autoRotationEnabled ?? true)
                    ? null
                    : last(split(cMKKeyVault::cMKKey!.properties.keyUriWithVersion, '/'))
            }
          : null
        identity: {
          userAssignedIdentity: !empty(customerManagedKey.?userAssignedIdentityResourceId)
            ? cMKUserAssignedIdentity.id
            : null
        }
      },
      (requireInfrastructureEncryption
        ? {
            requireInfrastructureEncryption: kind != 'Storage' ? requireInfrastructureEncryption : null
          }
        : {})
    )
    accessTier: (kind != 'Storage' && kind != 'BlockBlobStorage') ? accessTier : null
    sasPolicy: !empty(sasExpirationPeriod)
      ? {
          expirationAction: sasExpirationAction
          sasExpirationPeriod: sasExpirationPeriod
        }
      : null
    supportsHttpsTrafficOnly: supportsHttpsTrafficOnly
    isSftpEnabled: enableSftp
    isNfsV3Enabled: enableNfsV3 ? enableNfsV3 : any('')
    largeFileSharesState: (skuName == 'Standard_LRS') || (skuName == 'Standard_ZRS') ? largeFileSharesState : null
    minimumTlsVersion: minimumTlsVersion
    networkAcls: !empty(networkAcls)
      ? union(
          {
            resourceAccessRules: networkAcls.?resourceAccessRules
            defaultAction: networkAcls.?defaultAction ?? 'Deny'
            virtualNetworkRules: networkAcls.?virtualNetworkRules
            ipRules: networkAcls.?ipRules
          },
          (contains(networkAcls!, 'bypass') ? { bypass: networkAcls.?bypass } : {}) // setting `bypass` to `null`is not supported
        )
      : {
          // New default case that enables the firewall by default
          bypass: 'AzureServices'
          defaultAction: 'Deny'
        }
    allowBlobPublicAccess: allowBlobPublicAccess
    publicNetworkAccess: !empty(publicNetworkAccess)
      ? any(publicNetworkAccess)
      : (!empty(privateEndpoints) && empty(networkAcls) ? 'Disabled' : null)
    ...(!empty(azureFilesIdentityBasedAuthentication)
      ? { azureFilesIdentityBasedAuthentication: azureFilesIdentityBasedAuthentication }
      : {})
    ...(enableHierarchicalNamespace != null ? { isHnsEnabled: enableHierarchicalNamespace } : {})
  }
}

resource storageAccount_diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = [
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
      marketplacePartnerId: diagnosticSetting.?marketplacePartnerResourceId
      logAnalyticsDestinationType: diagnosticSetting.?logAnalyticsDestinationType
    }
    scope: storageAccount
  }
]

resource storageAccount_roleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for (roleAssignment, index) in (formattedRoleAssignments ?? []): {
    name: roleAssignment.?name ?? guid(storageAccount.id, roleAssignment.principalId, roleAssignment.roleDefinitionId)
    properties: {
      roleDefinitionId: roleAssignment.roleDefinitionId
      principalId: roleAssignment.principalId
      description: roleAssignment.?description
      principalType: roleAssignment.?principalType
      condition: roleAssignment.?condition
      conditionVersion: !empty(roleAssignment.?condition) ? (roleAssignment.?conditionVersion ?? '2.0') : null // Must only be set if condtion is set
      delegatedManagedIdentityResourceId: roleAssignment.?delegatedManagedIdentityResourceId
    }
    scope: storageAccount
  }
]

module storageAccount_privateEndpoints 'br/public:avm/res/network/private-endpoint:0.11.0' = [
  for (privateEndpoint, index) in (privateEndpoints ?? []): {
    name: '${uniqueString(deployment().name, location)}-sa-PrivateEndpoint-${index}'
    scope: resourceGroup(
      split(privateEndpoint.?resourceGroupResourceId ?? resourceGroup().id, '/')[2],
      split(privateEndpoint.?resourceGroupResourceId ?? resourceGroup().id, '/')[4]
    )
    params: {
      name: privateEndpoint.?name ?? 'pep-${last(split(storageAccount.id, '/'))}-${privateEndpoint.service}-${index}'
      privateLinkServiceConnections: privateEndpoint.?isManualConnection != true
        ? [
            {
              name: privateEndpoint.?privateLinkServiceConnectionName ?? '${last(split(storageAccount.id, '/'))}-${privateEndpoint.service}-${index}'
              properties: {
                privateLinkServiceId: storageAccount.id
                groupIds: [
                  privateEndpoint.service
                ]
              }
            }
          ]
        : null
      manualPrivateLinkServiceConnections: privateEndpoint.?isManualConnection == true
        ? [
            {
              name: privateEndpoint.?privateLinkServiceConnectionName ?? '${last(split(storageAccount.id, '/'))}-${privateEndpoint.service}-${index}'
              properties: {
                privateLinkServiceId: storageAccount.id
                groupIds: [
                  privateEndpoint.service
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

// Containers
module storageAccount_blobServices 'blob-service/blob-service.bicep' = if (!empty(blobServices)) {
  name: '${uniqueString(deployment().name, location)}-Storage-BlobServices'
  params: {
    storageAccountName: storageAccount.name
    containers: blobServices.?containers
    automaticSnapshotPolicyEnabled: blobServices.?automaticSnapshotPolicyEnabled
    changeFeedEnabled: blobServices.?changeFeedEnabled
    changeFeedRetentionInDays: blobServices.?changeFeedRetentionInDays
    containerDeleteRetentionPolicyEnabled: blobServices.?containerDeleteRetentionPolicyEnabled
    containerDeleteRetentionPolicyDays: blobServices.?containerDeleteRetentionPolicyDays
    containerDeleteRetentionPolicyAllowPermanentDelete: blobServices.?containerDeleteRetentionPolicyAllowPermanentDelete
    corsRules: blobServices.?corsRules
    defaultServiceVersion: blobServices.?defaultServiceVersion
    deleteRetentionPolicyAllowPermanentDelete: blobServices.?deleteRetentionPolicyAllowPermanentDelete
    deleteRetentionPolicyEnabled: blobServices.?deleteRetentionPolicyEnabled
    deleteRetentionPolicyDays: blobServices.?deleteRetentionPolicyDays
    isVersioningEnabled: blobServices.?isVersioningEnabled
    lastAccessTimeTrackingPolicyEnabled: blobServices.?lastAccessTimeTrackingPolicyEnabled
    restorePolicyEnabled: blobServices.?restorePolicyEnabled
    restorePolicyDays: blobServices.?restorePolicyDays
    diagnosticSettings: blobServices.?diagnosticSettings
  }
}

// Queue
module storageAccount_queueServices 'queue-service/queue-service.bicep' = if (!empty(queueServices)) {
  name: '${uniqueString(deployment().name, location)}-Storage-QueueServices'
  params: {
    storageAccountName: storageAccount.name
    diagnosticSettings: queueServices.?diagnosticSettings
    queues: queueServices.?queues
    corsRules: queueServices.?corsRules
  }
}

@description('The resource ID of the deployed storage account.')
output resourceId string = storageAccount.id

@description('The name of the deployed storage account.')
output name string = storageAccount.name

@description('All service endpoints of the deployed storage account, Note Standard_LRS and Standard_ZRS accounts only have a blob service endpoint.')
output serviceEndpoints object = storageAccount.properties.primaryEndpoints

// =============== //
//   Definitions   //
// =============== //

@export()
@description('The type for the network configuration.')
type networkAclsType = {
  @description('Optional. Sets the resource access rules. Array entries must consist of "tenantId" and "resourceId" fields only.')
  resourceAccessRules: {
    @description('Required. The ID of the tenant in which the resource resides in.')
    tenantId: string

    @description('Required. The resource ID of the target service. Can also contain a wildcard, if multiple services e.g. in a resource group should be included.')
    resourceId: string
  }[]?

  @description('Optional. Specifies whether traffic is bypassed for Logging/Metrics/AzureServices. Possible values are any combination of Logging,Metrics,AzureServices (For example, "Logging, Metrics"), or None to bypass none of those traffics.')
  bypass: (
    | 'None'
    | 'AzureServices'
    | 'Logging'
    | 'Metrics'
    | 'AzureServices, Logging'
    | 'AzureServices, Metrics'
    | 'AzureServices, Logging, Metrics'
    | 'Logging, Metrics')?

  @description('Optional. Sets the virtual network rules.')
  virtualNetworkRules: array?

  @description('Optional. Sets the IP ACL rules.')
  ipRules: array?

  @description('Optional. Specifies the default action of allow or deny when no other rules match.')
  defaultAction: ('Allow' | 'Deny')?
}
