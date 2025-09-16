metadata name = 'Storage Account blob Services'
metadata description = 'This module deploys a Storage Account Blob Service.'

@maxLength(24)
@description('Conditional. The name of the parent Storage Account. Required if the template is used in a standalone deployment.')
param storageAccountName string

@description('Optional. Automatic Snapshot is enabled if set to true.')
param automaticSnapshotPolicyEnabled bool = false

@description('Optional. The blob service properties for change feed events. Indicates whether change feed event logging is enabled for the Blob service.')
param changeFeedEnabled bool = false

@minValue(1)
@maxValue(146000)
@description('Optional. Indicates whether change feed event logging is enabled for the Blob service. Indicates the duration of changeFeed retention in days. If left blank, it indicates an infinite retention of the change feed.')
param changeFeedRetentionInDays int?

@description('Optional. The blob service properties for container soft delete. Indicates whether DeleteRetentionPolicy is enabled.')
param containerDeleteRetentionPolicyEnabled bool = true

@minValue(1)
@maxValue(365)
@description('Optional. Indicates the number of days that the deleted item should be retained.')
param containerDeleteRetentionPolicyDays int?

@description('Optional. This property when set to true allows deletion of the soft deleted blob versions and snapshots. This property cannot be used with blob restore policy. This property only applies to blob service and does not apply to containers or file share.')
param containerDeleteRetentionPolicyAllowPermanentDelete bool = false

@description('Optional. The List of CORS rules. You can include up to five CorsRule elements in the request.')
param corsRules corsRuleType[]?

@description('Optional. Indicates the default version to use for requests to the Blob service if an incoming request\'s version is not specified. Possible values include version 2008-10-27 and all more recent versions.')
param defaultServiceVersion string?

@description('Optional. The blob service properties for blob soft delete.')
param deleteRetentionPolicyEnabled bool = true

@minValue(1)
@maxValue(365)
@description('Optional. Indicates the number of days that the deleted blob should be retained.')
param deleteRetentionPolicyDays int = 7

@description('Optional. This property when set to true allows deletion of the soft deleted blob versions and snapshots. This property cannot be used with blob restore policy. This property only applies to blob service and does not apply to containers or file share.')
param deleteRetentionPolicyAllowPermanentDelete bool = false

@description('Optional. Use versioning to automatically maintain previous versions of your blobs.')
param isVersioningEnabled bool = false

@description('Optional. The blob service property to configure last access time based tracking policy. When set to true last access time based tracking is enabled.')
param lastAccessTimeTrackingPolicyEnabled bool = false

@description('Optional. The blob service properties for blob restore policy. If point-in-time restore is enabled, then versioning, change feed, and blob soft delete must also be enabled.')
param restorePolicyEnabled bool = false

@minValue(1)
@description('Optional. How long this blob can be restored. It should be less than DeleteRetentionPolicy days.')
param restorePolicyDays int = 7

@description('Optional. Blob containers to create.')
param containers array?

import { diagnosticSettingFullType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. The diagnostic settings of the service.')
param diagnosticSettings diagnosticSettingFullType[]?

var enableReferencedModulesTelemetry = false

// The name of the blob services
var name = 'default'

resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' existing = {
  name: storageAccountName
}

resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' = {
  name: name
  parent: storageAccount
  properties: {
    automaticSnapshotPolicyEnabled: automaticSnapshotPolicyEnabled
    changeFeed: changeFeedEnabled
      ? {
          enabled: true
          retentionInDays: changeFeedRetentionInDays
        }
      : null
    containerDeleteRetentionPolicy: {
      enabled: containerDeleteRetentionPolicyEnabled
      days: containerDeleteRetentionPolicyDays
      allowPermanentDelete: containerDeleteRetentionPolicyEnabled == true
        ? containerDeleteRetentionPolicyAllowPermanentDelete
        : null
    }
    cors: corsRules != null
      ? {
          corsRules: corsRules
        }
      : null
    defaultServiceVersion: defaultServiceVersion
    deleteRetentionPolicy: {
      enabled: deleteRetentionPolicyEnabled
      days: deleteRetentionPolicyDays
      allowPermanentDelete: deleteRetentionPolicyEnabled && deleteRetentionPolicyAllowPermanentDelete ? true : null
    }
    isVersioningEnabled: isVersioningEnabled
    lastAccessTimeTrackingPolicy: storageAccount.kind != 'Storage'
      ? {
          enable: lastAccessTimeTrackingPolicyEnabled
          name: lastAccessTimeTrackingPolicyEnabled == true ? 'AccessTimeTracking' : null
          trackingGranularityInDays: lastAccessTimeTrackingPolicyEnabled == true ? 1 : null
        }
      : null
    restorePolicy: restorePolicyEnabled
      ? {
          enabled: true
          days: restorePolicyDays
        }
      : null
  }
}

resource blobServices_diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = [
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
    scope: blobServices
  }
]

module blobServices_container 'container/main.bicep' = [
  for (container, index) in (containers ?? []): {
    name: '${deployment().name}-Container-${index}'
    params: {
      storageAccountName: storageAccount.name
      blobServiceName: blobServices.name
      name: container.name
      defaultEncryptionScope: container.?defaultEncryptionScope
      denyEncryptionScopeOverride: container.?denyEncryptionScopeOverride
      enableNfsV3AllSquash: container.?enableNfsV3AllSquash
      enableNfsV3RootSquash: container.?enableNfsV3RootSquash
      immutableStorageWithVersioningEnabled: container.?immutableStorageWithVersioningEnabled
      metadata: container.?metadata
      publicAccess: container.?publicAcces
      enableTelemetry: enableReferencedModulesTelemetry
    }
  }
]

@description('The name of the deployed blob service.')
output name string = blobServices.name

@description('The resource ID of the deployed blob service.')
output resourceId string = blobServices.id

@description('The name of the deployed blob service.')
output resourceGroupName string = resourceGroup().name

// =============== //
//   Definitions   //
// =============== //

@export()
@description('The type for a cors rule.')
type corsRuleType = {
  @description('Required. A list of headers allowed to be part of the cross-origin request.')
  allowedHeaders: string[]

  @description('Required. A list of HTTP methods that are allowed to be executed by the origin.')
  allowedMethods: ('CONNECT' | 'DELETE' | 'GET' | 'HEAD' | 'MERGE' | 'OPTIONS' | 'PATCH' | 'POST' | 'PUT' | 'TRACE')[]

  @description('Required. A list of origin domains that will be allowed via CORS, or "*" to allow all domains.')
  allowedOrigins: string[]

  @description('Required. A list of response headers to expose to CORS clients.')
  exposedHeaders: string[]

  @description('Required. The number of seconds that the client/browser should cache a preflight response.')
  maxAgeInSeconds: int
}
