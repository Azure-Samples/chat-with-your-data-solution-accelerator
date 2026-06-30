"""Type-level invariants for `shared.types`.

Pillar: Stable Core
Phase: 2

Locks the `OrchestratorChannel` `StrEnum` contract added in Q12
(2026-05-05). The enum has to satisfy three properties at once so
that the channel-literal sweep stays a *one-time* refactor instead of
re-introducing drift the next time a producer is added:

1. Frozen membership -- exactly the five locked channel keys, no
   more, no less.
2. `str` round-trip -- a bare string passed to
   `OrchestratorEvent(channel="answer", ...)` Pydantic-coerces to
   `OrchestratorChannel.ANSWER`, AND `event.channel == "answer"`
   keeps holding (because `StrEnum` members ARE strings). This is
   what lets the ~20 pre-existing tests using bare-string channels
   keep passing without modification.
3. Cross-equality between members -- the enum must compare equal to
   its own raw value but NOT to a sibling's value, so consumer code
   doing `if event.channel == OrchestratorChannel.ERROR` is
   unambiguous.
"""

from enum import StrEnum

import pytest
from pydantic import ValidationError

import backend.core.types as st
import backend.core.types as types_module
from backend.core.agents.presets import AssistantType
from backend.core.types import (
    AadScope,
    ChatMessage,
    ChatRole,
    MessageRecord,
    OrchestratorChannel,
    OrchestratorEvent,
    RuntimeConfig,
    SearchDocument,
)


def test_orchestrator_channel_is_a_strenum() -> None:
    """`StrEnum` subclassing is required by Hard Rule #11; assert it
    so a future refactor can't silently regress to a bare class."""
    assert issubclass(OrchestratorChannel, StrEnum)
    assert issubclass(OrchestratorChannel, str)


def test_orchestrator_channel_membership_is_frozen() -> None:
    """The five keys are part of the wire contract (frontend renders
    `REASONING` in a collapsible panel, dedupes on `CITATION.id`,
    raises 500 on `ERROR`, etc.). A new channel needs an explicit
    code change here AND a matching FE update."""
    assert {member.value for member in OrchestratorChannel} == {
        "reasoning",
        "tool",
        "answer",
        "citation",
        "error",
    }


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("reasoning", OrchestratorChannel.REASONING),
        ("tool", OrchestratorChannel.TOOL),
        ("answer", OrchestratorChannel.ANSWER),
        ("citation", OrchestratorChannel.CITATION),
        ("error", OrchestratorChannel.ERROR),
    ],
)
def test_orchestrator_event_coerces_bare_string(
    raw: str, expected: OrchestratorChannel
) -> None:
    """Bare-string emit sites (pre-Q12 producers + every test fixture)
    must keep working: Pydantic coerces the string into the matching
    enum member."""
    event = OrchestratorEvent(channel=raw, content="hi")  # type: ignore[arg-type]
    assert event.channel is expected
    # Cross-direction equality for `if event.channel == "answer":`
    # consumers (the Q12 sweep updated production code to compare
    # against the enum, but tests + future producers may keep using
    # the raw string).
    assert event.channel == raw


def test_orchestrator_event_rejects_unknown_channel() -> None:
    """Unknown channel keys must fail validation -- a typo in a new
    producer surfaces immediately at construction, not at the SSE
    consumer."""
    with pytest.raises(ValidationError):
        OrchestratorEvent(channel="thoughts", content="hi")  # type: ignore[arg-type]


def test_orchestrator_channel_equality_is_member_distinct() -> None:
    """Sanity check that `StrEnum` members compare equal to their own
    raw value but distinct from siblings -- protects the
    `event.channel == OrchestratorChannel.ERROR` consumer pattern in
    `routers/conversation.py` and the LangGraph orchestrator."""
    assert OrchestratorChannel.ANSWER == "answer"
    assert OrchestratorChannel.ANSWER != "error"
    assert OrchestratorChannel.ANSWER != OrchestratorChannel.ERROR


# ---------------------------------------------------------------------------
# ChatRole (Hard Rule #11 closed-set discriminator)
# ---------------------------------------------------------------------------
# Same three properties OrchestratorChannel locks: StrEnum subclassing,
# frozen membership, bidirectional str <-> enum coercion + equality.
# Required by Hard Rule #11 because `message.role` is dispatched on at
# runtime in `pipelines/chat.py::_latest_user_text` and
# `orchestrators/langgraph.py::_latest_user_text`.


def test_chat_role_is_a_strenum() -> None:
    assert issubclass(ChatRole, StrEnum)
    assert issubclass(ChatRole, str)


