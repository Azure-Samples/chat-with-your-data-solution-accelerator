"""Event parser for the ``blob_event`` blueprint.

``blob_event`` is the Event Grid trigger over Storage blob events on the
documents container: a ``BlobCreated`` event (bulk drop, admin upload,
any writer) drives ingestion, and a ``BlobDeleted`` event (bulk delete,
Storage Explorer) drives de-indexing. This module owns the first step:
classifying the event type (:class:`BlobEventType`) and extracting the
container + blob name the rest of the pipeline needs.

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
from enum import StrEnum
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

# Storage BlobCreated subject shape:
#   /blobServices/default/containers/<container>/blobs/<blob path>
# The container segment is a single path component; the blob remainder
# is captured greedily because virtual-directory blob names embed '/'.
_BLOB_SUBJECT_RE = re.compile(
    r"^/blobServices/default/containers/(?P<container>[^/]+)/blobs/(?P<blob>.+)$"
)


class BlobEventType(StrEnum):
    """The Storage blob events the ``blob_event`` handler acts on.

    ``CREATED`` drives ingestion (a blob was written -> enqueue a
    doc-processing job); ``DELETED`` drives de-indexing (a blob was
    removed -> delete its indexed chunks). Any other Event Grid event
    type is skipped by :func:`parse_blob_event`.
    """

    CREATED = "Microsoft.Storage.BlobCreated"
    DELETED = "Microsoft.Storage.BlobDeleted"


# Reverse map for narrowing a raw `eventType` string to a known member
# without a try/except (an unknown type maps to None -> skip).
_EVENT_TYPE_BY_VALUE = {member.value: member for member in BlobEventType}


class ParsedBlobRef(BaseModel):
    """Container + blob name extracted from a ``BlobCreated`` subject.

    Frozen + ``extra="forbid"`` so the parsed reference is an immutable
    value the handler reads to build a ``BatchPushQueueMessage``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    container_name: str = Field(min_length=1)
    filename: str = Field(min_length=1)


class ParsedBlobEvent(BaseModel):
    """Event type + blob reference parsed from one Event Grid message.

    Frozen + ``extra="forbid"``: the handler reads ``event_type`` to
    choose ingest (:attr:`BlobEventType.CREATED`) vs de-index
    (:attr:`BlobEventType.DELETED`) and ``ref`` for the container +
    blob name.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: BlobEventType
    ref: ParsedBlobRef


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


def _decode_event_payload(raw: bytes | str) -> dict[str, Any] | None:
    """Decode one Event Grid Storage-Queue message body to a dict.

    The body is tried as raw JSON first, then as base64-decoded JSON,
    because Event Grid's Storage-Queue wire encoding is an external
    behavior outside our control (raw JSON under the host's
    ``messageEncoding = none``, but base64 is tolerated defensively).
    A single-event JSON array is unwrapped to its first element.
    Returns ``None`` when the body is not a JSON object (so a malformed
    or non-event message is skipped rather than processed).
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
    return cast("dict[str, Any]", payload)


def parse_blob_event(raw: bytes | str) -> ParsedBlobEvent | None:
    """Parse a raw Event Grid message into a typed blob event.

    Extracts the ``eventType`` and ``subject`` from the message body and
    returns a :class:`ParsedBlobEvent` carrying the matched
    :class:`BlobEventType` (CREATED / DELETED) and the parsed container
    + blob reference. Returns ``None`` -- so the caller skips the
    message -- when the body is not a blob event we handle: a malformed
    / non-JSON body, an ``eventType`` other than BlobCreated /
    BlobDeleted, or a ``subject`` that is not a
    ``/containers/<c>/blobs/<b>`` blob path. (BlobCreated and BlobDeleted
    share the same subject shape, so one subject parser serves both.)
    """
    payload = _decode_event_payload(raw)
    if payload is None:
        return None
    event_type_raw = payload.get("eventType")
    event_type = (
        _EVENT_TYPE_BY_VALUE.get(event_type_raw)
        if isinstance(event_type_raw, str)
        else None
    )
    if event_type is None:
        return None
    subject = payload.get("subject")
    if not isinstance(subject, str):
        return None
    ref = parse_blob_created_subject(subject)
    if ref is None:
        return None
    return ParsedBlobEvent(event_type=event_type, ref=ref)
