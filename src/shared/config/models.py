"""Configuration models for active.json config schema."""

from __future__ import annotations

from pydantic import BaseModel


class PromptConfig(BaseModel):
    answering_system_prompt: str = ""
    answering_user_prompt: str = ""
    post_answering_prompt: str = ""
    enable_post_answering_prompt: bool = False
    enable_content_safety: bool = True


class EmbeddingConfig(BaseModel):
    model: str = "text-embedding-ada-002"
    model_version: str = ""
    chunk_size: int = 500
    chunk_overlap: int = 100


class DocumentProcessor(BaseModel):
    document_type: str = ""
    chunking_strategy: str = "layout"
    chunking_size: int = 500
    chunking_overlap: int = 100
    loading_strategy: str = ""
    use_advanced_image_processing: bool = False


class IntegratedVectorizationConfig(BaseModel):
    max_page_length: int = 2000
    page_overlap_length: int = 500


class ConfigModel(BaseModel):
    prompts: PromptConfig = PromptConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    document_processors: list[DocumentProcessor] = []
    integrated_vectorization_config: IntegratedVectorizationConfig | None = None
    logging: dict = {}
