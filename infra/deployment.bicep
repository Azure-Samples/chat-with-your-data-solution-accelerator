@description('provide a 2-13 character prefix for all resources.')
param ResourcePrefix string

@description('Location for all resources.')
param Location string = resourceGroup().location

@description('Name of the vnet resource group')
param VnetResourceGroup string

@description('Name of the vnet')
param VnetName string

@description('Name of the apps subnet')
param AppsSubnetName string

@description('Name of the endpoints subnet')
param EndpointsSubnetName string

@description('Name of the private DNS zone resource group')
param PrivateDnsZoneResourceGroup string

@description('Name of App Service plan')
param HostingPlanName string = '${ResourcePrefix}-hosting-plan'

@description('The pricing tier for the App Service plan')
@allowed([
  'F1'
  'D1'
  'B1'
  'B2'
  'B3'
  'S1'
  'S2'
  'S3'
  'P1'
  'P2'
  'P3'
  'P4'
])
param HostingPlanSku string = 'B3'

@description('Name of Web App')
param WebsiteName string = '${ResourcePrefix}-website'

@description('Name of Log Analytics Workspace for App Insights')
param logAnalyticsWorkspaceName string = '${ResourcePrefix}-loganalytics'

@description('Name of Application Insights')
param ApplicationInsightsName string = '${ResourcePrefix}-appinsights'

@description('Use semantic search')
param AzureSearchUseSemanticSearch string = 'false'

@description('Semantic search config')
param AzureSearchSemanticSearchConfig string = 'default'

@description('Is the index prechunked')
param AzureSearchIndexIsPrechunked string = 'false'

@description('Top K results')
param AzureSearchTopK string = '5'

@description('Enable in domain')
param AzureSearchEnableInDomain string = 'false'

@description('Content columns')
param AzureSearchContentColumns string = 'content'

@description('Filename column')
param AzureSearchFilenameColumn string = 'filename'

@description('Title column')
param AzureSearchTitleColumn string = 'title'

@description('Url column')
param AzureSearchUrlColumn string = 'url'

@description('Name of Azure OpenAI Resource')
param AzureOpenAIResource string = '${ResourcePrefix}oai'

@description('Azure OpenAI GPT Model Deployment Name')
param AzureOpenAIGPTModel string = 'gpt-35-turbo'

@description('Azure OpenAI GPT Model Name')
param AzureOpenAIGPTModelName string = 'gpt-35-turbo'

@description('Azure OpenAI GPT Model Version')
param AzureOpenAIGPTModelVersion string = '0613'

@description('Azure OpenAI Embedding Model Deployment Name')
param AzureOpenAIEmbeddingModel string = 'text-embedding-ada-002'

@description('Azure OpenAI GPT Model Name')
param AzureOpenAIEmbeddingModelName string = 'text-embedding-ada-002'

@description('Azure OpenAI GPT Model Version')
param AzureOpenAIEmbeddingModelVersion string = '2'

@description('Orchestration strategy: openai_function or langchain str. If you use a old version of turbo (0301), plese select langchain')
@allowed([
  'openai_function'
  'langchain'
])
param OrchestrationStrategy string

@description('Azure OpenAI Temperature')
param AzureOpenAITemperature string = '0'

@description('Azure OpenAI Top P')
param AzureOpenAITopP string = '1'

@description('Azure OpenAI Max Tokens')
param AzureOpenAIMaxTokens string = '1000'

@description('Azure OpenAI Stop Sequence')
param AzureOpenAIStopSequence string = '\n'

@description('Azure OpenAI System Message')
param AzureOpenAISystemMessage string = 'You are an AI assistant that helps people find information.'

@description('Azure OpenAI Api Version')
param AzureOpenAIApiVersion string = '2023-07-01-preview'

@description('Whether or not to stream responses from Azure OpenAI')
param AzureOpenAIStream string = 'true'

@description('Azure AI Search Resource')
param AzureAISearchName string = '${ResourcePrefix}-search'

@description('The SKU of the search service you want to create. E.g. free or standard')
@allowed([
  'free'
  'basic'
  'standard'
  'standard2'
  'standard3'
])
param AzureAISearchSku string = 'standard'

@description('Azure AI Search Index')
param AzureSearchIndex string = '${ResourcePrefix}-index'

@description('Azure AI Search Conversation Log Index')
param AzureSearchConversationLogIndex string = 'conversations'

@description('Name of Storage Account')
param StorageAccountName string = '${ResourcePrefix}str'

@description('Name of Function App for Batch document processing')
param FunctionName string = '${ResourcePrefix}-backend'

@description('Azure Form Recognizer Name')
param FormRecognizerName string = '${ResourcePrefix}-formrecog'

@description('Azure Form Recognizer Location')
param FormRecognizerLocation string = Location

@description('Azure Speech Service Name')
param SpeechServiceName string = '${ResourcePrefix}-speechservice'

@description('Azure Content Safety Name')
param ContentSafetyName string = '${ResourcePrefix}-contentsafety'
param newGuidString string = newGuid()

@allowed([
  'keys'
  'rbac'
])
param authType string = 'keys'

