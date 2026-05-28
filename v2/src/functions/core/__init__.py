"""Functions-only shared layer for the RAG indexing pipeline.

Pillar: Stable Core
Phase: 5.5 (Stable Core Refactor; broadened in Phase 6)

This package is the home for code that loads only when the Azure
Functions container spins up. Backend chat / history / admin runs
end-to-end without it.

Three shapes live here (see
[.github/instructions/v2-functions-core.instructions.md] for the
canonical decision tree):

1. **Ingestion-only** -- code with no chat-time consumer (e.g. a blob
   URI tracker for the indexer queue).
2. **Extension subclass** -- a subclass of a ``backend.core`` base
   that adds ingestion-specific behavior. Base stays in
   ``backend.core``; only the subclass lives here.
3. **Functions-runtime helper** -- wraps ``azure.functions`` types
   (``HttpRequest`` / ``HttpResponse`` / ``Blueprint``) or carries a
   Functions-only wire contract (queue envelope, blueprint-to-
   blueprint message). Examples include ``contracts``, ``http``,
   ``exception_mapping``.

Anti-duplication invariant: **no symbol is defined twice.** Storage,
credentials, settings, registry primitives -- if backend can use it,
it lives in ``backend.core`` and Functions imports it. There is no
``functions/_shared/``.

The four "what lives where" rules (locked in for Phase 5.5):

| Rule                                         | Destination                  |
|----------------------------------------------|------------------------------|
| Used **only** by backend at chat/query time  | ``v2/src/backend/core/``     |
| Used **only** by functions for ingestion     | ``v2/src/functions/core/``   |
| Used by **both**                             | ``v2/src/backend/core/``     |
| Used **only** by functions but extends a     | ``v2/src/functions/core/``   |
| ``backend.core`` library                     | (subclass / extension)       |
| Wraps ``azure.functions`` types or carries   | ``v2/src/functions/core/``   |
| a queue envelope shared across blueprints    | (Functions-runtime helper)   |
"""
