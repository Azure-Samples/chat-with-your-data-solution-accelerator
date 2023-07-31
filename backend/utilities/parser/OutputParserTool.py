from typing import List
import logging
import re
import json
from .ParserBase import ParserBase
from .SourceDocument import SourceDocument

class OutputParserTool(ParserBase):
    def __init__(self) -> None:
        self.name = "OutputParser"

    
    def _clean_up_answer(answer):
        return answer.replace('  ', ' ')
    
    def _get_source_urls_from_answer(answer):
        return re.findall(r'\[\[(.*?)\]\]', answer)
    
    def _replaces_urls_with_doc_in_answer(answer, source_urls):
        for idx, url in enumerate(source_urls):
            answer = answer.replace(f'[[{url}]]', f'[doc{idx+1}]')
        return answer
    
    def parse(self, question: str, answer: str, source_documents: List[SourceDocument], **kwargs: dict) -> List[dict]:     
        
        # Replace [[url]] with [docx] for citation feature to work
        answer = self._clean_up_answer(answer)
        source_urls = self._get_source_urls_from_answer(answer)
        answer = self._replaces_urls_with_doc_in_answer(answer, source_urls)
            
        # create return message object
        messages = [
            {
                "role": "tool",
                "content": {"citations": [], "intent": question},
                "end_turn": False,
            }
        ]
        
        for url_idx, url in enumerate(source_urls):
            # Check which result['source_documents'][x].metadata['source'] matches the url
            idx = None
            try:
                idx = [doc.metadata['source'] for doc in source_documents].index(url)
            except ValueError:
                print('Could not find source document for url: ' + url)
            if idx is not None:
                doc = source_documents[idx]

                # Then update the citation object in the response, it needs to have filepath and chunk_id to render in the UI as a file
                messages[0]["content"]["citations"].append(
                    {
                        "content": doc.get_markdown_url() + "\n\n\n" + doc.content,
                        "id": url_idx,
                        "chunk_id": doc.chunk,
                        "title": doc.title,
                        "filepath": doc.get_filename(include_path=True),
                        "url": doc.get_markdown_url(),
                        "metadata": {
                            "offset": doc.offset,
                            "source": doc.source_url,
                            "markdown_url": doc.get_markdown_url(),
                            "title": doc.title,
                            "original_url": doc.source_url,
                            "chunk": doc.chunk,
                            "key": doc.id,
                            "filename": doc.get_filename()
                        },
                    })
        if messages[0]["content"]["citations"] == []:
            answer = re.sub(r'\[doc\d+\]', '', answer)
        messages.append({"role": "assistant", "content": answer, "end_turn": True})
        # everything in content needs to be stringified to work with Azure BYOD frontend
        messages[0]["content"] = json.dumps(messages[0]["content"])
        return messages
    