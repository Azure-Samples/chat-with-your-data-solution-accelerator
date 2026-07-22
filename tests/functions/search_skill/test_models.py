"""Tests for src/functions/search_skill/models.py.

Validates the AI Search WebApiSkill request/response envelope
contract: camelCase ``recordId`` wire field maps to Python
``record_id`` via ``Field(alias="recordId")`` + ``populate_by_name
=True``; ``extra="forbid"`` rejects unknown wire fields; round-trip
serialization with ``model_dump(by_alias=True)`` emits the
externally-required camelCase shape; per-record error path
serializes ``data`` as ``{}`` via ``exclude_none=True``.
"""

import json

import pytest
from pydantic import ValidationError

from functions.search_skill.models import (
    SearchSkillInputData,
    SearchSkillInputRecord,
    SearchSkillOutputData,
    SearchSkillOutputRecord,
    SearchSkillRequest,
    SearchSkillResponse,
    SkillMessage,
)

# ---------------------------------------------------------------------------
# SkillMessage
# ---------------------------------------------------------------------------


def test_skill_message_round_trip() -> None:
    msg = SkillMessage(message="embedding failed")
    dumped = msg.model_dump()
    assert dumped == {"message": "embedding failed"}
    assert SkillMessage(**dumped) == msg


def test_skill_message_rejects_empty_message() -> None:
    with pytest.raises(ValidationError):
        SkillMessage(message="")


def test_skill_message_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SkillMessage.model_validate({"message": "ok", "level": "error"})


def test_skill_message_strips_whitespace() -> None:
    assert SkillMessage(message="  hi  ").message == "hi"


def test_skill_message_is_frozen() -> None:
    msg = SkillMessage(message="hi")
    with pytest.raises(ValidationError):
        msg.message = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SearchSkillInputData
# ---------------------------------------------------------------------------


def test_input_data_accepts_text() -> None:
    assert SearchSkillInputData(text="chunk to embed").text == "chunk to embed"


def test_input_data_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        SearchSkillInputData(text="")


def test_input_data_rejects_extras() -> None:
    with pytest.raises(ValidationError):
        SearchSkillInputData.model_validate({"text": "x", "language": "en"})


def test_input_data_strips_whitespace() -> None:
    assert SearchSkillInputData(text="  hello  ").text == "hello"


# ---------------------------------------------------------------------------
# SearchSkillInputRecord (alias bridge)
# ---------------------------------------------------------------------------


def test_input_record_accepts_wire_alias_recordId() -> None:
    record = SearchSkillInputRecord.model_validate(
        {"recordId": "1", "data": {"text": "hello"}}
    )
    assert record.record_id == "1"
    assert record.data.text == "hello"


def test_input_record_accepts_python_name_record_id() -> None:
    # populate_by_name=True lets handler code use snake_case construction.
    record = SearchSkillInputRecord(
        record_id="1", data=SearchSkillInputData(text="hello")
    )
    assert record.record_id == "1"


def test_input_record_rejects_missing_record_id() -> None:
    with pytest.raises(ValidationError):
        SearchSkillInputRecord.model_validate({"data": {"text": "x"}})


def test_input_record_rejects_empty_record_id() -> None:
    with pytest.raises(ValidationError):
        SearchSkillInputRecord.model_validate({"recordId": "", "data": {"text": "x"}})


def test_input_record_rejects_missing_data() -> None:
    with pytest.raises(ValidationError):
        SearchSkillInputRecord.model_validate({"recordId": "1"})


def test_input_record_rejects_extras() -> None:
    with pytest.raises(ValidationError):
        SearchSkillInputRecord.model_validate(
            {"recordId": "1", "data": {"text": "x"}, "extra": True}
        )


def test_input_record_serializes_with_by_alias_to_camelCase() -> None:
    record = SearchSkillInputRecord(
        record_id="1", data=SearchSkillInputData(text="hello")
    )
    dumped = record.model_dump(by_alias=True)
    assert dumped == {"recordId": "1", "data": {"text": "hello"}}


# ---------------------------------------------------------------------------
# SearchSkillRequest
# ---------------------------------------------------------------------------


def test_request_parses_full_indexer_payload() -> None:
    body = json.dumps(
        {
            "values": [
                {"recordId": "1", "data": {"text": "chunk one"}},
                {"recordId": "2", "data": {"text": "chunk two"}},
            ]
        }
    )
    request = SearchSkillRequest.model_validate_json(body)
    assert [r.record_id for r in request.values] == ["1", "2"]
    assert [r.data.text for r in request.values] == ["chunk one", "chunk two"]


def test_request_rejects_empty_values_list() -> None:
    with pytest.raises(ValidationError):
        SearchSkillRequest.model_validate({"values": []})


