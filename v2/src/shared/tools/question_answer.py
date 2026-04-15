"""RAG tool: retrieve from search and answer with LLM."""

from __future__ import annotations

import json
import logging
import warnings
from typing import TYPE_CHECKING

from shared.common.answer import Answer
from shared.llm.llm_helper import get_current_date_suffix
from shared.search.azure_search_helper import SearchFactory, SearchHandlerBase

if TYPE_CHECKING:
    from shared.config.env_settings import EnvSettings
    from shared.config.models import ConfigModel
    from shared.llm.llm_helper import LLMHelper

logger = logging.getLogger(__name__)


def _json_remove_whitespace(obj: str) -> str:
    """Remove whitespace from a JSON string."""
    try:
        return json.dumps(json.loads(obj), separators=(",", ":"))
    except json.JSONDecodeError:
        return obj


class QuestionAnswerTool:
    """Retrieves relevant documents from search and generates an answer."""

    def __init__(
        self,
        settings: EnvSettings,
        llm_helper: LLMHelper,
        config: ConfigModel,
        search_handler: SearchHandlerBase | None = None,
    ) -> None:
        self.settings = settings
        self.llm_helper = llm_helper
        self.config = config
        self.search_handler = search_handler or SearchFactory.get_handler(
            settings, llm_helper
        )

    def answer_question(
        self,
        question: str,
        chat_history: list[dict],
        **kwargs,
    ) -> Answer:
        # 1. Search
        source_documents = SearchFactory.get_source_documents(
            self.search_handler, question
        )

        # 2. Build messages (use OYD format if configured)
        if self.config.prompts.use_on_your_data_format:
            messages = self._build_on_your_data_messages(
                question, chat_history, source_documents
            )
        else:
            warnings.warn(
                "Azure OpenAI On Your Data prompt format is recommended "
                "and should be enabled in the Admin app.",
                stacklevel=2,
            )
            messages = self._build_simple_messages(question, source_documents)

        # 3. Call LLM
        response = self.llm_helper.get_chat_completion(messages, temperature=0)

        # 4. Build Answer
        return Answer(
            question=question,
            answer=response.choices[0].message.content or "",
            source_documents=source_documents,
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
        )

    def _build_simple_messages(
        self,
        question: str,
        source_documents,
    ) -> list[dict]:
        """Non-OYD format: simple sources + question as user message."""
        sources_text = "\n\n".join(
            f"[doc{i + 1}]: {doc.content}" for i, doc in enumerate(source_documents)
        )
        user_prompt = self.config.prompts.answering_user_prompt or "{sources}\n\n{question}"
        return [
            {
                "role": "user",
                "content": user_prompt.format(sources=sources_text, question=question),
            }
        ]

    def _build_on_your_data_messages(
        self,
        question: str,
        chat_history: list[dict],
        source_documents,
        image_urls: list[str] | None = None,
    ) -> list[dict]:
        """Build the On-Your-Data format message array matching the old CWYD pattern."""
        date_suffix = get_current_date_suffix()
        prompts = self.config.prompts
        messages: list[dict] = []
        image_urls = image_urls or []

        # System prompt
        system_prompt = (prompts.answering_system_prompt or "") + date_suffix
        messages.append({"role": "system", "content": system_prompt})

        # Few-shot examples (if all fields are set)
        example = self.config.example
        few_shot = {
            "sources": (example.documents or "").strip(),
            "question": (example.user_question or "").strip(),
            "answer": (example.answer or "").strip(),
        }
        if few_shot["sources"]:
            few_shot["sources"] = _json_remove_whitespace(few_shot["sources"])

        if any(few_shot.values()):
            if all(few_shot.values()):
                user_prompt = prompts.answering_user_prompt or "{sources}\n\n{question}"
                messages.append(
                    {
                        "role": "system",
                        "name": "example_user",
                        "content": user_prompt.format(
                            sources=few_shot["sources"],
                            question=few_shot["question"],
                        ),
                    }
                )
                messages.append(
                    {
                        "role": "system",
                        "name": "example_assistant",
                        "content": few_shot["answer"],
                    }
                )
            else:
                warnings.warn(
                    "Not all example fields are set in the config. Skipping few-shot example.",
                    stacklevel=2,
                )

        # Second system message (OpenAI system message)
        oai_system = (self.settings.openai.system_message or "") + date_suffix
        messages.append({"role": "system", "content": oai_system})

        # Chat history (cleaned to role+content only)
        for msg in chat_history:
            messages.append(
                {"role": msg.get("role", "user"), "content": msg.get("content", "")}
            )

        # User message with retrieved documents (supports multimodal image_urls)
        documents = json.dumps(
            {
                "retrieved_documents": [
                    {f"[doc{i + 1}]": {"content": doc.content}}
                    for i, doc in enumerate(source_documents)
                ],
            },
            separators=(",", ":"),
        )
        user_prompt = prompts.answering_user_prompt or "{sources}\n\n{question}"
        user_text = user_prompt.format(sources=documents, question=question)

        # Build content as multimodal array if image_urls present, else plain text
        if image_urls:
            content_parts: list[dict] = [{"type": "text", "text": user_text}]
            for url in image_urls:
                content_parts.append(
                    {"type": "image_url", "image_url": {"url": url}}
                )
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": user_text})

        return messages
