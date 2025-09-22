metadata name = 'Storage Account File Share Services'
metadata description = 'This module deploys a Storage Account File Share Service.'

@maxLength(24)
@description('Conditional. The name of the parent Storage Account. Required if the template is used in a standalone deployment.')
param storageAccountName string

@description('Optional. The name of the file service.')
param name string = 'default'

@description('Optional. Protocol settings for file service.')
param protocolSettings resourceInput<'Microsoft.Storage/storageAccounts/fileServices@2024-01-01'>.properties.protocolSettings = {}

@description('Optional. The service properties for soft delete.')
param shareDeleteRetentionPolicy resourceInput<'Microsoft.Storage/storageAccounts/fileServices@2024-01-01'>.properties.shareDeleteRetentionPolicy = {
  enabled: true
  days: 7
}

@description('Optional. The List of CORS rules. You can include up to five CorsRule elements in the request.')
param corsRules corsRuleType[]?

import { diagnosticSettingFullType } from 'br/public:avm/utl/types/avm-common-types:0.6.0'
@description('Optional. The diagnostic settings of the service.')
param diagnosticSettings diagnosticSettingFullType[]?

resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' existing = {
  name: storageAccountName
}

resource fileServices 'Microsoft.Storage/storageAccounts/fileServices@2024-01-01' = {
  name: name
  parent: storageAccount
  properties: {
    cors: corsRules != null
      ? {
          corsRules: corsRules
        }
      : null
    protocolSettings: protocolSettings
    shareDeleteRetentionPolicy: shareDeleteRetentionPolicy
  }
}

resource fileServices_diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = [
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
    scope: fileServices
  }
]

@description('The name of the deployed file share service.')
output name string = fileServices.name

@description('The resource ID of the deployed file share service.')
output resourceId string = fileServices.id

@description('The resource group of the deployed file share service.')
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
