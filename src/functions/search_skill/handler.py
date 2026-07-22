"""Pure orchestration handler for the ``search_skill`` HTTP blueprint.

``search_skill_handler`` takes a :class:`SearchSkillRequest` posted by
an AI Search indexer (WebApiSkill envelope per
:mod:`functions.search_skill.models`) and an injected
:class:`BaseEmbedder`, embeds every record's text on the fly, and
returns a :class:`SearchSkillResponse` with one
:class:`SearchSkillOutputRecord` per input record in the same order.

Design notes:

* The embedder contract takes :class:`backend.core.types.Chunk` inputs
  so the handler builds synthetic chunks per record (``id`` and
  ``source`` both set to ``record_id``; this skill does not deal with
  blobs or file paths). The embedder treats every chunk as
  free-floating text -- nothing downstream of the embedder reads the
  synthetic ``source``.
* Single batched embedder call. The embedder's SDK boundary is already
  wrapped per [v2/docs/exception_handling_policy.md] "Embedder
  providers" so any failure propagates here; the HTTP-trigger
  blueprint wraps the handler call in
  ``@map_function_exceptions`` to map ``AzureError`` / generic
  exceptions to 502 / 500. No try/except here -- adding another layer
  would double-log.
* A mismatch between embedded vector count and request record count
  is a programming bug (the embedder is contract-violating), not a
  per-record data problem; ``RuntimeError`` matches the precedent set
  by :func:`functions.batch_push.handler.batch_push_handler`.
* The per-record ``errors`` / ``warnings`` envelope stays modeled for
  future per-input validation (e.g., text-too-long) but is unused on
  the embed path: pure embedder calls are batch-semantic, not
  per-record-semantic. Both fields default to ``None`` on success.
"""

import logging

from backend.core.providers.embedders.registry import EmbedderInstance
from backend.core.types import Chunk
from functions.search_skill.models import (
    SearchSkillOutputData,
    SearchSkillOutputRecord,
    SearchSkillRequest,
    SearchSkillResponse,
)

logger = logging.getLogger(__name__)


def _build_chunk(record_id: str, text: str, index: int) -> Chunk:
    """Map one input record to a synthetic :class:`Chunk` for the embedder.

    ``id`` and ``source`` both default to ``record_id`` because the
    embedder is the only consumer of these chunks -- nothing
    downstream reads the synthetic ``source``.
    """
    return Chunk(id=record_id, content=text, source=record_id, index=index)


async def search_skill_handler(
    request: SearchSkillRequest, embedder: EmbedderInstance
) -> SearchSkillResponse:
    """Embed every input record's text and return the WebApiSkill response."""
    chunks = [
        _build_chunk(rec.record_id, rec.data.text, idx)
        for idx, rec in enumerate(request.values)
    ]
    embedding_results = await embedder.embed(chunks)
    vectors = [vector for result in embedding_results for vector in result.vectors]
    if len(vectors) != len(request.values):
        raise RuntimeError(
            "search_skill embedder vector count mismatch: expected "
            f"{len(request.values)} vectors for {len(request.values)} records, "
            f"got {len(vectors)}."
        )

    # ``recordId`` is the wire-protocol field name declared by
    # ``SearchSkillOutputRecord`` via ``Field(alias="recordId")``.
    # Construction uses the alias here so the type checker sees the
    # canonical parameter name; ``populate_by_name=True`` is runtime-only
    # and isn't reflected in the synthesized ``__init__`` signature.
    return SearchSkillResponse(
        values=[
            SearchSkillOutputRecord(
                recordId=record.record_id,
                data=SearchSkillOutputData(embedding=vector),
            )
            for record, vector in zip(request.values, vectors)
        ]
    )
