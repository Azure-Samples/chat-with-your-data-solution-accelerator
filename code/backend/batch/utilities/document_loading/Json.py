import jq
import json
import requests

from langchain.docstore.document import Document
from .DocumentLoadingBase import DocumentLoadingBase
from ..common.SourceDocument import SourceDocument


class JsonDocumentLoading(DocumentLoadingBase):
    def __init__(self, keywords_resolver_func=None,
                 source_url_resolver_func=None,
                 page_content_resolver_func=None,
                 jschema=None):
        super().__init__()

        self.jschema = '.' if jschema is None else jschema
        self.page_content_resolver_func = page_content_resolver_func if \
            page_content_resolver_func else self._page_content_resolver_func
        self.source_url_resolver_func = source_url_resolver_func if \
            source_url_resolver_func else self._source_url_resolver_func
        self.keywords_resolver_func = keywords_resolver_func if \
            keywords_resolver_func else self._keywords_resolver_func
        self.title_resolver_func = self._title_resolver_func

    def load(self, document_url: str):
        documents = list(self._load_from_json(
            jschema=self.jschema,
            url=document_url))

        source_documents = []
        for document in documents:
            if document.page_content != '':
                source_documents.append(
                    SourceDocument(
                        content=document.page_content,
                        source=document.metadata['source'],
                        keywords=document.metadata['keywords'],
                        title=document.metadata['title']
                    ))

        return source_documents

    def _keywords_resolver_func(self, record):
        tags = record.get('tags')
        keywords = []
        if tags:
            if isinstance(tags, dict):
                for key, value in tags.items():
                    if isinstance(value, list):
                        keywords.extend(value)
                    else:
                        keywords.extend([value])
            elif isinstance(tags, list):
                keywords.extend(tags)
            elif isinstance(tags, str):
                return tags

        return ', '.join(keywords)

    def _load_from_json(self, jschema, url):
        content = ''
        if url.startswith('http') or url.startswith('https'):
            response = requests.get(url)
            content = response.text
        else:
            with open(url, 'r') as file:
                content = file.read()

        jq_schema = jq.compile(jschema)

        index = 0
        for doc in self._parse(url, jq_schema, content, index):
            yield doc
            index += 1

    def _parse(self, url, jq_schema, content, index):
        data = jq_schema.input(json.loads(content))

        for i, value in enumerate(data, index + 1):
            page_content = self.page_content_resolver_func(content=value)
            metadata = {'source': self.source_url_resolver_func(value, str(url)), 'seq_num': i,
                        'keywords': self.keywords_resolver_func(value),
                        'title': self.title_resolver_func(value)}
            yield Document(page_content=page_content, metadata=metadata)

    def _title_resolver_func(self, content):
        if isinstance(content, dict):
            return content.get('title')

        return ''

    def _source_url_resolver_func(self, content, file_url):
        if isinstance(content, dict):
            source_url = content.get('source_url')
            if source_url:
                return source_url
        else:
            return file_url

    def _page_content_resolver_func(self, content):
        if isinstance(content, str):
            return content
        elif isinstance(content, dict):
            content = content['content']
            return json.dumps(content) if content else ''
        else:
            return str(content) if content is not None else ''
