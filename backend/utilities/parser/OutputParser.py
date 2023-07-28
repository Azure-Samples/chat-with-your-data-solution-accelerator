from typing import List
import logging
import re
import json
from .ParserBase import ParserBase
from ..azureblobstorage import AzureBlobStorageClient

class OutputParserTool(ParserBase):
    def __init__(self) -> None:
        self.name = "OutputParser"
    
    def parse(self, input: dict, **kwargs: dict) -> List[dict]:     
        result = input["result"]
        answer = result['answer'].replace('  ', ' ')
        
        # Replace [[url]] with [docx] for citation feature to work
        source_urls = re.findall(r'\[\[(.*?)\]\]', answer)
        for idx, url in enumerate(source_urls):
            answer = answer.replace(f'[[{url}]]', f'[doc{idx+1}]')
            
        print(f"answer: {answer}")

        # create return message object
        messages = [
            {
                "role": "tool",
                "content": {"citations": [], "intent": result["generated_question"]},
                "end_turn": False,
            }
        ]
        
        blob_client = AzureBlobStorageClient()    
        container_sas = blob_client.get_container_sas()
        for url_idx, url in enumerate(source_urls):
            # Check which result['source_documents'][x].metadata['source'] matches the url
            idx = None
            try:
                idx = [doc.metadata['source'] for doc in result["source_documents"]].index(url)
            except ValueError:
                print('Could not find source document for url: ' + url)
            if idx is not None:
                print(idx)
                doc = result["source_documents"][idx]
            
                # Then update the citation object in the response, it needs to have filepath and chunk_id to render in the UI as a file
                messages[0]["content"]["citations"].append(
                    {
                        "content": doc.metadata["source"].replace(
                            "_SAS_TOKEN_PLACEHOLDER_", container_sas
                        ) + "\n\n\n" + doc.page_content,
                        "id": url_idx,
                        "chunk_id": doc.metadata["chunk"],
                        "title": doc.metadata["title"], # we need to use original_filename as LangChain needs filename-chunk as unique identifier
                        "filepath": doc.metadata["title"],
                        "url": doc.metadata["source"].replace(
                            "_SAS_TOKEN_PLACEHOLDER_", container_sas
                        ),
                        "metadata": doc.metadata,
                    })
        if messages[0]["content"]["citations"] == []:
            answer = re.sub(r'\[doc\d+\]', '', answer)
        messages.append({"role": "assistant", "content": answer, "end_turn": True})
                # everything in content needs to be stringified to work with Azure BYOD frontend
        messages[0]["content"] = json.dumps(messages[0]["content"])
        return messages
    