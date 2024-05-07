from ..EnvHelper import EnvHelper
from ..AzureBlobStorageClient import AzureBlobStorageClient
from .PushEmbedder import PushEmbedder
from .IntegratedVectorizationEmbedder import (
    IntegratedVectorizationEmbedder,
)


class EmbedderFactory:
    @staticmethod
    def create(env_helper: EnvHelper):
        if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
            return IntegratedVectorizationEmbedder(env_helper)
        else:
            return PushEmbedder(AzureBlobStorageClient())
