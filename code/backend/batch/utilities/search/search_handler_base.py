from abc import ABC, abstractmethod
from ..helpers.env_helper import EnvHelper
from ..common.source_document import SourceDocument
from azure.search.documents import SearchClient


class SearchHandlerBase(ABC):
    _VECTOR_FIELD = "content_vector"
    _IMAGE_VECTOR_FIELD = "image_vector"

    def __init__(self, env_helper: EnvHelper):
        self.env_helper = env_helper
        self.search_client = self.create_search_client()

    def search_with_facets(self, query: str, facet: str, facet_count: int):
        if self.search_client is None:
            return None

        # Construct facet parameter based on facet_count
        facet_param = f"{facet},count:{facet_count}"

        # Perform search with facets and facet_param
        return self.search_client.search(query, facets=[facet_param])

    def get_unique_files(self, results, facet_key: str):
        if results:
            return [facet["value"] for facet in results.get_facets()[facet_key]]
        return []

    def delete_from_index(self, blob_url) -> None:
        documents = self.search_by_blob_url(blob_url)
        if documents is None or documents.get_count() == 0:
            return
        files_to_delete = self.output_results(documents)
        self.delete_files(files_to_delete)

    @abstractmethod
    def create_search_client(self) -> SearchClient:
        pass

    @abstractmethod
    def perform_search(self, filename):
        pass

    @abstractmethod
    def process_results(self, results):
        pass

    @abstractmethod
    def get_files(self):
        pass

    @abstractmethod
    def output_results(self, results):
        pass

    @abstractmethod
    def delete_files(self, files):
        pass

    @abstractmethod
    def query_search(self, question) -> list[SourceDocument]:
        pass

    @abstractmethod
    def search_by_blob_url(self, blob_url):
        pass
