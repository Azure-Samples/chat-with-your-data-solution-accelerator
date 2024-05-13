[Back to *Chat with your data* README](../README.md)

![Supporting documentation](images/supportingDocuments.png)
# Best practices

**Evaluate your data first**
It is important that you evaluate the retrieval/search and the generation of the answers for your data and tune these configurations accordingly before you use this repo in production. For a starting point to understand and perform RAG evaluations, we encourage you to look into the [RAG Experiment Accelerator](https://github.com/microsoft/rag-experiment-accelerator).

**Access to documents**

 Only upload data that can be accessed by any user of the application. Anyone who uses the application should also have clearance for any data that is uploaded to the application.

**Depth of responses**

The more limited the data set, the broader the questions should be. If the data in the repo is limited, the depth of information in the LLM response you can get with follow up questions may be limited. For more depth in your response, increase the data available for the LLM to access.

**Response consistency**

 Consider tuning the configuration of prompts to the level of precision required.  The more precision desired, the harder it may be to generate a response.

**Numerical queries**

 The accelerator is optimized to summarize unstructured data, such as PDFs or text files. The ChatGPT 3.5 Turbo model used by the accelerator is not currently optimized to handle queries about specific numerical data. The ChatGPT 4 model may be better able to handle numerical queries.

**Use your own judgement**

 AI-generated content may be incorrect and should be reviewed before usage.

**Azure AI Search used as retriever in RAG**

Azure AI Search, when used as a retriever in the Retrieval-Augmented Generation (RAG) pattern, plays a key role in fetching relevant information from a large corpus of data. The RAG pattern involves two key steps: retrieval of documents and generation of responses. Azure AI Search, in the retrieval phase, filters and ranks the most relevant documents from the dataset based on a given query.

The importance of optimizing data in the index for relevance lies in the fact that the quality of retrieved documents directly impacts the generation phase. The more relevant the retrieved documents are, the more accurate and pertinent the generated responses will be.

Azure AI Search allows for fine-tuning the relevance of search results through features such as [scoring profiles](https://learn.microsoft.com/azure/search/index-add-scoring-profiles), which assign weights to different fields, [Lucene's powerful full-text search capabilities](https://learn.microsoft.com/azure/search/query-lucene-syntax), [vector search](https://learn.microsoft.com/azure/search/vector-search-overview) for similarity search, multi-modal search, recommendations, [hybrid search](https://learn.microsoft.com/azure/search/hybrid-search-overview) and [semantic search](https://learn.microsoft.com/azure/search/search-get-started-semantic) to use AI from Microsoft to rescore search results and moving results that have more semantic relevance to the top of the list. By leveraging these features, one can ensure that the most relevant documents are retrieved first, thereby improving the overall effectiveness of the RAG pattern.

Moreover, optimizing the data in the index also enhances the efficiency, the speed of the retrieval process and increases relevance which is an integral part of the RAG pattern.

**Azure AI Search**

- Consider switching security keys and using [RBAC](https://learn.microsoft.com/azure/search/search-security-rbac) instead for authentication.
- Consider setting up a [firewall](https://learn.microsoft.com/azure/search/service-configure-firewall), [private endpoints](https://learn.microsoft.com/azure/search/service-create-private-endpoint) for inbound connections and [shared private links](https://learn.microsoft.com/azure/search/search-indexer-howto-access-trusted-service-exception) for [built-in pull indexers](https://learn.microsoft.com/en-us/azure/search/search-indexer-overview).
- For the best results, prepare your index data and consider [analyzers](https://learn.microsoft.com/azure/search/search-analyzers).
- Analyze your [resource capacity needs](https://learn.microsoft.com/azure/search/search-capacity-planning).

**Before deploying Azure RAG implementations to production**

- Follow the best practices described in [Azure Well-Architected-Framework](https://learn.microsoft.com/azure/well-architected/).
- Understand the [Retrieval Augmented Generation (RAG) in Azure AI Search](https://learn.microsoft.com/en-us/azure/search/retrieval-augmented-generation-overview).
- Understand the [functionality and configuration that would adapt better to your solution](https://techcommunity.microsoft.com/t5/azure-ai-services-blog/azure-cognitive-search-outperforming-vector-search-with-hybrid/ba-p/3929167) and test with your own data for optimal retrieval.
- Experiment with different options, define the prompts that are optimal for your needs and find ways to implement functionality tailored to your business needs with [this demo](https://github.com/Azure-Samples/azure-search-openai-demo), so you can then adapt to the accelerator.
- Follow the [Responsible AI best practices](https://www.microsoft.com/en-us/ai/tools-practices).
- Understand the [levels of access of your users and application](https://techcommunity.microsoft.com/t5/azure-ai-services-blog/access-control-in-generative-ai-applications-with-azure/ba-p/3956408).

**Chunking: Importance for RAG and strategies implemented as part of this repo**

Chunking is essential for managing large data sets, optimizing relevance, preserving context, integrating workflows, and enhancing the user experience. See [How to chunk documents](https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-chunk-documents) for more information.

These are the chunking strategy options you can choose from:
- **Layout**: An AI approach to determine a good chunking strategy.
-  **Page**: This strategy involves breaking down long documents into pages.
- **Fixed-Size Overlap**: This strategy involves defining a fixed size that’s sufficient for semantically meaningful paragraphs (for example, 250 words) and allows for some overlap (for example, 10-25% of the content). This usually helps creating good inputs for embedding vector models. Overlapping a small amount of text between chunks can help preserve the semantic context.
-  **Paragraph**: This strategy allows breaking down a difficult text into more manageable pieces and rewrite these “chunks” with a summarization of all of them.
