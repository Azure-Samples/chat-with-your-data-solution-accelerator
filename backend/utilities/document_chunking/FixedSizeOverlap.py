from typing import List
from .DocumentChunkingBase import DocumentChunkingBase
from langchain.docstore.document import Document
from langchain.text_splitter import TokenTextSplitter
from .MetadataHelper import MetadataHelper
from .Strategies import ChunkingSettings

class FixedSizeOverlapDocumentChunking(DocumentChunkingBase):
    def __init__(self) -> None:
        pass
        
    def chunk(self, documents: List[Document], chunking: ChunkingSettings) -> List[Document]:    
        metadata_helper = MetadataHelper()
        full_document_content = "".join(list(map(lambda document: document.page_content, documents)))
        document_url = documents[0].metadata['document_url']
        splitter = TokenTextSplitter.from_tiktoken_encoder(chunk_size=chunking.chunk_size, chunk_overlap=chunking.chunk_overlap)
        chunked_content_list = splitter.split_text(full_document_content)
        # Create document for each chunk
        documents = []
        chunk_offset = 0
        for idx, chunked_content in enumerate(chunked_content_list):
            documents.append(Document(page_content=chunked_content, metadata=metadata_helper.generate_metadata_and_key(document_url, idx, metadata={"offset": chunk_offset})))
            chunk_offset += len(chunked_content)
        return documents