def test_chat_role_membership_is_frozen() -> None:
    """The four roles mirror the OpenAI / AzureOpenAI chat message
    contract; a new role needs an explicit change here AND wherever
    `ChatMessage` is constructed from external payloads."""
    assert {member.value for member in ChatRole} == {
        "system",
        "user",
        "assistant",
        "tool",
    }


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("system", ChatRole.SYSTEM),
        ("user", ChatRole.USER),
        ("assistant", ChatRole.ASSISTANT),
        ("tool", ChatRole.TOOL),
    ],
)
def test_chat_message_coerces_string_role_to_enum_member(
    raw: str, expected: ChatRole
) -> None:
    """Wire payloads pass `role="user"` as a plain string; Pydantic
    must coerce to the matching enum member so dispatch sites can use
    `is ChatRole.USER` (identity, not equality)."""
    message = ChatMessage(role=raw, content="hi")  # type: ignore[arg-type]
    assert message.role is expected
    # Wire shape unchanged: StrEnum members ARE strings.
    assert message.role == raw


def test_chat_message_round_trips_via_model_dump_json() -> None:
    """JSON round-trip (the request/response shape) preserves role
    value AND survives Pydantic re-validation back into the enum."""
    original = ChatMessage(role="assistant", content="hello")  # type: ignore[arg-type]
    payload = original.model_dump_json()
    assert '"role":"assistant"' in payload  # wire shape
    rehydrated = ChatMessage.model_validate_json(payload)
    assert rehydrated == original
    assert rehydrated.role is ChatRole.ASSISTANT


def test_chat_message_metadata_defaults_to_empty_dict() -> None:
    """Every existing producer builds `ChatMessage(role=..., content=...)`
    with no metadata; the field must default to an empty dict so those
    call sites are unaffected."""
    message = ChatMessage(role="user", content="hi")  # type: ignore[arg-type]
    assert message.metadata == {}


def test_chat_message_carries_metadata_and_round_trips() -> None:
    """An assistant turn carries its citations in `metadata` so a
    reloaded conversation can rehydrate them; the JSON round-trip (the
    persisted wire shape) must preserve the nested structure."""
    citations = [{"id": "doc1", "title": "Benefit_Options.pdf", "url": ""}]
    original = ChatMessage(
        role="assistant",  # type: ignore[arg-type]
        content="hello",
        metadata={"citations": citations},
    )
    payload = original.model_dump_json()
    rehydrated = ChatMessage.model_validate_json(payload)
    assert rehydrated == original
    assert rehydrated.metadata["citations"] == citations


def test_chat_message_rejects_non_dict_metadata() -> None:
    """`metadata` is a dict field; a scalar must raise rather than
    silently coerce, keeping the persisted shape well-formed."""
    with pytest.raises(ValidationError):
        ChatMessage(
            role="user",  # type: ignore[arg-type]
            content="hi",
            metadata="oops",  # type: ignore[arg-type]
        )


def test_message_record_coerces_string_role_to_enum_member() -> None:
    """Persistence read-path: `cosmosdb._read_item` constructs
    `MessageRecord(role=item.get("role", "user"))` from a plain dict;
    the coercion must apply equally."""
    record = MessageRecord(
        id="m1",
        conversation_id="c1",
        role="user",  # type: ignore[arg-type]
        content="hi",
    )
    assert record.role is ChatRole.USER
    assert record.role == "user"  # str equality preserved for sentinel checks


def test_chat_role_dispatch_via_is_operator_matches_after_coercion() -> None:
    """Mirrors the production dispatch sites in `pipelines/chat.py` and
    `orchestrators/langgraph.py`: `if msg.role is ChatRole.USER`.
    StrEnum members are singletons so `is` is the canonical check."""
    message = ChatMessage(role="user", content="q")  # type: ignore[arg-type]
    assert message.role is ChatRole.USER
    assert message.role is not ChatRole.ASSISTANT


def test_chat_role_equality_is_member_distinct() -> None:
    assert ChatRole.USER == "user"
    assert ChatRole.USER != "assistant"
    assert ChatRole.USER != ChatRole.ASSISTANT


def test_chat_role_is_in_module_exports() -> None:
    assert "ChatRole" in types_module.__all__


# ---------------------------------------------------------------------------
# AadScope
# ---------------------------------------------------------------------------
#
# Closed-set discriminator for the single `*scopes: str` argument to
# `AsyncTokenCredential.get_token(...)`. Wire shape MUST match the
# exact literal Azure's AAD endpoint expects -- a typo silently breaks
# token acquisition only at first request, not at import.


