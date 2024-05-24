import logging
from typing import List
import urllib.request
import json

from .orchestrator_base import OrchestratorBase
from ..common.answer import Answer

logger = logging.getLogger(__name__)


class PromptFlowOrchestrator(OrchestratorBase):
    def __init__(self) -> None:
        super().__init__()

        # Set the URL and API key for the Prompt Flow endpoint
        # This could potentially be moved to LLM Helper
        # self.env_helper = EnvHelper()
        self.url = '<prompt-flow-host>/score' # self.url = self.env_helper.PROMPT_FLOW_URL
        self.api_key = ''  # self.api_key = self.env_helper.PROMPT_FLOW_API_KEY

    async def orchestrate(
        self, user_message: str, chat_history: List[dict], **kwargs: dict
    ) -> list[dict]:
        # Call Content Safety tool
        if self.config.prompts.enable_content_safety:
            if response := self.call_content_safety_input(user_message):
                return response

        # Call the Prompt Flow service
        data = {
            "user_input": user_message,
            "chat_history": chat_history
        }

        body = str.encode(json.dumps(data))

        # The azureml-model-deployment header will force the request to go to a specific deployment.
        # Remove this header to have the request observe the endpoint traffic rules
        headers = {
            'Content-Type':'application/json',
            'Authorization':('Bearer '+ self.api_key),
            'azureml-model-deployment': '<name-aml-model-deployment>' # TODO
        }

        req = urllib.request.Request(self.url, body, headers)

        try:
            response = urllib.request.urlopen(req)
            result = response.read()
            logger.debug(result)
        except urllib.error.HTTPError as error:
            logger.error("The request failed with status code: %s", str(error.code))
            logger.error(error.info())
            logger.error(error.read().decode("utf8", 'ignore'))

        # Transform response into answer
        answer = Answer(
            question=user_message,
            answer=result,
            prompt_tokens=0, # TODO: Does the response contain the number of tokens within metadata?
            completion_tokens=0, # TODO: As above.
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
