from .formrecognizer import AzureFormRecognizerClient
from .azureblobstorage import AzureBlobStorageClient

import os
import openai
from dotenv import load_dotenv
import logging
import re
import hashlib
from typing import Optional

from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores.base import VectorStore
from langchain.document_loaders.base import BaseLoader
from langchain.document_loaders import WebBaseLoader
from langchain.text_splitter import TokenTextSplitter, TextSplitter
from langchain.document_loaders.base import BaseLoader
from opencensus.ext.azure.log_exporter import AzureLogHandler


from .azuresearch import AzureSearch
from .ConfigHelper import ConfigHelper

import pandas as pd
import urllib

from fake_useragent import UserAgent


class DocumentProcessor:
    def __init__(
        self
    ):

        self.pdf_parser: AzureFormRecognizerClient = AzureFormRecognizerClient()
        self.blob_client: AzureBlobStorageClient = AzureBlobStorageClient() 
        self.user_agent: UserAgent = UserAgent()
        self.user_agent.random
        
        # FIX ME: Chunking strategy should be read by ConfigHelper
        self.chunk_size = int(os.getenv("CHUNK_SIZE", 500))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", 100))
        self.document_loaders: BaseLoader = WebBaseLoader
        self.text_splitter: TextSplitter = TokenTextSplitter(chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)

        # Azure Search settings
        self.azure_search_endpoint: str = os.getenv("AZURE_SEARCH_SERVICE")
        self.azure_search_key: str = os.getenv("AZURE_SEARCH_KEY")
        self.index_name: str = os.getenv("AZURE_SEARCH_INDEX")
        
        os.environ["OPENAI_API_BASE"] = f"https://{os.getenv('AZURE_OPENAI_RESOURCE')}.openai.azure.com/"
        os.environ["OPENAI_API_KEY"] = os.getenv("AZURE_OPENAI_KEY")
        os.environ["OPENAI_API_VERSION"] = os.getenv("AZURE_OPENAI_API_VERSION")

        openai.api_type = "azure"
        openai.api_base = os.getenv("OPENAI_API_BASE")
        openai.api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        openai.api_key = os.getenv("OPENAI_API_KEY")

        # Azure OpenAI settings
        self.api_base = openai.api_base
        self.api_version = openai.api_version

        self.model: str = os.getenv("OPENAI_EMBEDDINGS_ENGINE_DOC", "text-embedding-ada-002")
        self.embeddings: OpenAIEmbeddings = OpenAIEmbeddings(model=self.model, chunk_size=1)
    
        self.vector_store: VectorStore = AzureSearch(
                azure_cognitive_search_name=self.azure_search_endpoint,
                azure_cognitive_search_key=self.azure_search_key,
                index_name=self.index_name,
                embedding_function=self.embeddings.embed_query)
        self.k: int = 4
        
    def process_url_and_store_in_vector_store(self, source_url):
        try:
            documents = self.document_loaders(source_url).load()
            
            # Convert to UTF-8 encoding for non-ascii text
            for document in documents:
                try:
                    if document.page_content.encode(
                        "iso-8859-1"
                    ) == document.page_content.encode("latin-1"):
                        document.page_content = document.page_content.encode(
                            "iso-8859-1"
                        ).decode("utf-8", errors="ignore")
                except:
                    pass

            docs = self.text_splitter.split_documents(documents)

            # Remove half non-ascii character from start/end of doc content (langchain TokenTextSplitter may split a non-ascii character in half)
            pattern = re.compile(
                r"[\x00-\x1f\x7f\u0080-\u00a0\u2000-\u3000\ufff0-\uffff]"
            )
            for doc in docs:
                doc.page_content = re.sub(pattern, "", doc.page_content)
                if doc.page_content == "":
                    docs.remove(doc)

            keys = []
            for i, doc in enumerate(docs):
                # Create a unique key for the document
                source_url = source_url.split("?")[0]
                filename = "/".join(source_url.split("/")[4:])
                hash_key = hashlib.sha1(f"{source_url}_{i}".encode("utf-8")).hexdigest()
                hash_key = f"doc:{self.index_name}:{hash_key}"
                keys.append(hash_key)
                doc.metadata = {
                    "source": f"[{source_url}]({source_url}_SAS_TOKEN_PLACEHOLDER_)",
                    "chunk": i,
                    "key": hash_key,
                    "filename": filename,
                }
            
            self.vector_store.add_documents(documents=docs, keys=keys)

        except Exception as e:
            logging.error(f"Error adding embeddings for {source_url}: {e}")
            raise e

    def convert_file_create_embedings_and_store(
        self, source_url, filename
    ):
        # Extract the text from the file
        text = self.pdf_parser.analyze_read(source_url)

        # Upload the text to Azure Blob Storage
        converted_filename = f"converted/{filename}.txt"
        source_url = self.blob_client.upload_file(
            "\n".join(text),
            f"converted/{filename}.txt",
            content_type="text/plain; charset=utf-8",
        )

        print(f"Converted file uploaded to {source_url} with filename {filename}")
        # Update the metadata to indicate that the file has been converted
        self.blob_client.upsert_blob_metadata(filename, {"converted": "true"})

        self.process_url_and_store_in_vector_store(source_url=source_url)

        return converted_filename

    def get_all_documents(self, k: Optional[int] = None):
        result = self.vector_store.similarity_search(query="*", k=k if k else self.k)
        return pd.DataFrame(
            list(
                map(
                    lambda x: {
                        "key": x.metadata["key"],
                        "filename": x.metadata["filename"],
                        "source": urllib.parse.unquote(x.metadata["source"]),
                        "content": x.page_content,
                        "metadata": x.metadata,
                    },
                    result,
                )
            )
        )