from typing import List
from .DocumentChunkingBase import DocumentChunkingBase
from langchain.text_splitter import MarkdownTextSplitter
from .ChunkingStrategy import ChunkingSettings
from ..common.SourceDocument import SourceDocument


class PageDocumentChunking(DocumentChunkingBase):
    def __init__(self) -> None:
        pass

    def chunk(
        self, documents: List[SourceDocument], chunking: ChunkingSettings
    ) -> List[SourceDocument]:
        document_url = documents[0].source
        splitter = MarkdownTextSplitter.from_tiktoken_encoder(
            chunk_size=chunking.chunk_size, chunk_overlap=chunking.chunk_overlap
        )
        documents_chunked = []
        for idx, document in enumerate(documents):
            chunked_content_list = splitter.split_text(document.content)
            for chunked_content in chunked_content_list:
                documents_chunked.append(
                    SourceDocument.from_metadata(
                        content=chunked_content,
                        document_url=document_url,
                        metadata={
                            "offset": document.offset,
                            "page_number": document.page_number,
                        },
                        idx=idx,
                    )
                )
        return documents_chunked
