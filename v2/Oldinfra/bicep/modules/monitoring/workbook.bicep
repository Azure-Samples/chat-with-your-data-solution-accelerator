// ============================================================================
// Module: Azure Workbook
// Description: Deploys an Azure Monitor Workbook
// Resource: Microsoft.Insights/workbooks@2023-06-01
// Docs: https://learn.microsoft.com/azure/templates/microsoft.insights/workbooks
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Unique ID (GUID) for the workbook resource.')
param name string = guid(resourceGroup().id, solutionName, 'workbook')

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Display name for the workbook.')
param displayName string = 'workbook-${solutionName}'

@description('Serialized JSON content of the workbook definition.')
param serializedData string

@description('Resource ID of the source (e.g., Log Analytics workspace or App Insights). Defaults to Azure Monitor.')
param sourceId string = 'azure monitor'

@description('Gallery category for the workbook. E.g., workbook, tsg.')
param category string = 'workbook'

// ============================================================================
// Resource
// ============================================================================
resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: name
  location: location
  tags: tags
  kind: 'shared'
  properties: {
    displayName: displayName
    serializedData: serializedData
    version: '1.0'
    sourceId: sourceId
    category: category
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Name of the workbook.')
output name string = workbook.name

@description('Resource ID of the workbook.')
output resourceId string = workbook.id
