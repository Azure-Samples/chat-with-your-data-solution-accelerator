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
    keys = document_processor.process(
        document_url,
        Processor(
            Chunking({"strategy": "layout", "size": 500, "overlap": 100}),
            Loading({"strategy": "layout"}),
        ),
    )
    print(keys)
    assert len(keys) == 5


def test_document_processor_read():
    document_processor = DocumentProcessor()
    keys = document_processor.process(
        document_url,
        Processor(
            Chunking({"strategy": "layout", "size": 500, "overlap": 100}),
            Loading({"strategy": "read"}),
        ),
    )
    print(keys)
    assert len(keys) == 5


def test_document_processor_web():
    document_processor = DocumentProcessor()
    keys = document_processor.process(
        url,
        Processor(
            Chunking({"strategy": "layout", "size": 500, "overlap": 100}),
            Loading({"strategy": "web"}),
        ),
    )
    print(keys)
    assert len(keys) == 6
