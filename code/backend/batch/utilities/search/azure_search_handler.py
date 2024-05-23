from typing import List
from .search_handler_base import SearchHandlerBase
from ..helpers.llm_helper import LLMHelper
from ..helpers.azure_computer_vision_client import AzureComputerVisionClient
from ..helpers.azure_search_helper import AzureSearchHelper
from ..common.source_document import SourceDocument
import json
from azure.search.documents.models import VectorizedQuery
import tiktoken


class AzureSearchHandler(SearchHandlerBase):
    _ENCODER_NAME = "cl100k_base"

    def __init__(self, env_helper):
        super().__init__(env_helper)
        self.llm_helper = LLMHelper()
        self.azure_computer_vision_client = AzureComputerVisionClient(env_helper)

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
            # Note that images uploaded with advanced image processing do not have a chunk ID
            [json.loads(result["metadata"]).get("chunk", i), result["content"]]
            for i, result in enumerate(results)
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

        if self.env_helper.USE_ADVANCED_IMAGE_PROCESSING:
            vectorized_question = self.azure_computer_vision_client.vectorize_text(
                question
            )
        else:
            vectorized_question = None

        if self.env_helper.AZURE_SEARCH_USE_SEMANTIC_SEARCH:
            results = self._semantic_search(
                question, tokenised_question, vectorized_question
            )
        else:
            results = self._hybrid_search(
                question, tokenised_question, vectorized_question
            )

        return self._convert_to_source_documents(results)

    def _semantic_search(
        self,
        question: str,
        tokenised_question: list[int],
        vectorized_question: list[float] | None,
    ):
        return self.search_client.search(
            search_text=question,
            vector_queries=[
                VectorizedQuery(
                    vector=self.llm_helper.generate_embeddings(tokenised_question),
                    k_nearest_neighbors=self.env_helper.AZURE_SEARCH_TOP_K,
                    fields=self._VECTOR_FIELD,
                ),
                *(
                    [
                        VectorizedQuery(
                            vector=vectorized_question,
                            k_nearest_neighbors=self.env_helper.AZURE_SEARCH_TOP_K,
                            fields=self._IMAGE_VECTOR_FIELD,
                        )
                    ]
                    if vectorized_question is not None
                    else []
                ),
            ],
            filter=self.env_helper.AZURE_SEARCH_FILTER,
            query_type="semantic",
            semantic_configuration_name=self.env_helper.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG,
            query_caption="extractive",
            query_answer="extractive",
            top=self.env_helper.AZURE_SEARCH_TOP_K,
        )

    def _hybrid_search(
        self,
        question: str,
        tokenised_question: list[int],
        vectorized_question: list[float] | None,
    ):
        return self.search_client.search(
            search_text=question,
            vector_queries=[
                VectorizedQuery(
                    vector=self.llm_helper.generate_embeddings(tokenised_question),
                    k_nearest_neighbors=self.env_helper.AZURE_SEARCH_TOP_K,
                    filter=self.env_helper.AZURE_SEARCH_FILTER,
                    fields=self._VECTOR_FIELD,
                ),
                *(
                    [
                        VectorizedQuery(
                            vector=vectorized_question,
                            k_nearest_neighbors=self.env_helper.AZURE_SEARCH_TOP_K,
                            fields=self._IMAGE_VECTOR_FIELD,
                        )
                    ]
                    if vectorized_question is not None
                    else []
                ),
            ],
            query_type="simple",  # this is the default value
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
