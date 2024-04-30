from ..common.Answer import Answer
from ..helpers.LLMHelper import LLMHelper
from ..helpers.ConfigHelper import ConfigHelper


class PostPromptTool:
    def __init__(self) -> None:
        pass

    def validate_answer(self, answer: Answer) -> dict:
        config = ConfigHelper.get_active_config_or_default()
        llm_helper = LLMHelper()

        sources = "\n".join(
            [
                f"[doc{i+1}]: {source.content}"
                for i, source in enumerate(answer.source_documents)
            ]
        )

        message = (
            config.prompts.post_answering_prompt.replace("{sources}", sources)
            .replace("{question}", answer.question)
            .replace("{answer}", answer.answer)
        )
        messages = [{"role": "user", "content": message}]

        response = llm_helper.get_chat_completion(messages)
        if response.choices[0].message.content == "True":
            return Answer(
                question=answer.question,
                answer=answer.answer,
                source_documents=answer.source_documents,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            )
        else:
            return Answer(
                question=answer.question,
                answer=config.messages.post_answering_filter,
                source_documents=[],
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
            )
