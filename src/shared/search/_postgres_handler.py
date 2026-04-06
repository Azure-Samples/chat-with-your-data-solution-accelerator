"""PostgreSQL pgvector search handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from shared.common.answer import SourceDocument
from shared.search.azure_search_helper import SearchHandlerBase

if TYPE_CHECKING:
    from shared.config.env_settings import EnvSettings
    from shared.llm.llm_helper import LLMHelper

logger = logging.getLogger(__name__)


class PostgresSearchHandler(SearchHandlerBase):
    """Searches PostgreSQL using pgvector for similarity queries."""

    def __init__(self, settings: EnvSettings, llm_helper: LLMHelper) -> None:
        self.settings = settings
        self.llm_helper = llm_helper

    def query_search(self, question: str) -> list[SourceDocument]:
        # TODO: Phase 2 — implement pgvector similarity search
        # 1. Generate embedding for question
        # 2. Query PostgreSQL using pgvector <=> operator
        # 3. Convert rows to SourceDocument
        raise NotImplementedError("PostgreSQL search handler not yet implemented")
