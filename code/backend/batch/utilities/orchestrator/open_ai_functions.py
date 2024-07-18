import logging
from typing import List
import json

from .orchestrator_base import OrchestratorBase
from ..common.answer import Answer
from ..common.SourceDocument import SourceDocument
from ..helpers.EnvHelper import EnvHelper
from ..helpers.llm_helper import LLMHelper
from ..helpers.PowerPointHelper import PowerPointHelper, ProjectPresentationData
from ..tools.post_prompt_tool import PostPromptTool
from ..tools.question_answer_tool import QuestionAnswerTool
from ..tools.text_processing_tool import TextProcessingTool

logger = logging.getLogger(__name__)
env_helper = EnvHelper()
power_point_helper = PowerPointHelper()


class OpenAIFunctionsOrchestrator(OrchestratorBase):
    def __init__(self) -> None:
        super().__init__()
        self.functions = [
            {
                "name": "search_documents",
                "description": "Retrieve relevant documents to answer user fact-based questions",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The user's inquiry, formulated to extract pertinent information from available documents.",
                        },
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Relevant keywords, that are list of IT-related terms for precise search",
                        },
                    },
                    "required": ["question", "keywords"],
                },
            },
            {
                "name": "text_processing",
                "description": "Useful when you want to apply a transformation on the text, like translate, summarize, rephrase and so on.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to be processed",
                        },
                        "operation": {
                            "type": "string",
                            "description": "The operation to be performed on the text. Like Translate to Italian, Summarize, Paraphrase, etc. If a language is specified, return that as part of the operation. Preserve the operation name in the user language.",
                        },
                    },
                    "required": ["text", "operation"],
                },
            },
            {
                "name": "create_presentation",
                "description": "Creates PowerPoint presentation, based on projects information in context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "presentations": {
                            "type": "array",
                            "description": "Array of presentation data, each item represents one project",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Name of the project.",
                                    },
                                    "overview": {
                                        "type": "string",
                                        "description": "Brief summary of the client's company, including public information.",
                                    },
                                    "challenges": {
                                        "type": "string",
                                        "description": "Consise description of the challenges the company faced and their business goals and needs. This may include issues like recruitment difficulties, market expansion, product failures, or the need for technological expertise.",
                                    },
                                    "technologies": {
                                        "type": "string",
                                        "description": "List of technologies used in the project, including programming languages, tools, and cloud platforms.",
                                    },
                                    "results": {
                                        "type": "string",
                                        "description": "Some briefly described examples of how Capgemini contributed to the client's business and helped achieve goals, ideally including quantifiable metrics.",
                                    },
                                    "solution": {
                                        "type": "string",
                                        "description": "Consise explanation of how Capgemini addressed the client's needs and assisted them in meeting their goals. This should highlight both business achievements and technical features implemented by our teams.",
                                    },
                                },
                                "required": [
                                    "name",
                                    "overview",
                                    "challenges",
                                    "technologies",
                                    "results",
                                    "solution",
                                ],
                            },
                        }
                    },
                    "required": ["presentations"],
                },
            },
        ]

    async def orchestrate(
        self, user_message: str, chat_history: List[dict], **kwargs: dict
    ) -> list[dict]:
        # Call Content Safety tool
        if self.config.prompts.enable_content_safety:
            if response := self.call_content_safety_input(user_message):
                return response

        # Call function to determine route
        llm_helper = LLMHelper()

        system_message = """You help employees to navigate only private information sources, which encompass confidential company documents such as policies, project documentation, technical guides, how-to manuals, and other documentation typical of a large IT company.
        ### IMPORTANT: You must prioritize the function call over your general knowledge for any question by calling the search_documents function.
        ### Instructions for 'search_documents' function:
        1. **Focus on the Most Recent User Inquiry**: Always use the most recent user question as the sole context for the futher steps, we will address to this context as 'user question'. Ignore previous interactions or questions.
        2. **Analyze context**: Carefully read the 'user question' to grasp the intention clearly
        3. **Extract 'question'**:Identify the main intent of the 'user question', keeping it concise and straightforward
            - Ensure the query follows a simple structure suitable for Azure AI Search
            - Optimize the query for effective search results using Azure AI Search best practices
        4. **Extract 'keywords'**:
            - From the 'user question', identify and extract IT-related terms like domains, technologies, frameworks, approaches, testing strategies, etc. without assumptions. If no keywords are available in 'user question', pass an empty array

        ### Call the 'text_processing' function when the user request an operation on the current context, such as translate, summarize, or paraphrase. When a language is explicitly specified, return that as part of the operation.
        When directly replying to the user, always reply in the language the user is speaking.
        ### Call the 'create_presentation' function when the user requests to create presentation on the current context. All presentation related data must be consise.
        """
        # Create conversation history
        messages = [{"role": "system", "content": system_message}]
        for message in chat_history:
            messages.append({"role": message["role"], "content": message["content"]})
        messages.append({"role": "user", "content": user_message})

        result = llm_helper.get_chat_completion_with_functions(
            messages, self.functions, function_call="auto"
        )
        self.log_tokens(
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
        )

        # TODO: call content safety if needed

        if result.choices[0].finish_reason == "function_call":
            logger.info("Function call detected")
            if result.choices[0].message.function_call.name == "search_documents":
                logger.info("search_documents function detected")
                func_arguments = json.loads(
                    result.choices[0].message.function_call.arguments
                )
                question = func_arguments["question"]
                # keywords must be a list of strings []
                keywords = func_arguments.get("keywords")

                # run answering chain
                answering_tool = QuestionAnswerTool()
                answer = answering_tool.answer_question(
                    question, chat_history, keywords=keywords
                )

                self.log_tokens(
                    prompt_tokens=answer.prompt_tokens,
                    completion_tokens=answer.completion_tokens,
                )

                # Run post prompt if needed
                if self.config.prompts.enable_post_answering_prompt:
                    logger.debug("Running post answering prompt")
                    post_prompt_tool = PostPromptTool()
                    answer = post_prompt_tool.validate_answer(answer)
                    self.log_tokens(
                        prompt_tokens=answer.prompt_tokens,
                        completion_tokens=answer.completion_tokens,
                    )

            elif result.choices[0].message.function_call.name == "create_presentation":
                func_arguments = json.loads(
                    result.choices[0].message.function_call.arguments
                )
                source_documents = []
                citations = ""
                presentatin_names = []

                for index, presentation_item in enumerate(
                    func_arguments["presentations"]
                ):
                    presentation_data = ProjectPresentationData(
                        name=presentation_item["name"],
                        overview=presentation_item["overview"],
                        challenges=presentation_item["challenges"],
                        technologies=presentation_item["technologies"],
                        results=presentation_item["results"],
                        solution=presentation_item["solution"],
                    )
                    created_presentation_url = (
                        power_point_helper.create_project_presentation(
                            projectData=presentation_data
                        )
                    )
                    doc = SourceDocument(
                        "",
                        source=created_presentation_url,
                        id=f"doc{index}",
                        title=presentation_data.name,
                    )
                    citations += f"[doc{index}] "
                    source_documents.append(doc)
                    presentatin_names.append(presentation_data.name)

                presentations_count = len(presentatin_names)
                message = "Apologies for the inconvenience. I acknowledge the failure to create the presentation."
                if presentations_count > 0:
                    message = (
                        f"Presentations for projects {', '.join(presentatin_names)} were successfully created."
                        if presentations_count > 1
                        else f"Presentation for project {presentatin_names[0]} was successfully created."
                    )
                    message += citations

                answer = Answer(
                    question=user_message,
                    answer=message,
                    source_documents=source_documents,
                )
            elif result.choices[0].message.function_call.name == "text_processing":
                logger.info("text_processing function detected")
                text = json.loads(result.choices[0].message.function_call.arguments)[
                    "text"
                ]
                operation = json.loads(
                    result.choices[0].message.function_call.arguments
                )["operation"]
                text_processing_tool = TextProcessingTool()
                answer = text_processing_tool.answer_question(
                    user_message, chat_history, text=text, operation=operation
                )
                self.log_tokens(
                    prompt_tokens=answer.prompt_tokens,
                    completion_tokens=answer.completion_tokens,
                )
        else:
            logger.info("No function call detected")
            text = result.choices[0].message.content
            answer = Answer(question=user_message, answer=text)

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
