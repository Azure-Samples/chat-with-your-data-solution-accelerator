from typing import List
import numpy as np

from .search_handler_base import SearchHandlerBase
from ..helpers.azure_postgres_helper import AzurePostgresHelper
from ..common.source_document import SourceDocument


class AzurePostgresHandler(SearchHandlerBase):

    def __init__(self, env_helper):
        super().__init__(env_helper)
        self.azure_postgres_helper = AzurePostgresHelper()

    def query_search(self, question) -> List[SourceDocument]:
        user_input = question
        query_embedding = self.azure_postgres_helper.llm_helper.generate_embeddings(
            user_input
        )

        embedding_array = np.array(query_embedding)

        conn = self.azure_postgres_helper.connect()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM search_indexes ORDER BY content_vector <=> %s LIMIT 5",
                (embedding_array,),
            )
            search_results = cur.fetchall()
            return self._convert_to_source_documents(search_results)
        finally:
            conn.close()

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

    def create_search_client(self):
        raise NotImplementedError(
            "The method create_search_client is not implemented in AzurePostgresHandler."
        )

    def perform_search(self, filename):
        raise NotImplementedError(
            "The method perform_search is not implemented in AzurePostgresHandler."
        )

    def process_results(self, results):
        raise NotImplementedError(
            "The method process_results is not implemented in AzurePostgresHandler."
        )

    def get_files(self):
        raise NotImplementedError(
            "The method get_files is not implemented in AzurePostgresHandler."
        )

    def output_results(self, results):
        raise NotImplementedError(
            "The method output_results is not implemented in AzurePostgresHandler."
        )

    def delete_files(self, files):
        raise NotImplementedError(
            "The method delete_files is not implemented in AzurePostgresHandler."
        )

    def search_by_blob_url(self, blob_url):
        raise NotImplementedError(
            "The method search_by_blob_url is not implemented in AzurePostgresHandler."
        )
