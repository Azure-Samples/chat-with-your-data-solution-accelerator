import requests
import tempfile

from typing import List
from langchain.docstore.document import Document
from langchain_community.document_loaders.json_loader import JSONLoader
from .DocumentLoadingBase import DocumentLoadingBase
from ..common.SourceDocument import SourceDocument


class JsonDocumentLoading(DocumentLoadingBase):
    def __init__(self) -> None:
        super().__init__()

    def load(self, document_url: str) -> List[SourceDocument]:
        response = requests.get(document_url)
        temp = tempfile.NamedTemporaryFile()
        with open(temp.name, 'w') as file:
            file.write(response.text)

        documents: List[Document] = JSONLoader(file_path=temp.name, jq_schema=".pages[]", text_content=False).load()
        for document in documents:
            if document.page_content == "":
                documents.remove(document)
        source_documents: List[SourceDocument] = [
            SourceDocument(
                content=document.page_content,
                source=document.metadata["source"],
            )
            for document in documents
        ]
        return source_documents
