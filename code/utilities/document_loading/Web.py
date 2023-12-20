from typing import List
import re
from langchain.docstore.document import Document
from langchain.document_loaders import WebBaseLoader
from .DocumentLoadingBase import DocumentLoadingBase
from ..common.SourceDocument import SourceDocument


class WebDocumentLoading(DocumentLoadingBase):
    """
    This class represents a web document loader that inherits from DocumentLoadingBase.
    It provides methods to load web documents and process their content.
    """

    def __init__(self) -> None:
        super().__init__()

    def load(self, document_url: str) -> List[SourceDocument]:
        """
        Loads web documents from the specified URL and processes their content.

        Args:
            document_url (str): The URL of the web document.

        Returns:
            List[SourceDocument]: A list of SourceDocument objects containing the processed content of the web documents.
        """
        documents: List[Document] = WebBaseLoader(document_url).load()
        for document in documents:
            document.page_content = re.sub(
                '\n{3,}', '\n\n', document.page_content)
            # Remove half non-ascii character from start/end of doc content
            pattern = re.compile(
                r"[\x00-\x1f\x7f\u0080-\u00a0\u2000-\u3000\ufff0-\uffff]"
            )
            document.page_content = re.sub(pattern, "", document.page_content)
            if document.page_content == "":
                documents.remove(document)
        source_documents: List[SourceDocument] = [
            SourceDocument(
                content=document.page_content,
                source=document.metadata['source'],
            )
            for document in documents
        ]
        return source_documents
