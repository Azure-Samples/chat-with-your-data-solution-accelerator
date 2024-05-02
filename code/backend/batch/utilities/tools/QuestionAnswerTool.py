import json
import logging
import warnings
from ..search.Search import Search
from .AnsweringToolBase import AnsweringToolBase

from langchain.chains.llm import LLMChain
from langchain.prompts import (
    AIMessagePromptTemplate,
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
)
from langchain_community.callbacks import get_openai_callback
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage

from ..helpers.ConfigHelper import ConfigHelper
from ..helpers.LLMHelper import LLMHelper
from ..helpers.EnvHelper import EnvHelper
from ..common.Answer import Answer

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

    def generate_llm_chain(self, question: str, sources: list[Document]):
        answering_prompt = PromptTemplate(
            template=self.config.prompts.answering_user_prompt,
            input_variables=["question", "sources"],
        )

        sources_text = "\n\n".join(
            [f"[doc{i+1}]: {source.page_content}" for i, source in enumerate(sources)]
        )

        return answering_prompt, {
            "sources": sources_text,
            "question": question,
        }

    def generate_on_your_data_llm_chain(
        self,
        question: str,
        chat_history: list[dict],
        sources: list[Document],
    ):
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
                examples.append(few_shot_example)
            else:
                warnings.warn(
                    "Not all example fields are set in the config. Skipping few-shot example."
                )

        example_prompt = ChatPromptTemplate.from_messages(
            [
                HumanMessagePromptTemplate.from_template(
                    self.config.prompts.answering_user_prompt
                ),
                AIMessagePromptTemplate.from_template("{answer}"),
            ]
        )

        few_shot_prompt = FewShotChatMessagePromptTemplate(
            example_prompt=example_prompt,
            examples=examples,
        )

        answering_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self.config.prompts.answering_system_prompt),
                few_shot_prompt,
                SystemMessage(content=self.env_helper.AZURE_OPENAI_SYSTEM_MESSAGE),
                MessagesPlaceholder("chat_history"),
                HumanMessagePromptTemplate.from_template(
                    self.config.prompts.answering_user_prompt
                ),
            ]
        )

        documents = json.dumps(
            {
                "retrieved_documents": [
                    {f"[doc{i+1}]": {"content": source.page_content}}
                    for i, source in enumerate(sources)
                ],
            },
            separators=(",", ":"),
        )

        return answering_prompt, {
            "sources": documents,
            "question": question,
            "chat_history": chat_history,
        }

    def answer_question(self, question: str, chat_history: list[dict], **kwargs):
        sources = Search.get_source_documents(self.search_handler, question)

        if self.config.prompts.use_on_your_data_format:
            answering_prompt, input = self.generate_on_your_data_llm_chain(
                question, chat_history, sources
            )
        else:
            warnings.warn(
                "Azure OpenAI On Your Data prompt format is recommended and should be enabled in the Admin app.",
            )
            answering_prompt, input = self.generate_llm_chain(question, sources)

        llm_helper = LLMHelper()

        answer_generator = LLMChain(
            llm=llm_helper.get_llm(), prompt=answering_prompt, verbose=self.verbose
        )

        with get_openai_callback() as cb:
            result = answer_generator(input)

        answer = result["text"]
        logger.debug(f"Answer: {answer}")

        # Generate Answer Object
        source_documents = self.search_handler.return_answer_source_documents(sources)
        clean_answer = Answer(
            question=question,
            answer=answer,
            source_documents=source_documents,
            prompt_tokens=cb.prompt_tokens,
            completion_tokens=cb.completion_tokens,
        )
        return clean_answer
