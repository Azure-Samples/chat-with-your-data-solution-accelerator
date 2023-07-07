import pytest
from typing import List
from langchain.docstore.document import Document
from .DocumentProcessor import DocumentProcessor, Processor
from .DocumentLoading import Loading
from .ConfigHelper import Chunking

document_url = "https://csciblob.blob.core.windows.net/rag-sol-acc/cognitive-services.pdf"
url = "https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search"


def test_document_processor_layout():
    document_processor = DocumentProcessor()
    keys = document_processor.process(document_url, "cognitive-services.pdf")
    print(keys)
    assert len(keys) > 0


def test_document_processor_read():
    document_processor = DocumentProcessor()
    keys = document_processor.process(document_url, "cognitive-services.pdf")
    print(keys)
    assert len(keys) > 0


def test_document_processor_web():
    document_processor = DocumentProcessor()
    keys = document_processor.process(url, ".url")
    print(keys)
    assert len(keys) > 0
