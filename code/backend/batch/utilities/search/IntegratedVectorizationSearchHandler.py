from .SearchHandlerBase import SearchHandlerBase
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizableTextQuery
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from ..common.SourceDocument import SourceDocument
import re


class IntegratedVectorizationSearchHandler(SearchHandlerBase):
    def create_search_client(self):
        if self._check_index_exists():
            return SearchClient(
                endpoint=self.env_helper.AZURE_SEARCH_SERVICE,
                index_name=self.env_helper.AZURE_SEARCH_INDEX,
                credential=(
                    AzureKeyCredential(self.env_helper.AZURE_SEARCH_KEY)
                    if self.env_helper.is_auth_type_keys()
                    else DefaultAzureCredential()
                ),
            )

    def perform_search(self, filename):
        if self._check_index_exists():
            return self.search_client.search(
                search_text="*",
                select=["id", "chunk_id", "content"],
                filter=f"title eq '{filename}'",
            )

    def process_results(self, results):
        if results is None:
            return []
        data = [
            [re.findall(r"\d+", result["chunk_id"])[-1], result["content"]]
            for result in results
        ]
        return data

    def get_files(self):
        if self._check_index_exists():
            return self.search_client.search(
                "*", select="id, chunk_id, title", include_total_count=True
            )

    def output_results(self, results):
        files = {}
        for result in results:
            id = result["chunk_id"]
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
            ids_to_delete += [{"chunk_id": id} for id in ids]

        self.search_client.delete_documents(ids_to_delete)

        return ", ".join(files_to_delete)

    def query_search(self, question):
        if self._check_index_exists():
            vector_query = VectorizableTextQuery(
                text=question,
                k_nearest_neighbors=self.env_helper.AZURE_SEARCH_TOP_K,
                fields="content_vector",
                exhaustive=True,
            )
            search_results = self.search_client.search(
                search_text=question,
                vector_queries=[vector_query],
                top=self.env_helper.AZURE_SEARCH_TOP_K,
            )
            return search_results

    def return_answer_source_documents(self, search_results):
        source_documents = []
        for source in search_results:
            source_documents.append(
                SourceDocument(
                    id=source.metadata["id"],
                    content=source.page_content,
                    title=source.metadata["title"],
                    source=source.metadata["source"],
                    chunk_id=source.metadata["chunk_id"],
                )
            )
        return source_documents

    def _check_index_exists(self) -> bool:
        search_index_client = SearchIndexClient(
            endpoint=self.env_helper.AZURE_SEARCH_SERVICE,
            credential=(
                AzureKeyCredential(self.env_helper.AZURE_SEARCH_KEY)
                if self.env_helper.is_auth_type_keys()
                else DefaultAzureCredential()
            ),
        )

        return self.env_helper.AZURE_SEARCH_INDEX in [
            name for name in search_index_client.list_index_names()
        ]
