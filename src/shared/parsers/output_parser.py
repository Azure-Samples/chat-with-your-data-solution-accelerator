"""Output parser: extracts [docN] citations and formats the response for the UI."""

from __future__ import annotations

import json
import re

from shared.common.answer import SourceDocument


class OutputParser:
    """Converts an orchestrator answer into the tool+assistant message pair
    expected by the CWYD frontend."""

    @staticmethod
    def _clean_up_answer(answer: str) -> str:
        return answer.replace("  ", " ")

    @staticmethod
    def _get_source_doc_ids(answer: str) -> list[int]:
        return [int(i) for i in re.findall(r"\[doc(\d+)\]", answer)]

    @staticmethod
    def _make_doc_references_sequential(answer: str) -> str:
        doc_matches = list(re.finditer(r"\[doc\d+\]", answer))
        updated = answer
        offset = 0
        for i, match in enumerate(doc_matches):
            start, end = match.start() + offset, match.end() + offset
            new_ref = f"[doc{i + 1}]"
            updated = updated[:start] + new_ref + updated[end:]
            offset += len(new_ref) - (end - start)
        return updated

    @staticmethod
    def parse(
        question: str,
        answer: str,
        source_documents: list[SourceDocument] | None = None,
    ) -> list[dict]:
        source_documents = source_documents or []
        answer = OutputParser._clean_up_answer(answer)
        doc_ids = OutputParser._get_source_doc_ids(answer)
        answer = OutputParser._make_doc_references_sequential(answer)

        # Build citations from referenced source documents
        citations: list[dict] = []
        for i in doc_ids:
            idx = i - 1
            if idx < 0 or idx >= len(source_documents):
                continue
            doc = source_documents[idx]

            # chunk_id handling: extract numeric chunk from chunk_id if present
            if doc.chunk_id is not None:
                nums = re.findall(r"\d+", doc.chunk_id)
                chunk_id = nums[-1] if nums else doc.chunk_id
            else:
                chunk_id = doc.chunk

            # filepath: last segment of source path
            filepath = (doc.title or "").split("/")[-1] if doc.title else ""

            citations.append(
                {
                    "content": doc.content,
                    "id": doc.id,
                    "chunk_id": chunk_id,
                    "title": doc.title or "",
                    "filepath": filepath,
                    "url": doc.source,
                    "metadata": {
                        "offset": doc.offset,
                        "source": doc.source,
                        "title": doc.title,
                        "original_url": doc.source,
                        "chunk": doc.chunk,
                        "key": doc.id,
                        "filename": (doc.source or "").split("/")[-1].split(".")[0]
                        if doc.source
                        else "",
                    },
                }
            )

        # If no citations matched, strip leftover [docN] refs
        if not citations:
            answer = re.sub(r"\[doc\d+\]", "", answer)

        tool_msg = {
            "role": "tool",
            "content": json.dumps({"citations": citations, "intent": question}),
            "end_turn": False,
        }
        assistant_msg = {
            "role": "assistant",
            "content": answer,
            "end_turn": True,
        }
        return [tool_msg, assistant_msg]
