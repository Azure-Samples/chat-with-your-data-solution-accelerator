from semantic_kernel.functions import kernel_function
from semantic_kernel.functions.kernel_arguments import KernelArguments

from ..common.answer import Answer
from ..tools.post_prompt_tool import PostPromptTool


class PostAnsweringPlugin:
    @kernel_function(description="Run post answering prompt to validate the answer.")
    def validate_answer(self, arguments: KernelArguments) -> Answer:
        return PostPromptTool().validate_answer(arguments["answer"])
