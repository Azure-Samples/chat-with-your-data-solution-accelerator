from typing import List
from .DocumentLoadingBase import DocumentLoadingBase
from ..helpers.AzureFormRecognizerHelper import AzureFormRecognizerClient
from ..common.SourceDocument import SourceDocument


class LayoutDocumentLoading(DocumentLoadingBase):
    def __init__(self) -> None:
        super().__init__()

    def load(self, document_url: str) -> List[SourceDocument]:
        """
        Loads the document from the specified URL using layout analysis.

        Args:
            document_url (str): The URL of the document to load.

        Returns:
            List[SourceDocument]: A list of SourceDocument objects representing the loaded pages.
        """
        azure_form_recognizer_client = AzureFormRecognizerClient()
        pages_content = azure_form_recognizer_client.begin_analyze_document_from_url(
            document_url, use_layout=True)
        documents = [
            SourceDocument(
                content=page['page_text'],
                source=document_url,
                offset=page['offset'],
                page_number=page['page_number'],
            )
            for page in pages_content
        ]
        return documents
