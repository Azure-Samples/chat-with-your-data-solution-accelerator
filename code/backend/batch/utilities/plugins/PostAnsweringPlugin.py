from semantic_kernel.functions import kernel_function
from semantic_kernel.functions.kernel_arguments import KernelArguments

from ..common.Answer import Answer
from ..tools.PostPromptTool import PostPromptTool


class PostAnsweringPlugin:
    @kernel_function(description="Run post answering prompt to validate the answer.")
    def validate_answer(self, arguments: KernelArguments) -> Answer:
        # TODO: Use Semantic Kernel to call LLM
        return PostPromptTool().validate_answer(arguments["answer"])
