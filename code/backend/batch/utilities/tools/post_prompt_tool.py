from ..common.answer import Answer
from ..helpers.llm_helper import LLMHelper
from ..helpers.config.config_helper import ConfigHelper


class PostPromptTool:
    def __init__(self) -> None:
        pass

    def validate_answer(self, answer: Answer) -> Answer:
        config = ConfigHelper.get_active_config_or_default()
        llm_helper = LLMHelper()

        sources = "\n".join(
            [
                f"[doc{i+1}]: {source.content}"
                for i, source in enumerate(answer.source_documents)
            ]
        )

        message = config.prompts.post_answering_prompt.format(
            question=answer.question,
            answer=answer.answer,
            sources=sources,
        )

        response = llm_helper.get_chat_completion(
            [
                {
                    "role": "user",
                    "content": message,
                }
            ]
        )

        result = response.choices[0].message.content

        was_message_filtered = result.lower() not in ["true", "yes"]

        # Return filtered answer or just the original one
        if was_message_filtered:
            return Answer(
                question=answer.question,
                answer=config.messages.post_answering_filter,
                source_documents=[],
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            )
        else:
            return Answer(
                question=answer.question,
                answer=answer.answer,
                source_documents=answer.source_documents,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            )
