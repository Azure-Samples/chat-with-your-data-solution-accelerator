import hashlib
from urllib.parse import urlparse

class MetadataHelper:
    def __init__(self) -> None:
        pass

    def generate_metadata_and_key(self, document_url: str, idx: int, metadata: dict = {}) -> dict:
        parsed_url = urlparse(document_url)
        file_url = parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path
        filename = parsed_url.path
        hash_key = hashlib.sha1(f"{file_url}_{idx}".encode("utf-8")).hexdigest()
        hash_key = f"doc_{hash_key}"
        sas_placeholder = "_SAS_TOKEN_PLACEHOLDER_" if 'blob.core.windows.net' in parsed_url.netloc else ""
        source = f"[{file_url}]({file_url}{sas_placeholder})"
        metadata.update({"source": f"{filename}#{idx}", "markdown_url": source, "chunk": idx, "key": hash_key, "filename": filename,"title": filename, "original_url": file_url})
        return metadata
