from .SearchHandlerBase import SearchHandlerBase
from ..helpers.AzureSearchHelper import AzureSearchHelper
from ..common.SourceDocument import SourceDocument
import json


class AzureSearchHandler(SearchHandlerBase):
    def create_search_client(self):
        vector_store_helper = AzureSearchHelper()
        return vector_store_helper.get_vector_store().client

    def perform_search(self, filename):
        return self.search_client.search(
            "*", select="title, content, metadata", filter=f"title eq '{filename}'"
        )

    def process_results(self, results):
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

    def query_search(self, question):
        vector_store = AzureSearchHelper().get_vector_store()
        return vector_store.similarity_search(
            query=question,
            k=self.env_helper.AZURE_SEARCH_TOP_K,
            filters=self.env_helper.AZURE_SEARCH_FILTER,
        )

    def return_answer_source_documents(self, search_results):
        source_documents = []
        for source in search_results:
            source_documents.append(
                SourceDocument(
                    id=source.metadata["id"],
                    content=source.page_content,
                    title=source.metadata["title"],
                    source=source.metadata["source"],
                    chunk=source.metadata["chunk"],
                    offset=source.metadata["offset"],
                    page_number=source.metadata["page_number"],
                )
            )
        return source_documents
