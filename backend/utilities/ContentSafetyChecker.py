from azure.ai.contentsafety import ContentSafetyClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.contentsafety.models import AnalyzeTextOptions
from .EnvHelper import EnvHelper

class ContentSafetyChecker:
    def __init__(self):
        env_helper = EnvHelper()
        self.content_safety_client = ContentSafetyClient(env_helper.AZURE_CONTENT_SAFETY_ENDPOINT, AzureKeyCredential(env_helper.AZURE_CONTENT_SAFETY_KEY))

    def validate_input_and_replace_if_harmful(self, text):
        response_template = f"Unfortunately, I am not able to process your question, as I have detected sensitive content that I am not allowed to process. This might be a mistake, so please try rephrasing your question."
        return self._filter_text_and_replace(text, response_template)
        
    def validate_output_and_replace_if_harmful(self, text):
        response_template = f"Unfortunately, I have detected sensitive content in my answer, which I am not allowed to show you. This might be a mistake, so please try again and maybe rephrase your question."
        return self._filter_text_and_replace(text, response_template)
    
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
    
        if response.hate_result.severity > 0 or response.self_harm_result.severity > 0 or response.sexual_result.severity > 0 or response.violence_result.severity > 0:
            filtered_text = response_template
       
        return filtered_text