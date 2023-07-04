import streamlit as st
import os
import json
import traceback
import logging
from dotenv import load_dotenv
from utilities.ConfigHelper import ConfigHelper, ChunkingStrategy

load_dotenv()

logger = logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
st.set_page_config(page_title="Configure Prompts", page_icon=os.path.join('images','favicon.ico'), layout="wide", menu_items=None)

mod_page_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(mod_page_style, unsafe_allow_html=True)

try:
    config = ConfigHelper.get_active_config()
except Exception as e:
    config = ConfigHelper.get_default_config()

if 'condense_question_prompt' not in st.session_state:
    st.session_state['condense_question_prompt'] = config.prompts.condense_question_prompt

def check_variables_in_prompt():
    # Check if "summaries" is present in the string answering_prompt
    if "{summaries}" not in st.session_state.answering_prompt:
        st.warning("""Your custom prompt doesn't contain the variable "{summaries}".  
        This variable is used to add the content of the documents retrieved from the VectorStore to the prompt.  
        Please add it to your custom prompt to use the app.  
        Reverting to default prompt.
        """)
        st.session_state.answering_prompt = ""
    if "{question}" not in st.session_state.answering_prompt:
        st.warning("""Your custom prompt doesn't contain the variable "{question}".  
        This variable is used to add the user's question to the prompt.  
        Please add it to your custom prompt to use the app.  
        Reverting to default prompt.  
        """)
        st.session_state.answering_prompt = ""

try:
    # Prompt initialisation 
    if 'condense_question_prompt' not in st.session_state:
        st.session_state['condense_question_prompt'] = ""
    if 'answering_prompt' not in st.session_state:
        st.session_state['answering_prompt'] = ""
    if 'post_answering_prompt' not in st.session_state:
        st.session_state['post_answering_prompt'] = ""    

    answering_prompt_placeholder = """{summaries}  
    Please reply to the question using only the text above.  
    Question: {question}  
    Answer:"""
    condense_question_prompt_placeholder = """"""
    post_answering_prompt_placeholder = """"""

    condense_question_prompt_help = """You can configure a pre prompt by defining how the documents retrieved from the VectorStore will be combined and sent to LLM."""
    answering_prompt_help = """You can configure a custom prompt by adding the variables {summaries} and {question} to the prompt.
    {summaries} will be replaced with the content of the documents retrieved from the VectorStore.  
    {question} will be replaced with the user's question.
        """
    post_answering_prompt_help = """You can configure a post prompt by defining how the user's answer will be processed for fact checking or conflict resolution.
        """

    with st.expander("Prompt configuration", expanded=True):
        # Custom prompt
        st.text_area("Condense question prompt", key='condense_question_prompt', on_change=check_variables_in_prompt, placeholder= condense_question_prompt_placeholder,help=condense_question_prompt_help, height=50)
        st.text_area("Answering prompt", key='answering_prompt', on_change=check_variables_in_prompt, placeholder= answering_prompt_placeholder,help=answering_prompt_help, height=50)
        st.text_area("Post-answering prompt", key='post_answering_prompt', on_change=check_variables_in_prompt, placeholder= post_answering_prompt_placeholder,help=post_answering_prompt_help, height=50)

    with st.expander("Chunking configuration", expanded=True):
        # Chunking config input
        chunking_strategy = st.selectbox('Chunking strategy', [s.value for s in ChunkingStrategy], key="chunking_strategy")
        chunking_size = st.text_input("Chunk size (in tokens)", key='chunking_size', placeholder="500")
        chunking_overlap = st.text_input("Chunk overlap (in tokens)", key='chunking_overlap', placeholder="100")

    with st.expander("Logging configuration", expanded=True):       
        log_questions = st.checkbox('Log user input and output (questions, answers, chat history, sources)', value=True, key='log_user_interactions')
        log_answers = st.checkbox('Log tokens', value=True, key='log_tokens')
    
    if st.button("Save configuration"):
        current_config = {
            "prompts": {
                "condense_question_prompt": st.session_state['condense_question_prompt'],
                "answering_prompt": st.session_state['answering_prompt'],
                "post_answering_prompt": st.session_state['post_answering_prompt']
                },
            "chunking": [{
                "strategy": st.session_state['chunking_strategy'],
                "size": st.session_state['chunking_size'],
                "overlap": st.session_state['chunking_overlap']
                }],
            "logging": {
                "log_user_interactions": st.session_state['log_user_interactions'],
                "log_tokens": st.session_state['log_tokens']
            }
        }
        ConfigHelper.save_config_as_active(current_config)
        st.success("Configuration saved successfully!")

except Exception as e:
    st.error(traceback.format_exc())
