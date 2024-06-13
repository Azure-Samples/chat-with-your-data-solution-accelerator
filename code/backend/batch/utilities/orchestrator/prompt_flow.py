import logging
from typing import List
import json
import tempfile

from .orchestrator_base import OrchestratorBase
from ..common.answer import Answer
from ..helpers.llm_helper import LLMHelper
from ..helpers.env_helper import EnvHelper

logger = logging.getLogger(__name__)


class PromptFlowOrchestrator(OrchestratorBase):
    def __init__(self) -> None:
        super().__init__()
        self.llm_helper = LLMHelper()
        self.env_helper = EnvHelper()

        # Get the ML client, endpoint and deployment names
        self.ml_client = self.llm_helper.get_ml_client()
        self.enpoint_name = self.env_helper.PROMPT_FLOW_ENDPOINT_NAME
        self.deployment_name = self.env_helper.PROMPT_FLOW_DEPLOYMENT_NAME

    async def orchestrate(
        self, user_message: str, chat_history: List[dict], **kwargs: dict
    ) -> list[dict]:
        # Call Content Safety tool on question
        if self.config.prompts.enable_content_safety:
            if response := self.call_content_safety_input(user_message):
                return response

        transformed_chat_history = self.transform_chat_history(chat_history)

        file_name = self.transform_data_into_file(
            user_message, transformed_chat_history
        )

        # Call the Prompt Flow service
        try:
            response = self.ml_client.online_endpoints.invoke(
                endpoint_name=self.enpoint_name,
                request_file=file_name,
                deployment_name=self.deployment_name,
            )
            result = json.loads(response)
            logger.debug(result)
        except Exception as error:
            logger.error("The request failed: %s", error)
            raise RuntimeError(f"The request failed: {error}") from error

        # Transform response into answer for further processing
        answer = Answer(question=user_message, answer=result["chat_output"])

        # Call Content Safety tool on answer
        if self.config.prompts.enable_content_safety:
            if response := self.call_content_safety_output(user_message, answer.answer):
                return response

        # Format the output for the UI
        messages = self.output_parser.parse(
            question=answer.question,
            answer=answer.answer,
            source_documents=answer.source_documents,
        )
        return messages

    def transform_chat_history(self, chat_history):
        transformed_chat_history = []
        for i, message in enumerate(chat_history):
            if message["role"] == "user":
                user_message = message["content"]
                assistant_message = ""
                if (
                    i + 1 < len(chat_history)
                    and chat_history[i + 1]["role"] == "assistant"
                ):
                    assistant_message = chat_history[i + 1]["content"]
                transformed_chat_history.append(
                    {
                        "inputs": {"chat_input": user_message},
                        "outputs": {"chat_output": assistant_message},
                    }
                )
        return transformed_chat_history

    def transform_data_into_file(self, user_message, chat_history):
        # Transform data input into a file for the Prompt Flow service
        data = {"chat_input": user_message, "chat_history": chat_history}
        body = str.encode(json.dumps(data))
        with tempfile.NamedTemporaryFile(delete=False) as file:
            file.write(body)
        return file.name
