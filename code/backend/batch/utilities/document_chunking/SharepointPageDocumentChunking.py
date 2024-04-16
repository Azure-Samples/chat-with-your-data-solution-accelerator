import json
from typing import List
from .DocumentChunkingBase import DocumentChunkingBase
from .Strategies import ChunkingSettings
from ..common.SourceDocument import SourceDocument
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    RecursiveJsonSplitter,
)


class SharepointPageDocumentChunking(DocumentChunkingBase):
    def __init__(self) -> None:
        pass

    def chunk(
        self, documents: List[SourceDocument], chunking: ChunkingSettings
    ) -> List[SourceDocument]:
        json_splitter = RecursiveJsonSplitter(max_chunk_size=chunking.chunk_size)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunking.chunk_size,
            chunk_overlap=chunking.chunk_overlap,
            separators=["\n\n"],
        )
        documents_chunked = []
        for document in documents:
            document_url = document.source
            json_content = json.loads(document.content)
            chunked_content_list = text_splitter.split_text(json_content["text"])
            for i in range(len(chunked_content_list)):
                chunked_content_list[i] = {"text": chunked_content_list[i]}

            del json_content["text"]

            chunked_tags_and_title = json_splitter.split_json(
                json_data=json_content, convert_lists=True
            )
            chunked_content_list.extend(chunked_tags_and_title)
            chunk_offset = 0
            for idx, chunked_text_content in enumerate(chunked_content_list):
                documents_chunked.append(
                    SourceDocument.from_metadata(
                        content=json.dumps(chunked_text_content),
                        document_url=document_url,
                        metadata={
                            "offset": chunk_offset,
                            "project_name": document.project_name,
                        },
                        idx=idx,
                    )
                )
                chunk_offset += len(chunked_text_content)
        return documents_chunked
