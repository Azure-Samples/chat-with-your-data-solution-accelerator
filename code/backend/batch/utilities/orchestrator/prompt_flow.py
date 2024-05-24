import logging
from typing import List
import urllib.request
import json

from .orchestrator_base import OrchestratorBase
from ..common.answer import Answer

logger = logging.getLogger(__name__)


class PromptFlowOrchestrator(OrchestratorBase):
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

        url = '<prompt-flow-host>/score' # TODO
        api_key = ''  # TODO
        if not api_key:
            raise Exception("A key should be provided to invoke the endpoint")

        # The azureml-model-deployment header will force the request to go to a specific deployment.
        # Remove this header to have the request observe the endpoint traffic rules
        headers = {
            'Content-Type':'application/json',
            'Authorization':('Bearer '+ api_key),
            'azureml-model-deployment': '<name-aml-model-deployment>'
        }

        req = urllib.request.Request(url, body, headers)

        try:
            response = urllib.request.urlopen(req)

            result = response.read()

            # Debugging
            print(result)
        except urllib.error.HTTPError as error:
            print("The request failed with status code: " + str(error.code))

            # Debugging
            print(error.info())
            print(error.read().decode("utf8", 'ignore'))

        # Transform response into answer
        answer = Answer(
            question=user_message,
            answer=result,
            prompt_tokens=0, # TODO
            completion_tokens=0, # TODO
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