def test_aad_scope_is_a_strenum() -> None:
    """`StrEnum` subclassing is required by Hard Rule #11; assert it
    so a future refactor can't silently regress to a bare class."""
    assert issubclass(AadScope, StrEnum)
    assert issubclass(AadScope, str)


def test_aad_scope_membership_is_frozen() -> None:
    """Each member's value is the exact scope literal that Azure's AAD
    endpoint expects; a typo here would silently break token
    acquisition. The wire shape is part of the SDK contract."""
    assert {member.value for member in AadScope} == {
        "https://cognitiveservices.azure.com/.default",
        "https://ossrdbms-aad.database.windows.net/.default",
    }


def test_aad_scope_equality_is_member_distinct() -> None:
    """Each member equals its own raw scope value but not a sibling's
    -- so call sites that compare against a literal stay unambiguous."""
    assert AadScope.COGNITIVE_SERVICES == "https://cognitiveservices.azure.com/.default"
    assert AadScope.POSTGRES_FLEX == "https://ossrdbms-aad.database.windows.net/.default"
    assert AadScope.COGNITIVE_SERVICES != AadScope.POSTGRES_FLEX


def test_aad_scope_member_is_usable_as_str() -> None:
    """`AsyncTokenCredential.get_token(*scopes: str)` accepts the enum
    members transparently because each member IS a `str`."""
    assert isinstance(AadScope.COGNITIVE_SERVICES, str)
    assert isinstance(AadScope.POSTGRES_FLEX, str)


def test_aad_scope_is_in_module_exports() -> None:
    assert "AadScope" in types_module.__all__
    assert types_module.AadScope is AadScope


# ---------------------------------------------------------------------------
# RuntimeConfig (#35c-1)
# ---------------------------------------------------------------------------
#
# `RuntimeConfig` is the persisted shape of the admin-mutable subset
# of `AppSettings` -- the same 6 fields that `AdminConfig` exposes as
# read-only in #35b, plus two audit fields (`updated_at`,
# `updated_by`). Lives in `shared.types` (not `backend.routers.admin`)
# because both DB clients (Cosmos in #35c-4/5, Postgres in #35c-6)
# need to read/write it without depending on the backend package.
#
# Wire-shape decisions locked here:
#   * All 6 mutable fields are `T | None = None` so the persisted row
#     can distinguish "explicitly overridden" from "not overridden"
#     (critical for booleans like `search_use_semantic_search` where
#     `False` is a legitimate override distinct from "fall through to
#     env default" -- otherwise PATCH could never disable semantic
#     search without also disabling the override-vs-default
#     distinction).
#   * `updated_at` is an ISO-8601 string (mirrors `Conversation` /
#     `MessageRecord` -- "provider-formatted, wire shape stable
#     across providers"). Using `datetime` here would force every
#     provider to (de)serialize on the wire and break the existing
#     pattern.


def test_runtime_config_default_construction_is_all_unset() -> None:
    """All 6 mutable fields default to None so the persisted row
    distinguishes 'explicitly overridden' from 'not overridden' --
    a precondition for the RFC 7396 merge semantics in #35c-7."""
    rc = RuntimeConfig()
    assert rc.orchestrator_name is None
    assert rc.openai_temperature is None
    assert rc.openai_max_tokens is None
    assert rc.search_use_semantic_search is None
    assert rc.search_top_k is None
    assert rc.log_level is None
    # Audit fields default to empty strings (not None) so the
    # persistence layer always writes a value -- a row with
    # `updated_at=""` is unambiguously "never written" and a row
    # with a populated string is unambiguously "audit trail present".
    assert rc.updated_at == ""
    assert rc.updated_by == ""


def test_runtime_config_round_trips_explicit_overrides() -> None:
    """`model_dump()` -> `model_validate()` is what every DB
    provider (Cosmos JSON, Postgres JSONB column) will use to
    persist + read back, so the round-trip must be lossless for
    every field."""
    rc = RuntimeConfig(
        orchestrator_name="agent_framework",
        openai_temperature=0.7,
        openai_max_tokens=2048,
        search_use_semantic_search=False,
        search_top_k=10,
        log_level="DEBUG",
        updated_at="2026-05-06T12:00:00+00:00",
        updated_by="alice@example.com",
    )
    rebuilt = RuntimeConfig.model_validate(rc.model_dump())
    assert rebuilt == rc


