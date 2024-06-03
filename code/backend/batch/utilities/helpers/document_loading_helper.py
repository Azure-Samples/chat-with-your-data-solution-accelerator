from typing import List

from ..common.source_document import SourceDocument
from ..document_loading import LoadingSettings
from ..document_loading.strategies import get_document_loader


class DocumentLoading:
    def __init__(self) -> None:
        pass

    def load(self, document_url: str, loading: LoadingSettings) -> List[SourceDocument]:
        loader = get_document_loader(loading.loading_strategy.value)
        if loader is None:
            raise Exception(
                f"Unknown loader strategy: {loading.loading_strategy.value}"
            )
        return loader.load(document_url)
