import uuid

from ..common.SourceDocument import SourceDocument
from .DocumentChunkingBase import DocumentChunkingBase


class MockedDocumentChunking(DocumentChunkingBase):
    def __init__(self) -> None:
        pass

    def chunk(self, documents, chunking):
        source_documents = []
        for document in documents:
            source_documents.append(
                SourceDocument.from_metadata(
                    content=document.content,
                    document_url=document.source,
                    idx=0,
                    metadata={'keywords': document.keywords,
                              'title': document.title,
                              'id': str(uuid.uuid4())}
            ))
        return source_documents
