"""Admin router.

Operator surface for the v2 backend. Exposes:

* ``GET /api/admin/status`` -- sanitized snapshot of the running
  configuration (effective orchestrator key, db type, vector index
  store, environment, deployment names, feature-enabled flags, CORS
  list, app version). Surfaces only **non-secret** values: tenant ids,
  UAMI ids, and full database / Cosmos endpoints stay out of the
  payload (covered by ``test_status_does_not_leak_sensitive_settings``).

* ``GET /api/admin/config`` and ``PATCH /api/admin/config`` --
  read / write the runtime-toggle subset of ``AppSettings``.

* ``GET /api/admin/config/effective`` -- merged view of env defaults
  overlaid with persisted ``RuntimeConfig`` overrides + per-field
  provenance hints. Reads the override side via the live-reload
  channel so PATCHes are visible immediately.

* the document write routes (upload, URL ingest, reprocess, delete)
  that fan work onto the ingestion pipeline.

Every route resolves the caller through
:data:`backend.dependencies.UserIdDep`, which reads the
``x-ms-client-principal-id`` header and returns the caller's GUID when
it is present and well-formed, or the anonymous default GUID otherwise.
There is no role gate and no Easy Auth requirement -- the router never
rejects a request on identity grounds.
"""

import logging
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Body,
    File,
    HTTPException,
    Path,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError

