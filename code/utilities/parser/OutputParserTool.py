import json
import re
from typing import List

from .ParserBase import ParserBase
from ..common.SourceDocument import SourceDocument


class OutputParserTool(ParserBase):
    """
    A tool for parsing output data.

    Attributes:
        name (str): The name of the output parser tool.
    """

    def __init__(self) -> None:
        super().__init__()
        self.name = "OutputParser"

    def _clean_up_answer(self, answer):
        """
        Clean up the answer by replacing double spaces with single spaces.

        Args:
            answer (str): The answer to clean up.

        Returns:
            str: The cleaned up answer.
        """
        return answer.replace('  ', ' ')

    def _get_source_docs_from_answer(self, answer):
        """
        Extract the document IDs from the answer.

        Args:
            answer (str): The answer containing document references.

        Returns:
            List[int]: The list of document IDs.
        """
        results = re.findall(r'\[doc(\d+)\]', answer)
        return [int(i) for i in results]

    def _make_doc_references_sequential(self, answer, doc_ids):
        """
        Make the document references sequential.

        Args:
            answer (str): The answer containing document references.
            doc_ids (List[int]): The list of document IDs.

        Returns:
            str: The answer with sequential document references.
        """
        for i, idx in enumerate(doc_ids):
            answer = answer.replace(f'[doc{idx}]', f'[doc{i+1}]')
        return answer

    def parse(self, question: str, answer: str, source_documents: List[SourceDocument], **kwargs: dict) -> List[dict]:
        """
        Parse the output data.

        Args:
            question (str): The question asked.
            answer (str): The answer to the question.
            source_documents (List[SourceDocument]): The list of source documents.

        Returns:
            List[dict]: The list of messages containing the parsed data.
        """
        answer = self._clean_up_answer(answer)
        doc_ids = self._get_source_docs_from_answer(answer)
        answer = self._make_doc_references_sequential(answer, doc_ids)

        # create return message object
        messages = [
            {
                "role": "tool",
                "content": {"citations": [], "intent": question},
                "end_turn": False,
            }
        ]

        for i in doc_ids:
            idx = i-1
            doc = source_documents[idx]
            print(f"doc{idx}", doc)

            # Then update the citation object in the response, it needs to have filepath and chunk_id to render in
            # the UI as a file
            messages[0]["content"]["citations"].append(
                {
                    "content": doc.get_markdown_url() + "\n\n\n" + doc.content,
                    "id": doc.id,
                    "chunk_id": doc.chunk,
                    "title": doc.title,
                    "filepath": doc.get_filename(include_path=True),
                    "url": doc.get_markdown_url(),
                    "metadata": {
                        "offset": doc.offset,
                        "source": doc.source,
                        "markdown_url": doc.get_markdown_url(),
                        "title": doc.title,
                        "original_url": doc.source,  # TODO: do we need this?
                        "chunk": doc.chunk,
                        "key": doc.id,
                        "filename": doc.get_filename()
                    },
                })
        if messages[0]["content"]["citations"] == []:
            answer = re.sub(r'\[doc\d+\]', '', answer)
        messages.append(
            {"role": "assistant", "content": answer, "end_turn": True})
        # everything in content needs to be stringified to work with Azure BYOD frontend
        messages[0]["content"] = json.dumps(messages[0]["content"])
        return messages
