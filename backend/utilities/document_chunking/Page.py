from typing import List
from .DocumentChunkingBase import DocumentChunkingBase
from langchain.docstore.document import Document
from langchain.text_splitter import MarkdownTextSplitter
from .MetadataHelper import MetadataHelper
from .Strategies import ChunkingSettings

class PageDocumentChunking(DocumentChunkingBase):
    def __init__(self) -> None:
        pass
        
    def chunk(self, documents: List[Document], chunking: ChunkingSettings) -> List[Document]:
        metadata_helper = MetadataHelper()
        document_url = documents[0].metadata['document_url']
        splitter = MarkdownTextSplitter.from_tiktoken_encoder(chunk_size=chunking.chunk_size, chunk_overlap=chunking.chunk_overlap)
        documents_chunked = []
        for idx, document in enumerate(documents):
            chunked_content_list = splitter.split_text(document.page_content)
            for chunked_content in chunked_content_list:
                documents_chunked.append(Document(page_content=chunked_content, metadata=metadata_helper.generate_metadata_and_key(document_url, idx, metadata={"offset": document.metadata['offset'], "page_number": document.metadata['page_number']})))
        return documents_chunked    
    