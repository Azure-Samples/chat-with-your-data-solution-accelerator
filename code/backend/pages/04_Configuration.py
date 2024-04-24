import streamlit as st
import json
import jsonschema
import os
import traceback
from dotenv import load_dotenv
import sys
from batch.utilities.helpers.ConfigHelper import ConfigHelper
from azure.core.exceptions import ResourceNotFoundError

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

st.set_page_config(
    page_title="Configure Prompts",
    page_icon=os.path.join("images", "favicon.ico"),
    layout="wide",
    menu_items=None,
)

mod_page_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(mod_page_style, unsafe_allow_html=True)

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
    st.session_state["log_user_interactions"] = config.logging.log_user_interactions
if "log_tokens" not in st.session_state:
    st.session_state["log_tokens"] = config.logging.log_tokens

if "orchestrator_strategy" not in st.session_state:
    st.session_state["orchestrator_strategy"] = config.orchestrator.strategy.value


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
    with st.expander("Orchestrator configuration", expanded=True):
        cols = st.columns([2, 4])
        with cols[0]:
            st.selectbox(
                "Orchestrator strategy",
                key="orchestrator_strategy",
                options=config.get_available_orchestration_strategies(),
            )

    # # # condense_question_prompt_help = "This prompt is used to convert the user's input to a standalone question, using the context of the chat history."
    answering_system_prompt_help = "The system prompt used to answer the user's question. Only used if Azure OpenAI On Your Data prompt format is enabled."
    answering_user_prompt_help = (
        "The user prompt used to answer the user's question, using the sources that were retrieved from the knowledge base. If using the Azure OpenAI On Your Data prompt format, it is recommended to keep this simple, e.g.:  \n"
        """```
## Retrieved Documents
{sources}

## User Question
{question}
```"""
    )
    post_answering_prompt_help = "You can configure a post prompt that allows to fact-check or process the answer, given the sources, question and answer. This prompt needs to return `True` or `False`."
    use_on_your_data_format_help = "Whether to use a similar prompt format to Azure OpenAI On Your Data, including separate system and user messages, and a few-shot example."
    post_answering_filter_help = "The message that is returned to the user, when the post-answering prompt returns."

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

    document_processors = list(
        map(
            lambda x: {
                "document_type": x.document_type,
                "chunking_strategy": (
                    x.chunking.chunking_strategy.value if x.chunking else None
                ),
                "chunking_size": x.chunking.chunk_size if x.chunking else None,
                "chunking_overlap": x.chunking.chunk_overlap if x.chunking else None,
                "loading_strategy": (
                    x.loading.loading_strategy.value if x.loading else None
                ),
                "use_advanced_image_processing": x.use_advanced_image_processing,
            },
            config.document_processors,
        )
    )

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
                    options=[cs for cs in config.get_available_chunking_strategies()]
                ),
                "loading_strategy": st.column_config.SelectboxColumn(
                    options=[ls for ls in config.get_available_loading_strategies()]
                ),
            },
        )

    with st.expander("Logging configuration", expanded=True):
        st.checkbox(
            "Log user input and output (questions, answers, chat history, sources)",
            key="log_user_interactions",
        )
        st.checkbox("Log tokens", key="log_tokens")

    if st.button("Save configuration"):
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
                    "use_advanced_image_processing": x["use_advanced_image_processing"],
                },
                edited_document_processors,
            )
        )
        current_config = {
            "prompts": {
                "condense_question_prompt": "",  # st.session_state['condense_question_prompt'],
                "answering_system_prompt": st.session_state["answering_system_prompt"],
                "answering_user_prompt": st.session_state["answering_user_prompt"],
                "use_on_your_data_format": st.session_state["use_on_your_data_format"],
                "post_answering_prompt": st.session_state["post_answering_prompt"],
                "enable_post_answering_prompt": st.session_state[
                    "enable_post_answering_prompt"
                ],
                "enable_content_safety": st.session_state["enable_content_safety"],
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
        }
        ConfigHelper.save_config_as_active(current_config)
        st.success("Configuration saved successfully!")

    with st.popover(":red[Reset confiiguration to defaults]"):
        st.write(
            "**Resetting the configuration cannot be reversed, proceed with caution!**"
        )
        st.text_input('Enter "reset" to proceed', key="reset_configuration")
        if st.button(
            ":red[Reset]", disabled=st.session_state["reset_configuration"] != "reset"
        ):
            try:
                ConfigHelper.delete_config()
            except ResourceNotFoundError:
                pass

            for key in st.session_state:
                del st.session_state[key]

            st.session_state["reset"] = True
            st.session_state["reset_configuration"] = ""
            st.rerun()

        if st.session_state.get("reset") is True:
            st.success("Configuration reset successfully!")
            del st.session_state["reset"]
            del st.session_state["reset_configuration"]

except Exception:
    st.error(traceback.format_exc())
