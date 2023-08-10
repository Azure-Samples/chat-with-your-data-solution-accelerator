from typing import List
from .DocumentChunkingBase import DocumentChunkingBase
from langchain.text_splitter import MarkdownTextSplitter
from .Strategies import ChunkingSettings
from ..common.SourceDocument import SourceDocument

class LayoutDocumentChunking(DocumentChunkingBase):
    def __init__(self) -> None:
        pass
        
    def chunk(self, documents: List[SourceDocument], chunking: ChunkingSettings) -> List[SourceDocument]:
        full_document_content = "".join(list(map(lambda document: document.content, documents)))
        document_url = documents[0].source
        splitter = MarkdownTextSplitter.from_tiktoken_encoder(chunk_size=chunking.chunk_size, chunk_overlap=chunking.chunk_overlap)
        chunked_content_list = splitter.split_text(full_document_content)
        # Create document for each chunk
        documents = []
        chunk_offset = 0
        for idx, chunked_content in enumerate(chunked_content_list):
            documents.append(
                SourceDocument.from_metadata(
                    content=chunked_content,
                    document_url=document_url,
                    metadata={"offset": chunk_offset},
                    idx=idx,
                )
            )       
            
            chunk_offset += len(chunked_content)
        return documents
    