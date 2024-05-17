from typing import List
from promptflow import tool
from promptflow_vectordb.core.contracts import SearchResultEntity
import json


@tool
def generate_prompt_context(search_result: List[dict]) -> str:
    def format_doc(doc: dict):
        return f"Content: {doc['Content']}\nSource: {doc['Source']}"

    retrieved_docs = []
    for index, item in enumerate(search_result):

        entity = SearchResultEntity.from_dict(item)
        content = entity.text or ""

        retrieved_docs.append({f"[doc{index+1}]": {"content": content}})

    documents = json.dumps(
        {
            "retrieved_documents": retrieved_docs,
        },
        separators=(",", ":"),
    )

    return documents
