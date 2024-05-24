from ..search.azure_search_handler import AzureSearchHandler
from ..search.integrated_vectorization_search_handler import (
    IntegratedVectorizationSearchHandler,
)
from ..search.search_handler_base import SearchHandlerBase
from ..common.source_document import SourceDocument
from ..helpers.env_helper import EnvHelper


class Search:
    @staticmethod
    def get_search_handler(env_helper: EnvHelper) -> SearchHandlerBase:
        if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
            return IntegratedVectorizationSearchHandler(env_helper)
        else:
            return AzureSearchHandler(env_helper)

    @staticmethod
    def get_source_documents(
        search_handler: SearchHandlerBase, question: str
    ) -> list[SourceDocument]:
        return search_handler.query_search(question)
