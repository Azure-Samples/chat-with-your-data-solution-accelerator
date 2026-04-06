"""FastAPI dependency injection helpers."""

from __future__ import annotations

from functools import lru_cache

from shared.config.env_settings import EnvSettings
from shared.llm.llm_helper import LLMHelper


@lru_cache
def get_settings() -> EnvSettings:
    return EnvSettings()


def get_llm_helper() -> LLMHelper:
    return LLMHelper(get_settings())