def test_runtime_config_distinguishes_false_from_unset() -> None:
    """The `Optional[bool]` shape on `search_use_semantic_search`
    is load-bearing: a PATCH that disables semantic search must
    persist as `False` (a real override), distinct from an unset
    field that means 'fall through to env default'. If this test
    breaks, the merge semantics in #35c-7 collapse silently."""
    explicit_false = RuntimeConfig(search_use_semantic_search=False)
    unset = RuntimeConfig()
    assert explicit_false.search_use_semantic_search is False
    assert unset.search_use_semantic_search is None
    assert explicit_false != unset


def test_runtime_config_ai_assistant_type_defaults_to_none() -> None:
    # `None` = not overridden -> fall through to the default type (ADR 0030).
    assert RuntimeConfig().ai_assistant_type is None


def test_runtime_config_coerces_ai_assistant_type_string_to_enum() -> None:
    # The PATCH path validates the merged dict through RuntimeConfig, so a
    # wire string must coerce to the closed-set AssistantType member.
    rc = RuntimeConfig(ai_assistant_type="contract assistant")
    assert rc.ai_assistant_type is AssistantType.CONTRACT


def test_runtime_config_rejects_unknown_ai_assistant_type() -> None:
    with pytest.raises(ValidationError):
        RuntimeConfig(ai_assistant_type="chief of staff")


def test_runtime_config_round_trips_ai_assistant_type() -> None:
    rc = RuntimeConfig(ai_assistant_type=AssistantType.EMPLOYEE)
    rebuilt = RuntimeConfig.model_validate(rc.model_dump())
    assert rebuilt.ai_assistant_type is AssistantType.EMPLOYEE
    assert rebuilt == rc


def test_runtime_config_partial_override_leaves_other_fields_none() -> None:
    """A partial override (one field set, others not mentioned) is
    the common case -- the FE PATCH payload typically carries only
    the field the admin just toggled. Each unmentioned field must
    stay `None`, NOT take a Pydantic default that would silently
    overwrite the env value at merge time."""
    rc = RuntimeConfig(openai_temperature=0.3)
    assert rc.openai_temperature == 0.3
    assert rc.orchestrator_name is None
    assert rc.openai_max_tokens is None
    assert rc.search_use_semantic_search is None
    assert rc.search_top_k is None
    assert rc.log_level is None


def test_runtime_config_content_safety_enabled_defaults_to_none() -> None:
    """`content_safety_enabled` joins the existing mutable fields with
    the same `T | None = None` shape — None means 'no admin override,
    fall through to `AppSettings.content_safety.enabled` at request
    time via `get_content_safety_guard`'."""
    rc = RuntimeConfig()
    assert rc.content_safety_enabled is None


def test_runtime_config_content_safety_enabled_round_trips_true_and_false() -> None:
    """Both explicit boolean values must round-trip losslessly through
    `model_dump()` → `model_validate()` because the persisted shape
    (Cosmos JSON / Postgres JSONB) is the only way the override
    survives a process restart. Asserts on the field value (not just
    instance equality) because without `extra="forbid"`, equality
    alone would be a false positive when the field is absent."""
    rc_true = RuntimeConfig(content_safety_enabled=True)
    assert rc_true.content_safety_enabled is True
    rebuilt_true = RuntimeConfig.model_validate(rc_true.model_dump())
    assert rebuilt_true.content_safety_enabled is True
    assert rebuilt_true == rc_true

    rc_false = RuntimeConfig(content_safety_enabled=False)
    assert rc_false.content_safety_enabled is False
    rebuilt_false = RuntimeConfig.model_validate(rc_false.model_dump())
    assert rebuilt_false.content_safety_enabled is False
    assert rebuilt_false == rc_false


def test_runtime_config_content_safety_enabled_distinguishes_false_from_none() -> None:
    """Same load-bearing semantic as `search_use_semantic_search`: a
    PATCH that *disables* content safety must persist as `False` (a
    real override), distinct from an unset field that means 'fall
    through to env default'. If this collapses, the U-CS-7 override
    cascade in `get_content_safety_guard` can never honor an explicit
    admin disable."""
    explicit_false = RuntimeConfig(content_safety_enabled=False)
    unset = RuntimeConfig()
    assert explicit_false.content_safety_enabled is False
    assert unset.content_safety_enabled is None
    assert explicit_false != unset


def test_runtime_config_partial_override_preserves_content_safety_unset() -> None:
    """A partial override carrying only `content_safety_enabled` must
    leave every other mutable field at None — mirrors the existing
    `test_runtime_config_partial_override_leaves_other_fields_none`
    pattern from the other direction."""
    rc = RuntimeConfig(content_safety_enabled=True)
    assert rc.content_safety_enabled is True
    assert rc.orchestrator_name is None
    assert rc.openai_temperature is None
    assert rc.openai_max_tokens is None
    assert rc.search_use_semantic_search is None
    assert rc.search_top_k is None
    assert rc.log_level is None


