"""Pillar: Stable Core / Phase: 6 — tests for v2/src/functions/blob_event/event_parser.py."""

import base64
import json

import pytest
from pydantic import ValidationError

from functions.blob_event.event_parser import (
    BlobEventType,
    ParsedBlobEvent,
    ParsedBlobRef,
    parse_blob_created_subject,
    parse_blob_event,
)


def test_parses_canonical_documents_subject() -> None:
    subject = "/blobServices/default/containers/documents/blobs/Benefit_Options.pdf"
    assert parse_blob_created_subject(subject) == ParsedBlobRef(
        container_name="documents", filename="Benefit_Options.pdf"
    )


def test_captures_virtual_directory_blob_path_whole() -> None:
    subject = "/blobServices/default/containers/documents/blobs/2026/q1/report.pdf"
    parsed = parse_blob_created_subject(subject)
    assert parsed is not None
    assert parsed.container_name == "documents"
    # The blob path keeps its embedded '/' separators.
    assert parsed.filename == "2026/q1/report.pdf"


def test_non_documents_container_still_parses() -> None:
    # The parser is container-agnostic; the Event Grid filter scopes to
    # documents/, but parsing must not hard-code the container name.
    subject = "/blobServices/default/containers/config/blobs/settings.json"
    parsed = parse_blob_created_subject(subject)
    assert parsed is not None
    assert parsed.container_name == "config"
    assert parsed.filename == "settings.json"


@pytest.mark.parametrize(
    "subject",
    [
        "",
        "not-a-blob-subject",
        # Container-level event (no /blobs/ segment) -> skip.
        "/blobServices/default/containers/documents",
        "/blobServices/default/containers/documents/",
        # Missing the blobServices prefix.
        "/containers/documents/blobs/file.pdf",
        # A queue/table subject shape.
        "/queueServices/default/queues/doc-processing",
    ],
)
def test_non_matching_subject_returns_none(subject: str) -> None:
    assert parse_blob_created_subject(subject) is None


def test_blank_blob_segment_returns_none() -> None:
    # A subject whose blob segment is only whitespace is a skip, not a
    # ParsedBlobRef with an empty filename.
    subject = "/blobServices/default/containers/documents/blobs/   "
    assert parse_blob_created_subject(subject) is None


def test_parsed_ref_is_frozen() -> None:
    ref = parse_blob_created_subject(
        "/blobServices/default/containers/documents/blobs/a.pdf"
    )
    assert ref is not None
    with pytest.raises(ValidationError):
        ref.filename = "b.pdf"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Shared raw-event-body fixtures (used by the parse_blob_event cases below)
# ---------------------------------------------------------------------------

_SUBJECT = "/blobServices/default/containers/documents/blobs/Benefit_Options.pdf"


def _event_body(subject: str) -> dict[str, object]:
    return {
        "topic": "/subscriptions/x/resourceGroups/y/providers/Microsoft.Storage/storageAccounts/st",
        "subject": subject,
        "eventType": "Microsoft.Storage.BlobCreated",
        "id": "abc",
        "data": {"api": "PutBlob", "url": f"https://st.blob.core.windows.net{subject}"},
        "dataVersion": "1",
    }



# ---------------------------------------------------------------------------
# parse_blob_event — classify the event type + parse the blob reference
# ---------------------------------------------------------------------------


def _typed_event_body(subject: str, event_type: str) -> dict[str, object]:
    body = _event_body(subject)
    body["eventType"] = event_type
    return body


def test_parses_blob_created_event() -> None:
    raw = json.dumps(
        _typed_event_body(_SUBJECT, "Microsoft.Storage.BlobCreated")
    ).encode("utf-8")
    assert parse_blob_event(raw) == ParsedBlobEvent(
        event_type=BlobEventType.CREATED,
        ref=ParsedBlobRef(container_name="documents", filename="Benefit_Options.pdf"),
    )


def test_parses_blob_deleted_event() -> None:
    raw = json.dumps(
        _typed_event_body(_SUBJECT, "Microsoft.Storage.BlobDeleted")
    ).encode("utf-8")
    assert parse_blob_event(raw) == ParsedBlobEvent(
        event_type=BlobEventType.DELETED,
        ref=ParsedBlobRef(container_name="documents", filename="Benefit_Options.pdf"),
    )


def test_parses_event_from_single_event_array() -> None:
    raw = json.dumps(
        [_typed_event_body(_SUBJECT, "Microsoft.Storage.BlobDeleted")]
    ).encode("utf-8")
    parsed = parse_blob_event(raw)
    assert parsed is not None
    assert parsed.event_type == BlobEventType.DELETED


def test_parses_event_from_base64_body() -> None:
    raw = base64.b64encode(
        json.dumps(_typed_event_body(_SUBJECT, "Microsoft.Storage.BlobCreated")).encode(
            "utf-8"
        )
    )
    parsed = parse_blob_event(raw)
    assert parsed is not None
    assert parsed.event_type == BlobEventType.CREATED


def test_unknown_event_type_returns_none() -> None:
    raw = json.dumps(
        _typed_event_body(_SUBJECT, "Microsoft.Storage.BlobTierChanged")
    ).encode("utf-8")
    assert parse_blob_event(raw) is None


def test_missing_event_type_returns_none() -> None:
    body = _event_body(_SUBJECT)
    del body["eventType"]
    raw = json.dumps(body).encode("utf-8")
    assert parse_blob_event(raw) is None


def test_non_string_event_type_returns_none() -> None:
    raw = json.dumps(_typed_event_body(_SUBJECT, "")).encode("utf-8")
    # An empty eventType is not a known member -> skip.
    assert parse_blob_event(raw) is None


def test_event_with_malformed_subject_returns_none() -> None:
    raw = json.dumps(
        _typed_event_body("not-a-blob-subject", "Microsoft.Storage.BlobCreated")
    ).encode("utf-8")
    assert parse_blob_event(raw) is None


def test_event_without_subject_returns_none() -> None:
    raw = json.dumps({"eventType": "Microsoft.Storage.BlobCreated"}).encode("utf-8")
    assert parse_blob_event(raw) is None


def test_event_malformed_body_returns_none() -> None:
    assert parse_blob_event(b"not-json-not-base64-!!!") is None


def test_parsed_event_is_frozen() -> None:
    parsed = parse_blob_event(
        json.dumps(
            _typed_event_body(_SUBJECT, "Microsoft.Storage.BlobCreated")
        ).encode("utf-8")
    )
    assert parsed is not None
    with pytest.raises(ValidationError):
        parsed.event_type = BlobEventType.DELETED  # type: ignore[misc]
