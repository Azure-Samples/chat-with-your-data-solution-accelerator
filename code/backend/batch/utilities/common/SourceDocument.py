from typing import Optional, Type
import hashlib
import json
from urllib.parse import urlparse, quote
from ..helpers.AzureBlobStorageClient import AzureBlobStorageClient


class SourceDocument:
    def __init__(
        self,
        content: str,
        source: str,
        id: Optional[str] = None,
        title: Optional[str] = None,
        chunk: Optional[int] = None,
        offset: Optional[int] = None,
        page_number: Optional[int] = None,
        chunk_id: Optional[str] = None,
    ):
        self.id = id
        self.content = content
        self.source = source
        self.title = title
        self.chunk = chunk
        self.offset = offset
        self.page_number = page_number
        self.chunk_id = chunk_id

    def __str__(self):
        return f"SourceDocument(id={self.id}, title={self.title}, source={self.source}, chunk={self.chunk}, offset={self.offset}, page_number={self.page_number}, chunk_id={self.chunk_id})"

    def to_json(self):
        return json.dumps(self, cls=SourceDocumentEncoder)

    @classmethod
    def from_json(cls, json_string):
        return json.loads(json_string, cls=SourceDocumentDecoder)

    @classmethod
    def from_dict(cls, dict_obj):
        return cls(
            dict_obj["id"],
            dict_obj["content"],
            dict_obj["source"],
            dict_obj["title"],
            dict_obj["chunk"],
            dict_obj["offset"],
            dict_obj["page_number"],
            dict_obj["chunk_id"],
        )

    @classmethod
    def from_metadata(
        cls: Type["SourceDocument"],
        content: str,
        metadata: dict,
        document_url: Optional[str],
        idx: Optional[int],
    ) -> "SourceDocument":
        parsed_url = urlparse(document_url)
        file_url = parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path
        filename = parsed_url.path
        hash_key = hashlib.sha1(f"{file_url}_{idx}".encode("utf-8")).hexdigest()
        hash_key = f"doc_{hash_key}"
        sas_placeholder = (
            "_SAS_TOKEN_PLACEHOLDER_"
            if parsed_url.netloc
            and parsed_url.netloc.endswith(".blob.core.windows.net")
            else ""
        )
        return cls(
            id=metadata.get("id", hash_key),
            content=content,
            source=metadata.get("source", f"{file_url}{sas_placeholder}"),
            title=metadata.get("title", filename),
            chunk=metadata.get("chunk", idx),
            offset=metadata.get("offset"),
            page_number=metadata.get("page_number"),
            chunk_id=metadata.get("chunk_id"),
        )

    def convert_to_langchain_document(self):
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
                "chunk_id": self.chunk_id,
            },
        )

    def get_filename(self, include_path=False):
        filename = self.source.replace("_SAS_TOKEN_PLACEHOLDER_", "").replace(
            "http://", ""
        )
        if include_path:
            filename = filename.split("/")[-1]
        else:
            filename = filename.split("/")[-1].split(".")[0]
        return filename

    def get_markdown_url(self):
        url = quote(self.source, safe=":/")
        if "_SAS_TOKEN_PLACEHOLDER_" in url:
            blob_client = AzureBlobStorageClient()
            container_sas = blob_client.get_container_sas()
            url = url.replace("_SAS_TOKEN_PLACEHOLDER_", container_sas)
        return f"[{self.title}]({url})"


class SourceDocumentEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, SourceDocument):
            return {
                "id": obj.id,
                "content": obj.content,
                "source": obj.source,
                "title": obj.title,
                "chunk": obj.chunk,
                "offset": obj.offset,
                "page_number": obj.page_number,
                "chunk_id": obj.chunk_id,
            }
        return super().default(obj)


class SourceDocumentDecoder(json.JSONDecoder):
    def decode(self, s, **kwargs):
        obj = super().decode(s, **kwargs)
        return SourceDocument(
            id=obj["id"],
            content=obj["content"],
            source=obj["source"],
            title=obj["title"],
            chunk=obj["chunk"],
            offset=obj["offset"],
            page_number=obj["page_number"],
            chunk_id=obj["chunk_id"],
        )
