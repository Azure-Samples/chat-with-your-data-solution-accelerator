param workbookDisplayName string
param location string
param hostingPlanName string
param functionName string
param websiteName string
param adminWebsiteName string
param eventGridSystemTopicName string
param logAnalyticsName string
param azureOpenAIResourceName string
param azureAISearchName string
param storageAccountName string

var wookbookContents = loadTextContent('../workbooks/workbook.json')
var wookbookContentsSubReplaced = replace(wookbookContents, '{subscription-id}', subscription().id)
var wookbookContentsRGReplaced = replace(wookbookContentsSubReplaced, '{resource-group}', resourceGroup().name)
var wookbookContentsAppServicePlanReplaced = replace(wookbookContentsRGReplaced, '{app-service-plan}', hostingPlanName)
var wookbookContentsBackendAppServiceReplaced = replace(wookbookContentsAppServicePlanReplaced, '{backend-app-service}', functionName)
var wookbookContentsWebAppServiceReplaced = replace(wookbookContentsBackendAppServiceReplaced, '{web-app-service}', websiteName)
var wookbookContentsAdminAppServiceReplaced = replace(wookbookContentsWebAppServiceReplaced, '{admin-app-service}', adminWebsiteName)
var wookbookContentsEventGridReplaced = replace(wookbookContentsAdminAppServiceReplaced, '{event-grid}', eventGridSystemTopicName)
var wookbookContentsLogAnalyticsReplaced = replace(wookbookContentsEventGridReplaced, '{log-analytics}', logAnalyticsName)
var wookbookContentsOpenAIReplaced = replace(wookbookContentsLogAnalyticsReplaced, '{open-ai}', azureOpenAIResourceName)
var wookbookContentsAISearchReplaced = replace(wookbookContentsOpenAIReplaced, '{ai-search}', azureAISearchName)
var wookbookContentsStorageAccountReplaced = replace(wookbookContentsAISearchReplaced, '{storage-account}', storageAccountName)

module cwydsa_workbook '../core/monitor/workbook.bicep' = {
  name: workbookDisplayName
  params: {
    workbookId: 'd9bd03af-7ef0-4bac-b91b-b14ee4c7002b'
    workbookDisplayName: workbookDisplayName
    location: location
    workbookContents: wookbookContentsStorageAccountReplaced
  }
}
