from typing import List
from langchain.docstore.document import Document
from .DocumentChunkingBase import DocumentChunkingBase
from .MetadataHelper import MetadataHelper
from .Strategies import ChunkingSettings

class ParagraphDocumentChunking(DocumentChunkingBase):
    def __init__(self) -> None:
        pass
    
    # TO DO: Implement the following chunking strategies
    def chunk(self, documents: List[Document], chunking: ChunkingSettings) -> List[Document]:
        raise NotImplementedError("Paragraph chunking is not implemented yet")
