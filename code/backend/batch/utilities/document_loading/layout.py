from typing import List
from .document_loading_base import DocumentLoadingBase
from ..helpers.azure_form_recognizer_helper import AzureFormRecognizerClient
from ..common.source_document import SourceDocument


class LayoutDocumentLoading(DocumentLoadingBase):
    def __init__(self) -> None:
        super().__init__()

    def load(self, document_url: str) -> List[SourceDocument]:
        azure_form_recognizer_client = AzureFormRecognizerClient()
        pages_content = azure_form_recognizer_client.begin_analyze_document_from_url(
            document_url, use_layout=True
        )
        documents = [
            SourceDocument(
                content=page["page_text"],
                source=document_url,
                offset=page["offset"],
                page_number=page["page_number"],
            )
            for page in pages_content
        ]
        return documents
