# flake8: noqa
from langchain.prompts import PromptTemplate

template = """{summaries}
Please reply to the question using only the information present in the text above. 
Include references to the sources you used to create the answer if those are relevant ("SOURCES"). 
If you can't find it, reply politely that the information is not in the knowledge base.
Question: {question}
Answer:"""

PROMPT = PromptTemplate(template=template, input_variables=["summaries", "question"])

EXAMPLE_PROMPT = PromptTemplate(
    template="Content: {page_content}\nSource: {source}",
    input_variables=["page_content", "source"],
)


