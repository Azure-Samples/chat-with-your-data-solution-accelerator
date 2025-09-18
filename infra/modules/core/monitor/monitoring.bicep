metadata name = 'monitoring-solution'
metadata description = 'AVM WAF-compliant monitoring solution that integrates Application Insights with Log Analytics for centralized telemetry, diagnostics, and observability.'

// ========== //
// Parameters //
// ========== //

@description('Required. Name of the Log Analytics workspace.')
param logAnalyticsName string

@description('Optional. Unique deployment suffix to avoid naming conflicts.')
param deploymentSuffix string = utcNow('MMddHHmmss')

@description('Required. Name of the Application Insights instance.')
param applicationInsightsName string

@description('Required. Location for resources.')
param location string

@description('Optional. Enable redundancy for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enableRedundancy bool = false

@description('Optional. Enable private networking for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enablePrivateNetworking bool = false

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Optional. Replica location for redundancy (if enabled). Required if redundancy is enabled.')
param replicaLocation string = ''

import { lockType } from 'br/public:avm/utl/types/avm-common-types:0.5.1'
@description('Optional. The lock settings of the service.')
param lock lockType?

@description('Optional. Tags to apply to monitoring resources.')
param tags object = {}

@description('Optional. Retention for Application Insights (in days). AVM/WAF recommends 365.')
@minValue(30)
@maxValue(730)
param appInsightsRetentionInDays int = 365

@description('Optional. Use an existing Log Analytics workspace by providing its resource ID. If provided, the module will not create a new workspace.')
param existingLogAnalyticsWorkspaceId string = ''

@description('Optional. Dashboard name to create/link for Application Insights (pass-through).')
param applicationInsightsDashboardName string = ''

@description('Optional. Application type (e.g., web, other).')
@allowed([
  'web'
  'other'
])
param applicationType string = 'web'

// ========== //
// Resources  //
// ========== //

module avmWorkspace 'br/public:avm/res/operational-insights/workspace:0.12.0' = if (empty(existingLogAnalyticsWorkspaceId)) {
  name: take('avm.res.operational-insights.workspace.${logAnalyticsName}', 64)
  params: {
    name: logAnalyticsName
    tags: tags
    location: location
    enableTelemetry: enableTelemetry
    skuName: 'PerGB2018'
    dataRetention: 365
    features: { enableLogAccessUsingOnlyResourcePermissions: true }
    diagnosticSettings: [{ useThisWorkspace: true }]
    // WAF aligned configuration for Redundancy
    dailyQuotaGb: enableRedundancy ? 10 : null //WAF recommendation: 10 GB per day is a good starting point for most workloads
    replication: enableRedundancy
      ? {
          enabled: true
          location: replicaLocation
        }
      : null
    lock: lock
    // WAF aligned configuration for Private Networking
    publicNetworkAccessForIngestion: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    publicNetworkAccessForQuery: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    dataSources: enablePrivateNetworking
      ? [
          {
            tags: tags
            eventLogName: 'Application'
            eventTypes: [
              {
                eventType: 'Error'
              }
              {
                eventType: 'Warning'
              }
              {
                eventType: 'Information'
              }
            ]
            kind: 'WindowsEvent'
            name: 'applicationEvent'
          }
          {
            counterName: '% Processor Time'
            instanceName: '*'
            intervalSeconds: 60
            kind: 'WindowsPerformanceCounter'
            name: 'windowsPerfCounter1'
            objectName: 'Processor'
          }
          {
            kind: 'IISLogs'
            name: 'sampleIISLog1'
            state: 'OnPremiseEnabled'
          }
        ]
      : null
  }
}

var workspaceResourceId = empty(existingLogAnalyticsWorkspaceId)
  ? avmWorkspace!.outputs.resourceId
  : existingLogAnalyticsWorkspaceId

module avmAppInsights 'br/public:avm/res/insights/component:0.6.0' = {
  name: '${applicationInsightsName}-deploy'
  params: {
    name: applicationInsightsName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    retentionInDays: appInsightsRetentionInDays
    kind: applicationType
    disableIpMasking: false
    flowType: 'Bluefield'
    workspaceResourceId: empty(workspaceResourceId) ? '' : workspaceResourceId
    diagnosticSettings: empty(workspaceResourceId) ? null : [{ workspaceResourceId: workspaceResourceId }]
  }
}

module applicationInsightsDashboard 'br/public:avm/res/portal/dashboard:0.3.1' = if (!empty(applicationInsightsDashboardName)) {
  name: '${applicationInsightsDashboardName}-deploy'
  params: {
    name: applicationInsightsDashboardName
    location: location
    tags: tags
    lenses: [
      {
        order: 0
        parts: [
          {
            position: {
              x: 0
              y: 0
              colSpan: 2
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'id'
                  value: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                }
                {
                  name: 'Version'
                  value: '1.0'
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/AspNetOverviewPinnedPart'
              asset: {
                idInputName: 'id'
                type: 'ApplicationInsights'
              }
              defaultMenuItemId: 'overview'
            }
          }
          {
            position: {
              x: 2
              y: 0
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ComponentId'
                  value: {
                    Name: avmAppInsights.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'Version'
                  value: '1.0'
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/ProactiveDetectionAsyncPart'
              asset: {
                idInputName: 'ComponentId'
                type: 'ApplicationInsights'
              }
              defaultMenuItemId: 'ProactiveDetection'
            }
          }
          {
            position: {
              x: 3
              y: 0
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ComponentId'
                  value: {
                    Name: avmAppInsights.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'ResourceId'
                  value: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/QuickPulseButtonSmallPart'
              asset: {
                idInputName: 'ComponentId'
                type: 'ApplicationInsights'
              }
            }
          }
          {
            position: {
              x: 4
              y: 0
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ComponentId'
                  value: {
                    Name: avmAppInsights.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'TimeContext'
                  value: {
                    durationMs: 86400000
                    endTime: null
                    createdTime: '2018-05-04T01:20:33.345Z'
                    isInitialTime: true
                    grain: 1
                    useDashboardTimeRange: false
                  }
                }
                {
                  name: 'Version'
                  value: '1.0'
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/AvailabilityNavButtonPart'
              asset: {
                idInputName: 'ComponentId'
                type: 'ApplicationInsights'
              }
            }
          }
          {
            position: {
              x: 5
              y: 0
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ComponentId'
                  value: {
                    Name: avmAppInsights.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'TimeContext'
                  value: {
                    durationMs: 86400000
                    endTime: null
                    createdTime: '2018-05-08T18:47:35.237Z'
                    isInitialTime: true
                    grain: 1
                    useDashboardTimeRange: false
                  }
                }
                {
                  name: 'ConfigurationId'
                  value: '78ce933e-e864-4b05-a27b-71fd55a6afad'
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/AppMapButtonPart'
              asset: {
                idInputName: 'ComponentId'
                type: 'ApplicationInsights'
              }
            }
          }
          {
            position: {
              x: 0
              y: 1
              colSpan: 3
              rowSpan: 1
            }
            metadata: {
              inputs: []
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  settings: {
                    content: '# Usage'
                    title: ''
                    subtitle: ''
                  }
                }
              }
            }
          }
          {
            position: {
              x: 3
              y: 1
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ComponentId'
                  value: {
                    Name: avmAppInsights.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'TimeContext'
                  value: {
                    durationMs: 86400000
                    endTime: null
                    createdTime: '2018-05-04T01:22:35.782Z'
                    isInitialTime: true
                    grain: 1
                    useDashboardTimeRange: false
                  }
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/UsageUsersOverviewPart'
              asset: {
                idInputName: 'ComponentId'
                type: 'ApplicationInsights'
              }
            }
          }
          {
            position: {
              x: 4
              y: 1
              colSpan: 3
              rowSpan: 1
            }
            metadata: {
              inputs: []
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  settings: {
                    content: '# Reliability'
                    title: ''
                    subtitle: ''
                  }
                }
              }
            }
          }
          {
            position: {
              x: 7
              y: 1
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ResourceId'
                  value: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                }
                {
                  name: 'DataModel'
                  value: {
                    version: '1.0.0'
                    timeContext: {
                      durationMs: 86400000
                      createdTime: '2018-05-04T23:42:40.072Z'
                      isInitialTime: false
                      grain: 1
                      useDashboardTimeRange: false
                    }
                  }
                  isOptional: true
                }
                {
                  name: 'ConfigurationId'
                  value: '8a02f7bf-ac0f-40e1-afe9-f0e72cfee77f'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/CuratedBladeFailuresPinnedPart'
              isAdapter: true
              asset: {
                idInputName: 'ResourceId'
                type: 'ApplicationInsights'
              }
              defaultMenuItemId: 'failures'
            }
          }
          {
            position: {
              x: 8
              y: 1
              colSpan: 3
              rowSpan: 1
            }
            metadata: {
              inputs: []
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  settings: {
                    content: '# Responsiveness\r\n'
                    title: ''
                    subtitle: ''
                  }
                }
              }
            }
          }
          {
            position: {
              x: 11
              y: 1
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ResourceId'
                  value: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                }
                {
                  name: 'DataModel'
                  value: {
                    version: '1.0.0'
                    timeContext: {
                      durationMs: 86400000
                      createdTime: '2018-05-04T23:43:37.804Z'
                      isInitialTime: false
                      grain: 1
                      useDashboardTimeRange: false
                    }
                  }
                  isOptional: true
                }
                {
                  name: 'ConfigurationId'
                  value: '2a8ede4f-2bee-4b9c-aed9-2db0e8a01865'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/CuratedBladePerformancePinnedPart'
              isAdapter: true
              asset: {
                idInputName: 'ResourceId'
                type: 'ApplicationInsights'
              }
              defaultMenuItemId: 'performance'
            }
          }
          {
            position: {
              x: 12
              y: 1
              colSpan: 3
              rowSpan: 1
            }
            metadata: {
              inputs: []
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  settings: {
                    content: '# Browser'
                    title: ''
                    subtitle: ''
                  }
                }
              }
            }
          }
          {
            position: {
              x: 15
              y: 1
              colSpan: 1
              rowSpan: 1
            }
            metadata: {
              inputs: [
                {
                  name: 'ComponentId'
                  value: {
                    Name: avmAppInsights.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'MetricsExplorerJsonDefinitionId'
                  value: 'BrowserPerformanceTimelineMetrics'
                }
                {
                  name: 'TimeContext'
                  value: {
                    durationMs: 86400000
                    createdTime: '2018-05-08T12:16:27.534Z'
                    isInitialTime: false
                    grain: 1
                    useDashboardTimeRange: false
                  }
                }
                {
                  name: 'CurrentFilter'
                  value: {
                    eventTypes: [
                      4
                      1
                      3
                      5
                      2
                      6
                      13
                    ]
                    typeFacets: {}
                    isPermissive: false
                  }
                }
                {
                  name: 'id'
                  value: {
                    Name: avmAppInsights.name
                    SubscriptionId: subscription().subscriptionId
                    ResourceGroup: resourceGroup().name
                  }
                }
                {
                  name: 'Version'
                  value: '1.0'
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/AppInsightsExtension/PartType/MetricsExplorerBladePinnedPart'
              asset: {
                idInputName: 'ComponentId'
                type: 'ApplicationInsights'
              }
              defaultMenuItemId: 'browser'
            }
          }
          {
            position: {
              x: 0
              y: 2
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'sessions/count'
                          aggregationType: 5
                          namespace: 'microsoft.insights/components/kusto'
                          metricVisualization: {
                            displayName: 'Sessions'
                            color: '#47BDF5'
                          }
                        }
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'users/count'
                          aggregationType: 5
                          namespace: 'microsoft.insights/components/kusto'
                          metricVisualization: {
                            displayName: 'Users'
                            color: '#7E58FF'
                          }
                        }
                      ]
                      title: 'Unique sessions and users'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                      openBladeOnClick: {
                        openBlade: true
                        destinationBlade: {
                          extensionName: 'HubsExtension'
                          bladeName: 'ResourceMenuBlade'
                          parameters: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                            menuid: 'segmentationUsers'
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 4
              y: 2
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'requests/failed'
                          aggregationType: 7
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Failed requests'
                            color: '#EC008C'
                          }
                        }
                      ]
                      title: 'Failed requests'
                      visualization: {
                        chartType: 3
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                      openBladeOnClick: {
                        openBlade: true
                        destinationBlade: {
                          extensionName: 'HubsExtension'
                          bladeName: 'ResourceMenuBlade'
                          parameters: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                            menuid: 'failures'
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 8
              y: 2
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'requests/duration'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Server response time'
                            color: '#00BCF2'
                          }
                        }
                      ]
                      title: 'Server response time'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                      openBladeOnClick: {
                        openBlade: true
                        destinationBlade: {
                          extensionName: 'HubsExtension'
                          bladeName: 'ResourceMenuBlade'
                          parameters: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                            menuid: 'performance'
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 12
              y: 2
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'browserTimings/networkDuration'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Page load network connect time'
                            color: '#7E58FF'
                          }
                        }
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'browserTimings/processingDuration'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Client processing time'
                            color: '#44F1C8'
                          }
                        }
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'browserTimings/sendDuration'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Send request time'
                            color: '#EB9371'
                          }
                        }
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'browserTimings/receiveDuration'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Receiving response time'
                            color: '#0672F1'
                          }
                        }
                      ]
                      title: 'Average page load time breakdown'
                      visualization: {
                        chartType: 3
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 0
              y: 5
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'availabilityResults/availabilityPercentage'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Availability'
                            color: '#47BDF5'
                          }
                        }
                      ]
                      title: 'Average availability'
                      visualization: {
                        chartType: 3
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                      openBladeOnClick: {
                        openBlade: true
                        destinationBlade: {
                          extensionName: 'HubsExtension'
                          bladeName: 'ResourceMenuBlade'
                          parameters: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                            menuid: 'availability'
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 4
              y: 5
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'exceptions/server'
                          aggregationType: 7
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Server exceptions'
                            color: '#47BDF5'
                          }
                        }
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'dependencies/failed'
                          aggregationType: 7
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Dependency failures'
                            color: '#7E58FF'
                          }
                        }
                      ]
                      title: 'Server exceptions and Dependency failures'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 8
              y: 5
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'performanceCounters/processorCpuPercentage'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Processor time'
                            color: '#47BDF5'
                          }
                        }
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'performanceCounters/processCpuPercentage'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Process CPU'
                            color: '#7E58FF'
                          }
                        }
                      ]
                      title: 'Average processor and process CPU utilization'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 12
              y: 5
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'exceptions/browser'
                          aggregationType: 7
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Browser exceptions'
                            color: '#47BDF5'
                          }
                        }
                      ]
                      title: 'Browser exceptions'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 0
              y: 8
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'availabilityResults/count'
                          aggregationType: 7
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Availability test results count'
                            color: '#47BDF5'
                          }
                        }
                      ]
                      title: 'Availability test results count'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 4
              y: 8
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'performanceCounters/processIOBytesPerSecond'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Process IO rate'
                            color: '#47BDF5'
                          }
                        }
                      ]
                      title: 'Average process I/O rate'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
          {
            position: {
              x: 8
              y: 8
              colSpan: 4
              rowSpan: 3
            }
            metadata: {
              inputs: [
                {
                  name: 'options'
                  value: {
                    chart: {
                      metrics: [
                        {
                          resourceMetadata: {
                            id: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Insights/components/${avmAppInsights.name}'
                          }
                          name: 'performanceCounters/memoryAvailableBytes'
                          aggregationType: 4
                          namespace: 'microsoft.insights/components'
                          metricVisualization: {
                            displayName: 'Available memory'
                            color: '#47BDF5'
                          }
                        }
                      ]
                      title: 'Average available memory'
                      visualization: {
                        chartType: 2
                        legendVisualization: {
                          isVisible: true
                          position: 2
                          hideSubtitle: false
                        }
                        axisVisualization: {
                          x: {
                            isVisible: true
                            axisType: 2
                          }
                          y: {
                            isVisible: true
                            axisType: 1
                          }
                        }
                      }
                    }
                  }
                }
                {
                  name: 'sharedTimeRange'
                  isOptional: true
                }
              ]
              #disable-next-line BCP036
              type: 'Extension/HubsExtension/PartType/MonitorChartPart'
              settings: {}
            }
          }
        ]
      }
    ]
  }
}

// ========== //
// Outputs    //
// ========== //

@description('Resource ID of the Log Analytics workspace.')
output logAnalyticsWorkspaceId string = workspaceResourceId

@description('Resource ID of the Application Insights instance.')
output appInsightsId string = avmAppInsights.outputs.resourceId

// Compatibility aliases used by upstream templates
@description('Legacy alias for the Application Insights resource id (backwards compatibility).')
output applicationInsightsId string = avmAppInsights.outputs.resourceId

@description('Application Insights resource name (backwards compatibility).')
output applicationInsightsName string = applicationInsightsName

@description('Application Insights connection string (backwards compatibility).')
output applicationInsightsConnectionString string = avmAppInsights.outputs.connectionString

@description('Application Insights instrumentation key (backwards compatibility).')
output applicationInsightsInstrumentationKey string = avmAppInsights.outputs.instrumentationKey

@description('Application Insights dashboard name (pass-through).')
output applicationInsightsDashboardName string = applicationInsightsDashboardName

@description('Resource Group name where monitoring resources are deployed.')
output resourceGroupName string = resourceGroup().name

@description('Location where monitoring resources are deployed.')
output location string = location
