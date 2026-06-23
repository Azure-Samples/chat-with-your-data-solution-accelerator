// ============================================================================
// Module: Data Collection Rule
// Description: AVM wrapper for Azure Monitor Data Collection Rule
// AVM Module: avm/res/insights/data-collection-rule
// WAF: Monitoring for VM observability
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

@description('Optional. Override name for the data collection rule. Defaults to dcr-{solutionName}.')
param name string = 'dcr-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Resource ID of the Log Analytics workspace destination.')
param logAnalyticsWorkspaceResourceId string

@description('Name of the Log Analytics workspace (used for destination naming).')
param logAnalyticsWorkspaceName string = ''

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

var dcrLogAnalyticsDestinationName = !empty(logAnalyticsWorkspaceName) ? 'la-${logAnalyticsWorkspaceName}-destination' : 'la-${name}-destination'

// ============================================================================
// AVM Module Deployment
// ============================================================================
module dataCollectionRule 'br/public:avm/res/insights/data-collection-rule:0.11.0' = {
  name: take('avm.res.insights.data-collection-rule.${name}', 64)
  params: {
    name: name
    tags: tags
    enableTelemetry: enableTelemetry
    location: location
    dataCollectionRuleProperties: {
      kind: 'Windows'
      dataSources: {
        performanceCounters: [
          {
            streams: ['Microsoft-Perf']
            samplingFrequencyInSeconds: 60
            counterSpecifiers: [
              '\\Processor Information(_Total)\\% Processor Time'
              '\\Processor Information(_Total)\\% Privileged Time'
              '\\Processor Information(_Total)\\% User Time'
              '\\Processor Information(_Total)\\Processor Frequency'
              '\\System\\Processes'
              '\\Process(_Total)\\Thread Count'
              '\\Process(_Total)\\Handle Count'
              '\\System\\System Up Time'
              '\\System\\Context Switches/sec'
              '\\System\\Processor Queue Length'
              '\\Memory\\% Committed Bytes In Use'
              '\\Memory\\Available Bytes'
              '\\Memory\\Committed Bytes'
              '\\Memory\\Cache Bytes'
              '\\Memory\\Pool Paged Bytes'
              '\\Memory\\Pool Nonpaged Bytes'
              '\\Memory\\Pages/sec'
              '\\Memory\\Page Faults/sec'
              '\\Process(_Total)\\Working Set'
              '\\Process(_Total)\\Working Set - Private'
              '\\LogicalDisk(_Total)\\% Disk Time'
              '\\LogicalDisk(_Total)\\% Disk Read Time'
              '\\LogicalDisk(_Total)\\% Disk Write Time'
              '\\LogicalDisk(_Total)\\% Idle Time'
              '\\LogicalDisk(_Total)\\Disk Bytes/sec'
              '\\LogicalDisk(_Total)\\Disk Read Bytes/sec'
              '\\LogicalDisk(_Total)\\Disk Write Bytes/sec'
              '\\LogicalDisk(_Total)\\Disk Transfers/sec'
              '\\LogicalDisk(_Total)\\Disk Reads/sec'
              '\\LogicalDisk(_Total)\\Disk Writes/sec'
              '\\LogicalDisk(_Total)\\Avg. Disk sec/Transfer'
              '\\LogicalDisk(_Total)\\Avg. Disk sec/Read'
              '\\LogicalDisk(_Total)\\Avg. Disk sec/Write'
              '\\LogicalDisk(_Total)\\Avg. Disk Queue Length'
              '\\LogicalDisk(_Total)\\Avg. Disk Read Queue Length'
              '\\LogicalDisk(_Total)\\Avg. Disk Write Queue Length'
              '\\LogicalDisk(_Total)\\% Free Space'
              '\\LogicalDisk(_Total)\\Free Megabytes'
              '\\Network Interface(*)\\Bytes Total/sec'
              '\\Network Interface(*)\\Bytes Sent/sec'
              '\\Network Interface(*)\\Bytes Received/sec'
              '\\Network Interface(*)\\Packets/sec'
              '\\Network Interface(*)\\Packets Sent/sec'
              '\\Network Interface(*)\\Packets Received/sec'
              '\\Network Interface(*)\\Packets Outbound Errors'
              '\\Network Interface(*)\\Packets Received Errors'
            ]
            name: 'perfCounterDataSource60'
          }
        ]
        windowsEventLogs: [
          {
            name: 'SecurityAuditEvents'
            streams: ['Microsoft-WindowsEvent']
            xPathQueries: [
              'Security!*[System[(EventID=4624 or EventID=4625)]]'
            ]
          }
          {
            name: 'AuditSuccessFailure'
            streams: ['Microsoft-Event']
            xPathQueries: [
              'Security!*[System[(band(Keywords,13510798882111488)) and (EventID != 4624)]]'
            ]
          }
        ]
      }
      destinations: {
        logAnalytics: [
          {
            workspaceResourceId: logAnalyticsWorkspaceResourceId
            name: dcrLogAnalyticsDestinationName
          }
        ]
      }
      dataFlows: [
        {
          streams: ['Microsoft-Perf']
          destinations: [dcrLogAnalyticsDestinationName]
          transformKql: 'source'
          outputStream: 'Microsoft-Perf'
        }
        {
          streams: ['Microsoft-Event']
          destinations: [dcrLogAnalyticsDestinationName]
          transformKql: 'source'
          outputStream: 'Microsoft-Event'
        }
      ]
    }
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the data collection rule.')
output resourceId string = dataCollectionRule.outputs.resourceId

@description('Name of the data collection rule.')
output name string = dataCollectionRule.outputs.name
