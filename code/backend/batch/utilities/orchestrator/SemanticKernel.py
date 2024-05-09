import json
import logging

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai.utils import get_tool_call_object
from semantic_kernel.contents import ChatHistory
from semantic_kernel.contents.finish_reason import FinishReason
from semantic_kernel.contents.chat_message_content import ChatMessageContent

from ..common.Answer import Answer
from ..helpers.LLMHelper import LLMHelper
from ..plugins.ChatPlugin import ChatPlugin
from ..plugins.PostAnsweringPlugin import PostAnsweringPlugin
from .OrchestratorBase import OrchestratorBase

logger = logging.getLogger(__name__)


class SemanticKernelOrchestrator(OrchestratorBase):
    def __init__(self) -> None:
        super().__init__()
        self.kernel = Kernel()
        self.llm_helper = LLMHelper()

        # Add the Azure OpenAI service to the kernel
        self.chat_service = self.llm_helper.get_sk_chat_completion_service("cwyd")
        self.kernel.add_service(self.chat_service)

        self.kernel.add_plugin(
            plugin=PostAnsweringPlugin(), plugin_name="PostAnswering"
        )

    async def orchestrate(
        self, user_message: str, chat_history: list[dict], **kwargs: dict
    ) -> list[dict]:
        # Call Content Safety tool
        if self.config.prompts.enable_content_safety:
            if response := self.call_content_safety_input(user_message):
                return response

        system_message = """You help employees to navigate only private information sources.
You must prioritize the function call over your general knowledge for any question by calling the search_documents function.
Call the text_processing function when the user request an operation on the current context, such as translate, summarize, or paraphrase. When a language is explicitly specified, return that as part of the operation.
When directly replying to the user, always reply in the language the user is speaking."""

        self.kernel.add_plugin(
            plugin=ChatPlugin(question=user_message, chat_history=chat_history),
            plugin_name="Chat",
        )

        settings = self.llm_helper.get_sk_service_settings(self.chat_service)
        settings.tools = get_tool_call_object(
            kernel=self.kernel, filter={"include_plugin": ["Chat"]}
        )

        orchestrate_function = self.kernel.add_function(
            plugin_name="Main",
            function_name="orchestrate",
            prompt="{{$chat_history}}{{$user_message}}",
            prompt_execution_settings=settings,
        )

        history = ChatHistory(system_message=system_message)

        for message in chat_history.copy():
            history.add_message(message)

        result: ChatMessageContent = (
            await self.kernel.invoke(
                function=orchestrate_function,
                chat_history=history,
                user_message=user_message,
            )
        ).value[0]

        self.log_tokens(
            prompt_tokens=result.metadata["usage"].prompt_tokens,
            completion_tokens=result.metadata["usage"].completion_tokens,
        )

        if result.finish_reason == FinishReason.TOOL_CALLS:
            logger.info("Semantic Kernel function call detected")

            function_name = result.items[0].name
            logger.info(f"{function_name} function detected")
            function = self.kernel.get_function_from_fully_qualified_function_name(
                function_name
            )

            arguments = json.loads(result.items[0].arguments)

            answer: Answer = (
                await self.kernel.invoke(function=function, **arguments)
            ).value

            self.log_tokens(
                prompt_tokens=answer.prompt_tokens,
                completion_tokens=answer.completion_tokens,
            )

            # Run post prompt if needed
            if (
                self.config.prompts.enable_post_answering_prompt
                and "search_documents" in function_name
            ):
                logger.debug("Running post answering prompt")
                answer: Answer = (
                    await self.kernel.invoke(
                        function_name="validate_answer",
                        plugin_name="PostAnswering",
                        answer=answer,
                    )
                ).value

                self.log_tokens(
                    prompt_tokens=answer.prompt_tokens,
                    completion_tokens=answer.completion_tokens,
                )
        else:
            logger.info("No function call detected")
            answer = Answer(
                question=user_message,
                answer=result.content,
                prompt_tokens=result.metadata["usage"].prompt_tokens,
                completion_tokens=result.metadata["usage"].completion_tokens,
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
