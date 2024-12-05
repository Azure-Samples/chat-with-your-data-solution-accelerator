from ..env_helper import EnvHelper
from ..config.database_type import DatabaseType
from ..azure_blob_storage_client import AzureBlobStorageClient
from .push_embedder import PushEmbedder
from .postgres_embedder import PostgresEmbedder
from .integrated_vectorization_embedder import (
    IntegratedVectorizationEmbedder,
)


class EmbedderFactory:
    @staticmethod
    def create(env_helper: EnvHelper):
        if env_helper.DATABASE_TYPE == DatabaseType.POSTGRESQL.value:
            return PostgresEmbedder(AzureBlobStorageClient(), env_helper)
        else:
            if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
                return IntegratedVectorizationEmbedder(env_helper)
            else:
                return PushEmbedder(AzureBlobStorageClient(), env_helper)