def test_runtime_config_cwyd_agent_instructions_defaults_to_none() -> None:
    """`cwyd_agent_instructions` joins the existing mutable fields with
    the same `T | None = None` shape — None means 'no admin override,
    fall through to `CWYD_AGENT.instructions` at agent-creation time
    in the agents provider'."""
    rc = RuntimeConfig()
    assert rc.cwyd_agent_instructions is None


def test_runtime_config_cwyd_agent_instructions_round_trips() -> None:
    """The persisted shape (Cosmos JSON / Postgres JSONB) is the only
    way a custom system prompt survives a process restart, so
    `model_dump()` -> `model_validate()` must be lossless for the
    string payload."""
    rc = RuntimeConfig(cwyd_agent_instructions="You are a custom assistant.")
    assert rc.cwyd_agent_instructions == "You are a custom assistant."
    rebuilt = RuntimeConfig.model_validate(rc.model_dump())
    assert rebuilt.cwyd_agent_instructions == "You are a custom assistant."
    assert rebuilt == rc


def test_runtime_config_partial_override_preserves_cwyd_agent_unset() -> None:
    """A partial override carrying only `cwyd_agent_instructions` must
    leave every other mutable field at None — mirrors the existing
    partial-override tests for the other fields."""
    rc = RuntimeConfig(cwyd_agent_instructions="custom prompt")
    assert rc.cwyd_agent_instructions == "custom prompt"
    assert rc.orchestrator_name is None
    assert rc.openai_temperature is None
    assert rc.openai_max_tokens is None
    assert rc.search_use_semantic_search is None
    assert rc.search_top_k is None
    assert rc.log_level is None
    assert rc.content_safety_enabled is None


def test_runtime_config_is_in_module_exports() -> None:
    """Ensures `from backend.core.types import RuntimeConfig` works for
    every downstream consumer (DB clients in #35c-4/5/6, admin
    router in #35c-7) without a leading-underscore re-export."""
    assert "RuntimeConfig" in st.__all__


def test_search_document_is_frozen_and_forbids_extras() -> None:
    """Locks Hard Rule #15 invariants for the ingestion wire shape.

    Frozen + ``extra="forbid"`` so:

    * No ingestion blueprint can silently smuggle a provider-specific
      field through the Azure Search payload.
    * A typo at the construction site (``cotent_vector`` for
      ``content_vector``) fails immediately instead of dropping
      vectors at write time.
    """
    doc = SearchDocument(id="a", content="hello")
    with pytest.raises(ValidationError):
        doc.content = "mutated"  # type: ignore[misc]  -- frozen model rejects mutation
    with pytest.raises(ValidationError):
        SearchDocument(id="a", content="hello", evil="nope")  # type: ignore[call-arg]


def test_search_document_round_trips_via_model_dump() -> None:
    """Locks the SDK-boundary contract: ``model_dump()`` returns the
    dict shape ``push_documents`` forwards to the Azure SDK
    (``merge_or_upload_documents(documents=[...])``).

    The field names exactly mirror the read-side mapping in
    :class:`backend.core.providers.search.azure_search.AzureSearch`
    (``id``, ``content``, ``title``, ``content_vector``) so an
    in-place schema upgrade does not require a reindex.
    """
    doc = SearchDocument(
        id="doc.txt__0",
        content="hello",
        title="doc.txt",
        content_vector=[0.1, 0.2, 0.3],
    )
    dumped = doc.model_dump()
    assert dumped == {
        "id": "doc.txt__0",
        "content": "hello",
        "title": "doc.txt",
        "content_vector": [0.1, 0.2, 0.3],
    }
    assert SearchDocument(**dumped) == doc


def test_search_document_defaults_match_read_side_optional_fields() -> None:
    """Both ``title`` and ``content_vector`` are optional today --
    ``title`` defaults to ``""`` for sources without a real title
    (raw HTML, ad-hoc URLs); ``content_vector`` defaults to ``[]``
    so an ingestion path that hasn't run the embedder yet still
    type-checks against the model."""
    doc = SearchDocument(id="a", content="hello")
    assert doc.title == ""
    assert doc.content_vector == []


def test_search_document_is_in_module_exports() -> None:
    """Ensures `from backend.core.types import SearchDocument` works
    for downstream ingestion handlers + the writer helper without a
    leading-underscore re-export."""
    assert "SearchDocument" in st.__all__
