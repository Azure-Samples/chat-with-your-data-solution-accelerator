import logging
from azure.ai.contentsafety import ContentSafetyClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.contentsafety.models import AnalyzeTextOptions
from ..helpers.env_helper import EnvHelper
from .AnswerProcessingBase import AnswerProcessingBase
from ..common.Answer import Answer

logger = logging.getLogger(__name__)


class ContentSafetyChecker(AnswerProcessingBase):
    def __init__(self):
        env_helper = EnvHelper()

        if env_helper.AZURE_AUTH_TYPE == "rbac":
            self.content_safety_client = ContentSafetyClient(
                env_helper.AZURE_CONTENT_SAFETY_ENDPOINT,
                DefaultAzureCredential(),
            )
        else:
            self.content_safety_client = ContentSafetyClient(
                env_helper.AZURE_CONTENT_SAFETY_ENDPOINT,
                AzureKeyCredential(env_helper.AZURE_CONTENT_SAFETY_KEY),
            )

    def process_answer(self, answer: Answer, **kwargs: dict) -> Answer:
        response_template = kwargs["response_template"]
        answer.answer = self._filter_text_and_replace(answer.answer, response_template)
        return answer

    def validate_input_and_replace_if_harmful(self, text):
        response_template = f'{"Unfortunately, I am not able to process your question, as I have detected sensitive content that I am not allowed to process. This might be a mistake, so please try rephrasing your question."}'
        return self.process_answer(
            Answer(question="", answer=text, source_documents=[]),
            response_template=response_template,
        ).answer

    def validate_output_and_replace_if_harmful(self, text):
        response_template = f'{"Unfortunately, I have detected sensitive content in my answer, which I am not allowed to show you. This might be a mistake, so please try again and maybe rephrase your question."}'
        return self.process_answer(
            Answer(question="", answer=text, source_documents=[]),
            response_template=response_template,
        ).answer

    def _filter_text_and_replace(self, text, response_template):
        request = AnalyzeTextOptions(text=text)
        try:
            response = self.content_safety_client.analyze_text(request)
        except HttpResponseError as e:
            if e.error:
                logger.error(
                    f"Analyze text failed. Error code: {e.error.code}. Error message: {e.error.message}."
                )
                raise
            logger.exception("Analyze text failed.")
            raise

        filtered_text = text

        # if response.hate_result.severity > 0 or response.self_harm_result.severity > 0 or response.sexual_result.severity > 0 or response.violence_result.severity > 0:
        #     filtered_text = response_template
        for result in response.categories_analysis:
            if result.severity > 0:
                filtered_text = response_template

        return filtered_text
