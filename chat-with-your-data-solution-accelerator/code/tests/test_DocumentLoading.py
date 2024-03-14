import pytest
from backend.batch.utilities.helpers.DocumentLoadingHelper import (
    DocumentLoading,
    LoadingSettings,
)


@pytest.mark.azure("This test requires Azure Document Intelligence configured")
def test_document_loading_layout():
    # Azure Form Recognizer Layout
    document_loading = DocumentLoading()
    url = "https://dagrs.berkeley.edu/sites/default/files/2020-01/sample.pdf"
    data = document_loading.load(url, LoadingSettings({"strategy": "layout"}))
    assert len(data) == 10
    assert data[0].source == url
    assert data[0].page_number == 0
    assert data[0].offset == 0
    assert data[9].page_number == 9
    assert data[9].source == url


@pytest.mark.azure("This test requires Azure Document Intelligence configured")
def test_document_loading_read():
    # Azure Form Recognizer Read
    document_loading = DocumentLoading()
    url = "https://dagrs.berkeley.edu/sites/default/files/2020-01/sample.pdf"
    data = document_loading.load(url, LoadingSettings({"strategy": "read"}))
    assert len(data) == 10
    assert data[0].source == url
    assert data[0].page_number == 0
    assert data[0].offset == 0
    assert data[9].page_number == 9
    assert data[9].source == url


def test_document_loading_web():
    # WebLoad
    document_loading = DocumentLoading()
    url = "https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search"
    data = document_loading.load(url, LoadingSettings({"strategy": "web"}))
    assert len(data) == 1
    assert data[0].source == url


@pytest.mark.azure("This test requires Azure Document Intelligence configured")
def test_document_loading_docx():
    document_loading = DocumentLoading()
    url = "https://csciblob.blob.core.windows.net/rag-sol-acc/What is Azure OpenAI Service.docx"
    data = document_loading.load(url, LoadingSettings({"strategy": "docx"}))
    assert len(data) == 1
    assert data[0].source == url
    print(data[0].content)
