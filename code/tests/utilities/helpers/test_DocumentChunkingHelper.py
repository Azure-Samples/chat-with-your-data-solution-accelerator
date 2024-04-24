from backend.batch.utilities.common.SourceDocument import SourceDocument
from backend.batch.utilities.helpers.DocumentChunkingHelper import (
    DocumentChunking,
    ChunkingSettings,
    ChunkingStrategy,
)

# Create a sample document
documents = [
    SourceDocument(
        content="PAGE 1: This short sentence with 20 tokens shows how the different chunking strategies work now!",
        source="https://example.com/sample_document.pdf",
        offset=0,
        page_number=1,
    ),
    SourceDocument(
        content="PAGE 2: This short sentence with 20 tokens shows how the different chunking strategies work now!",
        source="https://example.com/sample_document_1.pdf",
        offset=0,
        page_number=2,
    ),
]


def test_document_chunking_layout():
    # Test layout chunking strategy
    chunking = ChunkingSettings(
        {"strategy": ChunkingStrategy.LAYOUT, "size": 10, "overlap": 5}
    )
    document_chunking = DocumentChunking()
    chunked_documents = document_chunking.chunk(documents, chunking)
    assert len(chunked_documents) == 8
    assert chunked_documents[0].content == "PAGE 1: This short sentence with 20 tokens"
    assert (
        chunked_documents[1].content
        == "short sentence with 20 tokens shows how the different"
    )
    assert (
        chunked_documents[2].content
        == "tokens shows how the different chunking strategies work"
    )
    assert chunked_documents[3].content == "different chunking strategies work now!PAGE"
    assert chunked_documents[4].content == "work now!PAGE 2: This short sentence"
    assert (
        chunked_documents[5].content
        == "2: This short sentence with 20 tokens shows how"
    )
    assert (
        chunked_documents[6].content
        == "with 20 tokens shows how the different chunking strategies"
    )
    assert chunked_documents[7].content == "the different chunking strategies work now!"


def test_document_chunking_page():
    # Test page chunking strategy
    chunking = ChunkingSettings(
        {"strategy": ChunkingStrategy.PAGE, "size": 10, "overlap": 5}
    )
    document_chunking = DocumentChunking()
    chunked_documents = document_chunking.chunk(documents, chunking)
    assert len(chunked_documents) == 8
    assert chunked_documents[0].content == "PAGE 1: This short sentence with 20 tokens"
    assert (
        chunked_documents[1].content
        == "short sentence with 20 tokens shows how the different"
    )
    assert (
        chunked_documents[2].content
        == "tokens shows how the different chunking strategies work"
    )
    assert chunked_documents[3].content == "different chunking strategies work now!"
    assert chunked_documents[4].content == "PAGE 2: This short sentence with 20 tokens"
    assert (
        chunked_documents[5].content
        == "short sentence with 20 tokens shows how the different"
    )
    assert (
        chunked_documents[6].content
        == "tokens shows how the different chunking strategies work"
    )
    assert chunked_documents[7].content == "different chunking strategies work now!"


def test_document_chunking_fixed_size_overlap():
    # Test fixed size overlap chunking strategy
    chunking = ChunkingSettings(
        {"strategy": ChunkingStrategy.FIXED_SIZE_OVERLAP, "size": 10, "overlap": 5}
    )
    document_chunking = DocumentChunking()
    chunked_documents = document_chunking.chunk(documents, chunking)
    assert len(chunked_documents) == 7
    assert chunked_documents[0].content == "PAGE 1: This short sentence with 20 tokens"
    assert (
        chunked_documents[1].content
        == " short sentence with 20 tokens shows how the different chunk"
    )
    assert (
        chunked_documents[2].content
        == " shows how the different chunking strategies work now!"
    )
    assert chunked_documents[3].content == "ing strategies work now!PAGE 2: This"
    assert chunked_documents[4].content == "PAGE 2: This short sentence with 20 tokens"
    assert (
        chunked_documents[5].content
        == " short sentence with 20 tokens shows how the different chunk"
    )
    assert (
        chunked_documents[6].content
        == " shows how the different chunking strategies work now!"
    )
