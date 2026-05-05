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

from shared.types import OrchestratorChannel, OrchestratorEvent


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
