import logging
import os
import sys
import json
import jsonschema
import streamlit as st
from batch.utilities.helpers.env_helper import EnvHelper
from batch.utilities.helpers.config.config_helper import ConfigHelper
from azure.core.exceptions import ResourceNotFoundError
from batch.utilities.helpers.config.assistant_strategy import AssistantStrategy
from batch.utilities.helpers.config.conversation_flow import ConversationFlow
from batch.utilities.helpers.config.database_type import DatabaseType

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
env_helper: EnvHelper = EnvHelper()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Configure Prompts",
    page_icon=os.path.join("images", "favicon.ico"),
    layout="wide",
    menu_items=None,
)


def load_css(file_path):
    with open(file_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# Load the common CSS
load_css("pages/common.css")

config = ConfigHelper.get_active_config_or_default()

# Populate all fields from Config values
# # # if 'condense_question_prompt' not in st.session_state:
# # #     st.session_state['condense_question_prompt'] = config.prompts.condense_question_prompt
if "answering_system_prompt" not in st.session_state:
    st.session_state["answering_system_prompt"] = config.prompts.answering_system_prompt
if "answering_user_prompt" not in st.session_state:
    st.session_state["answering_user_prompt"] = config.prompts.answering_user_prompt
if "use_on_your_data_format" not in st.session_state:
    st.session_state["use_on_your_data_format"] = config.prompts.use_on_your_data_format
if "post_answering_prompt" not in st.session_state:
    st.session_state["post_answering_prompt"] = config.prompts.post_answering_prompt
if "enable_post_answering_prompt" not in st.session_state:
    st.session_state["enable_post_answering_prompt"] = (
        config.prompts.enable_post_answering_prompt
    )
if "post_answering_filter_message" not in st.session_state:
    st.session_state["post_answering_filter_message"] = (
        config.messages.post_answering_filter
    )
if "enable_content_safety" not in st.session_state:
    st.session_state["enable_content_safety"] = config.prompts.enable_content_safety
if "example_documents" not in st.session_state:
    st.session_state["example_documents"] = config.example.documents
if "example_user_question" not in st.session_state:
    st.session_state["example_user_question"] = config.example.user_question
if "example_answer" not in st.session_state:
    st.session_state["example_answer"] = config.example.answer
if "log_user_interactions" not in st.session_state:
    st.session_state["log_user_interactions"] = (
        str(config.logging.log_user_interactions).lower() == "true"
    )
if "log_tokens" not in st.session_state:
    st.session_state["log_tokens"] = str(config.logging.log_tokens).lower() == "true"
if "orchestrator_strategy" not in st.session_state:
    st.session_state["orchestrator_strategy"] = config.orchestrator.strategy.value
if "ai_assistant_type" not in st.session_state:
    st.session_state["ai_assistant_type"] = config.prompts.ai_assistant_type
if "conversational_flow" not in st.session_state:
    st.session_state["conversational_flow"] = config.prompts.conversational_flow
if "enable_chat_history" not in st.session_state:
    st.session_state["enable_chat_history"] = (
        str(config.enable_chat_history).lower() == "true"
    )
if "database_type" not in st.session_state:
    st.session_state["database_type"] = config.database_type

if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
    if "max_page_length" not in st.session_state:
        st.session_state["max_page_length"] = (
            config.integrated_vectorization_config.max_page_length
        )

    if "page_overlap_length" not in st.session_state:
        st.session_state["page_overlap_length"] = (
            config.integrated_vectorization_config.page_overlap_length
        )


# # # def validate_question_prompt():
# # #     if "{chat_history}" not in st.session_state.condense_question_prompt:
# # #         st.warning("Your condense question prompt doesn't contain the variable `{chat_history}`")
# # #     if "{question}" not in st.session_state.condense_question_prompt:
# # #         st.warning("Your condense question prompt doesn't contain the variable `{question}`")


def validate_answering_user_prompt():
    if "{sources}" not in st.session_state.answering_user_prompt:
        st.warning("Your answering prompt doesn't contain the variable `{sources}`")
    if "{question}" not in st.session_state.answering_user_prompt:
        st.warning("Your answering prompt doesn't contain the variable `{question}`")


def config_assistant_prompt():
    if (
        st.session_state["ai_assistant_type"]
        == AssistantStrategy.CONTRACT_ASSISTANT.value
    ):
        st.success("Contract Assistant Prompt")
        st.session_state["answering_user_prompt"] = (
            ConfigHelper.get_default_contract_assistant()
        )
    elif (
        st.session_state["ai_assistant_type"]
        == AssistantStrategy.EMPLOYEE_ASSISTANT.value
    ):
        st.success("Employee Assistant Prompt")
        st.session_state["answering_user_prompt"] = (
            ConfigHelper.get_default_employee_assistant()
        )
    else:
        st.success("Default Assistant Prompt")
        st.session_state["answering_user_prompt"] = (
            ConfigHelper.get_default_assistant_prompt()
        )


def validate_post_answering_prompt():
    if (
        "post_answering_prompt" not in st.session_state
        or len(st.session_state.post_answering_prompt) == 0
    ):
        pass
    if "{sources}" not in st.session_state.post_answering_prompt:
        st.warning(
            "Your post answering prompt doesn't contain the variable `{sources}`"
        )
    if "{question}" not in st.session_state.post_answering_prompt:
        st.warning(
            "Your post answering prompt doesn't contain the variable `{question}`"
        )
    if "{answer}" not in st.session_state.post_answering_prompt:
        st.warning("Your post answering prompt doesn't contain the variable `{answer}`")


def validate_documents():
    documents_schema = {
        "type": "object",
        "required": ["retrieved_documents"],
        "additionalProperties": False,
        "properties": {
            "retrieved_documents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "patternProperties": {
                        r"^\[doc\d+\]$": {
                            "type": "object",
                            "required": ["content"],
                            "additionalProperties": False,
                            "properties": {"content": {"type": "string"}},
                        }
                    },
                },
            }
        },
    }

    documents_string = st.session_state.example_documents

    if not documents_string:
        return

    try:
        documents = json.loads(documents_string)
    except json.JSONDecodeError:
        st.warning("Documents: Invalid JSON object")
        return

    try:
        jsonschema.validate(documents, documents_schema)
    except jsonschema.ValidationError as e:
        st.warning(f"Documents: {e.message}")


