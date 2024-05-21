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

    def search_with_facets(self, query: str, facets: list[str]):
        if self.search_client is None:
            return None
        return self.search_client.search(query, facets=facets)

    def get_unique_files(self, results, facet_key: str):
        if results:
            return [facet["value"] for facet in results.get_facets()[facet_key]]
        return []

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

    def delete_by_source(self, source) -> None:
        if source is None:
            return

        documents = self._get_documents_by_source(source)
        if documents is None:
            return

        files_to_delete = self.output_results(documents)
        self.delete_files(files_to_delete)

    def _get_documents_by_source(self, source):
        if source is None:
            return None

        return self.search_client.search(
            "*",
            select="id, title",
            include_total_count=True,
            filter=f"source eq '{source}'",
        )
