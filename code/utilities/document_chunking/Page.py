from typing import List
from .DocumentChunkingBase import DocumentChunkingBase
from langchain.text_splitter import MarkdownTextSplitter
from .Strategies import ChunkingSettings
from ..common.SourceDocument import SourceDocument


class PageDocumentChunking(DocumentChunkingBase):
    """
    A class that implements document chunking based on specified settings.

    Attributes:
        None

    Methods:
        chunk(documents: List[SourceDocument], chunking: ChunkingSettings) -> List[SourceDocument]:
            Chunk the given list of SourceDocuments into smaller chunks based on the specified chunking settings.
    """
    
    def __init__(self) -> None:
        super().__init__()

    def chunk(self, documents: List[SourceDocument], chunking: ChunkingSettings) -> List[SourceDocument]:
        """
        Chunk the given list of SourceDocuments into smaller chunks based on the specified chunking settings.

        Args:
            documents (List[SourceDocument]): The list of SourceDocuments to be chunked.
            chunking (ChunkingSettings): The chunking settings specifying the chunk size and overlap.

        Returns:
            List[SourceDocument]: The list of chunked SourceDocuments.
        """
        document_url = documents[0].source
        splitter = MarkdownTextSplitter.from_tiktoken_encoder(
            chunk_size=chunking.chunk_size, chunk_overlap=chunking.chunk_overlap)
        documents_chunked = []
        for idx, document in enumerate(documents):
            chunked_content_list = splitter.split_text(document.content)
            for chunked_content in chunked_content_list:
                documents_chunked.append(
                    SourceDocument.from_metadata(
                        content=chunked_content,
                        document_url=document_url,
                        metadata={"offset": document.offset,
                                  "page_number": document.page_number},
                        idx=idx,
                    )
                )
        return documents_chunked
