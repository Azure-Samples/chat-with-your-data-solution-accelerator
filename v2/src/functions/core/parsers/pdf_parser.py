"""PDF parser routed through Document Intelligence on the unified Foundry AI Services endpoint.

Pillar: Stable Core
Phase: 7

Self-registers under key ``"pdf"`` per the registration convention in
``base.py`` (lowercase file extension, no leading dot). Eager-imported
from ``functions/core/parsers/registry.py`` so the registration fires
at process start (Option SE-1 in dev_plan §2.4.5).

Endpoint derivation -- the unified ``kind=AIServices`` account
(``v2/infra/main.bicep``) exposes Document Intelligence on the same
host as chat/agents/speech. The SDK appends ``/documentintelligence/``
internally, so the client just receives ``FoundrySettings.services_endpoint``
normalised to one trailing slash. Auth is UAMI bearer for
``AadScope.COGNITIVE_SERVICES`` per Hard Rule #2 (no keys, no Key Vault).

Chunking strategy -- one ``Chunk`` per Document Intelligence page,
joining ``page.lines[*].content`` with ``\\n``. Pages with no lines
(or whitespace-only content) are skipped and ``index`` stays dense
across emitted chunks so re-ingesting the same PDF produces stable
Search document keys via ``Chunk.id = f"{source}__{index}"``.
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


@registry.register("pdf")
class PdfParser(BaseParser):
    """Parse a PDF byte payload into one ``Chunk`` per page via Document Intelligence."""

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
        endpoint = f"{self._settings.foundry.services_endpoint.rstrip('/')}/"
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
                "pdf parse failed",
                extra={
                    "operation": "parse_pdf",
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
                    id=f"{source}__{index}",
                    content=page_text,
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