def test_request_rejects_missing_values() -> None:
    with pytest.raises(ValidationError):
        SearchSkillRequest.model_validate({})


def test_request_rejects_extras() -> None:
    with pytest.raises(ValidationError):
        SearchSkillRequest.model_validate(
            {
                "values": [{"recordId": "1", "data": {"text": "x"}}],
                "trace": True,
            }
        )


# ---------------------------------------------------------------------------
# SearchSkillOutputData
# ---------------------------------------------------------------------------


def test_output_data_defaults_embedding_to_none() -> None:
    assert SearchSkillOutputData().embedding is None


def test_output_data_accepts_populated_vector() -> None:
    data = SearchSkillOutputData(embedding=[0.1, 0.2, 0.3])
    assert data.embedding == [0.1, 0.2, 0.3]


def test_output_data_excludes_none_embedding_on_dump() -> None:
    # Wire-boundary contract: error records serialize ``data`` as ``{}``.
    assert SearchSkillOutputData().model_dump(exclude_none=True) == {}


def test_output_data_rejects_extras() -> None:
    with pytest.raises(ValidationError):
        SearchSkillOutputData.model_validate({"embedding": [0.1], "dim": 1})


# ---------------------------------------------------------------------------
# SearchSkillOutputRecord
# ---------------------------------------------------------------------------


def test_output_record_success_defaults_errors_and_warnings_to_none() -> None:
    record = SearchSkillOutputRecord(
        record_id="1", data=SearchSkillOutputData(embedding=[0.1, 0.2])
    )
    assert record.errors is None
    assert record.warnings is None


def test_output_record_accepts_populated_diagnostics() -> None:
    record = SearchSkillOutputRecord(
        record_id="1",
        data=SearchSkillOutputData(),
        errors=[SkillMessage(message="embedding failed")],
        warnings=[],
    )
    assert record.errors == [SkillMessage(message="embedding failed")]
    assert record.warnings == []


def test_output_record_serializes_success_with_by_alias() -> None:
    record = SearchSkillOutputRecord(
        record_id="1", data=SearchSkillOutputData(embedding=[0.1, 0.2])
    )
    dumped = record.model_dump(by_alias=True)
    assert dumped == {
        "recordId": "1",
        "data": {"embedding": [0.1, 0.2]},
        "errors": None,
        "warnings": None,
    }


def test_output_record_error_path_serializes_data_as_empty_object() -> None:
    # Per-record error path: ``data`` carries no embedding; the wire
    # boundary uses ``exclude_none=True`` so it serializes as ``{}``.
    record = SearchSkillOutputRecord(
        record_id="err",
        data=SearchSkillOutputData(),
        errors=[SkillMessage(message="embedding failed")],
        warnings=[],
    )
    dumped = record.model_dump(by_alias=True, exclude_none=True)
    assert dumped == {
        "recordId": "err",
        "data": {},
        "errors": [{"message": "embedding failed"}],
        "warnings": [],
    }


def test_output_record_rejects_extras() -> None:
    with pytest.raises(ValidationError):
        SearchSkillOutputRecord.model_validate(
            {
                "recordId": "1",
                "data": {"embedding": [0.1]},
                "errors": None,
                "warnings": None,
                "trace_id": "abc",
            }
        )


# ---------------------------------------------------------------------------
# SearchSkillResponse
# ---------------------------------------------------------------------------


def test_response_round_trip_with_by_alias() -> None:
    response = SearchSkillResponse(
        values=[
            SearchSkillOutputRecord(
                record_id="1",
                data=SearchSkillOutputData(embedding=[0.1, 0.2]),
            ),
            SearchSkillOutputRecord(
                record_id="2",
                data=SearchSkillOutputData(),
                errors=[SkillMessage(message="boom")],
                warnings=[],
            ),
        ]
    )
    dumped = response.model_dump(by_alias=True, exclude_none=True)
    assert dumped == {
        "values": [
            {
                "recordId": "1",
                "data": {"embedding": [0.1, 0.2]},
            },
            {
                "recordId": "2",
                "data": {},
                "errors": [{"message": "boom"}],
                "warnings": [],
            },
        ]
    }


def test_response_rejects_empty_values() -> None:
    with pytest.raises(ValidationError):
        SearchSkillResponse(values=[])


def test_response_round_trip_through_json_string() -> None:
    response = SearchSkillResponse(
        values=[
            SearchSkillOutputRecord(
                record_id="1",
                data=SearchSkillOutputData(embedding=[0.1]),
            )
        ]
    )
    payload = response.model_dump_json(by_alias=True, exclude_none=True)
    parsed = json.loads(payload)
    assert parsed == {"values": [{"recordId": "1", "data": {"embedding": [0.1]}}]}