@description('Id of the user or app to assign application roles')
param principalId string = ''

var WebAppImageName = 'DOCKER|fruoccopublic.azurecr.io/rag-webapp'
var AdminWebAppImageName = 'DOCKER|fruoccopublic.azurecr.io/rag-adminwebapp'
var BackendImageName = 'DOCKER|fruoccopublic.azurecr.io/rag-backend'

var BlobContainerName = 'documents'
var QueueName = 'doc-processing'
var ClientKey = '${uniqueString(guid(resourceGroup().id, deployment().name))}${newGuidString}'
var EventGridSystemTopicName = 'doc-processing'

//var storageFilePrivateEndpointName = '${StorageAccountName}-file-private-endpoint'
//var storageTablePrivateEndpointName = '${StorageAccountName}-table-private-endpoint'
var storageBlobPrivateEndpointName = '${StorageAccountName}-blob-private-endpoint'
var storageQueuePrivateEndpointName = '${StorageAccountName}-queue-private-endpoint'
var oaiPrivateEndpointName = '${AzureOpenAIResource}-private-endpoint'
var searchPrivateEndpointName = '${AzureAISearchName}-private-endpoint'
var speechPrivateEndpointName = '${SpeechServiceName}-private-endpoint'

//var storageFilePrivateDnsZoneName = 'privatelink.file.${environment().suffixes.storage}'
//var storageTablePrivateDnsZoneName = 'privatelink.table.${environment().suffixes.storage}'
var storageBlobPrivateDnsZoneName = 'privatelink.blob.${environment().suffixes.storage}'
var storageQueuePrivateDnsZoneName = 'privatelink.queue.${environment().suffixes.storage}'
var oaiPrivateDnsZoneName = 'privatelink.openai.azure.com'
var searchPrivateDnsZoneName = 'privatelink.search.windows.net'
var aiServicesPrivateDnsZoneName = 'privatelink.cognitiveservices.azure.com'

// VNET References
resource vnet 'Microsoft.Network/virtualNetworks@2023-06-01' existing = {
  scope: resourceGroup(VnetResourceGroup)
  name: VnetName
}

// resource appsSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-06-01' existing = {
//   parent: vnet
//   name: AppsSubnetName
// }

resource endpointsSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-06-01' existing = {
  parent: vnet
  name: EndpointsSubnetName
}

resource storageBlobPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  scope: resourceGroup(PrivateDnsZoneResourceGroup)
  name: storageBlobPrivateDnsZoneName
}

resource privateStorageQueueDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  scope: resourceGroup(PrivateDnsZoneResourceGroup)
  name: storageQueuePrivateDnsZoneName
}

resource oaiPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  scope: resourceGroup(PrivateDnsZoneResourceGroup)
  name: oaiPrivateDnsZoneName
}

resource searchPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  scope: resourceGroup(PrivateDnsZoneResourceGroup)
  name: searchPrivateDnsZoneName
}

resource aiServicesPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  scope: resourceGroup(PrivateDnsZoneResourceGroup)
  name: aiServicesPrivateDnsZoneName
}
// Storage account

// Using public bicep registry
module storageAccount 'br/public:storage/storage-account:3.0.1' = {
  name: '${StorageAccountName}-Deploy'
  params: {
    name: StorageAccountName
    location: Location
    kind: 'StorageV2'
    allowBlobPublicAccess: false
    supportHttpsTrafficOnly: true
    enablePublicNetworkAccess: false
    minimumTlsVersion: 'TLS1_2'
    encryption: {
      enable: true
      configurations: {
        keySource: 'Microsoft.Storage'
        requireInfrastructureEncryption: true
      }
    }
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
    }
    blobContainers: [
      {
        name: BlobContainerName
        properties: {
          publicAccess: 'None'
        }
      }
    ]
    privateEndpoints: [
      {
        name: storageBlobPrivateEndpointName
        subnetId: endpointsSubnet.id
        groupId: 'blob'
        privateDnsZoneId: storageBlobPrivateDnsZone.id
        isManualApproval: false
      }
      {
        name: storageQueuePrivateEndpointName
        subnetId: endpointsSubnet.id
        groupId: 'queue'
        privateDnsZoneId: privateStorageQueueDnsZone.id
        isManualApproval: false
      }
    ]
  }
}
//output storageAccountID string = storageAccount.outputs.id

resource StorageAccountName_default 'Microsoft.Storage/storageAccounts/queueServices@2022-09-01' = {
  name: '${StorageAccountName}/default'
  properties: {
    cors: {
      corsRules: []
    }
  }
  dependsOn: [
    storageAccount
  ]
}

resource StorageAccountName_default_doc_processing 'Microsoft.Storage/storageAccounts/queueServices/queues@2022-09-01' = {
  parent: StorageAccountName_default
  name: 'doc-processing'
  properties: {
    metadata: {}
  }
  dependsOn: []
}

resource StorageAccountName_default_doc_processing_poison 'Microsoft.Storage/storageAccounts/queueServices/queues@2022-09-01' = {
  parent: StorageAccountName_default
  name: 'doc-processing-poison'
  properties: {
    metadata: {}
  }
  dependsOn: []
}


