"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

Event parser for the ``blob_event`` blueprint.

``blob_event`` is the Event Grid trigger that turns a
``Microsoft.Storage.BlobCreated`` event into a CWYD ingestion job: any
blob written to the documents container -- by a bulk drop, an admin
upload, or any other writer -- fires ``BlobCreated``, and this module
owns the first step: extracting the container + blob name the rest of
the pipeline needs.

The reliable source of that pair is the event ``subject``, whose shape
for a Storage blob event is::

    /blobServices/default/containers/<container>/blobs/<blob path>

The blob path may contain ``/`` (virtual directories) and is captured
whole. A subject that does not match this shape (a non-blob event, a
container-level event, or a malformed value) yields ``None`` so the
caller skips it rather than enqueueing an un-processable job.

Unlike the event ``data.url`` field, ``subject`` carries the blob name
un-encoded, so no percent-decoding is required here.
"""

import base64
import binascii
import json
import re

from pydantic import BaseModel, ConfigDict, Field

# Storage BlobCreated subject shape:
#   /blobServices/default/containers/<container>/blobs/<blob path>
# The container segment is a single path component; the blob remainder
# is captured greedily because virtual-directory blob names embed '/'.
_BLOB_SUBJECT_RE = re.compile(
    r"^/blobServices/default/containers/(?P<container>[^/]+)/blobs/(?P<blob>.+)$"
)


class ParsedBlobRef(BaseModel):
    """Container + blob name extracted from a ``BlobCreated`` subject.

    Frozen + ``extra="forbid"`` so the parsed reference is an immutable
    value the handler reads to build a ``BatchPushQueueMessage``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    container_name: str = Field(min_length=1)
    filename: str = Field(min_length=1)


def parse_blob_created_subject(subject: str) -> ParsedBlobRef | None:
    """Extract the container + blob name from an Event Grid subject.

    Returns a :class:`ParsedBlobRef` when ``subject`` matches the
    ``/blobServices/default/containers/<c>/blobs/<b>`` shape, or
    ``None`` when it does not -- so a non-blob, container-level, or
    malformed subject is skipped instead of enqueued. A subject whose
    blob segment is only whitespace also yields ``None`` (the
    ``min_length=1`` field with ``str_strip_whitespace`` rejects it,
    surfaced here as a skip rather than an error).
    """
    match = _BLOB_SUBJECT_RE.match(subject)
    if match is None:
        return None
    container = match.group("container").strip()
    blob = match.group("blob").strip()
    if not container or not blob:
        return None
    return ParsedBlobRef(container_name=container, filename=blob)


def subject_from_event_message(raw: bytes | str) -> str | None:
    """Extract the ``subject`` from a raw Event Grid event message body.

    The Event Grid system topic delivers one ``BlobCreated`` event per
    Storage Queue message (EventGridSchema), whose top-level ``subject``
    is the ``/blobServices/default/containers/<c>/blobs/<b>`` path that
    :func:`parse_blob_created_subject` turns into a container + blob
    reference. Returns that subject string, or ``None`` when the body is
    not a JSON object carrying a string ``subject`` (so a malformed or
    non-event message is skipped rather than ingested).

    The body is tried as raw JSON first, then as base64-decoded JSON,
    because Event Grid's Storage-Queue wire encoding is an external
    behavior outside our control (raw JSON under the host's
    ``messageEncoding = none``, but base64 is tolerated defensively).
    A single-event JSON array is also accepted.
    """
    payload: object = None
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        try:
            payload = json.loads(base64.b64decode(raw, validate=True))
        except (binascii.Error, json.JSONDecodeError, ValueError, UnicodeDecodeError):
            return None
    if isinstance(payload, list):
        payload = payload[0] if payload else None
    if not isinstance(payload, dict):
        return None
    subject = payload.get("subject")
    return subject if isinstance(subject, str) else None
