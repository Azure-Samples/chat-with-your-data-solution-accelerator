"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

HTTP blueprint that exposes the ``add_url`` ingestion path from
:mod:`functions.add_url.handler` as ``POST /api/add_url``.

Companion to :mod:`functions.batch_push.blueprint`. ``batch_push`` is
the queue-triggered side of the ingestion pipeline (blob storage ->
parse -> embed -> search). ``add_url`` is the HTTP-triggered side
for one-off URL ingestion (httpx -> parse -> embed -> search).
Both share the parser registry, the embedder registry, and the
search-writer helper -- only the trigger semantics + the byte source
differ.

Trigger contract:

* ``POST /api/add_url`` with JSON body validated as
  :class:`functions.add_url.handler.AddUrlRequest` (``url`` required,
  ``ingestion_job_id`` optional uuid4 default).
* 200 response body shape:
  ``{"ingestion_job_id": str, "url": str, "document_count": int}``.
* 422 / 502 / 500 ladder owned by
  :func:`functions.core.exception_mapping.map_function_exceptions`
  (same as :mod:`functions.batch_start.blueprint`).

Registry-first collaborator wiring (Hard Rule #4):

* Credentials provider via ``credentials_registry``.
* Parser via ``ingestion_parsers_registry`` (key resolved from the
  URL path's file extension; see :func:`_parser_key_for_url`).
* Embedder via ``embedders_registry`` -- post-Phase-6 default key
  ``"azure_openai"`` (single concrete embedder today; promoted to
  settings when an alternate concrete lands).

The Azure Search write client is constructed directly (one-shot SDK
wiring; the writer protocol exists precisely so
:func:`add_url_handler` does not care which client satisfies it --
see decision D4 in dev_plan §4.6.1, also documented in
``batch_push/blueprint.py``).

The private :func:`_execute` helper is the single seam route-level
tests monkeypatch so they do not need a real credential, a real
Search service, or live HTTPS traffic.
"""

from http import HTTPStatus
from pathlib import PurePosixPath
from urllib.parse import urlparse

import azure.functions as func
from azure.search.documents.aio import SearchClient

from backend.core.providers.credentials import registry as credentials_registry
from backend.core.providers.embedders import registry as embedders_registry
from backend.core.providers.search.writer import SearchWriterAdapter
from backend.core.settings import AppSettings, get_settings
from backend.core.types import SearchDocument
from functions.add_url.handler import AddUrlRequest, add_url_handler
from functions.core.exception_mapping import map_function_exceptions
from functions.core.http import json_response
from functions.core.parsers import registry as ingestion_parsers_registry

bp = func.Blueprint()

# When a URL has no path extension (e.g. ``https://example.com/article``)
# we fall back to the text parser. Phase 6 ships only ``TextParser``;
# later phases that add an HTML parser will replace this default with
# the HTML key.
_DEFAULT_PARSER_KEY = "txt"


def _parser_key_for_url(url: str) -> str:
    """Return the parser-registry key for ``url``.

    Extracts the URL path's lowercase extension (sans dot). Falls
    back to :data:`_DEFAULT_PARSER_KEY` when the path has no
    extension so ext-less URLs still route to a parser. Mirrors
    :func:`functions.batch_push.blueprint._parser_key_for_filename`
    for blob filenames -- intentionally parallel so the two
    ingestion paths share a mental model.

    ``urlparse`` ignores the query string and fragment, so
    ``https://example.com/file.pdf?q=1`` resolves to ``"pdf"``.
    ``PurePosixPath`` keeps separator handling stable across Windows
    dev hosts and Linux Functions runtimes -- URL paths are always
    POSIX-style.
    """
    parsed = urlparse(url)
    suffix = PurePosixPath(parsed.path).suffix.lstrip(".").lower()
    return suffix or _DEFAULT_PARSER_KEY


async def _execute(
    request: AddUrlRequest, settings: AppSettings
) -> list[SearchDocument]:
    """Resolve collaborators and dispatch to ``add_url_handler``.

    Extracted from :func:`add_url` so route-level tests can
    monkeypatch this single seam instead of spinning up Foundry IQ +
    a real Search service + live HTTPS. Returns the documents pushed
    to Search (in chunk order) so :func:`add_url` can include a count
    in the wire response.
    """
    cred_provider = credentials_registry.registry.get(
        credentials_registry.select_default(settings.identity.uami_client_id)
    )(settings=settings)
    parser_cls = ingestion_parsers_registry.registry.get(
        _parser_key_for_url(request.url)
    )
    async with await cred_provider.get_credential() as credential:
        parser = parser_cls(settings=settings, credential=credential)
        embedder_cls = embedders_registry.registry.get("azure_openai")
        embedder = embedder_cls(settings=settings, credential=credential)
        try:
            async with SearchClient(
                endpoint=settings.search.endpoint,
                index_name=settings.search.index,
                credential=credential,
            ) as search_client:
                return await add_url_handler(
                    request,
                    parser,
                    embedder,
                    SearchWriterAdapter(search_client),
                )
        finally:
            await embedder.aclose()


@bp.route(route="add_url", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@map_function_exceptions("add_url")
async def add_url(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/add_url -- fetch one URL and write its chunks to Search.

    Request body (JSON): :class:`AddUrlRequest`.
    Responses:
      * 200 -- ``{"ingestion_job_id": str, "url": str,
        "document_count": int}``.
      * 422 -- body failed Pydantic validation (owned by
        :func:`map_function_exceptions`).
      * 502 -- upstream Azure error from embedder / Search (owned by
        :func:`map_function_exceptions`). ``httpx.HTTPError`` from
        :func:`fetch_url` is **not** caught by the decorator and
        falls through to 500; URL-fetch failures are caller errors
        (bad URL, dead host) not Azure upstream errors.
      * 500 -- unexpected handler failure including ``httpx.HTTPError``
        (final safety net owned by :func:`map_function_exceptions`).
    """
    request = AddUrlRequest.model_validate_json(req.get_body() or b"{}")
    documents = await _execute(request, get_settings())
    return json_response(
        {
            "ingestion_job_id": request.ingestion_job_id,
            "url": request.url,
            "document_count": len(documents),
        },
        HTTPStatus.OK,
    )
