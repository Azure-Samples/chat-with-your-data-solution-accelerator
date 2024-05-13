from typing import List
from .SearchHandlerBase import SearchHandlerBase
from ..helpers.llm_helper import LLMHelper
from ..helpers.azure_search_helper import AzureSearchHelper
from ..common.SourceDocument import SourceDocument
import json
from azure.search.documents.models import VectorizedQuery
import tiktoken


class AzureSearchHandler(SearchHandlerBase):

    _ENCODER_NAME = "cl100k_base"
    _VECTOR_FIELD = "content_vector"

    def __init__(self, env_helper):
        super().__init__(env_helper)
        self.llm_helper = LLMHelper()

    def create_search_client(self):
        return AzureSearchHelper().get_search_client()

    def perform_search(self, filename):
        return self.search_client.search(
            "*", select="title, content, metadata", filter=f"title eq '{filename}'"
        )

    def process_results(self, results):
        if results is None:
            return []
        data = [
            [json.loads(result["metadata"])["chunk"], result["content"]]
            for result in results
        ]
        return data

    def get_files(self):
        return self.search_client.search(
            "*", select="id, title", include_total_count=True
        )

    def output_results(self, results):
        files = {}
        for result in results:
            id = result["id"]
            filename = result["title"]
            if filename in files:
                files[filename].append(id)
            else:
                files[filename] = [id]

        return files

    def delete_files(self, files):
        ids_to_delete = []
        files_to_delete = []

        for filename, ids in files.items():
            files_to_delete.append(filename)
            ids_to_delete += [{"id": id} for id in ids]
        self.search_client.delete_documents(ids_to_delete)

        return ", ".join(files_to_delete)

    def query_search(self, question) -> List[SourceDocument]:
        encoding = tiktoken.get_encoding(self._ENCODER_NAME)
        tokenised_question = encoding.encode(question)
        if self.env_helper.AZURE_SEARCH_USE_SEMANTIC_SEARCH:
            results = self._semantic_search(question, tokenised_question)
        else:
            results = self._hybrid_search(question, tokenised_question)

        return self._convert_to_source_documents(results)

    def _semantic_search(self, question: str, tokenised_question: list[int]):
        return self.search_client.search(
            search_text=question,
            vector_queries=[
                VectorizedQuery(
                    vector=self.llm_helper.generate_embeddings(tokenised_question),
                    k_nearest_neighbors=self.env_helper.AZURE_SEARCH_TOP_K,
                    fields=self._VECTOR_FIELD,
                )
            ],
            filter=self.env_helper.AZURE_SEARCH_FILTER,
            query_type="semantic",
            semantic_configuration_name=self.env_helper.AZURE_SEARCH_SEMANTIC_CONFIG_NAME,
            query_caption="extractive",
            query_answer="extractive",
            top=self.env_helper.AZURE_SEARCH_TOP_K,
        )

    def _hybrid_search(self, question: str, tokenised_question: list[int]):
        return self.search_client.search(
            search_text=question,
            vector_queries=[
                VectorizedQuery(
                    vector=self.llm_helper.generate_embeddings(tokenised_question),
                    k_nearest_neighbors=self.env_helper.AZURE_SEARCH_TOP_K,
                    filter=self.env_helper.AZURE_SEARCH_FILTER,
                    fields=self._VECTOR_FIELD,
                )
            ],
            filter=self.env_helper.AZURE_SEARCH_FILTER,
            top=self.env_helper.AZURE_SEARCH_TOP_K,
        )

    def _convert_to_source_documents(self, search_results) -> List[SourceDocument]:
        source_documents = []
        for source in search_results:
            source_documents.append(
                SourceDocument(
                    id=source.get("id"),
                    content=source.get("content"),
                    title=source.get("title"),
                    source=source.get("source"),
                    chunk=source.get("chunk"),
                    offset=source.get("offset"),
                    page_number=source.get("page_number"),
                )
            )
        return source_documents
