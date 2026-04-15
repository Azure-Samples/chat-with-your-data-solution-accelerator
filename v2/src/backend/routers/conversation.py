"""Conversation endpoint: POST /api/conversation.

Supports two flows based on ``conversational_flow`` configuration:
  - **byod** — Direct Azure OpenAI call with ``data_sources`` extra_body.
    Supports streaming (``application/json-lines``) and non-streaming.
  - **custom** — Routes through the Orchestrator pipeline (OpenAI Functions,
    LangGraph, SK, Azure Agents).  Returns a JSON response.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from shared.config.config_helper import ConfigHelper
from shared.llm.llm_helper import LLMHelper, get_current_date_suffix
from shared.orchestrator.orchestrator import Orchestrator

from ..models.conversation import ConversationRequest

if TYPE_CHECKING:
    from openai import Stream
    from openai.types.chat import ChatCompletionChunk

    from shared.config.env_settings import EnvSettings
    from shared.llm.llm_helper import LLMHelper as LLMHelperType

logger = logging.getLogger(__name__)

router = APIRouter()

_ERROR_429_MESSAGE = (
    "We're currently experiencing a high number of requests. "
    "Please try again in a few seconds."
)
_ERROR_GENERIC_MESSAGE = (
    "An error occurred. Please try again. "
    "If the problem persists, please contact the site administrator."
)


# ── helpers ──────────────────────────────────────────────────────


def _build_data_source(settings: EnvSettings) -> dict:
    """Build the ``extra_body.data_sources`` block for Azure OYD."""
    search = settings.search
    auth = settings.auth
    oai = settings.openai

    if auth.azure_auth_type == "keys":
        authentication = {"type": "api_key", "key": search.key}
    else:
        authentication = {
            "type": "user_assigned_managed_identity",
            "managed_identity_resource_id": auth.managed_identity_resource_id,
        }

    query_type = (
        "vector_semantic_hybrid"
        if search.use_semantic_search
        else "vector_simple_hybrid"
    )

    return {
        "type": "azure_search",
        "parameters": {
            "authentication": authentication,
            "endpoint": f"https://{search.service}.search.windows.net",
            "index_name": search.index,
            "fields_mapping": {
                "content_fields": (
                    search.content_column.split("|") if search.content_column else []
                ),
                "vector_fields": [search.content_vector_column],
                "title_field": search.title_column or None,
                "url_field": search.fields_metadata or None,
                "filepath_field": search.filename_column or None,
            },
            "filter": search.filter or None,
            "in_scope": search.enable_in_domain,
            "top_n_documents": search.top_k,
            "embedding_dependency": {
                "type": "deployment_name",
                "deployment_name": oai.embedding_model,
            },
            "query_type": query_type,
            "semantic_configuration": (
                search.semantic_search_config
                if search.use_semantic_search and search.semantic_search_config
                else ""
            ),
            "role_information": oai.system_message + get_current_date_suffix(),
        },
    }


def _should_use_data(settings: EnvSettings) -> bool:
    """Check whether Azure Search is properly configured."""
    search = settings.search
    auth = settings.auth
    return bool(
        search.service
        and search.index
        and (search.key or auth.azure_auth_type == "rbac")
    )


# ── BYOD streaming generators ───────────────────────────────────


def _stream_with_data(response: Stream[ChatCompletionChunk]):
    """Yield ``application/json-lines`` chunks for BYOD *with data*."""
    response_obj: dict = {
        "id": "",
        "model": "",
        "created": 0,
        "object": "",
        "choices": [
            {
                "messages": [
                    {"content": "", "end_turn": False, "role": "tool"},
                    {"content": "", "end_turn": False, "role": "assistant"},
                ]
            }
        ],
    }

    for line in response:
        if not line.choices:
            continue
        choice = line.choices[0]

        if choice.model_extra and choice.model_extra.get("end_turn"):
            response_obj["choices"][0]["messages"][1]["end_turn"] = True
            yield json.dumps(response_obj, ensure_ascii=False) + "\n"
            return

        response_obj["id"] = line.id
        response_obj["model"] = line.model
        response_obj["created"] = line.created
        response_obj["object"] = line.object

        delta = choice.delta
        if delta.role == "assistant":
            context = delta.model_extra.get("context") if delta.model_extra else None
            if context:
                citations = _extract_citations(context)
                response_obj["choices"][0]["messages"][0]["content"] = json.dumps(
                    citations, ensure_ascii=False
                )
        else:
            if delta.content:
                response_obj["choices"][0]["messages"][1]["content"] += delta.content

        yield json.dumps(response_obj, ensure_ascii=False) + "\n"


def _stream_without_data(response: Stream[ChatCompletionChunk]):
    """Yield ``application/json-lines`` chunks for BYOD *without data*."""
    response_text = ""
    for line in response:
        if not line.choices:
            continue
        delta_text = line.choices[0].delta.content
        if delta_text is None:
            return
        response_text += delta_text
        yield json.dumps(
            {
                "id": line.id,
                "model": line.model,
                "created": line.created,
                "object": line.object,
                "choices": [
                    {"messages": [{"role": "assistant", "content": response_text}]}
                ],
            },
            ensure_ascii=False,
        ) + "\n"


def _extract_citations(context: dict) -> dict:
    """Extract citations from the OYD context object."""
    citations_out: list[dict] = []
    for c in context.get("citations", []):
        title = c.get("title", "")
        filepath = c.get("filepath", title)
        citations_out.append(
            {
                "content": c.get("content", ""),
                "id": c.get("id", ""),
                "chunk_id": c.get("chunk_id", ""),
                "title": title,
                "filepath": filepath,
                "url": c.get("url", ""),
            }
        )
    return {"citations": citations_out}


# ── BYOD flow ───────────────────────────────────────────────────


def _conversation_byod(
    payload: ConversationRequest, settings: EnvSettings
) -> JSONResponse | StreamingResponse:
    """Azure OpenAI 'On Your Data' flow (streaming or non-streaming)."""
    oai = settings.openai
    config = ConfigHelper.get_active_config_or_default()
    date_suffix = get_current_date_suffix()
    should_stream = oai.stream

    # Build message history
    messages: list[dict] = []
    if config.prompts.use_on_your_data_format:
        messages.append(
            {"role": "system", "content": config.prompts.answering_system_prompt + date_suffix}
        )
    for msg in payload.messages:
        messages.append({"role": msg.role, "content": msg.content})

    llm = LLMHelper(settings)
    use_data = _should_use_data(settings)

    call_kwargs: dict = {
        "model": oai.model,
        "messages": messages,
        "temperature": oai.temperature,
        "max_tokens": oai.max_tokens or None,
        "top_p": oai.top_p,
        "stream": should_stream,
    }
    if oai.stop_sequence:
        call_kwargs["stop"] = oai.stop_sequence.split("|")
    if use_data:
        call_kwargs["extra_body"] = {"data_sources": [_build_data_source(settings)]}

    response = llm.openai_client.chat.completions.create(**call_kwargs)

    # ── non-streaming ────────────────────────────────────────────
    if not should_stream:
        if use_data:
            context = response.choices[0].message.model_extra.get("context", {})
            citations = _extract_citations(context)
            resp_messages = [
                {
                    "content": json.dumps(citations, ensure_ascii=False),
                    "end_turn": False,
                    "role": "tool",
                },
                {
                    "end_turn": True,
                    "content": response.choices[0].message.content,
                    "role": "assistant",
                },
            ]
        else:
            resp_messages = [
                {
                    "role": "assistant",
                    "content": response.choices[0].message.content,
                }
            ]

        return JSONResponse(
            content={
                "id": response.id,
                "model": response.model,
                "created": response.created,
                "object": response.object,
                "choices": [{"messages": resp_messages}],
            }
        )

    # ── streaming ────────────────────────────────────────────────
    gen = _stream_with_data(response) if use_data else _stream_without_data(response)
    return StreamingResponse(gen, media_type="application/json-lines")


# ── Custom flow (orchestrator) ───────────────────────────────────


async def _conversation_custom(
    payload: ConversationRequest, settings: EnvSettings
) -> JSONResponse:
    """Orchestrator-based flow: routes to the configured strategy."""
    user_message = payload.messages[-1].content
    conversation_id = payload.conversation_id

    # Filter history: user/assistant only, exclude last message
    chat_history = [
        {"role": m.role, "content": m.content}
        for m in payload.messages[:-1]
        if m.role in ("user", "assistant")
    ]

    orchestrator = Orchestrator.get_strategy(settings)
    messages = await orchestrator.handle_message(
        user_message=user_message,
        chat_history=chat_history,
        conversation_id=conversation_id,
    )

    return JSONResponse(
        content={
            "id": conversation_id or "",
            "model": settings.openai.model,
            "created": 0,
            "object": "chat.completion",
            "choices": [{"messages": messages}],
        }
    )


# ── main endpoint ────────────────────────────────────────────────


@router.post("/conversation")
async def conversation(payload: ConversationRequest, req: Request):
    settings: EnvSettings = req.app.state.settings
    config = ConfigHelper.get_active_config_or_default()
    flow = config.prompts.conversational_flow

    try:
        if flow == "byod":
            return _conversation_byod(payload, settings)
        elif flow == "custom":
            return await _conversation_custom(payload, settings)
        else:
            return JSONResponse(
                status_code=500,
                content={"error": f"Invalid conversation flow: {flow}"},
            )
    except Exception as e:
        status = getattr(e, "status_code", 500)
        if status == 429:
            msg = _ERROR_429_MESSAGE
        else:
            msg = _ERROR_GENERIC_MESSAGE
            logger.exception("Conversation error")
        return JSONResponse(status_code=status, content={"error": msg})
