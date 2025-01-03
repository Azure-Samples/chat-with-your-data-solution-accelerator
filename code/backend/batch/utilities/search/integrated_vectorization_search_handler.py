import logging
from typing import List
from .search_handler_base import SearchHandlerBase
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizableTextQuery
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from ..common.source_document import SourceDocument
import re


class IntegratedVectorizationSearchHandler(SearchHandlerBase):
    def create_search_client(self):
        logging.info("Creating Azure Search Client.")
        if self._check_index_exists():
            logging.info("Search index exists. Returning Search Client.")
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
        logging.info(f"Performing search for file: {filename}.")
        if self._check_index_exists():
            return self.search_client.search(
                search_text="*",
                select=["id", "chunk_id", "content"],
                filter=f"title eq '{filename}'",
            )

    def process_results(self, results):
        logging.info("Processing search results.")
        if results is None:
            logging.warning("No results found to process.")
            return []
        data = [
            [re.findall(r"\d+", result["chunk_id"])[-1], result["content"]]
            for result in results
        ]
        logging.info(f"Processed {len(data)} results.")
        return data

    def get_files(self):
        logging.info("Fetching files from search index.")
        if self._check_index_exists():
            return self.search_client.search(
                "*", select="id, chunk_id, title", include_total_count=True
            )

    def output_results(self, results):
        logging.info("Organizing search results into output format.")
        files = {}
        for result in results:
            id = result["chunk_id"]
            filename = result["title"]
            if filename in files:
                files[filename].append(id)
            else:
                files[filename] = [id]
        return files

    def search_by_blob_url(self, blob_url: str):
        logging.info(f"Searching by blob URL: {blob_url}.")
        if self._check_index_exists():
            title = blob_url.split(f"{self.env_helper.AZURE_BLOB_CONTAINER_NAME}/")[1]
            return self.search_client.search(
                "*",
                select="id, chunk_id, title",
                include_total_count=True,
                filter=f"title eq '{title}'",
            )

    def delete_files(self, files):
        logging.info("Deleting files.")
        ids_to_delete = []
        files_to_delete = []

        for filename, ids in files.items():
            files_to_delete.append(filename)
            ids_to_delete += [{"chunk_id": id} for id in ids]

        self.search_client.delete_documents(ids_to_delete)

        logging.info(f"Deleted files: {', '.join(files_to_delete)}.")
        return ", ".join(files_to_delete)

    def query_search(self, question) -> List[SourceDocument]:
        logging.info(f"Querying search for question: {question}.")
        if self._check_index_exists():
            logging.info("Search index exists. Proceeding with search.")
            if self.env_helper.AZURE_SEARCH_USE_SEMANTIC_SEARCH:
                logging.info("Using semantic search.")
                search_results = self._semantic_search(question)
            else:
                logging.info("Using hybrid search.")
                search_results = self._hybrid_search(question)
            logging.info("Search completed. Converting results to SourceDocuments.")
            return self._convert_to_source_documents(search_results)

    def _hybrid_search(self, question: str):
        logging.info(f"Performing hybrid search for question: {question}.")
        vector_query = VectorizableTextQuery(
            text=question,
            k_nearest_neighbors=self.env_helper.AZURE_SEARCH_TOP_K,
            fields=self._VECTOR_FIELD,
            exhaustive=True,
        )
        return self.search_client.search(
            search_text=question,
            vector_queries=[vector_query],
            top=self.env_helper.AZURE_SEARCH_TOP_K,
        )

    def _semantic_search(self, question: str):
        logging.info(f"Performing semantic search for question: {question}.")
        vector_query = VectorizableTextQuery(
            text=question,
            k_nearest_neighbors=self.env_helper.AZURE_SEARCH_TOP_K,
            fields=self._VECTOR_FIELD,
            exhaustive=True,
        )
        return self.search_client.search(
            search_text=question,
            vector_queries=[vector_query],
            filter=self.env_helper.AZURE_SEARCH_FILTER,
            query_type="semantic",
            semantic_configuration_name=self.env_helper.AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG,
            query_caption="extractive",
            query_answer="extractive",
            top=self.env_helper.AZURE_SEARCH_TOP_K,
        )

    def _convert_to_source_documents(self, search_results) -> List[SourceDocument]:
        logging.info("Converting search results to SourceDocument objects.")
        source_documents = []
        for source in search_results:
            source_documents.append(
                SourceDocument(
                    id=source.get("id"),
                    content=source.get("content"),
                    title=source.get("title"),
                    source=self._extract_source_url(source.get("source")),
                    chunk_id=source.get("chunk_id"),
                )
            )
        logging.info("Converted SourceDocument objects.")
        return source_documents

    def _extract_source_url(self, original_source: str) -> str:
        logging.info("Extracting source URL.")
        matches = list(re.finditer(r"https?://", original_source))
        if len(matches) > 1:
            second_http_start = matches[1].start()
            source_url = original_source[second_http_start:]
        else:
            source_url = original_source + "_SAS_TOKEN_PLACEHOLDER_"
        logging.info(f"Extracted source URL: {source_url}.")
        return source_url

    def _check_index_exists(self) -> bool:
        logging.info("Checking if search index exists.")
        search_index_client = SearchIndexClient(
            endpoint=self.env_helper.AZURE_SEARCH_SERVICE,
            credential=(
                AzureKeyCredential(self.env_helper.AZURE_SEARCH_KEY)
                if self.env_helper.is_auth_type_keys()
                else DefaultAzureCredential()
            ),
        )

        exists = self.env_helper.AZURE_SEARCH_INDEX in [
            name for name in search_index_client.list_index_names()
        ]
        logging.info(f"Search index exists: {exists}.")
        return exists
