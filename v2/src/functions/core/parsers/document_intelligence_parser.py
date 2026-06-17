"""Document Intelligence parser routed through the unified Foundry AI Services endpoint.

Pillar: Stable Core
Phase: 7

Self-registers under multiple file-extension keys (``"pdf"``, ``"docx"``) per
the registration convention in ``base.py`` (lowercase file extension, no
leading dot). Eager-imported from ``functions/core/parsers/registry.py`` so
both registrations fire at process start.

The Document Intelligence ``prebuilt-layout`` model natively analyses PDF,
DOCX, XLSX, PPTX, HTML and image formats through the same
``begin_analyze_document`` call and returns the same
``AnalyzeResult.pages[*].lines[*].content`` shape, so a single class with
one decorator per supported extension covers every layout-extractable
format without duplication. Additional formats register by stacking another
``@registry.register("<ext>")`` decorator on the class -- no new SDK call,
no new credential, no new client.

Endpoint derivation -- the unified ``kind=AIServices`` account
(``v2/infra/main.bicep``) exposes Document Intelligence on the same host as
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
falls back to one ``Chunk`` per paragraph (the same semantic unit
``TextParser`` uses). Either way ``index`` stays dense across emitted
chunks so re-ingesting the same document produces stable, Search-safe
document keys via ``BaseParser.make_chunk_id(source, index)``.
"""

import logging

from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import AzureError

from backend.core.providers.parsers.base import BaseParser
from backend.core.settings import AppSettings
from backend.core.types import Chunk

from .registry import registry

logger = logging.getLogger(__name__)


@registry.register("docx")
@registry.register("pdf")
class DocumentIntelligenceParser(BaseParser):
    """Parse a document byte payload into one ``Chunk`` per page via Document Intelligence."""

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
        # chunks. Fall back to one ``Chunk`` per paragraph -- the same
        # semantic unit ``TextParser`` uses. The fallback runs only when the
        # page pass produced nothing, so paginated formats (PDF, images) keep
        # their one-chunk-per-page shape and never double-emit (a PDF returns
        # both ``page.lines`` and ``paragraphs``, but its page chunks suppress
        # this branch).
        if not chunks:
            for paragraph in result.paragraphs or []:
                paragraph_text = (paragraph.content or "").strip()
                if not paragraph_text:
                    continue
                chunks.append(
                    Chunk(
                        id=self.make_chunk_id(source, index),
                        content=paragraph_text,
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
