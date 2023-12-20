from typing import List
from azure.ai.contentsafety import ContentSafetyClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.contentsafety.models import AnalyzeTextOptions
from ..helpers.EnvHelper import EnvHelper
from .AnswerProcessingBase import AnswerProcessingBase
from ..common.Answer import Answer


class ContentSafetyChecker(AnswerProcessingBase):
    """
    A class that performs content safety checks on answers.

    Attributes:
        content_safety_client (ContentSafetyClient): The client for content safety analysis.

    Methods:
        __init__(): Initializes the ContentSafetyChecker object.
        process_answer(answer, **kwargs): Processes the answer and filters out sensitive content.
        validate_input_and_replace_if_harmful(text): Validates the input text and replaces it if it contains harmful content.
        validate_output_and_replace_if_harmful(text): Validates the output text and replaces it if it contains harmful content.
        _filter_text_and_replace(text, response_template): Filters the text and replaces it with the response template if it contains harmful content.
    """

    def __init__(self):
        super().__init__()
        env_helper = EnvHelper()
        self.content_safety_client = ContentSafetyClient(
            env_helper.AZURE_CONTENT_SAFETY_ENDPOINT, AzureKeyCredential(env_helper.AZURE_CONTENT_SAFETY_KEY))

    def process_answer(self, answer: Answer, **kwargs: dict) -> Answer:
        """
        Processes the answer and filters out sensitive content.

        Args:
            answer (Answer): The answer to process.
            kwargs (dict): Additional keyword arguments.

        Returns:
            Answer: The processed answer.
        """
        response_template = kwargs['response_template']
        answer.answer = self._filter_text_and_replace(
            answer.answer, response_template)
        return answer

    def validate_input_and_replace_if_harmful(self, text: str) -> str:
        """
        Validates the input text and replaces it if it contains harmful content.

        Args:
            text (str): The input text to validate.

        Returns:
            str: The validated and replaced text.
        """
        response_template = (f"Unfortunately, I am not able to process your question, as I have detected sensitive "
                             f"content that I am not allowed to process. This might be a mistake, so please try "
                             f"rephrasing your question.")
        return self.process_answer(Answer(question="", answer=text, source_documents=[]), response_template=response_template).answer

    def validate_output_and_replace_if_harmful(self, text: str) -> str:
        """
        Validates the output text and replaces it if it contains harmful content.

        Args:
            text (str): The output text to validate.

        Returns:
            str: The validated and replaced text.
        """
        response_template = (f"Unfortunately, I have detected sensitive content in my answer, which I am not allowed "
                             f"to show you. This might be a mistake, so please try again and maybe rephrase your "
                             f"question.")
        return self.process_answer(Answer(question="", answer=text, source_documents=[]), response_template=response_template).answer

    def _filter_text_and_replace(self, text: str, response_template: str) -> str:
        """
        Filters the text and replaces it with the response template if it contains harmful content.

        Args:
            text (str): The text to filter.
            response_template (str): The template to replace the text with.

        Returns:
            str: The filtered text.
        """
        request = AnalyzeTextOptions(text=text)
        try:
            response = self.content_safety_client.analyze_text(request)
        except HttpResponseError as e:
            print("Analyze text failed.")
            if e.error:
                print(f"Error code: {e.error.code}")
                print(f"Error message: {e.error.message}")
                raise
            print(e)
            raise

        filtered_text = text

        if response.hate_result.severity > 0 or response.self_harm_result.severity > 0 or response.sexual_result.severity > 0 or response.violence_result.severity > 0:
            filtered_text = response_template

        return filtered_text
