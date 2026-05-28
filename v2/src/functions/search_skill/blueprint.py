"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

HTTP blueprint that exposes the ``search_skill`` embed-on-the-fly
handler from :mod:`functions.search_skill.handler` as
``POST /api/search_skill``.

Companion to :mod:`functions.add_url.blueprint`. ``add_url`` is the
HTTP-triggered ingestion path (httpx -> parse -> embed -> search);
``search_skill`` is the HTTP-triggered AI Search custom-skill endpoint
the indexer calls **per record batch** during index build / refresh
(``input -> embed -> wire response`` -- no parser, no Search write).
Both share the embedder registry; only the trigger semantics + the
absence of parse/write differ.

Trigger contract:

* ``POST /api/search_skill`` with JSON body validated as
  :class:`functions.search_skill.models.SearchSkillRequest` (AI Search
  WebApiSkill envelope -- wire field ``recordId`` per record; see
  :mod:`functions.search_skill.models` for the camelCase ↔ snake_case
  bridge).
* 200 response body shape:
  ``{"values": [{"recordId": str, "data": {"embedding": [float...]}},
  ...]}`` -- :meth:`SearchSkillResponse.model_dump` is called with
  ``by_alias=True`` (emit ``recordId``) + ``exclude_none=True`` (drop
  the default-``None`` ``errors`` / ``warnings`` fields on the
  success path so the wire payload matches the v1 envelope shape one
  for one).
* 422 / 502 / 500 ladder owned by
  :func:`functions.core.exception_mapping.map_function_exceptions`
  (same as :mod:`functions.add_url.blueprint` and
  :mod:`functions.batch_start.blueprint`).

Registry-first collaborator wiring (Hard Rule #4):

* Credentials provider via ``credentials_registry``.
* Embedder via ``embedders_registry`` -- post-Phase-6 default key
  ``"azure_openai"`` (single concrete embedder today; promoted to
  settings when an alternate concrete lands).

No parser is resolved -- ``search_skill`` is the embed-on-the-fly
path: each input record already carries its chunk text, so the
embedder is the only collaborator the handler needs.

The private :func:`_execute` helper is the single seam route-level
tests monkeypatch so they do not need a real credential or a real
Azure OpenAI embedding deployment.
"""

from http import HTTPStatus

import azure.functions as func

from backend.core.providers.credentials import registry as credentials_registry
from backend.core.providers.embedders import registry as embedders_registry
from backend.core.settings import AppSettings, get_settings
from functions.core.exception_mapping import map_function_exceptions
from functions.core.http import json_response
from functions.search_skill.handler import search_skill_handler
from functions.search_skill.models import SearchSkillRequest, SearchSkillResponse

bp = func.Blueprint()


async def _execute(
    request: SearchSkillRequest, settings: AppSettings
) -> SearchSkillResponse:
    """Resolve collaborators and dispatch to ``search_skill_handler``.

    Extracted from :func:`search_skill` so route-level tests can
    monkeypatch this single seam instead of spinning up Foundry IQ +
    a real Azure OpenAI embedding deployment. Returns the typed
    :class:`SearchSkillResponse` so :func:`search_skill` can dump it
    to the wire shape with ``by_alias=True`` + ``exclude_none=True``.
    """
    cred_provider = credentials_registry.registry.get(
        credentials_registry.select_default(settings.identity.uami_client_id)
    )(settings=settings)
    async with await cred_provider.get_credential() as credential:
        embedder_cls = embedders_registry.registry.get("azure_openai")
        embedder = embedder_cls(settings=settings, credential=credential)
        try:
            return await search_skill_handler(request, embedder)
        finally:
            await embedder.aclose()


@bp.route(
    route="search_skill", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS
)
@map_function_exceptions("search_skill")
async def search_skill(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/search_skill -- embed every input record's text on the fly.

    Request body (JSON): :class:`SearchSkillRequest` (WebApiSkill
    envelope with camelCase wire field ``recordId``).
    Responses:
      * 200 -- ``{"values": [{"recordId": str, "data":
        {"embedding": [float...]}}, ...]}`` (errors / warnings
        omitted on the success path via ``exclude_none=True``).
      * 422 -- body failed Pydantic validation (owned by
        :func:`map_function_exceptions`).
      * 502 -- upstream Azure error from the embedder (owned by
        :func:`map_function_exceptions`).
      * 500 -- unexpected handler failure (final safety net owned by
        :func:`map_function_exceptions`). Vector-count mismatch
        (``RuntimeError`` from
        :func:`functions.search_skill.handler.search_skill_handler`)
        falls through to this branch.
    """
    request = SearchSkillRequest.model_validate_json(req.get_body() or b"{}")
    response = await _execute(request, get_settings())
    # ``model_dump`` is the SDK boundary per Hard Rule #15: ``by_alias``
    # emits the AI Search wire field ``recordId``; ``exclude_none``
    # omits the default-``None`` ``errors`` / ``warnings`` fields on
    # the success path so the wire payload stays minimal and matches
    # the v1 envelope shape.
    return json_response(
        response.model_dump(by_alias=True, exclude_none=True), HTTPStatus.OK
    )