from backend.dependencies import (
    AgentsProviderDep,
    CredentialDep,
    DatabaseClientDep,
    RuntimeOverridesDep,
    SearchProviderDep,
    SettingsDep,
    UserIdDep,
)
from backend.core.agents.definitions import CWYD_DEFAULT_BODY
from backend.core.agents.presets import (
    ASSISTANT_PRESETS,
    DEFAULT_ASSISTANT_TYPE,
    DEFAULT_POST_ANSWERING_FILTER_MESSAGE,
    DEFAULT_POST_ANSWERING_PROMPT,
)
from backend.core.types import AdminAuditEntry, RuntimeConfig
from backend.models.admin import (
    APP_VERSION,
    AdminConfig,
    AdminStatus,
    ConfigSource,
    DeleteDocumentResponse,
    EffectiveAdminConfig,
    IngestUrlRequest,
    IngestUrlResponse,
    ListDocumentsResponse,
    PROMPT_FIELDS,
    ReprocessResponse,
    UploadResponse,
    WRITABLE_FIELDS,
)
from backend.models.errors import ErrorResponse
from backend.services.admin import (
    host_only,
    resolve_effective_config,
    utcnow_iso,
    validate_prompt_with_rai,
)
from backend.services.files import delete_document
from backend.services.ingestion import (
    UploadRejected,
    ingest_url,
    reprocess_all,
    upload_document,
    validate_upload,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


# Routes


@router.get(
    "/status",
    response_model=AdminStatus,
    summary="Get runtime status",
    description=(
        "Return a sanitized runtime status snapshot: the effective "
        "orchestrator (env default overlaid with any persisted override), "
        "the configured database / index store, and enabled-feature flags. "
        "Secrets are never surfaced."
    ),
)
async def status_endpoint(
    settings: SettingsDep,
    overrides: RuntimeOverridesDep,
    _user: UserIdDep,
) -> AdminStatus:
    """Return the sanitized runtime status snapshot.

    The orchestrator is the **effective** value -- the env / code
    default overlaid with any persisted ``RuntimeConfig`` override --
    resolved through the same `resolve_effective_config` seam the chat
    path and ``GET /config/effective`` use, so the snapshot matches what
    the deployment actually runs: immediately after a save (PATCH
    live-reloads ``app.state.runtime_overrides``) and after a restart
    (the lifespan re-seeds that attribute from the database at boot).
    The remaining fields are infra / env settings that are not
    admin-overridable, so they surface from ``settings`` directly.
    """
    obs_conn = settings.observability.app_insights_connection_string.strip()
    effective = resolve_effective_config(settings, overrides)
    return AdminStatus(
        orchestrator_name=effective.orchestrator_name,
        db_type=settings.database.db_type,
        index_store=settings.database.index_store,
        environment=settings.environment,
        foundry_project_endpoint_host=host_only(settings.foundry.project_endpoint),
        gpt_deployment=settings.openai.gpt_deployment,
        embedding_deployment=settings.openai.embedding_deployment,
        search_enabled=bool(settings.search.endpoint),
        app_insights_enabled=bool(obs_conn),
        cors_origins=list(settings.network.cors_origins),
        version=APP_VERSION,
    )


@router.get(
    "/config",
    response_model=AdminConfig,
    summary="Get runtime config defaults",
    description=(
        "Return the read-only, runtime-toggleable subset of application "
        "settings (env / code defaults). Mutations go through "
        "PATCH /api/admin/config."
    ),
)
async def config_endpoint(
    settings: SettingsDep,
    _user: UserIdDep,
) -> AdminConfig:
    """Return the runtime-toggle subset of ``AppSettings``.

    Read-only. Mutations go through ``PATCH /api/admin/config``.
    """
    return AdminConfig(
        orchestrator_name=settings.orchestrator.name,
        openai_temperature=settings.openai.temperature,
        openai_max_tokens=settings.openai.max_tokens,
        search_use_semantic_search=settings.search.use_semantic_search,
        search_top_k=settings.search.top_k,
        log_level=settings.observability.log_level,
        content_safety_enabled=settings.content_safety.enabled,
        # The editable persona body -- not the guardrail-wrapped runtime
        # prompt. The fixed guardrail is appended exactly once at request
        # time by `resolve_effective_config`; surfacing the body here keeps
        # the operator's editor free of the non-negotiable rules so a
        # seed-edit-save round-trip cannot bake the guardrail into the
        # stored override and double-wrap it.
        cwyd_agent_instructions=CWYD_DEFAULT_BODY,
        ai_assistant_type=DEFAULT_ASSISTANT_TYPE,
        post_answering_prompt=DEFAULT_POST_ANSWERING_PROMPT,
        post_answering_enabled=False,
        post_answering_filter_message=DEFAULT_POST_ANSWERING_FILTER_MESSAGE,
    )


@router.get(
    "/config/effective",
    response_model=EffectiveAdminConfig,
    summary="Get effective runtime config",
    description=(
        "Return the effective runtime config: env defaults overlaid with "
        "persisted overrides, plus per-field provenance (env vs override) "
        "and audit metadata. Reflects saved PATCHes immediately."
    ),
)
async def config_effective_endpoint(
    settings: SettingsDep,
    overrides: RuntimeOverridesDep,
    _user: UserIdDep,
) -> EffectiveAdminConfig:
    """Return env defaults overlaid with persisted overrides + per-field
    provenance hints.

    Reads the override side via the live-reload channel
    (`get_runtime_overrides` -> `request.app.state.runtime_overrides`)
    seeded by the lifespan loader and refreshed by every successful
    PATCH, so this endpoint reflects PATCHes immediately
    without a database round-trip.
    """
    # Env defaults -- same surface as `GET /api/admin/config`.
    env_values: dict[str, Any] = {
        "orchestrator_name": settings.orchestrator.name,
        "openai_temperature": settings.openai.temperature,
        "openai_max_tokens": settings.openai.max_tokens,
        "search_use_semantic_search": settings.search.use_semantic_search,
        "search_top_k": settings.search.top_k,
        "log_level": settings.observability.log_level,
        "content_safety_enabled": settings.content_safety.enabled,
        # The editable persona body baseline -- a persisted override (also
        # a raw body) overlays it below. Neither carries the fixed
        # guardrail; it is appended once at request time by
        # `resolve_effective_config`.
        "cwyd_agent_instructions": CWYD_DEFAULT_BODY,
        "ai_assistant_type": DEFAULT_ASSISTANT_TYPE,
        "post_answering_prompt": DEFAULT_POST_ANSWERING_PROMPT,
        "post_answering_enabled": False,
        "post_answering_filter_message": DEFAULT_POST_ANSWERING_FILTER_MESSAGE,
    }
    merged: dict[str, Any] = dict(env_values)
    sources: dict[str, ConfigSource] = {name: ConfigSource.ENV for name in env_values}
    if overrides is not None:
        for name in env_values:
            override_value = getattr(overrides, name)
            # `None` means "not overridden, fall through to env default"
            # (the storage shape uses `T | None = None` per RuntimeConfig
            # docstring); only non-None values count as overrides.
            if override_value is not None:
                merged[name] = override_value
                sources[name] = ConfigSource.OVERRIDE

    # Surface audit fields whenever an override row exists, even if
    # every field has been cleared back to env -- the row itself is
    # the receipt that an operator interacted with the config.
    updated_at: str | None = None
    updated_by: str | None = None
    if overrides is not None:
        updated_at = overrides.updated_at or None
        updated_by = overrides.updated_by or None

    return EffectiveAdminConfig(
        values=AdminConfig(**merged),
        sources=sources,
        assistant_type_presets={
            member.value: body for member, body in ASSISTANT_PRESETS.items()
        },
        updated_at=updated_at,
        updated_by=updated_by,
    )


# PATCH /api/admin/config -- runtime overrides
#
# RFC 7396 JSON Merge Patch over the same 6-field surface as GET. The
# merge is computed at the route layer (NOT pushed into the storage
# layer) so the storage contract stays a dumb full-payload overwrite
# (`upsert_runtime_config` writes whatever it's given) -- mirrors the
# `upsert_agent_id` precedent and keeps merge semantics tested in one
# place. Live-reload of `app.state.settings` is **deliberately
# deferred**. Operators observe their PATCHes immediately in the
# response body and on the next container restart.


@router.patch(
    "/config",
    response_model=RuntimeConfig,
    summary="Patch runtime config",
    description=(
        "Apply an RFC 7396 JSON Merge Patch to the persisted runtime "
        "config and return the merged shape. An explicit null clears an "
        "override (reverting the field to its env default); an unknown key "
        "or wrong-type value responds 422."
    ),
    responses={
        422: {
            "model": ErrorResponse,
            "description": ("Unknown field, wrong-type value, or RAI-rejected prompt."),
        },
    },
)
async def patch_config_endpoint(
    request: Request,
    db: DatabaseClientDep,
    user_id: UserIdDep,
    agents: AgentsProviderDep,
    payload: Annotated[dict[str, Any], Body(...)],
) -> RuntimeConfig:
    """Apply an RFC 7396 JSON Merge Patch to the persisted
    `RuntimeConfig` and return the merged shape.

    Semantics:

    * Absent JSON key -> existing override unchanged.
    * Explicit ``null`` -> override cleared (the field reverts to its
      `AppSettings` env default on the next live-reload).
    * Explicit value -> override set / replaced.
    * Unknown JSON key -> 422 (allow-list lock-in).
    * Wrong-type value -> 422 (Pydantic validation on the merged
      `RuntimeConfig`).

    The body is read as a raw `dict[str, Any]` -- not bound to a
    Pydantic model with all-optional fields -- so the route can
    distinguish 'absent' from 'explicit null' (RFC 7396 §1). A
    Pydantic-bound body would silently coerce both into `None`,
    breaking the 'undo my override' UX.
    """
    # Allow-list lock-in (rejects unknown fields with 422)
    unknown = set(payload) - WRITABLE_FIELDS
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "msg": "Unknown field(s) in PATCH body",
                "unknown_fields": sorted(unknown),
                "allowed_fields": sorted(WRITABLE_FIELDS),
            },
        )

    # RAI safety gate on operator-authored prompts. Runs BEFORE the
    # merge / type validation / upsert / live-reload / audit chain so a
    # rejected payload never lands in storage and never triggers an audit
    # row (matches the 422-validation precedent below). Only fields keyed
    # in `PROMPT_FIELDS` are screened; clearing a prompt (`null`) and
    # empty / whitespace strings short-circuit the classifier so the
    # operator can revert to the default without paying a Foundry
    # round-trip.
    for field_name in PROMPT_FIELDS:
        if field_name not in payload:
            continue
        value = payload[field_name]
        if not isinstance(value, str):
            # Non-string values (`null`, numerics) are handled by the
            # downstream Pydantic type check on the merged shape; the
            # RAI gate only classifies actual prompt text.
            continue
        reason = await validate_prompt_with_rai(value, agents, db)
        if reason is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "msg": "RAI safety check rejected the submitted prompt",
                    "field": field_name,
                    "reason": reason,
                },
            )

    # Read current overrides; default to a fresh RuntimeConfig on cold
    # start so the first-ever PATCH still goes through the merge path.
    # `before` keeps the raw fetch (None on first-ever PATCH) so the
    # audit row can distinguish 'no prior override' from
    # 'all-cleared override'.
    before = await db.get_runtime_config()
    current = before or RuntimeConfig()
    merged_data: dict[str, Any] = current.model_dump()

    # Apply the patch (overwrites None when key is `null`, sets when
    # key carries a value, leaves field untouched when key is absent).
    for key, value in payload.items():
        merged_data[key] = value

    # Server-set audit fields -- always overwritten on every PATCH so
    # an operator probing 'what's the latest override state?' can sort
    # by `updated_at` deterministically.
    merged_data["updated_at"] = utcnow_iso()
    merged_data["updated_by"] = user_id

    # Type validation on the merged shape (turns wrong-type values
    # into 422 with Pydantic's structured error detail).
    try:
        merged = RuntimeConfig.model_validate(merged_data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc

    await db.upsert_runtime_config(merged)
    # Live-reload. Reassign `app.state.runtime_overrides` to
    # the same instance we just persisted so the next request's
    # `get_runtime_overrides` dependency surfaces the new override
    # without a container restart. Atomic Python attribute write --
    # no lock needed because Python's GIL makes single-attribute
    # rebinds visible-or-not, never half-applied.
    request.app.state.runtime_overrides = merged

    # Audit hook. Fire-and-forget append to the
    # `admin_audit` log so a future forensic query can answer
    # who / what / before / after for every successful PATCH.
    # **Best-effort policy**: a failure here MUST NOT roll back
    # the PATCH -- the override is already persisted AND
    # live-reloaded; surfacing 500 to the operator would mislead
    # them into retrying a PATCH that actually succeeded. The
    # failure is logged so the gap is observable in App Insights.
    try:
        await db.write_admin_audit(
            AdminAuditEntry(
                actor=user_id,
                action="patch_config",
                before=before,
                after=merged,
            )
        )
    except Exception:
        logger.exception(
            "write_admin_audit failed; PATCH succeeded but audit row missing",
            extra={
                "operation": "write_admin_audit",
                "actor": user_id,
                "action": "patch_config",
            },
        )

    return merged


# GET /api/admin/documents -- list every distinct source currently indexed,
# with the chunk count per source. Feeds the admin UI's Delete Data grid.


@router.get(
    "/documents",
    response_model=ListDocumentsResponse,
    status_code=status.HTTP_200_OK,
    summary="List indexed documents",
    description=(
        "List every distinct indexed source (filename or URL) with its "
        "chunk count, sorted by source name. Returns an empty list when "
        "nothing is indexed; responds 503 when no search backend is "
        "configured."
    ),
    responses={
        503: {
            "model": ErrorResponse,
            "description": "Search backend not configured.",
        },
    },
)
async def list_documents_endpoint(
    search: SearchProviderDep,
    _user: UserIdDep,
) -> ListDocumentsResponse:
    """List every distinct source currently indexed.

    Returns one :class:`SourceListing` per distinct source (filename or
    URL set on the ``title`` field at ingestion), with the chunk count
    per source. The list is service-side sorted by source name so the
    FE grid is deterministic without a client-side sort.

    Status surface:

    * ``200`` + :class:`ListDocumentsResponse` -- always, even when no
      sources are indexed (``documents=[]``, ``total=0``). An empty
      index is a valid operating state, not an error.
    * ``503`` when the deployment has no search backend configured
      (the route stays mounted so operators discover the gap
      explicitly instead of routing-404-ing it).
    * Upstream ``AzureError`` / ``asyncpg.PostgresError`` propagate to
      the app-level handlers in :mod:`backend.app`, which sanitise
      both into 503 responses with no SDK detail leaked.
    """
    if search is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search backend is not configured for this deployment.",
        )
    listings = await search.list_sources()
    return ListDocumentsResponse(
        documents=list(listings),
        total=len(listings),
    )


