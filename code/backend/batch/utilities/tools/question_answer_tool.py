import json
import logging
import warnings

from ..common.answer import Answer
from ..common.source_document import SourceDocument
from ..helpers.azure_blob_storage_client import AzureBlobStorageClient
from ..helpers.config.config_helper import ConfigHelper
from ..helpers.env_helper import EnvHelper
from ..helpers.llm_helper import LLMHelper
from ..search.search import Search
from .answering_tool_base import AnsweringToolBase
from openai.types.chat import ChatCompletion

logger = logging.getLogger(__name__)


class QuestionAnswerTool(AnsweringToolBase):
    def __init__(self) -> None:
        self.name = "QuestionAnswer"
        self.env_helper = EnvHelper()
        self.llm_helper = LLMHelper()
        self.search_handler = Search.get_search_handler(env_helper=self.env_helper)
        self.verbose = True

        self.config = ConfigHelper.get_active_config_or_default()

    @staticmethod
    def json_remove_whitespace(obj: str) -> str:
        """
        Remove whitespace from a JSON string.
        """
        try:
            return json.dumps(json.loads(obj), separators=(",", ":"))
        except json.JSONDecodeError:
            return obj

    @staticmethod
    def clean_chat_history(chat_history: list[dict]) -> list[dict]:
        return [
            {
                "content": message["content"],
                "role": message["role"],
            }
            for message in chat_history
        ]

    def generate_messages(self, question: str, sources: list[SourceDocument]):
        sources_text = "\n\n".join(
            [f"[doc{i+1}]: {source.content}" for i, source in enumerate(sources)]
        )

        return [
            {
                "content": self.config.prompts.answering_user_prompt.format(
                    question=question, sources=sources_text
                ),
                "role": "user",
            },
        ]

    def generate_on_your_data_messages(
        self,
        question: str,
        chat_history: list[dict],
        sources: list[SourceDocument],
        image_urls: list[str] = [],
    ) -> list[dict]:
        examples = []

        few_shot_example = {
            "sources": self.config.example.documents.strip(),
            "question": self.config.example.user_question.strip(),
            "answer": self.config.example.answer.strip(),
        }

        if few_shot_example["sources"]:
            few_shot_example["sources"] = QuestionAnswerTool.json_remove_whitespace(
                few_shot_example["sources"]
            )

        if any(few_shot_example.values()):
            if all((few_shot_example.values())):
                examples.append(
                    {
                        "content": self.config.prompts.answering_user_prompt.format(
                            sources=few_shot_example["sources"],
                            question=few_shot_example["question"],
                        ),
                        "name": "example_user",
                        "role": "system",
                    }
                )
                examples.append(
                    {
                        "content": few_shot_example["answer"],
                        "name": "example_assistant",
                        "role": "system",
                    }
                )
            else:
                warnings.warn(
                    "Not all example fields are set in the config. Skipping few-shot example."
                )

        documents = json.dumps(
            {
                "retrieved_documents": [
                    {f"[doc{i+1}]": {"content": source.content}}
                    for i, source in enumerate(sources)
                ],
            },
            separators=(",", ":"),
        )

        return [
            {
                "content": self.config.prompts.answering_system_prompt,
                "role": "system",
            },
            *examples,
            {
                "content": self.env_helper.AZURE_OPENAI_SYSTEM_MESSAGE,
                "role": "system",
            },
            *QuestionAnswerTool.clean_chat_history(chat_history),
            {
                "content": [
                    {
                        "type": "text",
                        "text": self.config.prompts.answering_user_prompt.format(
                            sources=documents,
                            question=question,
                        ),
                    },
                    *(
                        [
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url},
                            }
                            for image_url in image_urls
                        ]
                    ),
                ],
                "role": "user",
            },
        ]

    def answer_question(self, question: str, chat_history: list[dict], **kwargs):
        source_documents = Search.get_source_documents(self.search_handler, question)

        if self.env_helper.USE_ADVANCED_IMAGE_PROCESSING:
            image_urls = self.create_image_url_list(source_documents)
        else:
            image_urls = []

        model = self.env_helper.AZURE_OPENAI_VISION_MODEL if image_urls else None

        if self.config.prompts.use_on_your_data_format:
            messages = self.generate_on_your_data_messages(
                question, chat_history, source_documents, image_urls
            )
        else:
            warnings.warn(
                "Azure OpenAI On Your Data prompt format is recommended and should be enabled in the Admin app.",
            )
            messages = self.generate_messages(question, source_documents)

        llm_helper = LLMHelper()

        response = llm_helper.get_chat_completion(messages, model=model, temperature=0)
        clean_answer = self.format_answer_from_response(
            response, question, source_documents
        )

        return clean_answer

    def create_image_url_list(self, source_documents):
        image_types = self.config.get_advanced_image_processing_image_types()

        blob_client = AzureBlobStorageClient()
        container_sas = blob_client.get_container_sas()

        image_urls = [
            doc.source.replace("_SAS_TOKEN_PLACEHOLDER_", container_sas)
            for doc in source_documents
            if doc.title is not None and doc.title.split(".")[-1] in image_types
        ][: self.env_helper.ADVANCED_IMAGE_PROCESSING_MAX_IMAGES]

        return image_urls

    def format_answer_from_response(
        self,
        response: ChatCompletion,
        question: str,
        source_documents: list[SourceDocument],
    ):
        answer = response.choices[0].message.content
        logger.debug(f"Answer: {answer}")

        # Generate Answer Object
        clean_answer = Answer(
            question=question,
            answer=answer,
            source_documents=source_documents,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
        )

        return clean_answer
