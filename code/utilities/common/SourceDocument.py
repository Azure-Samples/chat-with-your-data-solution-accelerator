from typing import Optional, Type
import hashlib
import json
from urllib.parse import urlparse, quote
from ..helpers.AzureBlobStorageHelper import AzureBlobStorageClient


class SourceDocument:
    def __init__(self, content: str, source: str, id: Optional[str] = None, title: Optional[str] = None, chunk: Optional[int] = None, offset: Optional[int] = None, page_number: Optional[int] = None):
        """
        Represents a source document.

        Args:
            content (str): The content of the document.
            source (str): The source of the document.
            id (Optional[str], optional): The ID of the document. Defaults to None.
            title (Optional[str], optional): The title of the document. Defaults to None.
            chunk (Optional[int], optional): The chunk number of the document. Defaults to None.
            offset (Optional[int], optional): The offset of the document. Defaults to None.
            page_number (Optional[int], optional): The page number of the document. Defaults to None.
        """
        self.id = id
        self.content = content
        self.source = source
        self.title = title
        self.chunk = chunk
        self.offset = offset
        self.page_number = page_number

    def __str__(self):
        """
        Returns a string representation of the SourceDocument object.

        Returns:
            str: The string representation of the SourceDocument object.
        """
        return f"SourceDocument(id={self.id}, title={self.title}, source={self.source}, chunk={self.chunk}, offset={self.offset}, page_number={self.page_number})"

    def to_json(self):
        """
        Converts the SourceDocument object to a JSON string.

        Returns:
            str: The JSON string representation of the SourceDocument object.
        """
        return json.dumps(self, cls=SourceDocumentEncoder)

    @classmethod
    def from_json(cls, json_string):
        """
        Creates a SourceDocument object from a JSON string.

        Args:
            json_string (str): The JSON string representation of the SourceDocument object.

        Returns:
            SourceDocument: The SourceDocument object created from the JSON string.
        """
        return json.loads(json_string, cls=SourceDocumentDecoder)

    @classmethod
    def from_dict(cls, dict_obj):
        """
        Creates a SourceDocument object from a dictionary.

        Args:
            dict_obj (dict): The dictionary containing the attributes of the SourceDocument object.

        Returns:
            SourceDocument: The SourceDocument object created from the dictionary.
        """
        return cls(
            dict_obj['id'],
            dict_obj['content'],
            dict_obj['source'],
            dict_obj['title'],
            dict_obj['chunk'],
            dict_obj['offset'],
            dict_obj['page_number']
        )

    @classmethod
    def from_metadata(
        cls: Type['SourceDocument'],
        content: str,
        metadata: dict,
        document_url: Optional[str],
        idx: Optional[int],
    ) -> 'SourceDocument':
        """
        Creates a SourceDocument object from metadata.

        Args:
            content (str): The content of the document.
            metadata (dict): The metadata of the document.
            document_url (Optional[str]): The URL of the document. Defaults to None.
            idx (Optional[int]): The index of the document. Defaults to None.

        Returns:
            SourceDocument: The SourceDocument object created from the metadata.
        """
        parsed_url = urlparse(document_url)
        file_url = parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path
        filename = parsed_url.path
        hash_key = hashlib.sha3_256(
            f"{file_url}_{idx}".encode("utf-8")).hexdigest()
        hash_key = f"doc_{hash_key}"
        sas_placeholder = "_SAS_TOKEN_PLACEHOLDER_" if 'blob.core.windows.net' in parsed_url.netloc else ""
        return cls(
            id=metadata.get('id', hash_key),
            content=content,
            source=metadata.get('source', f"{file_url}{sas_placeholder}"),
            title=metadata.get('title', filename),
            chunk=metadata.get('chunk', idx),
            offset=metadata.get('offset'),
            page_number=metadata.get('page_number'),
        )

    def convert_to_langchain_document(self):
        """
        Converts the SourceDocument object to a LangChain Document object.

        Returns:
            Document: The LangChain Document object.
        """
        from langchain.docstore.document import Document
        return Document(
            page_content=self.content,
            metadata={
                "id": self.id,
                "source": self.source,
                "title": self.title,
                "chunk": self.chunk,
                "offset": self.offset,
                "page_number": self.page_number,
            }
        )

    def get_filename(self, include_path=False):
        """
        Gets the filename of the document.

        Args:
            include_path (bool, optional): Whether to include the path in the filename. Defaults to False.

        Returns:
            str: The filename of the document.
        """
        filename = self.source.replace(
            '_SAS_TOKEN_PLACEHOLDER_', '').replace('https://', '')
        if include_path:
            filename = filename.split('/')[-1]
        else:
            filename = filename.split('/')[-1].split('.')[0]
        return filename

    def get_markdown_url(self):
        """
        Gets the markdown URL of the document.

        Returns:
            str: The markdown URL of the document.
        """
        url = quote(self.source, safe=':/')
        if '_SAS_TOKEN_PLACEHOLDER_' in url:
            blob_client = AzureBlobStorageClient()
            container_sas = blob_client.get_container_sas()
            url = url.replace("_SAS_TOKEN_PLACEHOLDER_", container_sas)
        return f"[{self.title}]({url})"


class SourceDocumentEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for serializing SourceDocument objects.
    """

    def default(self, obj):
        if isinstance(obj, SourceDocument):
            return {
                'id': obj.id,
                'content': obj.content,
                'source': obj.source,
                'title': obj.title,
                'chunk': obj.chunk,
                'offset': obj.offset,
                'page_number': obj.page_number
            }
        return super().default(obj)


class SourceDocumentDecoder(json.JSONDecoder):
    """
    Custom JSON decoder for decoding SourceDocument objects.
    """

    def decode(self, s, **kwargs):
        """
        Decode the JSON string and return a SourceDocument object.

        Args:
            s (str): The JSON string to decode.
            **kwargs: Additional keyword arguments.

        Returns:
            SourceDocument: The decoded SourceDocument object.
        """
        obj = super().decode(s, **kwargs)
        return SourceDocument(
            id=obj['id'],
            content=obj['content'],
            source=obj['source'],
            title=obj['title'],
            chunk=obj['chunk'],
            offset=obj['offset'],
            page_number=obj['page_number']
        )