# DELETE /api/admin/documents/{source} -- remove every indexed chunk attached
# to the given source (filename or URL set at ingestion time).


@router.delete(
    "/documents/{source:path}",
    response_model=DeleteDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete an indexed document",
    description=(
        "Remove a document's indexed chunks and its source blob so it "
        "becomes fully unreachable. Responds 404 when neither existed and "
        "503 when no search backend is configured."
    ),
    responses={
        404: {
            "model": ErrorResponse,
            "description": "No indexed chunks or source blob found.",
        },
        503: {
            "model": ErrorResponse,
            "description": "Search backend not configured.",
        },
    },
)
async def delete_document_endpoint(
    source: Annotated[
        str, Path(description="Blob source path to de-index and delete.")
    ],
    settings: SettingsDep,
    credential: CredentialDep,
    search: SearchProviderDep,
    _user: UserIdDep,
) -> DeleteDocumentResponse:
    """Delete a document's indexed chunks **and** its source blob.

    ``source`` is the per-chunk filename or URL set at ingestion (the
    ``title`` field on every search backend). The ``{source:path}``
    converter captures URL-typed sources that contain slashes;
    FastAPI percent-decodes the path segment before the handler runs.

    Removal is two-part so a deleted document becomes fully unreachable:

    * the indexed chunks (search / pgvector), via
      :meth:`BaseSearch.delete_by_source`; and
    * the source blob in the documents container, via
      :func:`backend.services.files.delete_document` -- attempted only
      when a documents container is configured, and skipped for
      URL-typed sources (a URL carries path separators, has no backing
      blob, and raises :class:`ValueError` from filename validation).

    Status surface:

    * ``200`` + ``{"deleted": N, "blob_deleted": bool}`` when at least
      one indexed chunk was removed or the source blob was deleted.
    * ``404`` when neither an indexed chunk nor a source blob existed.
    * ``503`` when the deployment has no search backend configured
      (the route stays mounted so operators discover the gap
      explicitly instead of routing-404-ing it).
    * Upstream ``AzureError`` / ``asyncpg.PostgresError`` propagate to
      the app-level handlers in :mod:`backend.app`, which sanitise
      both into 503 responses with no SDK detail leaked.
    """
    if search is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search backend is not configured for this deployment.",
        )
    deleted = await search.delete_by_source(source)
    blob_deleted = False
    if settings.storage.documents_container:
        try:
            blob_deleted = await delete_document(
                source, settings=settings, credential=credential
            )
        except ValueError:
            # URL-typed sources (add_url ingestion) carry path
            # separators and have no backing blob -- nothing to delete.
            blob_deleted = False
    if deleted == 0 and not blob_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No indexed chunks or source blob found for source {source!r}.",
        )
    logger.info(
        "Admin deleted document.",
        extra={
            "operation": "delete_document",
            "source": source,
            "deleted_count": deleted,
            "blob_deleted": blob_deleted,
        },
    )
    return DeleteDocumentResponse(deleted=deleted, blob_deleted=blob_deleted)


