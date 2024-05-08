import hashlib
from unittest.mock import patch
from urllib.parse import urlparse
from backend.batch.utilities.common.SourceDocument import (
    SourceDocument,
    SourceDocumentDecoder,
    SourceDocumentEncoder,
)


def test_convert_to_langchain_document():
    # Given
    source_document = SourceDocument(
        id="1",
        content="Some content",
        title="A title",
        source="A source",
        chunk="A chunk",
        offset="An offset",
        page_number="1",
        chunk_id="abcd",
    )

    # When
    langchain_document = source_document.convert_to_langchain_document()

    # Then
    assert langchain_document.page_content == "Some content"
    assert langchain_document.metadata == {
        "id": "1",
        "source": "A source",
        "title": "A title",
        "chunk": "A chunk",
        "offset": "An offset",
        "page_number": "1",
        "chunk_id": "abcd",
    }


def test_get_filename():
    # Given
    source_document = SourceDocument(
        id="1",
        content="Some content",
        title="A title",
        source="http://example.com/path/to/file.txt_SAS_TOKEN_PLACEHOLDER_",
        chunk="A chunk",
        offset="An offset",
        page_number="1",
    )

    # When
    filename = source_document.get_filename()

    # Then
    assert filename == "file"


@patch("backend.batch.utilities.common.SourceDocument.AzureBlobStorageClient")
def test_get_markdown_url(azure_blob_service_mock):
    # Given
    azure_blob_service_mock().get_container_sas.return_value = "_12345"
    source_document = SourceDocument(
        id="1",
        content="Some content",
        title="A title",
        source="http://example.com/path/to/file.txt_SAS_TOKEN_PLACEHOLDER_",
        chunk="A chunk",
        offset="An offset",
        page_number="1",
    )

    # When
    markdown_url = source_document.get_markdown_url()

    # Then
    assert markdown_url == "[A title](http://example.com/path/to/file.txt_12345)"


def test_from_metadata_returns_empty_sas_placeholder():
    # Given
    content = "Some content"
    metadata = {}
    # blob.core.windows.net needs to be the domain name - not a faked one as per CWE-20
    document_url = "http://blob.core.windows.net.example.com/path/to/file.txt"
    expectedFileName = "/path/to/file.txt"
    idx = 0

    # When
    source_document = SourceDocument.from_metadata(content, metadata, document_url, idx)

    # Then
    parsed_url = urlparse(document_url)
    file_url = parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path
    hash_key = hashlib.sha1(f"{file_url}_{idx}".encode("utf-8")).hexdigest()
    hash_key = f"doc_{hash_key}"

    assert source_document.id == hash_key
    assert source_document.content == content
    assert source_document.source == document_url
    assert source_document.title == expectedFileName
    assert source_document.chunk == idx
    assert source_document.offset is None
    assert source_document.page_number is None


def test_from_metadata_returns_sas_placeholder():
    # Given
    content = "Some content"
    metadata = {}
    document_url = "http://example.blob.core.windows.net/path/to/file.txt"
    expectedFileName = "/path/to/file.txt"
    expected_sas_placeholder = "_SAS_TOKEN_PLACEHOLDER_"
    idx = 0

    # When
    source_document = SourceDocument.from_metadata(content, metadata, document_url, idx)

    # Then
    parsed_url = urlparse(document_url)
    file_url = parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path
    hash_key = hashlib.sha1(f"{file_url}_{idx}".encode("utf-8")).hexdigest()
    hash_key = f"doc_{hash_key}"

    assert source_document.id == hash_key
    assert source_document.content == content
    assert source_document.source == f"{file_url}{expected_sas_placeholder}"
    assert source_document.title == expectedFileName
    assert source_document.chunk == idx
    assert source_document.offset is None
    assert source_document.page_number is None


def test_from_metadata():
    # Given
    content = "Some content"
    metadata = {
        "id": "1",
        "source": "http://example.com/path/to/file.txt",
        "title": "A title",
        "chunk": "A chunk",
        "offset": "An offset",
        "page_number": "1",
    }
    document_url = "http://example.com/path/to/file.txt"
    idx = 0

    # When
    source_document = SourceDocument.from_metadata(content, metadata, document_url, idx)

    # Then
    parsed_url = urlparse(document_url)
    file_url = parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path
    filename = parsed_url.path
    hash_key = hashlib.sha1(f"{file_url}_{idx}".encode("utf-8")).hexdigest()
    hash_key = f"doc_{hash_key}"

    expected_source_document = SourceDocument(
        id=metadata.get("id", hash_key),
        content=content,
        source=metadata.get("source", document_url),
        title=metadata.get("title", filename),
        chunk=metadata.get("chunk", idx),
        offset=metadata.get("offset"),
        page_number=metadata.get("page_number"),
    )
    assert source_document.id == expected_source_document.id
    assert source_document.content == expected_source_document.content
    assert source_document.source == expected_source_document.source
    assert source_document.title == expected_source_document.title
    assert source_document.chunk == expected_source_document.chunk
    assert source_document.offset == expected_source_document.offset
    assert source_document.page_number == expected_source_document.page_number


def test_default_method_returns_expected_dict():
    # Given
    source_document = SourceDocument(
        id="1",
        content="Some content",
        title="A title",
        source="A source",
        chunk="A chunk",
        offset="An offset",
        page_number="1",
        chunk_id="abcd",
    )

    # When
    result = SourceDocumentEncoder().default(source_document)

    # Then
    assert isinstance(result, dict)

    # Then
    expected_dict = {
        "id": "1",
        "content": "Some content",
        "source": "A source",
        "title": "A title",
        "chunk": "A chunk",
        "offset": "An offset",
        "page_number": "1",
        "chunk_id": "abcd",
    }
    assert result == expected_dict


def test_default_method_calls_super_default():
    # Given
    source_document = SourceDocument(
        id="1",
        content="Some content",
        title="A title",
        source="A source",
        chunk="A chunk",
        offset="An offset",
        page_number="1",
    )

    # When
    with patch.object(SourceDocumentEncoder, "default") as super_default_mock:
        SourceDocumentEncoder.default(source_document)

    # Then
    super_default_mock.assert_called_once_with(source_document)


def test_decode_method_returns_expected_source_document():
    # Given
    obj = '{"id": "1","content": "Some content","source": "A source","title": "A title","chunk": "A chunk","offset": "An offset","page_number": "1", "chunk_id": "abcd"}'

    # When
    result = SourceDocumentDecoder().decode(obj)

    # Then
    assert isinstance(result, SourceDocument)

    expected_source_document = SourceDocument(
        id="1",
        content="Some content",
        source="A source",
        title="A title",
        chunk="A chunk",
        offset="An offset",
        page_number="1",
        chunk_id="abcd",
    )
    assert result.id == expected_source_document.id
    assert result.content == expected_source_document.content
    assert result.source == expected_source_document.source
    assert result.title == expected_source_document.title
    assert result.chunk == expected_source_document.chunk
    assert result.offset == expected_source_document.offset
    assert result.page_number == expected_source_document.page_number
