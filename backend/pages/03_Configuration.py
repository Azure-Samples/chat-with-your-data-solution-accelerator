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

config = ConfigHelper.get_active_config_or_default()

# Populate all fields from Config values
if 'condense_question_prompt' not in st.session_state:
    st.session_state['condense_question_prompt'] = config.prompts.condense_question_prompt
if 'answering_prompt' not in st.session_state:
    st.session_state['answering_prompt'] = config.prompts.answering_prompt
if 'post_answering_prompt' not in st.session_state:
    st.session_state['post_answering_prompt'] = config.prompts.post_answering_prompt
if 'enable_post_answering_prompt' not in st.session_state:
    st.session_state['enable_post_answering_prompt'] = config.prompts.enable_post_answering_prompt
    
if 'post_answering_filter_message' not in st.session_state:
    st.session_state['post_answering_filter_message'] = config.messages.post_answering_filter
    
if 'chunking_strategy' not in st.session_state:
    st.session_state['chunking_strategy'] = config.chunking[0].chunking_strategy.value
if 'chunking_size' not in st.session_state:
    st.session_state['chunking_size'] = config.chunking[0].chunk_size
if 'chunking_overlap' not in st.session_state:
    st.session_state['chunking_overlap'] = config.chunking[0].chunk_overlap
    
if 'log_user_interactions' not in st.session_state:
    st.session_state['log_user_interactions'] = config.logging.log_user_interactions
if 'log_tokens' not in st.session_state:
    st.session_state['log_tokens'] = config.logging.log_tokens
    
    
def validate_question_prompt():
    if "{chat_history}" not in st.session_state.condense_question_prompt:
        st.warning("Your condense question prompt doesn't contain the variable `{chat_history}`")
    if "{question}" not in st.session_state.condense_question_prompt:
        st.warning("Your condense question prompt doesn't contain the variable `{question}`")

def validate_answering_prompt():
    if "{sources}" not in st.session_state.answering_prompt:
        st.warning("Your answering prompt doesn't contain the variable `{sources}`")
    if "{question}" not in st.session_state.answering_prompt:
        st.warning("Your answering prompt doesn't contain the variable `{question}`")
        
def validate_post_answering_prompt():
    if "post_answering_prompt" not in st.session_state or len(st.session_state.post_answering_prompt) == 0:
        pass
    if "{sources}" not in st.session_state.post_answering_prompt:
        st.warning("Your post answering prompt doesn't contain the variable `{sources}`")
    if "{question}" not in st.session_state.post_answering_prompt:
        st.warning("Your post answering prompt doesn't contain the variable `{question}`")
    if "{answer}" not in st.session_state.post_answering_prompt:
        st.warning("Your post answering prompt doesn't contain the variable `{answer}`")

try:
    condense_question_prompt_help = "This prompt is used to convert the user's input to a standalone question, using the context of the chat history."
    answering_prompt_help = "This prompt is used to answer the user's question, using the sources that were retrieved from the knowledge base."
    post_answering_prompt_help = "You can configure a post prompt that allows to fact-check or process the answer, given the sources, question and answer. This prompt needs to return `True` or `False`."
    post_answering_filter_help = "The message that is returned to the user, when the post-answering prompt returns."

    with st.expander("Prompt configuration", expanded=True):
        st.text_area("Condense question prompt", key='condense_question_prompt', on_change=validate_question_prompt, help=condense_question_prompt_help, height=200)
        st.text_area("Answering prompt", key='answering_prompt', on_change=validate_answering_prompt, help=answering_prompt_help, height=400)

        st.text_area("Post-answering prompt", key='post_answering_prompt', on_change=validate_post_answering_prompt, help=post_answering_prompt_help, height=200)
        st.checkbox('Enable post-answering prompt', key='enable_post_answering_prompt')

        st.text_area("Post-answering filter message", key='post_answering_filter_message', help=post_answering_filter_help, height=200)

    with st.expander("Chunking configuration", expanded=True):
        st.selectbox('Chunking strategy', [s.value for s in ChunkingStrategy], key="chunking_strategy")
        st.number_input("Chunk size (in tokens)", key='chunking_size', min_value=10)
        st.number_input("Chunk overlap (in tokens)", key='chunking_overlap', min_value=10)

    with st.expander("Logging configuration", expanded=True):       
        st.checkbox('Log user input and output (questions, answers, chat history, sources)', key='log_user_interactions')
        st.checkbox('Log tokens', key='log_tokens')
    
    if st.button("Save configuration"):
        current_config = {
            "prompts": {
                "condense_question_prompt": st.session_state['condense_question_prompt'],
                "answering_prompt": st.session_state['answering_prompt'],
                "post_answering_prompt": st.session_state['post_answering_prompt'],
                "enable_post_answering_prompt": st.session_state['enable_post_answering_prompt']
                },
            "messages": {
                "post_answering_filter": st.session_state['post_answering_filter_message']
            },
            "chunking": [{
                "strategy": st.session_state['chunking_strategy'],
                "size": int(st.session_state['chunking_size']),
                "overlap": int(st.session_state['chunking_overlap'])
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