# POST /api/admin/documents/url -- download one URL, store it as a blob, and
# ingest it like an uploaded file (the same store -> batch_push pipeline).
# FE-facing entry point so the admin UI can drive URL ingest through FastAPI
# instead of reaching into the Functions HTTP trigger.


@router.post(
    "/documents/url",
    response_model=IngestUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a document from a URL",
    description=(
        "Download the given URL, store its bytes as a blob, and index it "
        "through the same pipeline as an uploaded file. Responds 422 on an "
        "invalid URL and 503 when storage or the processing queue is not "
        "configured."
    ),
    responses={
        422: {"model": ErrorResponse, "description": "Invalid URL."},
        503: {
            "model": ErrorResponse,
            "description": "Storage or processing queue not configured.",
        },
    },
)
async def ingest_url_endpoint(
    body: IngestUrlRequest,
    settings: SettingsDep,
    credential: CredentialDep,
    _user: UserIdDep,
) -> IngestUrlResponse:
    """Download ``body.url`` and ingest its content like an uploaded file.

    Delegates to :func:`backend.services.ingestion.ingest_url`, which
    fetches the URL, writes its bytes to the documents container as a
    blob, and lets the same ``batch_push`` pipeline used by file upload
    index it (enqueued under ``DIRECT_ENQUEUE``; Event-Grid-driven
    otherwise). Mirrors v1's ``download_url_and_upload_to_blob`` admin
    path so URL and file ingestion share one pipeline.

    Status surface:

    * ``200`` + :class:`IngestUrlResponse` (URL echo + the upload
      receipt) on success.
    * ``422`` when the body fails Pydantic validation (URL empty or
      too long).
    * ``503`` when the deployment has no documents container or
      doc-processing queue configured -- the route stays mounted so
      operators discover the gap explicitly instead of routing-404-ing
      it.
    * Upstream ``httpx.HTTPError`` (bad URL, dead host) / ``AzureError``
      (blob write, queue send) propagate to the app-level handlers in
      :mod:`backend.app`.
    """
    if (
        not settings.storage.documents_container
        or not settings.storage.doc_processing_queue
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Storage is not configured for this deployment "
                "(documents container / doc-processing queue)."
            ),
        )
    return await ingest_url(
        body,
        settings=settings,
        credential=credential,
    )


