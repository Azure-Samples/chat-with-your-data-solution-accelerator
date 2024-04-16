import uuid
from .DocumentChunkingBase import DocumentChunkingBase


class MockedDocumentChunking(DocumentChunkingBase):
    def __init__(self) -> None:
        pass

    def chunk(self, documents, chunking):
        for document in documents:
            if not document.id or document.id == "":
                document.id = str(uuid.uuid4())

        return documents
