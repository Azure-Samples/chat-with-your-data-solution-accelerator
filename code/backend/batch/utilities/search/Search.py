from ..search.AzureSearchHandler import AzureSearchHandler
from ..search.IntegratedVectorizationSearchHandler import (
    IntegratedVectorizationSearchHandler,
)
from langchain_core.documents import Document
import re
from ..helpers.EnvHelper import EnvHelper


class Search:
    @staticmethod
    def get_search_handler(env_helper: EnvHelper):
        if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
            return IntegratedVectorizationSearchHandler(env_helper)
        else:
            return AzureSearchHandler(env_helper)

    @staticmethod
    def get_source_documents(search_handler, question):
        if isinstance(search_handler, IntegratedVectorizationSearchHandler):
            search_results = search_handler.query_search(question)
            return Search.generate_source_documents(search_results)
        else:
            return search_handler.query_search(question)

    @staticmethod
    def generate_source_documents(search_results):
        sources = []
        for result in search_results:
            source_url = Search._extract_source_url(result.get("source", ""))

            metadata_dict = {
                "id": result.get("id", ""),
                "title": result.get("title", ""),
                "source": source_url,
                "chunk_id": result.get("chunk_id", ""),
            }
            sources.append(
                Document(
                    page_content=result["content"],
                    metadata=metadata_dict,
                )
            )
        return sources

    @staticmethod
    def _extract_source_url(original_source):
        matches = list(re.finditer(r"https?://", original_source))
        if len(matches) > 1:
            second_http_start = matches[1].start()
            source_url = original_source[second_http_start:]
        else:
            source_url = original_source + "_SAS_TOKEN_PLACEHOLDER_"
        return source_url
