import logging
from typing import List
from langchain.agents import Tool
from langchain.memory import ConversationBufferMemory
from langchain.agents import ZeroShotAgent, AgentExecutor
from langchain.chains import LLMChain
from langchain_community.callbacks import get_openai_callback

from .OrchestratorBase import OrchestratorBase
from ..helpers.LLMHelper import LLMHelper
from ..tools.PostPromptTool import PostPromptTool
from ..tools.QuestionAnswerTool import QuestionAnswerTool
from ..tools.TextProcessingTool import TextProcessingTool
from ..common.Answer import Answer

logger = logging.getLogger(__name__)


class LangChainAgent(OrchestratorBase):
    def __init__(self) -> None:
        super().__init__()
        self.question_answer_tool = QuestionAnswerTool()
        self.text_processing_tool = TextProcessingTool()
        self.llm_helper = LLMHelper()

        self.tools = [
            Tool(
                name="Question Answering",
                func=self.run_tool,
                description="useful for when you need to answer questions about anything. Input should be a fully formed question. Do not call the tool for text processing operations like translate, summarize, make concise.",
                return_direct=True,
            ),
            Tool(
                name="Text Processing",
                func=self.run_text_processing_tool,
                description="""useful for when you need to process text like translate to Italian, summarize, make concise, in Spanish.
                Always start the input with be a proper text operation with language if mentioned and then the full text to process.
                e.g. translate to Spanish: <text to translate>""",
                return_direct=True,
            ),
        ]

    def run_tool(self, user_message):
        answer = self.question_answer_tool.answer_question(
            user_message, chat_history=[]
        )
        return answer.to_json()

    def run_text_processing_tool(self, user_message):
        answer = self.text_processing_tool.answer_question(
            user_message, chat_history=[]
        )
        return answer.to_json()

    async def orchestrate(
        self, user_message: str, chat_history: List[dict], **kwargs: dict
    ) -> list[dict]:

        # Call Content Safety tool
        if self.config.prompts.enable_content_safety:
            if response := self.call_content_safety_input(user_message):
                return response

        # Call function to determine route
        prefix = """Have a conversation with a human, answering the following questions as best you can. You have access to the following tools:"""
        suffix = """Begin!"

        {chat_history}
        Question: {input}
        {agent_scratchpad}"""
        prompt = ZeroShotAgent.create_prompt(
            self.tools,
            prefix=prefix,
            suffix=suffix,
            input_variables=["input", "chat_history", "agent_scratchpad"],
        )
        # Create conversation memory
        memory = ConversationBufferMemory(
            memory_key="chat_history", return_messages=True
        )
        for message in chat_history:
            if message["role"] == "user":
                memory.chat_memory.add_user_message(message["content"])
            elif message["role"] == "assistant":
                memory.chat_memory.add_ai_message(message["content"])
        # Define Agent and Agent Chain
        llm_chain = LLMChain(llm=self.llm_helper.get_llm(), prompt=prompt)
        agent = ZeroShotAgent(llm_chain=llm_chain, tools=self.tools, verbose=True)
        agent_chain = AgentExecutor.from_agent_and_tools(
            agent=agent, tools=self.tools, verbose=True, memory=memory
        )
        # Run Agent Chain
        with get_openai_callback() as cb:
            answer = agent_chain.run(user_message)
            self.log_tokens(
                prompt_tokens=cb.prompt_tokens,
                completion_tokens=cb.completion_tokens,
            )

        try:
            answer = Answer.from_json(answer)
        except Exception:
            answer = Answer(question=user_message, answer=answer)

        if self.config.prompts.enable_post_answering_prompt:
            logger.debug("Running post answering prompt")
            post_prompt_tool = PostPromptTool()
            answer = post_prompt_tool.validate_answer(answer)
            self.log_tokens(
                prompt_tokens=answer.prompt_tokens,
                completion_tokens=answer.completion_tokens,
            )

        # Call Content Safety tool
        if self.config.prompts.enable_content_safety:
            if response := self.call_content_safety_output(user_message, answer.answer):
                return response

        # Format the output for the UI
        messages = self.output_parser.parse(
            question=answer.question,
            answer=answer.answer,
            source_documents=answer.source_documents,
        )
        return messages
