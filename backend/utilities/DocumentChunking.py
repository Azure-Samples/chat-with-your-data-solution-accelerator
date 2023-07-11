from typing import List, Optional
from enum import Enum
import hashlib
from urllib.parse import urlparse
from langchain.docstore.document import Document
from langchain.text_splitter import MarkdownTextSplitter, TokenTextSplitter


class ChunkingStrategy(Enum):
    LAYOUT = 'layout'
    PAGE = 'page'
    FIXED_SIZE_OVERLAP = 'fixed_size_overlap'
    PARAGRAPH = 'paragraph'

class Chunking:
    def __init__(self, chunking:dict):
        self.chunking_strategy = ChunkingStrategy(chunking['strategy'])
        self.chunk_size = chunking['size']
        self.chunk_overlap = chunking['overlap']

class DocumentChunking:
    def __init__(self) -> None:
        pass
    
    def chunk(self, documents: List[Document], chunking: Chunking) -> List[Document]:
        if chunking.chunking_strategy == ChunkingStrategy.LAYOUT:
            return self.layout_chunk(documents, chunking)
        elif chunking.chunking_strategy == ChunkingStrategy.PAGE:
            return self.page_chunk(documents, chunking)
        elif chunking.chunking_strategy == ChunkingStrategy.FIXED_SIZE_OVERLAP:
            return self.fixed_size_overlap_chunk(documents, chunking)
        elif chunking.chunking_strategy == ChunkingStrategy.PARAGRAPH:
            return self.paragraph_chunk(documents, chunking)
        else:
            raise Exception(f"Unknown chunking strategy: {chunking.chunking_strategy}")
        
    def _generate_metadata_and_key(self, document_url: str, idx: int, metadata: dict = {}) -> dict:
        parsed_url = urlparse(document_url)
        file_url = parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path
        filename = parsed_url.path
        hash_key = hashlib.sha1(f"{file_url}_{idx}".encode("utf-8")).hexdigest()
        hash_key = f"doc_{hash_key}"
        sas_placeholder = "_SAS_TOKEN_PLACEHOLDER_" if 'blob.core.windows.net' in parsed_url.netloc else ""
        source = f"[{file_url}]({file_url}{sas_placeholder})"
        metadata.update({"source": f"{filename}#{idx}", "markdown_url": source, "chunk": idx, "key": hash_key, "filename": filename,"title": filename, "original_url": file_url})
        return metadata
                    
    def layout_chunk(self, documents: List[Document], chunking: Chunking) -> List[Document]:
        full_document_content = "".join(list(map(lambda document: document.page_content, documents)))
        document_url = documents[0].metadata['document_url']
        splitter = MarkdownTextSplitter.from_tiktoken_encoder(chunk_size=chunking.chunk_size, chunk_overlap=chunking.chunk_overlap)
        chunked_content_list = splitter.split_text(full_document_content)
        # Create document for each chunk
        documents = []
        chunk_offset = 0
        for idx, chunked_content in enumerate(chunked_content_list):
            documents.append(Document(page_content=chunked_content, metadata=self._generate_metadata_and_key(document_url, idx, metadata={"offset": chunk_offset})))
            chunk_offset += len(chunked_content)
        return documents
    
    def page_chunk(self, documents: List[Document], chunking: Chunking) -> List[Document]:
        document_url = documents[0].metadata['document_url']
        splitter = MarkdownTextSplitter.from_tiktoken_encoder(chunk_size=chunking.chunk_size, chunk_overlap=chunking.chunk_overlap)
        documents_chunked = []
        for idx, document in enumerate(documents):
            chunked_content_list = splitter.split_text(document.page_content)
            for chunked_content in chunked_content_list:
                documents_chunked.append(Document(page_content=chunked_content, metadata=self._generate_metadata_and_key(document_url, idx, metadata={"offset": document.metadata['offset'], "page_number": document.metadata['page_number']})))
        return documents_chunked    

    def fixed_size_overlap_chunk(self, documents: List[Document], chunking: Chunking) -> List[Document]:    
        full_document_content = "".join(list(map(lambda document: document.page_content, documents)))
        document_url = documents[0].metadata['document_url']
        splitter = TokenTextSplitter.from_tiktoken_encoder(chunk_size=chunking.chunk_size, chunk_overlap=chunking.chunk_overlap)
        chunked_content_list = splitter.split_text(full_document_content)
        # Create document for each chunk
        documents = []
        chunk_offset = 0
        for idx, chunked_content in enumerate(chunked_content_list):
            documents.append(Document(page_content=chunked_content, metadata=self._generate_metadata_and_key(document_url, idx, metadata={"offset": chunk_offset})))
            chunk_offset += len(chunked_content)
        return documents

    # TO DO: Implement the following chunking strategies
    def paragraph_chunk(self, documents: List[Document], chunking: Chunking) -> List[Document]:
        raise NotImplementedError("Paragraph chunking is not implemented yet")
    