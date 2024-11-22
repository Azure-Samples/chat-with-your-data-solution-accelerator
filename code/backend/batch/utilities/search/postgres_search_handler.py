from typing import List
import numpy as np

from .search_handler_base import SearchHandlerBase
from ..helpers.azure_postgres_helper import AzurePostgresHelper
from ..common.source_document import SourceDocument


class AzurePostgresHandler(SearchHandlerBase):

    def __init__(self, env_helper):
        self.azure_postgres_helper = AzurePostgresHelper()
        super().__init__(env_helper)

    def query_search(self, question) -> List[SourceDocument]:
        user_input = question
        query_embedding = self.azure_postgres_helper.llm_helper.generate_embeddings(
            user_input
        )

        embedding_array = np.array(query_embedding).tolist()  # Convert to a list

        conn = self.azure_postgres_helper.get_search_client()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, title, chunk, "offset", page_number, content, source
                FROM search_indexes
                ORDER BY content_vector <=> %s::vector
                LIMIT 3
                """,
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
                    id=source[0],
                    title=source[1],
                    chunk=source[2],
                    offset=source[3],
                    page_number=source[4],
                    content=source[5],
                    source=source[6],
                )
            )
        return source_documents

    def create_search_client(self):
        return self.azure_postgres_helper.get_search_client()

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
