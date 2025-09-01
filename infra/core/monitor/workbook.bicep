metadata name = 'workbook'
metadata description = 'AVM WAF-compliant Workbook deployment using Microsoft.Insights resource type. Ensures governance, observability, tagging, and consistency with other monitoring resources.'

// ========== //
// Parameters //
// ========== //

@description('Required. The friendly display name for the workbook. Must be unique within the resource group.')
param workbookDisplayName string

@description('Optional. The gallery category under which the workbook will appear. Supported values: workbook, tsg, etc.')
param workbookType string = 'workbook'

@description('Optional. Resource ID of the source this workbook is associated with. Example: Log Analytics workspace or App Insights instance.')
param workbookSourceId string = 'azure monitor'

@description('Required. Unique GUID for this workbook instance. Acts as the resource name.')
param workbookId string

@description('Required. JSON content of the workbook definition.')
param workbookContents string

@description('Optional. Azure region where the workbook is deployed. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('Optional. Tags to apply to the workbook resource for governance, cost tracking, and compliance.')
param tags object = {}

// ======== //
// Resource //
// ======== //

resource workbook_resource 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: workbookId
  location: location
  kind: 'shared'
  tags: tags
  properties: {
    displayName: workbookDisplayName
    serializedData: workbookContents
    version: '1.0'
    sourceId: workbookSourceId
    category: workbookType
  }
}

// ======= //
// Outputs //
// ======= //

@description('The full resource ID of the deployed workbook.')
output workbookResourceId string = workbook_resource.id
