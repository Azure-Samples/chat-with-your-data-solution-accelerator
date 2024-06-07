import logging
from typing import List
import urllib.request
import json
import tempfile

from .orchestrator_base import OrchestratorBase
from ..common.answer import Answer
from ..helpers.llm_helper import LLMHelper

logger = logging.getLogger(__name__)


class PromptFlowOrchestrator(OrchestratorBase):
    def __init__(self) -> None:
        super().__init__()
        self.llm_helper = LLMHelper()

        # Get the ML client and endpoint name
        self.ml_client = self.llm_helper.get_ml_client()
        print("ML Client: ", self.ml_client)  # TOREMOVE
        self.enpoint_name = self.llm_helper.get_endpoint_name()
        print("Endpoint Name: ", self.enpoint_name)  # TOREMOVE
        self.deployment_name = self.llm_helper.get_deployment_name()

    async def orchestrate(
        self, user_message: str, chat_history: List[dict], **kwargs: dict
    ) -> list[dict]:
        # Call Content Safety tool
        if self.config.prompts.enable_content_safety:
            if response := self.call_content_safety_input(user_message):
                return response

        # Transform conversation history into the right format for the Prompt Flow service
        transformed_chat_history = self.llm_helper.transform_chat_history_for_pf(chat_history)

        # Transform input into the right format for the Prompt Flow service
        data = {"chat_input": user_message, "chat_history": transformed_chat_history}
        print("Data: ", data)  # TOREMOVE
        body = str.encode(json.dumps(data))
        with tempfile.NamedTemporaryFile(delete=False) as file:
            file.write(body)

        # Call the Prompt Flow service
        try:
            response = self.ml_client.online_endpoints.invoke(
                endpoint_name=self.enpoint_name, request_file=file.name,
                deployment_name=self.deployment_name
            )
            print("Response: ", response)  # TOREMOVE
            result = json.loads(response)
            print("Chat output: ", result)  # TOREMOVE
            logger.debug(result)
        except urllib.error.HTTPError as error:
            logger.error("The request failed with status code: %s", str(error.code))
            logger.error(error.info())
            logger.error(error.read().decode("utf8", "ignore"))

        # Transform response into answer
        answer = Answer(
            question=user_message,
            answer=result['chat_output'],
            prompt_tokens=0,  # TODO: Does the response contain the number of tokens within metadata?
            completion_tokens=0,  # TODO: As above.
        )

        # Call Content Safety tool
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
