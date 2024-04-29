from ..search.AzureSearchHandler import AzureSearchHandler
from ..search.IntegratedVectorizationSearchHandler import (
    IntegratedVectorizationSearchHandler,
)


class Search:
    @staticmethod
    def get_search_handler(env_helper):
        if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
            return IntegratedVectorizationSearchHandler(env_helper)
        else:
            return AzureSearchHandler(env_helper)