try:
    conversational_flow_help = "Whether to use the custom conversational flow or byod conversational flow. Refer to the Conversational flow options README for more details."
    with st.expander("Conversational flow configuration", expanded=True):
        cols = st.columns([2, 4])
        with cols[0]:
            conv_flow = st.selectbox(
                "Conversational flow",
                key="conversational_flow",
                options=config.get_available_conversational_flows(),
                help=conversational_flow_help,
                disabled=(
                    True
                    if env_helper.DATABASE_TYPE == DatabaseType.POSTGRESQL.value
                    else False
                ),
            )

    with st.expander("Orchestrator configuration", expanded=True):
        cols = st.columns([2, 4])
        with cols[0]:
            st.selectbox(
                "Orchestrator strategy",
                key="orchestrator_strategy",
                options=config.get_available_orchestration_strategies(),
                disabled=(
                    True
                    if st.session_state["conversational_flow"]
                    == ConversationFlow.BYOD.value
                    or env_helper.DATABASE_TYPE == "PostgreSQL"
                    else False
                ),
            )

    # # # condense_question_prompt_help = "This prompt is used to convert the user's input to a standalone question, using the context of the chat history."
    answering_system_prompt_help = "The system prompt used to answer the user's question. Only used if Azure OpenAI On Your Data prompt format is enabled."
    answering_user_prompt_help = (
        "The user prompt used to answer the user's question, using the sources that were retrieved from the knowledge base. If using the Azure OpenAI On Your Data prompt format, it is recommended to keep this simple, e.g.:  \n"
        """```
## Retrieved Documents
{sources}

## User Question
Use the Retrieved Documents to answer the question: {question}
```"""
    )
    post_answering_prompt_help = "You can configure a post prompt that allows to fact-check or process the answer, given the sources, question and answer. This prompt needs to return `True` or `False`."
    use_on_your_data_format_help = "Whether to use a similar prompt format to Azure OpenAI On Your Data, including separate system and user messages, and a few-shot example."
    post_answering_filter_help = "The message that is returned to the user, when the post-answering prompt returns."
    ai_assistant_type_help = "Whether to use the default user prompt or the Contract Assistance user prompt. Refer to the Contract Assistance README for more details."
    example_documents_help = (
        "JSON object containing documents retrieved from the knowledge base, in the following format:  \n"
        """```json
{
  "retrieved_documents": [
    {
      "[doc1]": {
        "content": "..."
      }
    },
    {
      "[doc2]": {
        "content": "..."
      }
    },
    ...
  ]
}
```"""
    )
    example_user_question_help = "The example user question."
    example_answer_help = "The expected answer."
    with st.expander("Assistant type configuration", expanded=True):
        cols = st.columns([2, 4])
        with cols[0]:
            st.selectbox(
                "Assistant Type",
                key="ai_assistant_type",
                on_change=config_assistant_prompt,
                options=config.get_available_ai_assistant_types(),
                help=ai_assistant_type_help,
            )
    with st.expander("Prompt configuration", expanded=True):
        # # # st.text_area("Condense question prompt", key='condense_question_prompt', on_change=validate_question_prompt, help=condense_question_prompt_help, height=200)
        st.checkbox(
            "Use Azure OpenAI On Your Data prompt format",
            key="use_on_your_data_format",
            help=use_on_your_data_format_help,
        )
        st.text_area(
            "Answering user prompt",
            key="answering_user_prompt",
            on_change=validate_answering_user_prompt,
            help=answering_user_prompt_help,
            height=400,
        )

        st.text_area(
            "Answering system prompt",
            key="answering_system_prompt",
            help=answering_system_prompt_help,
            height=400,
            disabled=not st.session_state["use_on_your_data_format"],
        )

        st.text_area(
            "Post-answering prompt",
            key="post_answering_prompt",
            on_change=validate_post_answering_prompt,
            help=post_answering_prompt_help,
            height=200,
        )
        st.checkbox("Enable post-answering prompt", key="enable_post_answering_prompt")
        st.text_area(
            "Post-answering filter message",
            key="post_answering_filter_message",
            help=post_answering_filter_help,
            height=200,
        )

        st.checkbox("Enable Azure AI Content Safety", key="enable_content_safety")

    with st.expander("Few shot example", expanded=True):
        st.write(
            "The following can be used to configure a few-shot example to be used in the answering prompt. Only used if Azure OpenAI On Your Data prompt format is enabled.  \n"
            "The configuration is optional, but all three options must be provided to be valid."
        )
        st.text_area(
            "Documents",
            key="example_documents",
            help=example_documents_help,
            on_change=validate_documents,
            height=200,
            disabled=not st.session_state["use_on_your_data_format"],
        )
        st.text_area(
            "User Question",
            key="example_user_question",
            help=example_user_question_help,
            disabled=not st.session_state["use_on_your_data_format"],
        )
        st.text_area(
            "User Answer",
            key="example_answer",
            help=example_answer_help,
            disabled=not st.session_state["use_on_your_data_format"],
        )

    with st.form("config_form", border=False):
        document_processors = list(
            map(
                lambda x: {
                    "document_type": x.document_type,
                    "chunking_strategy": (
                        x.chunking.chunking_strategy.value if x.chunking else "layout"
                    ),
                    "chunking_size": x.chunking.chunk_size if x.chunking else None,
                    "chunking_overlap": (
                        x.chunking.chunk_overlap if x.chunking else None
                    ),
                    "loading_strategy": (
                        x.loading.loading_strategy.value if x.loading else "layout"
                    ),
                    "use_advanced_image_processing": x.use_advanced_image_processing,
                },
                config.document_processors,
            )
        )

        if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION:
            with st.expander("Integrated Vectorization configuration", expanded=True):
                st.text_input("Max Page Length", key="max_page_length")
                st.text_input("Page Overlap Length", key="page_overlap_length")
                integrated_vectorization_config = {
                    "max_page_length": st.session_state["max_page_length"],
                    "page_overlap_length": st.session_state["page_overlap_length"],
                }

        else:
            with st.expander("Document processing configuration", expanded=True):
                edited_document_processors = st.data_editor(
                    data=document_processors,
                    use_container_width=True,
                    num_rows="dynamic",
                    column_config={
                        "document_type": st.column_config.SelectboxColumn(
                            options=config.get_available_document_types()
                        ),
                        "chunking_strategy": st.column_config.SelectboxColumn(
                            options=[
                                cs for cs in config.get_available_chunking_strategies()
                            ]
                        ),
                        "loading_strategy": st.column_config.SelectboxColumn(
                            options=[
                                ls for ls in config.get_available_loading_strategies()
                            ]
                        ),
                    },
                )

        with st.expander("Chat history configuration", expanded=True):
            st.checkbox("Enable chat history", key="enable_chat_history")

        with st.expander("Logging configuration", expanded=True):
            disable_checkboxes = (
                True
                if env_helper.DATABASE_TYPE == DatabaseType.POSTGRESQL.value
                else False
            )
            st.checkbox(
                "Log user input and output (questions, answers, conversation history, sources)",
                key="log_user_interactions",
                disabled=disable_checkboxes,
            )
            st.checkbox(
                "Log tokens",
                key="log_tokens",
                disabled=disable_checkboxes,
            )

        if st.form_submit_button("Save configuration"):
            document_processors = []
            should_save = True
            if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION is False:
                valid = all(
                    row["document_type"]
                    and row["chunking_strategy"]
                    and row["chunking_size"]
                    and row["chunking_overlap"]
                    and row["loading_strategy"]
                    for row in edited_document_processors
                )
                if not valid:
                    st.error(
                        "Please ensure all fields are selected and not left blank in Document processing configuration."
                    )
                    should_save = False
                document_processors = list(
                    map(
                        lambda x: {
                            "document_type": x["document_type"],
                            "chunking": {
                                "strategy": x["chunking_strategy"],
                                "size": x["chunking_size"],
                                "overlap": x["chunking_overlap"],
                            },
                            "loading": {
                                "strategy": x["loading_strategy"],
                            },
                            "use_advanced_image_processing": x[
                                "use_advanced_image_processing"
                            ],
                        },
                        edited_document_processors,
                    )
                )
            if should_save:
                current_config = {
                    "prompts": {
                        "condense_question_prompt": "",  # st.session_state['condense_question_prompt'],
                        "answering_system_prompt": st.session_state[
                            "answering_system_prompt"
                        ],
                        "answering_user_prompt": st.session_state["answering_user_prompt"],
                        "use_on_your_data_format": st.session_state[
                            "use_on_your_data_format"
                        ],
                        "post_answering_prompt": st.session_state["post_answering_prompt"],
                        "enable_post_answering_prompt": st.session_state[
                            "enable_post_answering_prompt"
                        ],
                        "enable_content_safety": st.session_state["enable_content_safety"],
                        "ai_assistant_type": st.session_state["ai_assistant_type"],
                        "conversational_flow": st.session_state["conversational_flow"],
                    },
                    "messages": {
                        "post_answering_filter": st.session_state[
                            "post_answering_filter_message"
                        ]
                    },
                    "example": {
                        "documents": st.session_state["example_documents"],
                        "user_question": st.session_state["example_user_question"],
                        "answer": st.session_state["example_answer"],
                    },
                    "document_processors": document_processors,
                    "logging": {
                        "log_user_interactions": st.session_state["log_user_interactions"],
                        "log_tokens": st.session_state["log_tokens"],
                    },
                    "orchestrator": {"strategy": st.session_state["orchestrator_strategy"]},
                    "integrated_vectorization_config": (
                        integrated_vectorization_config
                        if env_helper.AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION
                        else None
                    ),
                    "enable_chat_history": st.session_state["enable_chat_history"],
                }
                ConfigHelper.save_config_as_active(current_config)
                st.success(
                    "Configuration saved successfully! Please restart the chat service for these changes to take effect."
                )

    @st.dialog("Reset Configuration", width="small")
    def reset_config_dialog():
        st.write("**Resetting the configuration cannot be reversed. Proceed with caution!**")

        st.text_input('Enter "reset" to proceed', key="reset_configuration")
        if st.button(
            ":red[Reset]",
            disabled=st.session_state.get("reset_configuration", "") != "reset",
            key="confirm_reset"
        ):
            with st.spinner("Resetting Configuration to Default values..."):
                try:
                    ConfigHelper.delete_config()
                except ResourceNotFoundError:
                    pass

                ConfigHelper.clear_config()
            st.session_state.clear()
            st.session_state["reset"] = True
            st.session_state["reset_configuration"] = ""
            st.session_state["show_reset_dialog"] = False
            st.rerun()

    # Reset configuration button
    if st.button(":red[Reset configuration to defaults]"):
        st.session_state["show_reset_dialog"] = True

    # Open the dialog if needed
    if st.session_state.get("show_reset_dialog"):
        reset_config_dialog()
        st.session_state["show_reset_dialog"] = False

    # After reset success
    if st.session_state.get("reset"):
        st.success("Configuration reset successfully!")
        del st.session_state["reset"]
        del st.session_state["reset_configuration"]

except Exception as e:
    logger.error(f"Error occurred: {e}")
    st.error(e)
