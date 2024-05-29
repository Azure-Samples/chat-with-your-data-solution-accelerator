from typing import List
from promptflow import tool
from promptflow_vectordb.core.contracts import SearchResultEntity


@tool
def generate_prompt_context(search_result: List[dict]) -> str:
    retrieved_docs = []
    for index, item in enumerate(search_result):

        entity = SearchResultEntity.from_dict(item)
        content = entity.text or ""
        additional_fields = entity.additional_fields
        filepath = additional_fields.get("source")
        chunk_id = additional_fields.get("chunk_id", additional_fields.get("chunk", ""))

        retrieved_docs.append(
            {
                f"[doc{index+1}]": {
                    "content": content,
                    "filepath": filepath,
                    "chunk_id": chunk_id,
                }
            }
        )

    return {"retrieved_documents": retrieved_docs}
