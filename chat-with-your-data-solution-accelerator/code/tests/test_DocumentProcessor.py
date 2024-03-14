import pytest
from backend.batch.utilities.helpers.DocumentProcessorHelper import (
    DocumentProcessor,
)
from backend.batch.utilities.helpers.ConfigHelper import ConfigHelper

document_url = "https://dagrs.berkeley.edu/sites/default/files/2020-01/sample.pdf"
url = "https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search"
docx_url = "https://csciblob.blob.core.windows.net/rag-sol-acc/What is Azure OpenAI Service.docx"


@pytest.mark.azure("This test requires Azure")
def test_document_processor_layout():
    document_processor = DocumentProcessor()
    processors = list(
        filter(
            lambda x: x.document_type == "pdf",
            ConfigHelper.get_active_config_or_default().document_processors,
        )
    )
    keys = document_processor.process(source_url=document_url, processors=processors)
    print(keys)
    assert len(keys) > 0


@pytest.mark.azure("This test requires Azure")
def test_document_processor_read():
    document_processor = DocumentProcessor()
    processors = list(
        filter(
            lambda x: x.document_type == "pdf",
            ConfigHelper.get_active_config_or_default().document_processors,
        )
    )
    keys = document_processor.process(source_url=document_url, processors=processors)
    print(keys)
    assert len(keys) > 0


@pytest.mark.azure("This test requires Azure")
def test_document_processor_web():
    document_processor = DocumentProcessor()
    processors = list(
        filter(
            lambda x: x.document_type == "url",
            ConfigHelper.get_active_config_or_default().document_processors,
        )
    )
    keys = document_processor.process(source_url=url, processors=processors)
    print(keys)
    assert len(keys) > 0


@pytest.mark.azure("This test requires Azure")
def test_document_processor_docx():
    document_processor = DocumentProcessor()
    processors = list(
        filter(
            lambda x: x.document_type == "docx",
            ConfigHelper.get_active_config_or_default().document_processors,
        )
    )
    keys = document_processor.process(source_url=docx_url, processors=processors)
    print(keys)
    assert len(keys) > 0
