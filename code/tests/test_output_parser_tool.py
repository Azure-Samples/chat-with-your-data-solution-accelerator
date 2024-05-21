import json

from typing import List

from backend.batch.utilities.parser.output_parser_tool import OutputParserTool
from backend.batch.utilities.common.source_document import SourceDocument


def test_returns_parsed_messages():
    # Given
    output_parser = OutputParserTool()
    question = "A question?"
    answer = "An answer"
    source_documents = []

    # When
    messages = output_parser.parse(
        question=question, answer=answer, source_documents=source_documents
    )

    # Then
    assert messages == [
        {
            "content": '{"citations": [], "intent": "A question?"}',
            "end_turn": False,
            "role": "tool",
        },
        {"content": "An answer", "end_turn": True, "role": "assistant"},
    ]


def test_removes_double_spaces_from_answer():
    # Given
    output_parser = OutputParserTool()
    question = "A question?"
    answer = "An  answer"
    source_documents = []

    # When
    messages = output_parser.parse(
        question=question, answer=answer, source_documents=source_documents
    )

    # Then
    assert messages == [
        {
            "content": '{"citations": [], "intent": "A question?"}',
            "end_turn": False,
            "role": "tool",
        },
        {"content": "An answer", "end_turn": True, "role": "assistant"},
    ]


def test_returns_citations():
    # Given
    output_parser = OutputParserTool()
    question = "A question?"
    answer = "An answer [doc1] [doc2]"
    source_documents = [
        SourceDocument(
            id="1",
            content="Some content",
            title="A title",
            source="A source",
            chunk="A chunk",
            offset="An offset",
            page_number="1",
        ),
        SourceDocument(
            id="2",
            content="Some more content",
            title="Another title",
            source="Another source",
            chunk="Another chunk",
            offset="Another offset",
            page_number="",
        ),
    ]

    # When
    messages = output_parser.parse(
        question=question, answer=answer, source_documents=source_documents
    )

    # Then
    expected_content = json.dumps(
        _convert_source_documents_to_content(question, source_documents)
    )
    assert messages[0]["content"] == expected_content


def test_orders_citations_in_ascending_order():
    # Given
    output_parser = OutputParserTool()
    question = "A question?"
    answer = "An answer [doc2] [doc3] [doc1]. With some more text."
    source_documents = [
        SourceDocument(
            id="3",
            content="Yet some more content",
            title="Yet another title",
            source="Yet another source",
            chunk="Yet another chunk",
            offset="Yet another offset",
            page_number="3",
        ),
        SourceDocument(
            id="2",
            content="Some more content",
            title="Another title",
            source="Another source",
            chunk="Another chunk",
            offset="Another offset",
            page_number="2",
        ),
        SourceDocument(
            id="1",
            content="Some content",
            title="A title",
            source="A source",
            chunk="A chunk",
            offset="An offset",
            page_number="1",
        ),
    ]

    # When
    messages = output_parser.parse(
        question=question, answer=answer, source_documents=source_documents
    )

    # Then
    assert (
        messages[1]["content"] == "An answer [doc1] [doc2] [doc3]. With some more text."
    )


def test_removes_doc_ids_from_answer_if_no_citations():
    # Given
    output_parser = OutputParserTool()
    question = "A question?"
    answer = "An answer [doc1] [doc2]"
    source_documents = []

    # When
    messages = output_parser.parse(
        question=question, answer=answer, source_documents=source_documents
    )

    # Then
    assert messages[1]["content"] == "An answer  "


def test_does_not_remove_doc_ids_from_answer_if_missing_citations():
    # Given
    output_parser = OutputParserTool()
    question = "A question?"
    answer = "An answer [doc1] [doc2]"
    source_documents = [
        SourceDocument(
            id="2",
            content="Some more content",
            title="Another title",
            source="Another source",
            chunk="Another chunk",
            offset="Another offset",
            page_number="",
        )
    ]
    # When
    messages = output_parser.parse(
        question=question, answer=answer, source_documents=source_documents
    )

    # Then
    assert messages[1]["content"] == "An answer [doc1] [doc2]"


def test_returns_chunk_number():
    # Given
    output_parser = OutputParserTool()
    question = "A question?"
    answer = "An answer [doc1] [doc2]"
    source_documents = [
        SourceDocument(
            id="2",
            content="Some more content",
            title="Another title",
            source="Another source",
            chunk=None,
            offset="Another offset",
            page_number="",
            chunk_id="abcd_pages_2",
        )
    ]

    # When
    messages = output_parser.parse(
        question=question, answer=answer, source_documents=source_documents
    )

    # Then
    expected = json.loads(messages[0]["content"])
    assert expected["citations"][0]["chunk_id"] == "2"


def _convert_source_documents_to_content(
    question: str, source_documents: List[SourceDocument]
) -> dict:
    content = {"citations": [], "intent": question}

    for source_document in source_documents:
        content["citations"].append(
            {
                "content": source_document.get_markdown_url()
                + "\n\n\n"
                + source_document.content,
                "id": source_document.id,
                "chunk_id": source_document.chunk,
                "title": source_document.title,
                "filepath": source_document.get_filename(include_path=True),
                "url": source_document.get_markdown_url(),
                "metadata": {
                    "offset": source_document.offset,
                    "source": source_document.source,
                    "markdown_url": source_document.get_markdown_url(),
                    "title": source_document.title,
                    "original_url": source_document.source,
                    "chunk": source_document.chunk,
                    "key": source_document.id,
                    "filename": source_document.get_filename(),
                },
            }
        )

    return content
