import jq
import json
import requests

from langchain.docstore.document import Document
from .DocumentLoadingBase import DocumentLoadingBase
from ..common.SourceDocument import SourceDocument


class JsonDocumentLoading(DocumentLoadingBase):
    def __init__(self, keywords_resolver_func=None, jschema=None):
        super().__init__()
        self.jschema = '.pages[]' if jschema is None else jschema
        self.keywords_resolver_func = self._keywords_resolver_func if \
            keywords_resolver_func is None else keywords_resolver_func

    def load(self, document_url: str):
        documents = list(self._load_from_json(
            jschema=self.jschema,
            url=document_url, keywords_resolver=self.keywords_resolver_func))

        for document in documents:
            if document.page_content == "":
                documents.remove(document)
        source_documents = [
            SourceDocument(
                content=document.page_content,
                source=document.metadata['source'],
                keywords=document.metadata['keywords']
            )
            for document in documents
        ]
        return source_documents

    def _keywords_resolver_func(self, record: dict):
        tags = record.get('tags')
        if tags:
            if isinstance(tags, list):
                return ' '.join([str(tag) for tag in tags])
            elif isinstance(tags, str):
                return tags
        else:
            return ''

    def _load_from_json(self, jschema, url, keywords_resolver):
        content = ''
        if url.startswith('http') or url.startswith('https'):
            response = requests.get(url)
            content = response.text
        else:
            with open(url, 'r') as file:
                content = file.read()

        jq_schema = jq.compile(jschema)

        index = 0
        for doc in self._parse(url, jq_schema, content, keywords_resolver, index):
            yield doc
            index += 1

    def _parse(self, url, jq_schema, content, keywords_resolver, index):
        data = jq_schema.input(json.loads(content))

        for i, sample in enumerate(data, index + 1):
            text = self._get_text(content=sample)
            metadata = {'source': str(url), 'seq_num': i,
                        'keywords': keywords_resolver(sample)}
            yield Document(page_content=text, metadata=metadata)

    def _get_text(self, content):
        if isinstance(content, str):
            return content
        elif isinstance(content, dict):
            return json.dumps(content) if content else ''
        else:
            return str(content) if content is not None else ''
