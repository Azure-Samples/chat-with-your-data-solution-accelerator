from typing import List
from .DocumentChunkingBase import DocumentChunkingBase
from .Strategies import ChunkingSettings
from ..common.SourceDocument import SourceDocument
from langchain.text_splitter import RecursiveCharacterTextSplitter


class SharepointPageDocumentChunking(DocumentChunkingBase):
    def __init__(self) -> None:
        pass

    def chunk(
        self, documents: List[SourceDocument], chunking: ChunkingSettings
    ) -> List[SourceDocument]:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunking.chunk_size,
            chunk_overlap=chunking.chunk_overlap,
            separators=["\n\n"],
        )
        documents_chunked = []
        for document in documents:
            document_url = document.source
            chunked_content_list = text_splitter.split_text(document.content)

            chunk_offset = 0
            for idx, chunked_text_content in enumerate(chunked_content_list):
                documents_chunked.append(
                    SourceDocument.from_metadata(
                        content=chunked_text_content,
                        document_url=document_url,
                        metadata={
                            "offset": chunk_offset,
                            "project_name": document.project_name,
                            "keywords": document.keywords,
                        },
                        idx=idx,
                    )
                )
                chunk_offset += len(chunked_text_content)
        return documents_chunked
