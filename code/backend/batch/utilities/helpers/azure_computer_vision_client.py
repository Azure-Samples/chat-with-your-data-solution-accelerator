import logging
from urllib.parse import urljoin
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

import requests
from requests import Response

from .env_helper import EnvHelper

logger = logging.getLogger(__name__)


class AzureComputerVisionClient:

    __TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"
    __VECTORIZE_IMAGE_PATH = "computervision/retrieval:vectorizeImage"
    __VECTORIZE_TEXT_PATH = "computervision/retrieval:vectorizeText"
    __RESPONSE_VECTOR_KEY = "vector"

    def __init__(self, env_helper: EnvHelper) -> None:
        self.host = env_helper.AZURE_COMPUTER_VISION_ENDPOINT
        self.timeout = env_helper.AZURE_COMPUTER_VISION_TIMEOUT
        self.key = env_helper.AZURE_COMPUTER_VISION_KEY
        self.use_keys = env_helper.is_auth_type_keys()
        self.api_version = env_helper.AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_API_VERSION
        self.model_version = (
            env_helper.AZURE_COMPUTER_VISION_VECTORIZE_IMAGE_MODEL_VERSION
        )

    def vectorize_image(self, image_url: str) -> list[float]:
        logger.info(f"Making call to computer vision to vectorize image: {image_url}")
        response = self.__make_request(
            self.__VECTORIZE_IMAGE_PATH,
            body={"url": image_url},
        )
        self.__validate_response(response)

        response_json = self.__get_json_body(response)
        return self.__get_vectors(response_json)

    def vectorize_text(self, text: str) -> list[float]:
        logger.debug(f"Making call to computer vision to vectorize text: {text}")
        response = self.__make_request(
            self.__VECTORIZE_TEXT_PATH,
            body={"text": text},
        )
        self.__validate_response(response)

        response_json = self.__get_json_body(response)
        return self.__get_vectors(response_json)

    def __make_request(self, path: str, body) -> Response:
        try:
            headers = {}
            if self.use_keys:
                headers["Ocp-Apim-Subscription-Key"] = self.key
            else:
                token_provider = get_bearer_token_provider(
                    DefaultAzureCredential(), self.__TOKEN_SCOPE
                )
                headers["Authorization"] = "Bearer " + token_provider()

            return requests.post(
                url=urljoin(self.host, path),
                params={
                    "api-version": self.api_version,
                    "model-version": self.model_version,
                },
                json=body,
                headers=headers,
                timeout=self.timeout,
            )
        except Exception as e:
            raise Exception("Call to Azure Computer Vision failed") from e

    def __validate_response(self, response: Response):
        if response.status_code != 200:
            raise Exception(
                f"Call to Azure Computer Vision failed with status: {response.status_code}, body: {response.text}"
            )

    def __get_json_body(self, response: Response) -> dict:
        try:
            return response.json()
        except Exception as e:
            raise Exception(
                f"Call to Azure Computer Vision returned malformed response body: {response.text}",
            ) from e

    def __get_vectors(self, response_json: dict) -> list[float]:
        if self.__RESPONSE_VECTOR_KEY in response_json:
            return response_json[self.__RESPONSE_VECTOR_KEY]
        else:
            raise Exception(
                f"Call to Azure Computer Vision returned no vector: {response_json}"
            )
