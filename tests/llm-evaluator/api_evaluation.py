import os
import pathlib
from typing import TypedDict

import pandas as pd
from azure.ai.evaluation import (CoherenceEvaluator, FluencyEvaluator,
                                 GroundednessEvaluator, RelevanceEvaluator,
                                 SimilarityEvaluator, evaluate)
from cwyd_conversation_client import CWYDConversationClient
from dotenv import load_dotenv
from typing_extensions import Self

# Load environment variables from .env file
load_dotenv()

# Accessing environment variables
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
tenant_id = os.getenv("TENANT_ID")
subscription_id = os.getenv("SUBSCRIPTION_ID")
resource_group_name = os.getenv("RESOURCE_GROUP_NAME")
# project_name = os.getenv("PROJECT_NAME")
azure_endpoint = os.getenv("AZURE_ENDPOINT")
azure_deployment = os.getenv("AZURE_DEPLOYMENT")
base_url = os.getenv("BASE_URL")  # Fetch the base URL from .env


class QADatasetEvaluator:
    def __init__(self, client_id, client_secret, tenant_id, base_url):
        self.client = CWYDConversationClient(
            client_id, client_secret, tenant_id, base_url
        )

    def create_dataset_entry(self, query, api_response, latency):
        """Create a dataset entry in the required format"""
        try:
            # Extract the assistant's response from the second message with role "assistant"
            messages = api_response["choices"][0]["messages"]
            assistant_response = next(
                msg["content"] for msg in messages if msg["role"] == "assistant"
            )

            # Create the dataset entry
            entry = {
                "query": query,
                "response": assistant_response,
                "latency": round(latency, 6),
                "response_length": len(assistant_response),
            }

            return entry, assistant_response
        except Exception as e:
            raise Exception(f"Error creating dataset entry: {str(e)}")

    def get_conversation_response(self, question):
        """Wrapper to call CWYDConversationClient"""
        return self.client.get_conversation_response(question)


class ModelEndpoint:
    def __init__(self: Self, model_config: dict, qa_evaluator_config: dict) -> None:
        self.model_config = model_config
        self.qa_evaluator_config = (
            qa_evaluator_config  # Store the config dictionary here
        )
        self.qa_creator = QADatasetEvaluator(
            self.qa_evaluator_config["client_id"],
            self.qa_evaluator_config["client_secret"],
            self.qa_evaluator_config["tenant_id"],
            self.qa_evaluator_config[
                "base_url"
            ],  # Pass the base URL to QADatasetCreator
        )
        print(self.model_config)

    class Response(TypedDict):
        query: str
        response: str

    def __call__(self: Self, query: str) -> Response:
        # Use the QADatasetCreator API to get the response
        try:
            api_response, latency = self.qa_creator.get_conversation_response(query)
            # Create the dataset entry with the response and latency
            entry, assistant_response = self.qa_creator.create_dataset_entry(
                query, api_response, latency
            )
            return {"query": query, "response": assistant_response}
        except Exception as e:
            return {"query": query, "response": f"Error: {str(e)}"}


def main():
    # Initialize the QADatasetEvaluator configuration with the necessary credentials
    qa_evaluator_config = {
        "client_id": client_id,
        "client_secret": client_secret,
        "tenant_id": tenant_id,
        "base_url": base_url,  # Include the base URL here
    }

    # Load data from JSONL file
    df = pd.read_json("data/dataset.jsonl", lines=True)
    # print(df.head())
    print(f"Total entries in dataset: {len(df)}")

    # Define the Azure AI project details
    # azure_ai_project = {
    #     "subscription_id": subscription_id,
    #     "resource_group_name": resource_group_name,
    #     "project_name": project_name,
    # }

    # Define the model configuration
    model_config = {
        "azure_endpoint": azure_endpoint,
        "azure_deployment": azure_deployment,
    }

    # Initialize evaluators
    # content_safety_evaluator = ContentSafetyEvaluator(
    #     azure_ai_project=azure_ai_project, credential=DefaultAzureCredential()
    # )
    relevance_evaluator = RelevanceEvaluator(model_config)
    coherence_evaluator = CoherenceEvaluator(model_config)
    groundedness_evaluator = GroundednessEvaluator(model_config)
    fluency_evaluator = FluencyEvaluator(model_config)
    similarity_evaluator = SimilarityEvaluator(model_config)

    # Define the path to the data file
    path = str(pathlib.Path.cwd() / "data" / "dataset.jsonl")

    # Run the evaluation using the new ModelEndpoint with QADatasetCreator config
    results = evaluate(
        evaluation_name="Eval-Run-" + "-" + model_config["azure_deployment"].title(),
        data=path,
        target=ModelEndpoint(
            model_config, qa_evaluator_config
        ),  # Pass the config dictionary
        evaluators={
            # "content_safety": content_safety_evaluator,
            "coherence": coherence_evaluator,
            "relevance": relevance_evaluator,
            "groundedness": groundedness_evaluator,
            "fluency": fluency_evaluator,
            "similarity": similarity_evaluator,
        },
        evaluator_config={
            "content_safety": {
                "column_mapping": {
                    "query": "${data.query}",
                    "response": "${target.response}",
                }
            },
            "coherence": {
                "column_mapping": {
                    "response": "${target.response}",
                    "query": "${data.query}",
                }
            },
            "relevance": {
                "column_mapping": {
                    "response": "${target.response}",
                    "context": "${data.context}",
                    "query": "${data.query}",
                }
            },
            "groundedness": {
                "column_mapping": {
                    "response": "${target.response}",
                    "context": "${data.context}",
                    "query": "${data.query}",
                }
            },
            "fluency": {
                "column_mapping": {
                    "response": "${target.response}",
                    "context": "${data.context}",
                    "query": "${data.query}",
                }
            },
            "similarity": {
                "column_mapping": {
                    "response": "${target.response}",
                    "ground_truth": "${data.ground_truth}",
                    "query": "${data.query}",
                }
            },
        },
    )

    # Convert the results to a DataFrame and save to Excel
    result_df = pd.DataFrame(results["rows"])

    # Define the file path for saving Excel
    excel_file_path = "data/evaluation_results.xlsx"

    # Save to Excel
    result_df.to_excel(excel_file_path, index=False)
    print(f"Evaluation results saved to {excel_file_path}")


if __name__ == "__main__":
    main()
