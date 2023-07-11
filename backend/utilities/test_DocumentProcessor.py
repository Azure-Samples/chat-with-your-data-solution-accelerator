import pytest
from .DocumentProcessor import DocumentProcessor
from .ConfigHelper import ConfigHelper

document_url = "https://csciblob.blob.core.windows.net/rag-sol-acc/cognitive-services.pdf"
url = "https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search"


def test_document_processor_layout():
    document_processor = DocumentProcessor()
    processors = list(filter(lambda x : x.document_type == 'pdf', ConfigHelper.get_active_config_or_default().document_processors))
    keys = document_processor.process(source_url= document_url, processors=processors)
    print(keys)
    assert len(keys) > 0


def test_document_processor_read():
    document_processor = DocumentProcessor()
    processors = list(filter(lambda x : x.document_type == 'pdf', ConfigHelper.get_active_config_or_default().document_processors))
    keys = document_processor.process(source_url= document_url, processors=processors)
    print(keys)
    assert len(keys) > 0


def test_document_processor_web():
    document_processor = DocumentProcessor()
    processors = list(filter(lambda x : x.document_type == 'url', ConfigHelper.get_active_config_or_default().document_processors))
    keys = document_processor.process(source_url= url, processors=processors)    
    print(keys)
    assert len(keys) > 0
