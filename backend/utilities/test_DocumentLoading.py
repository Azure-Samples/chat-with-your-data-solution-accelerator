import pytest
from typing import List
from .DocumentLoading import DocumentLoading, LoadingSettings


def test_document_loading_layout():
    # Azure Form Recognizer Layout
    document_loading = DocumentLoading()
    url = "https://csciblob.blob.core.windows.net/rag-sol-acc/cognitive-services.pdf"
    data = document_loading.load(url, LoadingSettings({"strategy": "layout"}))
    assert len(data) == 5
    assert data[0].metadata["document_url"] == url
    assert data[0].metadata["page_number"] == 0
    assert data[0].metadata["offset"] == 0
    assert data[4].metadata["page_number"] == 4
    assert data[0].metadata["document_url"] == url

def test_document_loading_read():
    # Azure Form Recognizer Read
    document_loading = DocumentLoading()
    url = "https://csciblob.blob.core.windows.net/rag-sol-acc/cognitive-services.pdf"
    data = document_loading.load(url, LoadingSettings({"strategy": "read"}))
    assert len(data) == 5
    assert data[0].metadata["document_url"] == url
    assert data[0].metadata["page_number"] == 0
    assert data[0].metadata["offset"] == 0
    assert data[4].metadata["page_number"] == 4
    assert data[0].metadata["document_url"] == url
    
def test_document_loading_web():
    # WebLoad
    document_loading = DocumentLoading()
    url = "https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search"
    data = document_loading.load(url, LoadingSettings({"strategy": "web"}))
    assert len(data) == 1
    assert data[0].metadata["document_url"] == url