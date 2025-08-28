@description('The friendly name for the workbook.  This name must be unique within a resource group.')
param workbookDisplayName string

@description('The gallery that the workbook will been shown under. Supported values include workbook, tsg, etc. Usually, this is \'workbook\'')
param workbookType string = 'workbook'

@description('The id of resource instance to which the workbook will be associated')
param workbookSourceId string = 'azure monitor'

@description('The unique guid for this workbook instance')
param workbookId string

@description('The json content of the workbook')
param workbookContents string

param location string = resourceGroup().location

resource workbook_resource 'microsoft.insights/workbooks@2023-06-01' = {
  name: workbookId
  location: location
  kind: 'shared'
  properties: {
    displayName: workbookDisplayName
    serializedData: workbookContents
    version: '1.0'
    sourceId: workbookSourceId
    category: workbookType
  }
}

output workbookId string = workbook_resource.id
