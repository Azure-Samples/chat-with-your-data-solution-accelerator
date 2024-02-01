from azure.ai.contentsafety import ContentSafetyClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory
from ..helpers.EnvHelper import EnvHelper
from .AnswerProcessingBase import AnswerProcessingBase
from ..common.Answer import Answer


class ContentSafetyChecker(AnswerProcessingBase):
    def __init__(self):
        env_helper = EnvHelper()
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
            print("Analyze text failed.")
            if e.error:
                print(f"Error code: {e.error.code}")
                print(f"Error message: {e.error.message}")
                raise
            print(e)
            raise

        filtered_text = text
                
        hate_result = next(item for item in response.categories_analysis if item.category == TextCategory.HATE)
        self_harm_result = next(item for item in response.categories_analysis if item.category == TextCategory.SELF_HARM)
        sexual_result = next(item for item in response.categories_analysis if item.category == TextCategory.SEXUAL)
        violence_result = next(item for item in response.categories_analysis if item.category == TextCategory.VIOLENCE)
    
        if (
            hate_result.severity > 0
            or self_harm_result.severity > 0
            or sexual_result.severity > 0
            or violence_result.severity > 0
        ):
            filtered_text = response_template

        return filtered_text
