import json
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

        embedding_array = np.array(query_embedding).tolist()

        search_results = self.azure_postgres_helper.get_vector_store(embedding_array)

        return self._convert_to_source_documents(search_results)

    def _convert_to_source_documents(self, search_results) -> List[SourceDocument]:
        source_documents = []
        for source in search_results:
            source_documents.append(
                SourceDocument(
                    id=source["id"],
                    title=source["title"],
                    chunk=source["chunk"],
                    offset=source["offset"],
                    page_number=source["page_number"],
                    content=source["content"],
                    source=source["source"],
                )
            )
        return source_documents

    def create_search_client(self):
        return self.azure_postgres_helper.get_search_client()

    def create_vector_store(self, documents_to_upload):
        return self.azure_postgres_helper.create_vector_store(documents_to_upload)

    def perform_search(self, filename):
        return self.azure_postgres_helper.perform_search(filename)

    def process_results(self, results):
        if results is None:
            return []
        data = [
            [json.loads(result["metadata"]).get("chunk", i), result["content"]]
            for i, result in enumerate(results)
        ]
        return data

    def get_files(self):
        results = self.azure_postgres_helper.get_files()
        if results is None or len(results) == 0:
            return []
        return results

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
        self.azure_postgres_helper.delete_documents(ids_to_delete)

        return ", ".join(files_to_delete)

    def search_by_blob_url(self, blob_url):
        return self.azure_postgres_helper.search_by_blob_url(blob_url)

    def delete_from_index(self, blob_url) -> None:
        documents = self.search_by_blob_url(blob_url)
        if documents is None or len(documents) == 0:
            return
        files_to_delete = self.output_results(documents)
        self.delete_files(files_to_delete)

    def get_unique_files(self):
        results = self.azure_postgres_helper.get_unique_files()
        unique_titles = [row["title"] for row in results]
        return unique_titles
