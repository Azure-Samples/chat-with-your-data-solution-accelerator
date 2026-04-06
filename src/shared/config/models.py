"""Configuration models for active.json config schema."""

from __future__ import annotations

from pydantic import BaseModel


class PromptConfig(BaseModel, extra="ignore"):
    condense_question_prompt: str = ""
    answering_system_prompt: str = ""
    answering_user_prompt: str = ""
    post_answering_prompt: str = ""
    use_on_your_data_format: bool = True
    enable_post_answering_prompt: bool = False
    enable_content_safety: bool = True
    ai_assistant_type: str = "default"
    conversational_flow: str = "custom"


class ExampleConfig(BaseModel):
    documents: str = ""
    user_question: str = ""
    answer: str = ""


class MessagesConfig(BaseModel):
    post_answering_filter: str = (
        "I'm sorry, but I'm unable to provide a response to that question based on the available information."
    )


class OrchestratorConfig(BaseModel):
    strategy: str = "openai_function"


class LoggingConfig(BaseModel):
    log_user_interactions: bool = False
    log_tokens: bool = False


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


class ConfigModel(BaseModel, extra="ignore"):
    prompts: PromptConfig = PromptConfig()
    example: ExampleConfig = ExampleConfig()
    messages: MessagesConfig = MessagesConfig()
    orchestrator: OrchestratorConfig = OrchestratorConfig()
    logging: LoggingConfig = LoggingConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    document_processors: list[DocumentProcessor] = []
    integrated_vectorization_config: IntegratedVectorizationConfig | None = None
    enable_chat_history: bool = False
    database_type: str = "CosmosDB"
