from langchain.vectorstores.azuresearch import AzureSearch
from azure.search.documents.indexes.models import (
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SimpleField,
)
from .LLMHelper import LLMHelper
from .EnvHelper import EnvHelper

class AzureSearchHelper():
    def __init__(self):
        pass
    
    def get_vector_store(self):
        llm_helper = LLMHelper()
        env_helper = EnvHelper()
        fields = [
            SimpleField(
                name="id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
            ),
            SearchableField(
                name="content",
                type=SearchFieldDataType.String,
            ),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=len(llm_helper.get_embedding_model().embed_query("Text")),
                vector_search_configuration="default",
            ),
            SearchableField(
                name="metadata",
                type=SearchFieldDataType.String,
            ),
            SearchableField(
                name="title",
                type=SearchFieldDataType.String,
                facetable=True,
                filterable=True,
            ),
            SearchableField(
                name="source",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SimpleField(
                name="chunk",
                type=SearchFieldDataType.Int32,
                filterable=True,
            ),
            SimpleField(
                name="offset",
                type=SearchFieldDataType.Int32,
                filterable=True,
            ),
        ]
        
        return AzureSearch(
            azure_search_endpoint=env_helper.AZURE_SEARCH_SERVICE,
            azure_search_key=env_helper.AZURE_SEARCH_KEY,
            index_name=env_helper.AZURE_SEARCH_INDEX,
            embedding_function=llm_helper.get_embedding_model().embed_query,
            fields=fields,
        )
    