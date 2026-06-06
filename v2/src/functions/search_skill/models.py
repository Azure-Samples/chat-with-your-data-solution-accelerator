"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

AI Search custom-skill request/response Pydantic models.

The ``search_skill`` HTTP route is invoked by an Azure Cognitive
Search indexer as a WebApiSkill ("custom skill"). The wire
envelope is part of the AI Search WebApiSkill protocol: the
indexer batches input records and posts them as
``{"values": [{"recordId": ..., "data": {...}}, ...]}``; the
handler returns the same envelope shape with per-record
``{"data": {...}, "errors": ..., "warnings": ...}`` so the
indexer can correlate inputs to outputs by ``recordId``.

This module owns only the request / response DTOs. The
embed-on-the-fly handler lives in ``handler.py`` and the HTTP
trigger blueprint lives in ``blueprint.py``.

Wire shape (this skill only -- embed input text as a vector)::

    # Request
    {"values": [
        {"recordId": "1", "data": {"text": "chunk to embed"}},
        {"recordId": "2", "data": {"text": "another chunk"}}
    ]}

    # Successful response
    {"values": [
        {"recordId": "1",
         "data": {"embedding": [0.1, 0.2, ...]},
         "errors": null,
         "warnings": null},
        ...
    ]}

    # Per-record error response
    {"values": [
        {"recordId": "1",
         "data": {},
         "errors": [{"message": "embedding failed"}],
         "warnings": []}
    ]}

camelCase ``recordId`` is the wire-protocol field name (AI Search
contract); Python attributes use snake_case ``record_id`` per
Hard Rule #11. ``Field(alias="recordId")`` + ``populate_by_name=
True`` bridges the two -- this is the first use of the alias
pattern in v2; AI Search's externally-defined WebApiSkill
envelope is the canonical case where a third-party protocol
imposes camelCase on the wire.

Reference: v1 ``code/backend/batch/combine_pages_chunknos.py``
implements the same envelope but uses raw ``dict`` for ``data``.
v2 narrows ``data`` to typed sub-models per skill so the handler
gets compile-time guarantees on field names (no dict-key typos
at runtime) and the wire shape is self-documenting.
"""

from pydantic import BaseModel, ConfigDict, Field


class SkillMessage(BaseModel):
    """One ``{"message": str}`` entry in an ``errors`` or ``warnings`` list.

    Matches the AI Search WebApiSkill spec for per-record
    diagnostics: both ``errors`` and ``warnings`` are lists of
    objects with a single ``message`` string field that the
    indexer surfaces in its execution history.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=1)


class SearchSkillInputData(BaseModel):
    """Per-record input payload: the text to embed."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1)


class SearchSkillInputRecord(BaseModel):
    """One input record in the AI Search WebApiSkill envelope.

    ``record_id`` is the Python attribute name; the wire field is
    ``recordId`` per the AI Search contract. ``populate_by_name``
    lets the handler construct records with either name.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    record_id: str = Field(alias="recordId", min_length=1)
    data: SearchSkillInputData


class SearchSkillRequest(BaseModel):
    """Inbound HTTP payload from an AI Search indexer WebApiSkill call.

    ``values`` is constrained to at least one record so a malformed
    indexer post (empty batch) surfaces as a Pydantic
    ``ValidationError`` at the trigger boundary instead of silently
    succeeding with no work performed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    values: list[SearchSkillInputRecord] = Field(min_length=1)


class SearchSkillOutputData(BaseModel):
    """Per-record output payload: the embedding vector.

    ``embedding`` is optional with a default of ``None`` because
    per-record error paths emit ``{"data": {}}`` (v1 precedent --
    see [code/backend/batch/combine_pages_chunknos.py] line ~55).
    The wire boundary uses ``model_dump(exclude_none=True)`` so
    a record carrying only ``errors`` serializes its ``data`` as
    ``{}`` rather than ``{"embedding": null}``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    embedding: list[float] | None = None


class SearchSkillOutputRecord(BaseModel):
    """One output record in the AI Search WebApiSkill response envelope.

    ``errors`` and ``warnings`` default to ``None``; v1 emits
    ``null`` on the success path and ``[{"message": "..."}]`` /
    ``[]`` respectively on the per-record failure path. Defaulting
    to ``None`` lets the handler construct success records with
    just ``record_id`` + ``data`` and lets ``model_dump
    (exclude_none=True)`` produce minimal wire payloads.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    record_id: str = Field(alias="recordId", min_length=1)
    data: SearchSkillOutputData
    errors: list[SkillMessage] | None = None
    warnings: list[SkillMessage] | None = None


class SearchSkillResponse(BaseModel):
    """Outbound HTTP payload returned to the AI Search indexer."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    values: list[SearchSkillOutputRecord] = Field(min_length=1)
