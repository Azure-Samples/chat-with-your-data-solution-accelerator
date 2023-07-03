import streamlit as st
import os
import traceback
import logging
from dotenv import load_dotenv
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

st.write("TODO: This does not work yet")

def check_variables_in_prompt():
    # Check if "summaries" is present in the string custom_prompt
    if "{summaries}" not in st.session_state.custom_prompt:
        st.warning("""Your custom prompt doesn't contain the variable "{summaries}".  
        This variable is used to add the content of the documents retrieved from the VectorStore to the prompt.  
        Please add it to your custom prompt to use the app.  
        Reverting to default prompt.
        """)
        st.session_state.custom_prompt = ""
    if "{question}" not in st.session_state.custom_prompt:
        st.warning("""Your custom prompt doesn't contain the variable "{question}".  
        This variable is used to add the user's question to the prompt.  
        Please add it to your custom prompt to use the app.  
        Reverting to default prompt.  
        """)
        st.session_state.custom_prompt = ""

try:
    # Prompt initialisation 
    if 'pre_prompt' not in st.session_state:
        st.session_state['pre_prompt'] = ""
    if 'custom_prompt' not in st.session_state:
        st.session_state['custom_prompt'] = ""
    if 'post_prompt' not in st.session_state:
        st.session_state['post_prompt'] = ""    

    custom_prompt_placeholder = """{summaries}  
    Please reply to the question using only the text above.  
    Question: {question}  
    Answer:"""
    pre_prompt_placeholder = """"""
    post_prompt_placeholder = """"""

    pre_prompt_help = """You can configure a pre prompt by defining how the documents retrieved from the VectorStore will be combined and sent to LLM.
        """
    custom_prompt_help = """You can configure a custom prompt by adding the variables {summaries} and {question} to the prompt.  
    {summaries} will be replaced with the content of the documents retrieved from the VectorStore.  
    {question} will be replaced with the user's question.
        """
    post_prompt_help = """You can configure a post prompt by defining how the user's answer will be processed for fact checking or conflict resolution.
        """

    with st.expander("Define your prompt (check help icon for details on each field)", expanded=True):
        # Custom prompt
        st.text_area("Pre Prompt", key='pre_prompt', on_change=check_variables_in_prompt, placeholder= pre_prompt_placeholder,help=pre_prompt_help, height=50)
        st.text_area("Custom Prompt", key='custom_prompt', on_change=check_variables_in_prompt, placeholder= custom_prompt_placeholder,help=custom_prompt_help, height=50)
        st.text_area("Post Prompt", key='post_prompt', on_change=check_variables_in_prompt, placeholder= post_prompt_placeholder,help=post_prompt_help, height=50)

    with st.expander("Chunking config placeholder", expanded=True):
        # Chunking config input
        ch_size=st.text_input("Chunk size (in tokens)", key='chunking_size', placeholder="500")
        ch_overlap=st.text_input("Chunk overlap (in tokens)", key='chunking_overlap', placeholder="100")
        # Placeholder for future chunking strategies like dynamic layout
        ch_selection=st.selectbox('Chunking strategy', ['Fixed size + Overlap', 'Layout based'], key="chunking_strategy")

    with st.expander("Logging placeholder", expanded=True):
        # Logging placeholder
        st.write("Placeholder for future log configuration")

    # TODO: Implement prompt persistency and management

except Exception as e:
    st.error(traceback.format_exc())
