"""OpenAPI field-description coverage.

Builds a minimal FastAPI app that references every model whose fields
gained ``Field(description=...)`` and asserts each representative field
carries a non-empty ``description`` in the generated schema, so the
FastAPI Swagger SCHEMA panels render per-field documentation. This test
fails if a target model's field descriptions are removed.
"""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from backend.core.providers.search.base import SourceListing
from backend.core.types import (
    ChatMessage,
    Citation,
    Conversation,
    MessageRecord,
    RuntimeConfig,
)
from backend.models.admin import AdminConfig, AdminStatus, EffectiveAdminConfig
from backend.models.conversation import ConversationRequest, ConversationResponse
from backend.models.health import DependencyCheck, HealthResponse
from backend.models.history import (
    AddMessageRequest,
    ConversationDetail,
    CreateConversationRequest,
    HistoryStatus,
    RenameConversationRequest,
    SetFeedbackRequest,
)

_MODELS: list[type[BaseModel]] = [
    ConversationRequest,
    ConversationResponse,
    DependencyCheck,
    HealthResponse,
    AddMessageRequest,
    ConversationDetail,
    CreateConversationRequest,
    HistoryStatus,
    RenameConversationRequest,
    SetFeedbackRequest,
    AdminConfig,
    AdminStatus,
    EffectiveAdminConfig,
    ChatMessage,
    Citation,
    Conversation,
    MessageRecord,
    RuntimeConfig,
    SourceListing,
]

# One guaranteed-present field per edited model. The pair is asserted to
# carry a non-empty ``description`` in the generated OpenAPI schema.
_EXPECTED_DESCRIBED_FIELDS: list[tuple[str, str]] = [
    ("ConversationRequest", "messages"),
    ("ConversationResponse", "content"),
    ("DependencyCheck", "name"),
    ("HealthResponse", "status"),
    ("AddMessageRequest", "content"),
    ("ConversationDetail", "messages"),
    ("CreateConversationRequest", "title"),
    ("HistoryStatus", "enabled"),
    ("RenameConversationRequest", "title"),
    ("SetFeedbackRequest", "feedback"),
    ("AdminConfig", "orchestrator_name"),
    ("AdminStatus", "orchestrator_name"),
    ("EffectiveAdminConfig", "assistant_type_presets"),
    ("ChatMessage", "role"),
    ("Citation", "id"),
    ("Conversation", "id"),
    ("MessageRecord", "id"),
    ("RuntimeConfig", "orchestrator_name"),
    ("SourceListing", "source"),
]


def _build_app() -> FastAPI:
    app = FastAPI()
    for index, model in enumerate(_MODELS):

        async def _endpoint() -> Any:  # pragma: no cover - never called
            ...

        app.add_api_route(
            f"/model-{index}",
            _endpoint,
            methods=["GET"],
            response_model=model,
        )
    return app


def test_edited_models_expose_field_descriptions() -> None:
    app = _build_app()
    spec = app.openapi()
    schemas = spec["components"]["schemas"]

    for model_name, field_name in _EXPECTED_DESCRIBED_FIELDS:
        assert model_name in schemas, f"{model_name} missing from OpenAPI schemas"
        properties = schemas[model_name]["properties"]
        assert (
            field_name in properties
        ), f"{model_name}.{field_name} missing from schema properties"
        description = properties[field_name].get("description")
        assert (
            description
        ), f"{model_name}.{field_name} has no OpenAPI field description"
