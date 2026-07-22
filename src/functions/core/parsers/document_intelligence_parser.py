"""Document Intelligence parser routed through the unified Foundry AI Services endpoint.

Self-registers under multiple file-extension keys (``"pdf"``, ``"docx"``,
``"jpeg"``, ``"jpg"``, ``"png"``) per the registration convention in
``base.py`` (lowercase file extension, no leading dot). Eager-imported from
``functions/core/parsers/registry.py`` so all registrations fire at process start.

The Document Intelligence ``prebuilt-layout`` model natively analyses PDF,
DOCX, XLSX, PPTX, HTML and image formats through the same
``begin_analyze_document`` call and returns the same
``AnalyzeResult.pages[*].lines[*].content`` shape, so a single class with
one decorator per supported extension covers every layout-extractable
format without duplication. Additional formats register by stacking another
``@registry.register("<ext>")`` decorator on the class -- no new SDK call,
no new credential, no new client.

Endpoint derivation -- the unified ``kind=AIServices`` account
(``infra/main.bicep``) exposes Document Intelligence on the same host as
chat / agents / speech. The SDK appends ``/documentintelligence/``
internally, so the client just receives ``FoundrySettings.services_endpoint``
normalised to one trailing slash. Auth is UAMI bearer for
``AadScope.COGNITIVE_SERVICES`` per Hard Rule #2 (no keys, no Key Vault).

Chunking strategy -- paginated formats (PDF, images) emit one ``Chunk``
per Document Intelligence page, joining ``page.lines[*].content`` with
``\\n``; pages with no lines (or whitespace-only content) are skipped.
Office and HTML formats (DOCX, PPTX, XLSX, HTML) are "pageless" -- the
service returns their text in ``result.paragraphs`` and leaves
``page.lines`` empty, so when the page pass yields nothing the parser
falls back to grouping consecutive ``result.paragraphs`` into chunks of
up to ``_FALLBACK_CHUNK_TARGET_CHARS`` characters (joined with a blank
line). Document Intelligence segments text far more finely than a
semantic paragraph -- one entry per heading, list item, or table cell --
so grouping approximates the paragraph-as-semantic-unit granularity
``TextParser`` produces instead of thousands of sub-sentence chunks; a
single paragraph longer than the target stays a whole chunk. Either way
``index`` stays dense across emitted
chunks so re-ingesting the same document produces stable, Search-safe
document keys via ``BaseParser.make_chunk_id(source, index)``.
"""

import logging

from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError

from backend.core.providers.parsers.base import BaseParser, ParserKey
from backend.core.settings import AppSettings
from backend.core.types import Chunk

from .registry import registry

logger = logging.getLogger(__name__)

# Target chunk size (characters) for the pageless paragraph fallback:
# consecutive Document Intelligence paragraphs are grouped up to this budget so
# a large document yields retrieval-friendly chunks instead of thousands of
# sub-sentence ones.
_FALLBACK_CHUNK_TARGET_CHARS = 2000


@registry.register(ParserKey.DOCX)
@registry.register(ParserKey.PDF)
@registry.register(ParserKey.JPEG)
@registry.register(ParserKey.JPG)
@registry.register(ParserKey.PNG)
class DocumentIntelligenceParser(BaseParser):
    """Parse a document byte payload into one ``Chunk`` per page via Document Intelligence."""

    # Document Intelligence is a network parser: it needs
    # AZURE_AI_SERVICES_ENDPOINT to parse, so the admin upload boundary
    # refuses a DI-routed file when that endpoint is unset (see
    # BaseParser.requires_ai_services).
    requires_ai_services = True

    _settings: AppSettings
    _credential: AsyncTokenCredential
    _client: DocumentIntelligenceClient | None
    _client_override: DocumentIntelligenceClient | None

    def __init__(
        self,
        settings: AppSettings,
        credential: AsyncTokenCredential,
        *,
        client: DocumentIntelligenceClient | None = None,
    ) -> None:
        super().__init__(settings=settings, credential=credential)
        self._client_override = client
        self._client = client

    def _get_client(self) -> DocumentIntelligenceClient:
        if self._client is not None:
            return self._client
        raw = self._settings.foundry.services_endpoint
        if not raw.lower().startswith("https://"):
            raise ValueError(
                "AZURE_AI_SERVICES_ENDPOINT must be a non-empty https:// URL to "
                "parse documents via Document Intelligence; got "
                f"{raw!r}. Set it in the ingestion runtime environment "
                "(Functions local.settings.json or the Container App settings)."
            )
        endpoint = f"{raw.rstrip('/')}/"
        self._client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=self._credential,
            api_version=self._settings.document_intelligence.api_version,
        )
        return self._client

    async def parse(self, content: bytes, *, source: str) -> list[Chunk]:
        client = self._get_client()
        try:
            poller = await client.begin_analyze_document(
                self._settings.document_intelligence.model_id,
                AnalyzeDocumentRequest(bytes_source=content),
            )
            result = await poller.result()
        except AzureError:
            logger.exception(
                "document parse failed",
                extra={
                    "operation": "parse",
                    "provider": "document_intelligence",
                    "source": source,
                    "model_id": self._settings.document_intelligence.model_id,
                },
            )
            raise

        chunks: list[Chunk] = []
        index = 0
        for page in result.pages or []:
            page_text = "\n".join(
                line.content for line in (page.lines or []) if line.content
            ).strip()
            if not page_text:
                continue
            chunks.append(
                Chunk(
                    id=self.make_chunk_id(source, index),
                    content=page_text,
                    source=source,
                    index=index,
                )
            )
            index += 1

        # Office and HTML formats (DOCX, PPTX, XLSX, HTML) are "pageless":
        # Document Intelligence returns their text in ``result.paragraphs``
        # and leaves ``page.lines`` empty, so the page pass above yields no
        # chunks. Group consecutive paragraphs into chunks of up to
        # ``_FALLBACK_CHUNK_TARGET_CHARS`` characters -- Document Intelligence
        # segments text per heading / list item / table cell, so one chunk
        # per paragraph would explode a large document into thousands of
        # sub-sentence chunks. The fallback runs only when the page pass
        # produced nothing, so paginated formats (PDF, images) keep their
        # one-chunk-per-page shape and never double-emit.
        if not chunks:
            group: list[str] = []
            group_len = 0
            for paragraph in result.paragraphs or []:
                paragraph_text = (paragraph.content or "").strip()
                if not paragraph_text:
                    continue
                if (
                    group
                    and group_len + len(paragraph_text) > _FALLBACK_CHUNK_TARGET_CHARS
                ):
                    chunks.append(
                        Chunk(
                            id=self.make_chunk_id(source, index),
                            content="\n\n".join(group),
                            source=source,
                            index=index,
                        )
                    )
                    index += 1
                    group = []
                    group_len = 0
                group.append(paragraph_text)
                group_len += len(paragraph_text)
            if group:
                chunks.append(
                    Chunk(
                        id=self.make_chunk_id(source, index),
                        content="\n\n".join(group),
                        source=source,
                        index=index,
                    )
                )
                index += 1

        return chunks

    async def aclose(self) -> None:
        if self._client is not None and self._client_override is None:
            await self._client.close()
            self._client = None
