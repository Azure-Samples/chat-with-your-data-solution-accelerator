import json
import os

from cwyd_conversation_client import CWYDConversationClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Accessing environment variables
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
tenant_id = os.getenv("TENANT_ID")
base_url = os.getenv("BASE_URL")


class QADatasetCreator:
    def __init__(self, client_id, client_secret, tenant_id, base_url):
        self.client = CWYDConversationClient(
            client_id, client_secret, tenant_id, base_url
        )

    def extract_filename(self, citation):
        """Safely extract filename from citation metadata"""
        if "metadata" in citation and "filename" in citation["metadata"]:
            return citation["metadata"]["filename"]
        elif "title" in citation:
            # Extract filename from title if it exists
            title = citation["title"]
            if title.startswith("/documents/"):
                return title.split("/")[-1].replace(".pdf", "")
        return "Unknown Source"

    def get_conversation_response(self, question):
        """Wrapper to call CWYDConversationClient"""
        return self.client.get_conversation_response(question)

    def create_dataset_entry(self, query, api_response, latency):
        """Create a dataset entry in the required format"""
        try:
            # Extract the assistant's response from the API response
            messages = api_response["choices"][0]["messages"]
            response_content = next(
                msg["content"] for msg in messages if msg["role"] == "assistant"
            )

            # Get context from the tool message if available
            context = ""
            for msg in messages:
                if msg["role"] == "tool":
                    tool_content = json.loads(msg["content"])
                    if "citations" in tool_content:
                        for citation in tool_content["citations"]:
                            if "content" in citation:
                                filename = self.extract_filename(citation)
                                context += f"{filename}: {citation['content']}\n\n"

            # Create the dataset entry
            dataset_entry = {
                "query": query,
                "ground_truth": response_content,  # Set ground_truth as the response content
                "context": context.strip(),
                "latency": round(latency, 6),
                "response_length": len(response_content),
            }

            return dataset_entry
        except Exception as e:
            raise Exception(f"Error creating dataset entry: {str(e)}")


def load_questions_from_file(file_path):
    """Load questions from a JSON file"""
    with open(file_path, "r") as file:
        data = json.load(file)
    return data.get("questions", [])


def main():
    # Configuration
    config = {
        "client_id": client_id,
        "client_secret": client_secret,
        "tenant_id": tenant_id,
        "base_url": base_url,
    }

    # Initialize creator
    creator = QADatasetCreator(**config)

    # Load questions from questions.json file
    questions = load_questions_from_file("data/input_questions.json")
    print(f"Total questions to process: {len(questions)}")

    # Create dataset
    dataset = []

    with open("data/dataset.jsonl", "a") as dataset_file:
        for index, question in enumerate(
            questions, start=1
        ):  # Process only the first 3 questions for testing
            try:
                api_response, latency = creator.get_conversation_response(question)
                dataset_entry = creator.create_dataset_entry(
                    question, api_response, latency
                )
                dataset.append(dataset_entry)
                dataset_file.write(json.dumps(dataset_entry) + "\n")

                print(
                    f"[{index}/{len(questions)}] Successfully processed question: {question}"
                )

            except Exception as e:
                print(
                    f"[{index}/{len(questions)}] Error processing question '{question}': {str(e)}"
                )
                continue

        return dataset


if __name__ == "__main__":
    main()
