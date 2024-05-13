from ..env_helper import EnvHelper
from ..azure_blob_storage_client import AzureBlobStorageClient
from .push_embedder import PushEmbedder
from .integrated_vectorization_embedder import (
    IntegratedVectorizationEmbedder,
)


class EmbedderFactory:
    @staticmethod
    def create(env_helper: EnvHelper):
        if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
            return IntegratedVectorizationEmbedder(env_helper)
        else:
            return PushEmbedder(AzureBlobStorageClient())
