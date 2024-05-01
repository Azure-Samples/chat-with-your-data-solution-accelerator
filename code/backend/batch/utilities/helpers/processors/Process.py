from ..AzureBlobStorageHelper import AzureBlobStorageClient
from .DocumentProcessorHelper import DocumentProcessor
from .IntegratedVectorizationProcessorHelper import (
    IntegratedVectorizationProcessorHelper,
)


class Process:
    @staticmethod
    def get_processor_handler(env_helper):
        if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
            return IntegratedVectorizationProcessorHelper(env_helper)
        else:
            return DocumentProcessor(AzureBlobStorageClient())
