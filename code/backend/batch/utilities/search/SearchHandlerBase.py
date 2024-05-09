from abc import ABC, abstractmethod
from ..helpers.EnvHelper import EnvHelper

from ..common.SourceDocument import SourceDocument


class SearchHandlerBase(ABC):
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
    def create_search_client(self):
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
    def output_results(self, results, id_field):
        pass

    @abstractmethod
    def delete_files(self, files, id_field):
        pass

    @abstractmethod
    def query_search(self, question) -> list[SourceDocument]:
        pass
