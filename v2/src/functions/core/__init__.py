"""Functions-only extension layer for the RAG indexing pipeline.

Pillar: Stable Core
Phase: 5.5 (Stable Core Refactor, REFACTOR-B sub-unit B2)

This package is the home for ingestion-only code that extends
``backend.core``. It is **opt-in** -- it only loads when the Azure
Functions container spins up. Backend chat / history / admin runs
end-to-end without it.

The four "what lives where" rules (locked in for Phase 5.5, see
``v2/docs/development_plan.md`` §3.4):

| Rule                                         | Destination                  |
|----------------------------------------------|------------------------------|
| Used **only** by backend at chat/query time  | ``v2/src/backend/core/``     |
| Used **only** by functions for ingestion     | ``v2/src/functions/core/``   |
| Used by **both**                             | ``v2/src/backend/core/``     |
| Used **only** by functions but extends a     | ``v2/src/functions/core/``   |
| ``backend.core`` library                     | (subclass / extension)       |

Anti-duplication invariant: **no symbol is defined twice.** If functions
needs to add behavior to a ``backend.core`` provider (e.g. a chunking
strategy on a parser), the subclass lives here and inherits from
``backend.core``. Empty-by-design at Phase 5.5; populated in Phase 6
(``batch_start`` / ``batch_push`` / ``add_url`` / ``search_skill``
blueprints land their ingestion-specific extensions here).
"""