# POST /api/admin/documents -- multipart file upload. Writes to the source
# blob container and enqueues a push message so the existing ``batch_push``
# queue consumer runs the same parse + embed + push pipeline used by
# ``batch_start``.


@router.post(
    "/documents",
    response_model=UploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload a document",
    description=(
        "Upload a single document (multipart) and enqueue it for indexing. "
        "Responds 413 when too large, 415 for an unsupported file type, "
        "and 503 when storage / the processing queue is not configured."
    ),
    responses={
        413: {"model": ErrorResponse, "description": "Uploaded file too large."},
        415: {
            "model": ErrorResponse,
            "description": "Unsupported file type.",
        },
        422: {
            "model": ErrorResponse,
            "description": "Missing file part or empty filename.",
        },
        503: {
            "model": ErrorResponse,
            "description": (
                "Storage / processing queue not configured, or Document "
                "Intelligence not configured for this file type."
            ),
        },
    },
)
async def upload_document_endpoint(
    settings: SettingsDep,
    credential: CredentialDep,
    _user: UserIdDep,
    file: Annotated[UploadFile, File(...)],
) -> UploadResponse:
    """Upload a single document and enqueue it for indexing.

    Status surface:

    * ``200`` + :class:`UploadResponse` on success.
    * ``413`` when the uploaded file exceeds
      :data:`backend.services.ingestion.MAX_UPLOAD_SIZE_BYTES`.
    * ``415`` when the filename has no extension or an extension
      that is not registered in the parser registry -- the parser
      registry is the authoritative source of "supported file
      types" for the whole pipeline (Hard Rule #4).
    * ``422`` when the multipart body is missing the ``file`` part
      or the filename is empty (FastAPI / Pydantic native).
    * ``503`` when the deployment has no documents container or
      doc-processing queue configured -- the route stays mounted so
      operators discover the gap explicitly instead of
      routing-404-ing it.
    * ``503`` when a Document-Intelligence-routed file (PDF / DOCX) is
      uploaded while ``AZURE_AI_SERVICES_ENDPOINT`` is unset or not an
      https URL -- the parse step would poison every queued message, so
      the route refuses at the boundary rather than reporting a success
      the file can never honour.
    * Upstream ``AzureError`` (blob upload, queue send) propagates
      to the app-level handlers in :mod:`backend.app`, which
      sanitise it into a 503 response with no SDK detail leaked.
    """
    filename = (file.filename or "").strip()
    content = await file.read()
    try:
        validate_upload(filename, len(content), settings=settings)
    except UploadRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return await upload_document(
        filename=filename,
        content=content,
        settings=settings,
        credential=credential,
    )


