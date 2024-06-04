from promptflow import tool
import re


def _clean_up_answer(answer: str):
    return answer.replace("  ", " ")


def _get_source_docs_from_answer(answer):
    # extract all [docN] from answer and extract N, and just return the N's as a list of ints
    results = re.findall(r"\[doc(\d+)\]", answer)
    return [int(i) for i in results]


def _replace_last(text, old, new):
    """Replaces the last occurence of a substring in a string

    This is done by reversing the string using [::-1], replacing the first occurence of the reversed substring, and
    reversing the string again.
    """
    return (text[::-1].replace(old[::-1], new[::-1], 1))[::-1]


def _make_doc_references_sequential(answer, doc_ids):
    for i, idx in enumerate(doc_ids):
        answer = _replace_last(answer, f"[doc{idx}]", f"[doc{i+1}]")
    return answer


@tool
def my_python_tool(answer: str, sources: dict) -> str:
    answer = _clean_up_answer(answer)
    doc_ids = _get_source_docs_from_answer(answer)
    answer = _make_doc_references_sequential(answer, doc_ids)

    source_documents = sources.get("retrieved_documents", [])
    citations = []
    for i in doc_ids:
        idx = i - 1

        if idx >= len(source_documents):
            continue

        doc = source_documents[idx]
        citations.append(doc)

    return answer, citations