// Open AI
resource OpenAI 'Microsoft.CognitiveServices/accounts@2021-10-01' = {
  name: AzureOpenAIResource
  location: Location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: AzureOpenAIResource
    publicNetworkAccess: 'Disabled'
  }
  identity: {
    type: 'SystemAssigned'
  }

  resource OpenAIGPTDeployment 'deployments@2023-05-01' = {
    name: AzureOpenAIGPTModelName
    properties: {
      model: {
        format: 'OpenAI'
        name: AzureOpenAIGPTModel
        version: AzureOpenAIGPTModelVersion
      }
    }
    sku: {
      name: 'Standard'
      capacity: 30
    }
  }

  resource OpenAIEmbeddingDeployment 'deployments@2023-05-01' = {
    name: AzureOpenAIEmbeddingModelName
    properties: {
      model: {
        format: 'OpenAI'
        name: AzureOpenAIEmbeddingModel
        version: AzureOpenAIEmbeddingModelVersion
      }
    }
    sku: {
      name: 'Standard'
      capacity: 30
    }
    dependsOn: [
      OpenAIGPTDeployment
    ]
  }
}

resource oaiPrivateEndpoint 'Microsoft.Network/privateEndpoints@2022-11-01' = {
  name: oaiPrivateEndpointName
  location: Location
  properties: {
    privateLinkServiceConnections: [
      {
        name: '${oaiPrivateEndpointName}-connection'
        properties: {
          privateLinkServiceId: OpenAI.id
          groupIds: [
            'account'
          ]
          privateLinkServiceConnectionState: {
            status: 'Approved'
            description: 'Approved'
            actionsRequired: 'None'
          }
        }
      }
    ]
    customNetworkInterfaceName: '${oaiPrivateEndpointName}-nic'
    subnet: {
      id: endpointsSubnet.id
    }
  }
}

resource oaiPrivateEndpointDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2021-05-01' = {
  parent: oaiPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'config1'
        properties: {
          privateDnsZoneId: oaiPrivateDnsZone.id
        }
      }
    ]
  }
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2021-06-01' = {
  name: logAnalyticsWorkspaceName
  location: Location
  properties: {
    sku: {
      name: 'pergb2018'
    }
  }
}

resource ApplicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: ApplicationInsightsName
  location: Location
  tags: {
    'hidden-link:${resourceId('Microsoft.Web/sites', ApplicationInsightsName)}': 'Resource'
  }
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
  }
  kind: 'web'
}

resource AzureAISearch 'Microsoft.Search/searchServices@2022-09-01' = {
  name: AzureAISearchName
  location: Location
  tags: {
    deployment : 'chatwithyourdata-sa'
  }
  sku: {
    name: AzureAISearchSku
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    authOptions: authType == 'keys' ? {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    } : null
    disableLocalAuth: authType == 'keys' ? false : true
    replicaCount: 1
    partitionCount: 1
    publicNetworkAccess: 'disabled'
  }
}


resource searchPrivateEndpoint 'Microsoft.Network/privateEndpoints@2022-11-01' = {
  name: searchPrivateEndpointName
  location: Location
  properties: {
    privateLinkServiceConnections: [
      {
        name: '${searchPrivateEndpointName}-connection'
        properties: {
          privateLinkServiceId: AzureAISearch.id
          groupIds: [
            'searchService'
          ]
          privateLinkServiceConnectionState: {
            status: 'Approved'
            description: 'Approved'
            actionsRequired: 'None'
          }
        }
      }
    ]
    customNetworkInterfaceName: '${searchPrivateEndpointName}-nic'
    subnet: {
      id: endpointsSubnet.id
    }
  }
}

resource searchPrivateEndpointDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2021-05-01' = {
  parent: searchPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'config1'
        properties: {
          privateDnsZoneId: searchPrivateDnsZone.id
        }
      }
    ]
  }
}

resource SpeechService 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: SpeechServiceName
  location: Location
  sku: {
    name: 'S0'
  }
  kind: 'SpeechServices'
  identity: {
    type: 'None'
  }
  properties: {
    networkAcls: {
      defaultAction: 'Deny'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Disabled'  
    customSubDomainName: SpeechServiceName  
  }
}


resource speechPrivateEndpoint 'Microsoft.Network/privateEndpoints@2022-11-01' = {
  name: speechPrivateEndpointName
  location: Location
  properties: {
    privateLinkServiceConnections: [
      {
        name: '${speechPrivateEndpointName}-connection'
        properties: {
          privateLinkServiceId: SpeechService.id
          groupIds: [
            'account'
          ]
          privateLinkServiceConnectionState: {
            status: 'Approved'
            description: 'Approved'
            actionsRequired: 'None'
          }
        }
      }
    ]
    customNetworkInterfaceName: '${speechPrivateEndpointName}-nic'
    subnet: {
      id: endpointsSubnet.id
    }
  }
}

resource speechPrivateEndpointDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2021-05-01' = {
  parent: speechPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'config1'
        properties: {
          privateDnsZoneId: aiServicesPrivateDnsZone.id
        }
      }
    ]
  }
}