# POST /api/admin/documents/reprocess -- re-fan every blob in the documents
# container onto the push queue so every existing document is re-parsed,
# re-embedded, and re-pushed through the same pipeline a freshly-uploaded
# file traverses. Single ``batch_start_handler`` invocation under the hood.


@router.post(
    "/documents/reprocess",
    response_model=ReprocessResponse,
    status_code=status.HTTP_200_OK,
    summary="Reprocess all documents",
    description=(
        "Re-fan every blob in the documents container onto the push queue "
        "so all indexed documents are re-parsed, re-embedded, and "
        "re-pushed. Responds 503 when storage / the processing queue is "
        "not configured."
    ),
    responses={
        503: {
            "model": ErrorResponse,
            "description": "Storage or processing queue not configured.",
        },
    },
)
async def reprocess_all_endpoint(
    settings: SettingsDep,
    credential: CredentialDep,
    _user: UserIdDep,
) -> ReprocessResponse:
    """Fan every blob in the documents container out to the push queue.

    Status surface:

    * ``200`` + :class:`ReprocessResponse` on success.
      ``ingestion_job_id`` is ``None`` when the container is empty so
      the FE can distinguish "nothing to do" from "queued N items".
    * ``503`` when the deployment has no documents container or
      doc-processing queue configured -- the route stays mounted so
      operators discover the gap explicitly instead of
      routing-404-ing it.
    * Upstream ``AzureError`` (blob listing, queue send) propagates
      to the app-level handlers in :mod:`backend.app`.
    """
    if (
        not settings.storage.documents_container
        or not settings.storage.doc_processing_queue
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=("Document storage is not configured for this deployment."),
        )
    return await reprocess_all(settings=settings, credential=credential)


__all__ = [
    "ConfigSource",
    "router",
]
