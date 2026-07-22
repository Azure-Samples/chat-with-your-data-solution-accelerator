"""Files router.

Single endpoint: ``GET /api/files/{filename}`` -- streams an ingested
document blob back to the browser so a chat citation can deep-link to
its source file.

The response sets ``Content-Disposition: inline`` with the original
filename plus a best-effort ``Content-Type`` guessed from the
extension, so the browser renders the document (PDF viewer, image,
...) in a new tab instead of forcing a download.

Status surface:

* ``200`` + raw bytes on success.
* ``400`` when the filename is malformed -- empty, overlong, or
  carrying a path-separator / parent-directory / control-character
  payload (the service layer's :func:`backend.services.files._validate_filename`
  raises :class:`ValueError`).
* ``404`` when no blob with that name exists.
* ``503`` when the deployment has no documents container configured
  (the route stays mounted so operators discover the gap explicitly
  instead of routing-404-ing it), and for any upstream
  ``AzureError`` -- which propagates to the app-level handler in
  :mod:`backend.exception_handlers` and is sanitised there with no SDK
  detail leaked.
"""

import mimetypes
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from fastapi.responses import Response

from backend.dependencies import CredentialDep, SettingsDep
from backend.models.errors import ErrorResponse
from backend.services.files import download_document

router = APIRouter(prefix="/api", tags=["files"])


@router.get(
    "/files/{filename}",
    summary="Stream a document blob",
    description=(
        "Stream a stored source-document blob by filename for inline "
        "rendering in the browser (for example when opening a citation). "
        "Responds 503 when document storage is not configured for the "
        "deployment."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid filename."},
        404: {"model": ErrorResponse, "description": "Blob not found."},
        503: {
            "model": ErrorResponse,
            "description": "Storage temporarily unavailable.",
        },
    },
)
async def get_file(
    filename: Annotated[str, Path(description="Stored blob filename to stream.")],
    settings: SettingsDep,
    credential: CredentialDep,
) -> Response:
    """Stream the document blob ``filename`` for inline rendering."""
    if not settings.storage.documents_container:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is not configured for this deployment.",
        )
    try:
        content = await download_document(
            filename, settings=settings, credential=credential
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        ) from exc
    # ``download_document`` already validated the filename (no control
    # characters), so it is safe to embed in the Content-Disposition
    # header without risk of header injection.
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
