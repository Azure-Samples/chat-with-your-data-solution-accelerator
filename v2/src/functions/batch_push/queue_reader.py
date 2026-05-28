"""Pillar: Stable Core
Phase: 6 (Functions blueprints / modular RAG indexing pipeline)

Queue reader for the ``batch_push`` blueprint.

``batch_push`` is the consumer side of the doc-processing queue that
``batch_start`` produces onto via
:func:`functions.batch_start.queue_writer.enqueue_push_message`. The
wire format is :class:`functions.core.contracts.BatchPushQueueMessage`
serialized with ``model_dump_json()``.

This module owns only the parse step: turn the raw
``azure.functions.QueueMessage`` body into a validated envelope.

Failure mode: a malformed / drifted body raises
``pydantic.ValidationError`` (the envelope is ``frozen=True,
extra="forbid"``). The blueprint's HTTP wrapper does not apply here
(queue trigger), so the exception propagates to the Functions
runtime which applies its retry policy and ultimately moves the
message to the poison queue. That is the desired behavior --
drifted producer + dropped message would be silent data loss.
"""

import azure.functions as func

from functions.core.contracts import BatchPushQueueMessage


def parse_push_message(msg: func.QueueMessage) -> BatchPushQueueMessage:
    """Validate ``msg`` body bytes into a :class:`BatchPushQueueMessage`.

    Pydantic's ``model_validate_json`` accepts ``bytes`` directly, so
    no intermediate ``str`` decode is required (avoids a needless
    UTF-8 round-trip vs. v1's ``json.loads(msg.get_body().decode())``).
    """
    return BatchPushQueueMessage.model_validate_json(msg.get_body())
