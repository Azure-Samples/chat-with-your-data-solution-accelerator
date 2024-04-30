import json
import logging
from typing import List
import warnings
from .AnsweringToolBase import AnsweringToolBase

from ..helpers.AzureSearchHelper import AzureSearchHelper
from ..helpers.ConfigHelper import ConfigHelper
from ..helpers.LLMHelper import LLMHelper
from ..helpers.EnvHelper import EnvHelper
from ..common.Answer import Answer
from ..common.SourceDocument import SourceDocument
from azure.search.documents.models import VectorizedQuery


logger = logging.getLogger(__name__)


class QuestionAnswerTool(AnsweringToolBase):

    def __init__(self) -> None:
        self.name = "QuestionAnswer"
        self.azure_search_helper = AzureSearchHelper()
        self.llm_helper = LLMHelper()
        self.env_helper = EnvHelper()
        self.config = ConfigHelper.get_active_config_or_default()

    def answer_question(
        self, question: str, chat_history: List[dict], **kwargs: dict
    ) -> Answer:
        question_embeddings = self.llm_helper.generate_embeddings(question)

        # Now that we are querying Azure Search using the official libraries, we can add and modify the query any way we need, such as adding a query for image embeddings
        vector_query = VectorizedQuery(
            vector=question_embeddings,
            k_nearest_neighbors=self.env_helper.AZURE_SEARCH_TOP_K,
            fields="content_vector",
        )
        search_results = self.azure_search_helper.search_client.search(
            search_text=question,
            top=self.env_helper.AZURE_SEARCH_TOP_K,
            vector_queries=[vector_query],
        )

        retrieved_documents = []
        source_documents = []
        i = 1
        for page in search_results.by_page():
            for document in page:
                retrieved_documents.append(
                    {f"[doc{i}]": {"content": document.get("content")}}
                )
                source_documents.append(
                    SourceDocument(
                        id=document.get("id"),
                        content=document.get("content"),
                        title=document.get("title"),
                        source=document.get("source"),
                        chunk=document.get("chunk"),
                        offset=document.get("offset"),
                        page_number=document.get("page_number"),
                    )
                )
                i += 1

        ret_docs_json = json.dumps(
            {"retrieved_documents": retrieved_documents}, separators=(",", ":")
        )
        question_with_sources = self.config.prompts.answering_user_prompt.replace(
            "{sources}", ret_docs_json
        ).replace("{question}", question)

        if self.config.prompts.use_on_your_data_format:
            example_question = self.config.prompts.answering_user_prompt.replace(
                "{sources}", self.config.example.documents
            ).replace("{question}", self.config.example.user_question)
            messages = [
                # {"role": "system", "content": f"{self.config.prompts.answering_system_prompt} {self.env_helper.AZURE_OPENAI_SYSTEM_MESSAGE}"}, # TODO is this second system message needed?
                {
                    "role": "system",
                    "content": self.config.prompts.answering_system_prompt,
                },
                {"role": "system", "name": "example_user", "content": example_question},
                {
                    "role": "system",
                    "name": "example_assistant",
                    "content": self.config.example.answer,
                },
            ]

            for message in chat_history:
                messages.append(
                    {"role": message["role"], "content": message["content"]}
                )  # TODO should this be in the else too?

        else:
            warnings.warn(
                "Azure OpenAI On Your Data prompt format is recommended and should be enabled in the Admin app.",
            )
            messages = []

        messages.append({"role": "user", "content": question_with_sources})

        response = self.llm_helper.get_chat_completion(messages)
        logger.info(response)

        return Answer(
            question=question,
            answer=response.choices[0].message.content,
            source_documents=source_documents,
            completion_tokens=response.usage.completion_tokens,
            prompt_tokens=response.usage.prompt_tokens,
        )
